#!/usr/bin/env python3
"""praxis-verify — run a ledger task's verify command and record the result.

The evidence gate (hooks/praxis_guard.py) accepts only results recorded by this
runner, so an agent cannot mark a task done by writing a log file itself.

  praxis-verify <task-id> [--ledger PATH] [--project-dir DIR] [--timeout SEC] [--json]
  praxis-verify --record-review <pass|changes_requested|incomplete> --source NAME
                [--findings N] [--project-dir DIR]

What one run writes
  .project/local/evidence/<task>/<run>/output.log    full stdout+stderr (gitignored)
  .project/operational/verification/<task>--<run>.json  small committed summary:
      command + its sha256, exit code, pass/fail counts when recognisable,
      git HEAD, tree fingerprints before/after the run, log path + sha256 + tail.

The command runs with `bash -c` from the project root, exactly as the ledger
states it. It can drop extra artifacts (JUnit XML, screenshots) into
$PRAXIS_EVIDENCE_DIR. Old-style commands that redirect into
.project/working/verify-<id>.log still work: those files are moved into the
evidence folder after the run.

Exit code: the verify command's exit code (124 on timeout); 2 for usage errors.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.path.join(HERE, "..", "hooks"), os.path.join(HERE, "hooks"), HERE):
    if os.path.isfile(os.path.join(cand, "praxis_project.py")):
        sys.path.insert(0, os.path.abspath(cand))
        break
import praxis_project as pp  # noqa: E402

COUNT_PATTERNS = [
    # pytest: "== 12 passed, 1 failed, 2 skipped in 3.2s =="
    (re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)\b"), None),
    # jest/vitest: "Tests:       1 failed, 41 passed, 42 total"
    (re.compile(r"Tests:\s+(.*)total"), "jest"),
    # go test: "ok  	pkg	0.1s" / "FAIL	pkg"
    (re.compile(r"^(ok|FAIL)\s+\S+", re.M), "go"),
]


def counts_from(text: str) -> dict:
    tail = text[-20000:]
    out: dict = {}
    m = COUNT_PATTERNS[1][0].search(tail)
    if m:
        for n, k in re.findall(r"(\d+) (passed|failed|skipped|todo)", m.group(1)):
            out[k] = int(n)
        return out
    for n, k in COUNT_PATTERNS[0][0].findall(tail):
        k = "errors" if k.startswith("error") else k
        out[k] = int(n)
    if out:
        return out
    gos = COUNT_PATTERNS[2][0].findall(tail)
    if gos:
        out = {"packages_ok": gos.count("ok"), "packages_failed": gos.count("FAIL")}
    return out


def write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def head_of(root: str) -> str | None:
    try:
        r = pp.git(root, "rev-parse", "HEAD", timeout=5)
        return (r.stdout.strip() or None) if r.returncode == 0 else None
    except Exception:
        return None


def run_id() -> str:
    """Sortable run id: UTC time to the millisecond plus a random suffix."""
    now = time.time()
    return (time.strftime("%Y%m%dT%H%M%S", time.gmtime(now)) + f"{int(now * 1000) % 1000:03d}Z-"
            + secrets.token_hex(2))


def record_review(root: str, verdict: str, source: str, findings: int | None) -> int:
    rid = run_id()
    data = {"schema": pp.SCHEMA, "runner": pp.RUNNER, "kind": "review", "task": f"review-{pp.safe_id(source)}",
            "run_id": rid, "verdict": verdict, "source": source, "findings": findings,
            "finished_at": pp.now_iso(), "git_head": head_of(root), "tree_after": pp.fingerprint(root)}
    path = os.path.join(pp.summaries_dir(root), f"review-{pp.safe_id(source)}--{rid}.json")
    write_json(path, data)
    print(pp.rel(root, path))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", nargs="?")
    ap.add_argument("--ledger")
    ap.add_argument("--project-dir")
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("PRAXIS_VERIFY_TIMEOUT", "1800")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record-review", choices=["pass", "changes_requested", "incomplete"])
    ap.add_argument("--source", default="review")
    ap.add_argument("--findings", type=int)
    a = ap.parse_args()

    root = pp.find_root(a.project_dir)
    if not root:
        print("praxis-verify: no .project/ found above this directory", file=sys.stderr)
        return 2
    if a.record_review:
        return record_review(root, a.record_review, a.source, a.findings)
    if not a.task:
        ap.print_usage(sys.stderr)
        return 2
    ledger = os.path.abspath(a.ledger) if a.ledger else None
    hits = pp.find_task(root, a.task, ledger)
    if not hits:
        print(f"praxis-verify: task {a.task} not found in any .project/working/slice-*-tasks.yaml", file=sys.stderr)
        return 2
    picked = pp.pick_task(hits)
    if not picked:
        print(f"praxis-verify: task {a.task} is in several ledgers; pass --ledger: "
              + ", ".join(pp.rel(root, h[0]) for h in hits), file=sys.stderr)
        return 2
    ledger, task = picked
    cmd = task.get("verify")
    if pp.is_null(cmd):
        print(f"praxis-verify: task {a.task} has verify: null (human-checked); nothing to run", file=sys.stderr)
        return 2
    if cmd.strip() in ("|", ">", "|-", ">-"):
        print("praxis-verify: multi-line verify commands are not supported; put the steps in a script "
              "and call it from `verify:`", file=sys.stderr)
        return 2

    rid = run_id()
    ev_dir = os.path.join(pp.evidence_root(root), pp.safe_id(a.task), rid)
    os.makedirs(ev_dir, exist_ok=True)
    log_path = os.path.join(ev_dir, "output.log")
    legacy = {x: os.path.join(root, ".project", "working", f"verify-{a.task}.{x}") for x in ("log", "exit")}
    legacy_mtime = {x: (os.path.getmtime(p) if os.path.exists(p) else None) for x, p in legacy.items()}

    tree_before = pp.fingerprint(root)
    started, t0 = pp.now_iso(), time.time()
    env = dict(os.environ, PRAXIS_VERIFY_TASK=a.task, PRAXIS_EVIDENCE_DIR=ev_dir, PRAXIS_NESTED="1")
    with open(log_path, "wb") as fh:
        try:
            proc = subprocess.run(["bash", "-c", cmd], cwd=root, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                  timeout=a.timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            fh.write(f"\n[praxis-verify] timed out after {a.timeout}s\n".encode())
            code = 124
    duration = round(time.time() - t0, 2)

    # Old-style commands wrote their own log into working/: move it into evidence.
    for x, p in legacy.items():
        if os.path.exists(p) and os.path.getmtime(p) != legacy_mtime[x]:
            shutil.move(p, os.path.join(ev_dir, f"command.{x}"))
    text = open(log_path, errors="replace").read()
    cmd_log = os.path.join(ev_dir, "command.log")
    if os.path.isfile(cmd_log):
        text += "\n" + open(cmd_log, errors="replace").read()

    tree_after = pp.fingerprint(root)
    artifacts = sorted(f for f in os.listdir(ev_dir) if f != "output.log")
    mroot = pp.main_root(root)
    summary = {
        "schema": pp.SCHEMA, "runner": pp.RUNNER, "kind": "verify",
        "task": a.task, "run_id": rid, "ledger": pp.rel(root, ledger),
        "command": cmd, "command_sha256": pp.sha256_text(cmd),
        "exit_code": code, "passed": code == 0, "counts": counts_from(text),
        "started_at": started, "finished_at": pp.now_iso(), "duration_s": duration,
        "git_head": head_of(root), "tree_before": tree_before, "tree_after": tree_after,
        "harness": os.environ.get("PRAXIS_HARNESS") or ("codex" if os.environ.get("CODEX_HOME") else None),
        "log": {"path": pp.rel(mroot, log_path), "sha256": pp.sha256_file(log_path),
                "bytes": os.path.getsize(log_path), "tail": text.strip().splitlines()[-12:]},
        "artifacts": artifacts,
    }
    out = os.path.join(pp.summaries_dir(root), f"{pp.safe_id(a.task)}--{rid}.json")
    write_json(out, summary)
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        state = "PASS" if code == 0 else f"FAIL (exit {code})"
        c = ", ".join(f"{v} {k}" for k, v in summary["counts"].items())
        print(f"praxis-verify {a.task}: {state} in {duration}s{' — ' + c if c else ''}")
        print(f"  summary: {pp.rel(root, out)}")
        print(f"  log:     {summary['log']['path']}")
        if code != 0:
            print("  last lines:")
            for line in summary["log"]["tail"]:
                print("    " + line[:200])
    return code


if __name__ == "__main__":
    sys.exit(main())
