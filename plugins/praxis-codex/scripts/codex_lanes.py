#!/usr/bin/env python3
"""codex_lanes.py — run independent Praxis slice lanes in parallel, one git worktree each.

This sits ABOVE the single-lane controller (codex_drive.py), which it runs
unchanged inside each worktree. It adds only: lane selection, worktrees, and a
merge policy.

Which lanes run in parallel
  Only lanes that are ready AND explicitly declare `depends_on_slices` in their
  ledger (use `depends_on_slices: []` to state "independent"), with every
  declared dependency closed. A lane that declares nothing is never run in
  parallel: silence is not a statement of independence.

Merge policy (never forced, never automatic conflict resolution)
  1. Each lane works on branch praxis/lane-<slice> in .praxis-worktrees/<slice>.
  2. When a lane's controller exits 0, its work is committed on its branch.
  3. Lanes merge into the starting branch one at a time, in slice-id order,
     with `git merge --no-ff`.
  4. On a conflict the merge is aborted, the branch and worktree are KEPT, and
     the lane is reported as needs_manual_merge. Nothing is overwritten.
  5. A lane whose controller failed is not merged; its worktree is kept.
  .project/ is usually untracked, so each lane's own ledger, verify logs and
  review verdicts are copied back to the main checkout after a clean merge.

Requirements: a git repository with no uncommitted changes to tracked files.

  codex_lanes.py --project-dir . --max-parallel 3 [--dry-run] [--json]
Exit: 0 all selected lanes merged, 1 some lane failed or needs a manual merge,
2 cannot run (not a git repo, dirty tree, kill switch, nothing to do).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from codex_drive import READY, dependency_ready, read_ledgers  # noqa: E402
from project_root import find_project_root  # noqa: E402  (codex_drive adds hooks/ to sys.path)

WORKTREES = ".praxis-worktrees"


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=check)


def select_lanes(root: Path, only: list[str] | None, limit: int):
    ledgers = read_ledgers(root)
    by_id = {l.slice_id: l for l in ledgers}
    picked, skipped = [], {}
    for ledger in sorted(ledgers, key=lambda l: l.slice_id):
        sid = ledger.slice_id
        if only and sid not in only:
            continue
        if ledger.lane() not in READY:
            if only:
                skipped[sid] = f"lane is {ledger.lane()}, not ready"
            continue
        if ledger.top.get("depends_on_slices") is None:
            skipped[sid] = "no depends_on_slices declared (add `depends_on_slices: []` to mark it independent)"
            continue
        if not dependency_ready(ledger, by_id, set()):
            skipped[sid] = "a declared dependency is not closed"
            continue
        if len(picked) >= limit:
            skipped[sid] = f"over --max-parallel {limit}; will run next time"
            continue
        picked.append(ledger)
    return picked, skipped


def copy_project_state(src: Path, dst: Path) -> None:
    """.project/ is normally untracked, so a fresh worktree lacks it."""
    s, d = src / ".project", dst / ".project"
    if not s.is_dir():
        return
    ignore = shutil.ignore_patterns("*.lock", "codex-controller.json", "STOP", ".drive.lock")
    shutil.copytree(s, d, dirs_exist_ok=True, ignore=ignore)
    agents = src / ".codex"
    if agents.is_dir() and not (dst / ".codex").exists():
        shutil.copytree(agents, dst / ".codex")


def copy_lane_state_back(worktree: Path, root: Path, sid: str) -> list[str]:
    """Bring back only this lane's own files; never another lane's ledger."""
    copied = []
    wsrc, wdst = worktree / ".project" / "working", root / ".project" / "working"
    if not wsrc.is_dir():
        return copied
    task_ids = []
    ledger = wsrc / f"slice-{sid}-tasks.yaml"
    if ledger.is_file():
        for line in ledger.read_text(errors="replace").splitlines():
            s = line.strip()
            if s.startswith("- id:"):
                task_ids.append(s.split(":", 1)[1].strip().strip("\"'"))
    for path in sorted(wsrc.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(wsrc)
        name = path.name
        mine = (f"slice-{sid}-" in name or rel.parts[0] == "reviews"
                or any(name.startswith(f"verify-{t}.") for t in task_ids))
        if not mine:
            continue
        target = wdst / rel
        if target.is_file() and target.read_bytes() == path.read_bytes():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(str(rel))
    return copied


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project-dir", type=Path, default=Path.cwd())
    ap.add_argument("--max-parallel", type=int, default=int(os.environ.get("PRAXIS_MAX_PARALLEL_LANES", "2")))
    ap.add_argument("--slice", action="append", help="limit to these slices (repeatable)")
    ap.add_argument("--controller", type=Path, default=HERE / "codex_drive.py",
                    help="single-lane controller to run in each worktree")
    ap.add_argument("--keep-worktrees", action="store_true", help="keep worktrees even after a clean merge")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = find_project_root(args.project_dir)
    if root is None:
        print("codex_lanes: no ancestor has .project/working", file=sys.stderr)
        return 2
    root = Path(root)
    if (root / ".project" / "STOP").exists():
        print("codex_lanes: kill switch .project/STOP exists; not starting", file=sys.stderr)
        return 2
    if git(root, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        print("codex_lanes: not a git repository; parallel lanes need git worktrees", file=sys.stderr)
        return 2
    top = Path(git(root, "rev-parse", "--show-toplevel").stdout.strip())
    if top.resolve() != root.resolve():
        print(f"codex_lanes: project root {root} is not the git top level {top}", file=sys.stderr)
        return 2
    dirty = [l for l in git(root, "status", "--porcelain", "--untracked-files=no").stdout.splitlines() if l.strip()]
    if dirty and not args.dry_run:
        print("codex_lanes: tracked files have uncommitted changes; commit or stash first:\n  "
              + "\n  ".join(dirty[:10]), file=sys.stderr)
        return 2
    base = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if base == "HEAD":
        print("codex_lanes: detached HEAD; check out a branch first", file=sys.stderr)
        return 2

    lanes, skipped = select_lanes(root, args.slice, max(1, args.max_parallel))
    report = {"base_branch": base, "selected": [l.slice_id for l in lanes], "skipped": skipped, "lanes": {}}
    if args.dry_run or not lanes:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"codex_lanes: would run {report['selected'] or 'nothing'} in parallel on top of {base}")
            for sid, why in skipped.items():
                print(f"  skip {sid}: {why}")
        return 0 if lanes or args.dry_run else 2

    wt_root = root / WORKTREES
    wt_root.mkdir(exist_ok=True)
    exclude = root / ".git" / "info" / "exclude"
    if exclude.parent.is_dir() and WORKTREES not in (exclude.read_text() if exclude.is_file() else ""):
        with exclude.open("a") as fh:
            fh.write(f"\n{WORKTREES}/\n")

    procs = {}
    for lane in lanes:
        sid = lane.slice_id
        branch, wt = f"praxis/lane-{sid}", wt_root / sid
        entry = report["lanes"][sid] = {"branch": branch, "worktree": str(wt)}
        if not wt.exists():
            exists = git(root, "rev-parse", "--verify", "--quiet", branch, check=False).returncode == 0
            made = git(root, "worktree", "add", str(wt), branch, check=False) if exists else \
                git(root, "worktree", "add", "-b", branch, str(wt), base, check=False)
            if made.returncode != 0:
                entry.update(status="failed", reason="git worktree add failed: " + made.stderr.strip()[-300:])
                continue
        copy_project_state(root, wt)
        log = (root / ".project" / "telemetry" / f"lane-{sid}.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(args.controller), "--project-dir", str(wt), "--slice", sid]
        fh = log.open("a")
        procs[sid] = (subprocess.Popen(cmd, cwd=wt, stdout=fh, stderr=subprocess.STDOUT,
                                       env=dict(os.environ, PRAXIS_PARALLEL_LANE=sid)), fh, wt)
        entry.update(status="running", log=str(log))
        print(f"[lanes] started {sid} in {wt} (log {log})", file=sys.stderr, flush=True)

    # Wait; pass the kill switch down to every worktree.
    while any(p.poll() is None for p, _, _ in procs.values()):
        if (root / ".project" / "STOP").exists():
            for _, _, wt in procs.values():
                (wt / ".project").mkdir(exist_ok=True)
                (wt / ".project" / "STOP").touch()
        time.sleep(float(os.environ.get("PRAXIS_LANES_POLL_SECONDS", "2")))
    for sid, (proc, fh, _) in procs.items():
        fh.close()
        report["lanes"][sid]["controller_exit"] = proc.returncode

    # Merge, one lane at a time, in slice-id order.
    for sid in sorted(procs):
        entry, wt = report["lanes"][sid], procs[sid][2]
        branch = entry["branch"]
        if entry["controller_exit"] != 0:
            entry.update(status="failed", reason=f"controller exited {entry['controller_exit']}; worktree kept")
            continue
        git(wt, "add", "-A")
        if git(wt, "status", "--porcelain").stdout.strip():
            done = git(wt, "-c", "user.name=praxis", "-c", "user.email=praxis@localhost", "commit", "-q",
                       "-m", f"praxis: lane {sid}", check=False)
            if done.returncode != 0:
                entry.update(status="failed", reason="commit failed: " + done.stderr.strip()[-300:])
                continue
        ahead = git(root, "rev-list", "--count", f"{base}..{branch}").stdout.strip()
        if ahead != "0":
            merged = git(root, "-c", "user.name=praxis", "-c", "user.email=praxis@localhost", "merge",
                         "--no-ff", "--no-edit", "-m", f"praxis: merge lane {sid}", branch, check=False)
            if merged.returncode != 0:
                git(root, "merge", "--abort", check=False)
                entry.update(status="needs_manual_merge",
                             reason=f"merge conflict; aborted. Resolve by hand: git merge {branch}")
                continue
        entry["state_copied_back"] = copy_lane_state_back(wt, root, sid)
        entry.update(status="merged", commits=int(ahead))
        if not args.keep_worktrees:
            git(root, "worktree", "remove", "--force", str(wt), check=False)
            git(root, "branch", "-D", branch, check=False)

    ok = all(e.get("status") == "merged" for e in report["lanes"].values())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for sid, e in sorted(report["lanes"].items()):
            print(f"[lanes] {sid}: {e.get('status')}" + (f" — {e['reason']}" if e.get("reason") else ""))
        for sid, why in skipped.items():
            print(f"[lanes] skipped {sid}: {why}")
    try:
        with (root / ".project" / "telemetry" / "lanes.jsonl").open("a") as fh:
            fh.write(json.dumps(dict(report, ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
