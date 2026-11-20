#!/usr/bin/env python3
"""praxis_project.py — shared .project/ helpers for every harness. Zero dependencies.

Used by the guard hook, the session-start hooks (Claude Code, Codex, Antigravity),
scripts/praxis-verify.py, scripts/praxis-memory.py and the commit-trailer hook.

Layout (v0.3.0)
  .project/local/                 gitignored, machine-local, safe to delete
    evidence/<task>/<run>/        full output of every praxis-verify run
    scratch/                      run scratch: fixtures, dumps, patches
    bin/                          shims refreshed every session start:
                                  praxis-verify, praxis-memory, praxis-commit-trailer
  .project/telemetry/*.jsonl      gitignored raw telemetry (summaries/ stays tracked)
  .project/operational/verification/<task>--<run>.json
                                  committed run summaries: what ran, exit code,
                                  the tree it ran against, log hash. Small.

Parallel lanes (git worktrees) share ONE evidence store: evidence_root() resolves
to the main checkout through `git rev-parse --git-common-dir`.

CLI (used by the shell and Antigravity session-start hooks):
  praxis_project.py ensure <root> [--plugin-root P]   create layout, seed files, shims
  praxis_project.py map <root>                         print the memory map (<= 40 lines)
  praxis_project.py where <root> <kind>                print the configured path for a kind
  praxis_project.py fingerprint <root>                 print the working-tree fingerprint
"""
from __future__ import annotations

import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

RUNNER = "praxis-verify"
SCHEMA = 1
GITIGNORE_BEGIN = "# >>> praxis-managed (praxis_project.py) >>>"
GITIGNORE_END = "# <<< praxis-managed <<<"
GITIGNORE_BODY = """# Machine-local state. Never committed; safe to delete.
local/
telemetry/*.jsonl
telemetry/.guard-*
telemetry/.goal-continue-*
telemetry/lane-*.log
*.lock
.drive.lock
STOP
STEER.delivered-*
"""
DEFAULT_KINDS = {
    "adr": ".project/decision",
    "incident": ".project/operational",
    "postmortem": ".project/operational",
    "review": ".project/operational/reviews",
    "risk_acceptance": ".project/operational/risk-acceptances",
    "episodic": ".project/episodic",
    "semantic": ".project/semantic",
    "procedural": ".project/procedural",
    "working": ".project/working",
    "inbox": ".project/working/inbox.md",
    "verification": ".project/operational/verification",
    "evidence": ".project/local/evidence",
    "review_rules": ".project/procedural/REVIEW.md",
    "review_checks": ".project/procedural/checks.yaml",
}
DEFAULT_BUDGETS = {"map_lines": 40, "injected_chars": 6000, "note_kb": 32}
DEFAULT_RETENTION = {"evidence_keep_runs": 3, "evidence_keep_days": 30, "working_stale_days": 30,
                     "review_rounds_keep": 1, "review_rounds_min_age_days": 14}
SHIMS = {
    "praxis-verify": "scripts/praxis-verify.py",
    "praxis-memory": "scripts/praxis-memory.py",
    "praxis-commit-trailer": "hooks/praxis_commit_trailer.py",
}


# ── basics ──────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_root(start: str | None = None) -> str:
    cur = os.path.abspath(start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, ".project")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


def git(root: str, *args: str, env: dict | None = None, timeout: float = 20,
        input_text: str | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    e.pop("GIT_INDEX_FILE", None)
    if env:
        e.update(env)
    return subprocess.run(["git", *args], cwd=root, env=e, capture_output=True, text=True,
                          timeout=timeout, input=input_text)


def is_git(root: str) -> bool:
    try:
        return git(root, "rev-parse", "--is-inside-work-tree", timeout=5).stdout.strip() == "true"
    except Exception:
        return False


def main_root(root: str) -> str:
    """The main checkout's project root (same as root outside a linked worktree)."""
    try:
        common = git(root, "rev-parse", "--path-format=absolute", "--git-common-dir", timeout=5).stdout.strip()
        top = git(root, "rev-parse", "--show-toplevel", timeout=5).stdout.strip()
    except Exception:
        return root
    if not common or not top:
        return root
    main_top = os.path.dirname(common) if os.path.basename(common) == ".git" else ""
    if not main_top or os.path.realpath(main_top) == os.path.realpath(top):
        return root
    rel = os.path.relpath(os.path.realpath(root), os.path.realpath(top))
    cand = os.path.normpath(os.path.join(main_top, rel))
    return cand if os.path.isdir(os.path.join(cand, ".project")) else root


def evidence_root(root: str) -> str:
    return os.path.join(main_root(root), ".project", "local", "evidence")


def summaries_dir(root: str) -> str:
    return os.path.join(root, *where(root, "verification").split("/"))


def rel(root: str, path: str) -> str:
    try:
        return os.path.relpath(path, root).replace(os.sep, "/")
    except Exception:
        return path


# ── memory layout (configurable per project) ────────────────────────────────
def _read_layout(root: str) -> tuple[dict, dict, list, dict]:
    kinds, budgets, injected = dict(DEFAULT_KINDS), dict(DEFAULT_BUDGETS), []
    retention = dict(DEFAULT_RETENTION)
    path = os.path.join(root, ".project", "governance", "memory-layout.yaml")
    if not os.path.isfile(path):
        return kinds, budgets, [".project/semantic/project-charter.md"], retention
    section = None
    for line in open(path, errors="replace").read().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.rstrip().endswith(":"):
            section = line.strip()[:-1]
            continue
        if not line.startswith(" "):
            section = None
            continue
        s = line.strip()
        if section == "injected" and s.startswith("- "):
            injected.append(unquote(s[2:].split(" #")[0].strip()))
            continue
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", s)
        if not m:
            continue
        key, val = m.group(1), unquote(strip_comment(m.group(2)))
        if section == "kinds" and val:
            kinds[key] = val.rstrip("/")
        elif section in ("budgets", "retention"):
            try:
                (budgets if section == "budgets" else retention)[key] = int(val)
            except ValueError:
                pass
    return kinds, budgets, injected or [".project/semantic/project-charter.md"], retention


def where(root: str, kind: str) -> str:
    return _read_layout(root)[0].get(kind, DEFAULT_KINDS.get(kind, ""))


def layout(root: str) -> dict:
    kinds, budgets, injected, retention = _read_layout(root)
    return {"kinds": kinds, "budgets": budgets, "injected": injected, "retention": retention}


# ── YAML-ish scalar handling (no dependency) ────────────────────────────────
def strip_comment(v: str) -> str:
    v = v.strip()
    if v[:1] in ("'", '"'):
        return v
    return re.split(r"\s+#", v, maxsplit=1)[0].strip()


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == '"':
        end, i, out = None, 1, []
        while i < len(v):
            c = v[i]
            if c == "\\" and i + 1 < len(v):
                nxt = v[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
                i += 2
                continue
            if c == '"':
                end = i
                break
            out.append(c)
            i += 1
        return "".join(out) if end is not None else v
    if len(v) >= 2 and v[0] == "'":
        i, out = 1, []
        while i < len(v):
            if v[i] == "'":
                if i + 1 < len(v) and v[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out)
            out.append(v[i])
            i += 1
        return v
    return v


TASK_FIELDS = ("status", "verify", "completed_at", "verify_changed_reason", "attempts")


def parse_tasks(text: str) -> dict:
    """{task_id: {status, verify, completed_at, verify_changed_reason, attempts}} from a ledger."""
    tasks, cur, indent = {}, None, None
    for line in text.splitlines():
        m = re.match(r"^(\s*)-\s+id:\s*(.+?)\s*$", line)
        if m:
            tid = unquote(strip_comment(m.group(2)))
            cur, indent = tasks.setdefault(tid, {}), len(m.group(1))
            continue
        if cur is None:
            continue
        m = re.match(r"^(\s+)(%s):\s*(.*?)\s*$" % "|".join(TASK_FIELDS), line)
        if m and len(m.group(1)) > (indent or 0) and m.group(2) not in cur:
            cur[m.group(2)] = unquote(strip_comment(m.group(3)))
    return tasks


def is_null(v) -> bool:
    return v is None or str(v).strip() in ("", "null", "~", "None")


def ledgers(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, ".project", "working", "slice-*-tasks.y*ml")))


def pick_task(hits: list):
    """One (ledger, task) from several ledgers sharing a task id: the only active one."""
    if len(hits) <= 1:
        return hits[0] if hits else None
    active = [h for h in hits if h[1].get("status") in ("open", "in_progress")]
    return active[0] if len(active) == 1 else None


def find_task(root: str, task_id: str, ledger: str | None = None):
    paths = [ledger] if ledger else ledgers(root)
    hits = []
    for p in paths:
        try:
            t = parse_tasks(open(p, errors="replace").read())
        except Exception:
            continue
        if task_id in t:
            hits.append((p, t[task_id]))
    return hits


# ── tree fingerprints ───────────────────────────────────────────────────────
EXCLUDE = (".project", ".praxis-worktrees")


def _temp_index(root: str):
    idx = git(root, "rev-parse", "--path-format=absolute", "--git-path", "index", timeout=5).stdout.strip()
    fd, tmp = tempfile.mkstemp(prefix="praxis-index-")
    os.close(fd)
    if idx and os.path.isfile(idx):
        shutil.copy2(idx, tmp)
    else:
        os.unlink(tmp)
    return tmp


def object_env(root: str, write: bool = False) -> dict:
    """Keep fingerprint objects out of the repository's own object store.

    Blobs for untracked or modified files are written to the gitignored
    .project/local/git-objects/ (an alternate store), so fingerprinting never
    grows .git/. Readers (diffs between fingerprints) add it as an alternate.
    """
    local = os.path.join(main_root(root), ".project", "local", "git-objects")
    try:
        real = git(root, "rev-parse", "--path-format=absolute", "--git-path", "objects", timeout=5).stdout.strip()
    except Exception:
        real = ""
    if write:
        os.makedirs(local, exist_ok=True)
        return {"GIT_OBJECT_DIRECTORY": local, "GIT_ALTERNATE_OBJECT_DIRECTORIES": real}
    return {"GIT_ALTERNATE_OBJECT_DIRECTORIES": local} if os.path.isdir(local) else {}


def _tree_from_index(root: str, tmp: str, add_all: bool, timeout: float) -> str | None:
    env = {"GIT_INDEX_FILE": tmp, **object_env(root, write=True)}
    if add_all:
        spec = ["--", "."] + [f":(exclude){x}" for x in EXCLUDE]
        r = git(root, "add", "-A", *spec, env=env, timeout=timeout)
        if r.returncode != 0:
            return None
    git(root, "rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", *EXCLUDE, env=env, timeout=timeout)
    r = git(root, "write-tree", env=env, timeout=timeout)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def fingerprint(root: str, timeout: float | None = None) -> str | None:
    """Tree id of every non-ignored file under root, excluding .project/. None if not git/slow."""
    if not is_git(root):
        return None
    timeout = timeout or float(os.environ.get("PRAXIS_FINGERPRINT_TIMEOUT", "20"))
    tmp = None
    try:
        tmp = _temp_index(root)
        return _tree_from_index(root, tmp, True, timeout)
    except Exception:
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def staged_fingerprint(root: str) -> str | None:
    """Tree id of what `git commit` will record, excluding .project/."""
    if not is_git(root):
        return None
    tmp = None
    try:
        tmp = _temp_index(root)
        return _tree_from_index(root, tmp, False, 20)
    except Exception:
        return None
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def changed_paths(root: str, tree_a: str, tree_b: str, limit: int = 200) -> list[str] | None:
    try:
        r = git(root, "diff", "--name-only", "--no-renames", tree_a, tree_b, env=object_env(root), timeout=20)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.splitlines() if p][:limit]


# ── verification summaries ──────────────────────────────────────────────────
def safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:80]


def summaries(root: str, task_id: str | None = None) -> list[dict]:
    out, seen = [], set()
    for base in {summaries_dir(root), summaries_dir(main_root(root))}:
        pat = f"{safe_id(task_id)}--*.json" if task_id else "*.json"
        for p in glob.glob(os.path.join(base, pat)):
            name = os.path.basename(p)
            if name in seen:
                continue
            seen.add(name)
            try:
                d = json.load(open(p))
            except Exception:
                continue
            d["_path"] = p
            out.append(d)
    # run_id is UTC-to-the-millisecond, so it orders runs within one second too.
    out.sort(key=lambda d: (d.get("finished_at") or "", d.get("run_id") or ""), reverse=True)
    return out


def latest_summary(root: str, task_id: str, ledger: str | None = None) -> dict | None:
    """Newest verify summary for task_id; scoped to `ledger` when task ids repeat across slices."""
    want = rel(root, os.path.abspath(ledger)) if ledger else None
    for d in summaries(root, task_id):
        if d.get("task") != task_id or d.get("kind", "verify") != "verify":
            continue
        if want and d.get("ledger") and d.get("ledger") != want:
            continue
        return d
    return None


def legacy_problem(root: str, task_id: str) -> str | None:
    work = os.path.join(root, ".project", "working")
    log_path, exit_path = (os.path.join(work, f"verify-{task_id}.{x}") for x in ("log", "exit"))
    if os.path.isfile(exit_path):
        code = open(exit_path, errors="replace").read().strip()
        return None if code == "0" else f"verify-{task_id}.exit records exit code {code or '?'} (must be 0)"
    return None if os.path.isfile(log_path) else "no legacy verify log either"


def evidence_problem(root: str, task_id: str, task: dict, check_fresh: bool = False,
                     ledger: str | None = None) -> str | None:
    """None if the task's evidence is acceptable, else a reason string."""
    verify = task.get("verify")
    if is_null(verify):
        return None  # human-checked task
    shim = ".project/local/bin/praxis-verify"
    s = latest_summary(root, task_id, ledger)
    if not s:
        if os.environ.get("PRAXIS_ALLOW_LEGACY_EVIDENCE") == "1" and legacy_problem(root, task_id) is None:
            return None
        return (f"no verification run on record. Run `{shim} {task_id}`; it runs the task's verify "
                f"command and records the result (agent-written logs are not accepted)")
    if s.get("runner") != RUNNER or s.get("schema") != SCHEMA:
        return f"{rel(root, s['_path'])} was not written by {RUNNER}; run `{shim} {task_id}`"
    if s.get("command_sha256") != sha256_text(str(verify)):
        return (f"the verify command changed after the last run ({s.get('finished_at')}); "
                f"run `{shim} {task_id}` again")
    if s.get("exit_code") != 0:
        return (f"the last run ({s.get('finished_at')}) exited {s.get('exit_code')}; see "
                f"{(s.get('log') or {}).get('path', 'its log')}. Fix the cause and run `{shim} {task_id}`")
    if check_fresh and os.environ.get("PRAXIS_EVIDENCE_FRESHNESS", "tree") != "off":
        then = s.get("tree_after") or s.get("tree_before")
        if then:
            cur = fingerprint(root, timeout=float(os.environ.get("PRAXIS_FINGERPRINT_TIMEOUT", "6")))
            if cur and cur != then:
                paths = changed_paths(root, then, cur, 6) or []
                return (f"code changed after the verification run at {s.get('finished_at')} "
                        f"({', '.join(paths) or 'files differ'}); run `{shim} {task_id}` again")
    return None


# ── project layout bootstrap ────────────────────────────────────────────────
def _write_if_changed(path: str, content: str, mode: int | None = None) -> bool:
    try:
        if os.path.isfile(path) and open(path, errors="replace").read() == content:
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
        if mode is not None:
            os.chmod(path, mode)
        return True
    except Exception:
        return False


def ensure_gitignore(root: str) -> bool:
    path = os.path.join(root, ".project", ".gitignore")
    block = f"{GITIGNORE_BEGIN}\n{GITIGNORE_BODY}{GITIGNORE_END}\n"
    text = open(path, errors="replace").read() if os.path.isfile(path) else ""
    if GITIGNORE_BEGIN in text and GITIGNORE_END in text:
        new = re.sub(re.escape(GITIGNORE_BEGIN) + r".*?" + re.escape(GITIGNORE_END) + r"\n?",
                     block, text, flags=re.S)
    else:
        new = (text.rstrip("\n") + "\n\n" if text.strip() else "") + block
    return _write_if_changed(path, new)


def ensure_shims(root: str, plugin_root: str) -> list[str]:
    made = []
    bindir = os.path.join(root, ".project", "local", "bin")
    for name, target in SHIMS.items():
        script = os.path.join(plugin_root, target)
        if not os.path.isfile(script):
            continue
        body = ("#!/bin/sh\n# Praxis shim, rewritten at every session start. Do not edit.\n"
                f"exec python3 '{script}' \"$@\"\n")
        if _write_if_changed(os.path.join(bindir, name), body, 0o755):
            made.append(name)
    return made


def ensure_commit_hook(root: str) -> str:
    """Install prepare-commit-msg when no hook exists. Never replaces a foreign hook."""
    if os.environ.get("PRAXIS_COMMIT_TRAILER", "on") == "off" or not is_git(root):
        return "off"
    try:
        hooks = git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks", timeout=5).stdout.strip()
    except Exception:
        return "error"
    if not hooks:
        return "error"
    path = os.path.join(hooks, "prepare-commit-msg")
    shim = os.path.join(main_root(root), ".project", "local", "bin", "praxis-commit-trailer")
    body = ("#!/bin/sh\n# praxis-managed: adds a Praxis-Verified trailer. Remove this file to opt out,\n"
            "# or set PRAXIS_COMMIT_TRAILER=off before the session starts.\n"
            f"[ -x '{shim}' ] && '{shim}' \"$@\"\nexit 0\n")
    if os.path.isfile(path) and "praxis-managed" not in open(path, errors="replace").read():
        return "skipped (existing prepare-commit-msg hook)"
    _write_if_changed(path, body, 0o755)
    return "installed"


def ensure(root: str, plugin_root: str | None = None) -> dict:
    proj = os.path.join(root, ".project")
    if not os.path.isdir(proj):
        return {"ok": False, "reason": "no .project"}
    for sub in ("local/evidence", "local/scratch", "local/bin", "telemetry/summaries",
                "operational/verification", "governance"):
        os.makedirs(os.path.join(proj, sub), exist_ok=True)
    info = {"ok": True, "gitignore": ensure_gitignore(root)}
    if plugin_root:
        seed = os.path.join(plugin_root, "governance", "memory-layout.yaml")
        dst = os.path.join(proj, "governance", "memory-layout.yaml")
        if os.path.isfile(seed) and not os.path.isfile(dst):
            shutil.copy2(seed, dst)
            info["seeded_layout"] = True
        info["shims"] = ensure_shims(root, plugin_root)
        info["commit_hook"] = ensure_commit_hook(root)
    return info


# ── memory map (session-start injected layer) ───────────────────────────────
def _count(path: str, pattern: str = "*.md") -> int:
    return len(glob.glob(os.path.join(path, "**", pattern), recursive=True)) if os.path.isdir(path) else 0


def _du(path: str) -> int:
    total = 0
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def memory_map(root: str) -> str:
    lay = layout(root)
    k, limit = lay["kinds"], lay["budgets"].get("map_lines", 40)
    lines = ["Project memory map (where to look; read only what the task needs):"]
    for kind, label in (("adr", "decisions (ADRs)"), ("semantic", "domain, glossary, assumptions"),
                        ("procedural", "how this project works"), ("episodic", "slice and milestone history"),
                        ("review", "review dispositions"), ("incident", "incidents, risks, change log")):
        p = os.path.join(root, k[kind])
        n = _count(p) if os.path.isdir(p) else 0
        for other in ("review", "risk_acceptance", "verification"):
            q = os.path.join(root, k.get(other, ""))
            if other != kind and os.path.isdir(q) and os.path.realpath(q).startswith(os.path.realpath(p) + os.sep):
                n -= _count(q)
        if n > 0:
            lines.append(f"- {label}: {k[kind]}/ ({n} notes)")
    idx = os.path.join(root, ".project", "INDEX.yaml")
    if os.path.isfile(idx):
        lines.append("- index: .project/INDEX.yaml (by tag and domain; regenerate: praxis-memory index)")
    recent = []
    for kind in ("adr", "episodic"):
        p = os.path.join(root, k[kind])
        if os.path.isdir(p):
            recent += [(os.path.getmtime(f), f) for f in glob.glob(os.path.join(p, "**", "*.md"), recursive=True)
                       if os.path.basename(f) not in ("INDEX.md", "README.md")]
    if recent:
        lines.append("- recently changed: " + ", ".join(
            rel(root, f) for _, f in sorted(recent, reverse=True)[:5]))
    led = [os.path.basename(p) for p in ledgers(root)]
    open_led = []
    for p in ledgers(root):
        try:
            text = open(p, errors="replace").read()
            t = parse_tasks(text)
        except Exception:
            continue
        if re.search(r"^state:\s*[\"']?(closed|done|complete|completed)\b", text, re.M):
            continue
        n = sum(1 for v in t.values() if v.get("status") in ("open", "in_progress", "blocked"))
        if n:
            open_led.append(f"{os.path.basename(p)} ({n} open)")
    if open_led:
        lines.append("- active ledgers: " + ", ".join(open_led[:6]))
    elif led:
        lines.append(f"- ledgers: {len(led)} in .project/working/ (none open)")
    lines.append("- verification: run `.project/local/bin/praxis-verify <task>`; never hand-write evidence")
    overrides = [f"{kk}={vv}" for kk, vv in k.items() if DEFAULT_KINDS.get(kk) != vv]
    if overrides:
        lines.append("- layout overrides (.project/governance/memory-layout.yaml): " + ", ".join(overrides[:6]))
    warn = []
    work = os.path.join(root, ".project", "working")
    if os.path.isdir(work):
        n = len(os.listdir(work))
        if n > 150:
            warn.append(f"working/ has {n} entries (run: praxis-memory consolidate)")
    stray = [f for f in glob.glob(os.path.join(work, "*")) if re.search(r"\.(log|xml|sql|exit)$", f)]
    if len(stray) > 20:
        warn.append(f"{len(stray)} raw log/xml/sql files in working/ (run: praxis-memory migrate-local)")
    if warn:
        lines.append("- memory hygiene: " + "; ".join(warn))
    md = os.path.join(root, "CLAUDE.md")
    if os.path.isfile(md):
        try:
            if "# Compact instructions" not in open(md, errors="replace").read():
                lines.append("- context: CLAUDE.md has no compaction instructions "
                             "(run: praxis-memory context-setup --apply)")
        except Exception:
            pass
    return "\n".join(lines[:limit])


# ── context budget (in-session drive hand-off) ──────────────────────────────
CONTEXT_DEFAULTS = {"on_session_budget": "continue",
                    "session_max_tasks": 3, "session_max_context_tokens": 350000,
                    "iteration_alert_tokens": 2000000,
                    "max_turns_deep": 40, "max_turns_standard": 30, "max_turns_light": 20}


def context_budget(root: str) -> dict:
    """governance/autonomy.yaml `context_budget:` (project copy wins), env overrides."""
    out = dict(CONTEXT_DEFAULTS)
    for path in (os.path.join(root, ".project", "governance", "autonomy.yaml"),):
        if not os.path.isfile(path):
            continue
        section, sub = None, None
        for line in open(path, errors="replace").read().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if not line.startswith(" "):
                section = line.split(":", 1)[0].strip()
                sub = None
                continue
            if section != "context_budget":
                continue
            m = re.match(r"^(\s+)([A-Za-z0-9_]+):\s*(.*)$", line)
            if not m:
                continue
            key, val = m.group(2), strip_comment(m.group(3))
            if len(m.group(1)) <= 2 and not val:
                sub = key
                continue
            name = f"max_turns_{key}" if sub == "max_turns_by_tier" and len(m.group(1)) > 2 else key
            if name == "on_session_budget":
                out[name] = unquote(val) if unquote(val) in ("continue", "ask") else "continue"
                continue
            try:
                out[name] = int(val)
            except ValueError:
                pass
    for key in list(out):
        env = os.environ.get("PRAXIS_" + key.upper())
        if env and env.isdigit():
            out[key] = int(env)
        elif env and key == "on_session_budget" and env in ("continue", "ask"):
            out[key] = env
    return out


def transcript_tokens(path: str) -> int | None:
    """Rough size of the live context: transcript bytes after the last compaction, / 5."""
    try:
        size = os.path.getsize(path)
        start = 0
        with open(path, "rb") as fh:
            # Scan the tail in chunks for the last compaction marker.
            pos, chunk = size, 1 << 20
            while pos > 0:
                pos = max(0, pos - chunk)
                fh.seek(pos)
                data = fh.read(min(chunk + 200, size - pos))
                idx = max(data.rfind(b"compact_boundary"), data.rfind(b'"type":"compacted"'),
                          data.rfind(b'"type": "compacted"'))
                if idx >= 0:
                    start = pos + idx
                    break
                if size - pos > 64 * chunk:
                    break
        return (size - start) // 5
    except Exception:
        return None


def done_since(root: str, since: float, ledger_hint: str = "") -> list[str]:
    """Task ids marked done (completed_at) at or after `since` (epoch seconds)."""
    out = []
    for p in ledgers(root):
        if ledger_hint and ledger_hint not in os.path.basename(p):
            continue
        try:
            tasks = parse_tasks(open(p, errors="replace").read())
        except Exception:
            continue
        for tid, t in tasks.items():
            if t.get("status") != "done" or is_null(t.get("completed_at")):
                continue
            try:
                ts = datetime.datetime.fromisoformat(str(t["completed_at"]).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
                if ts.timestamp() >= since - 1:
                    out.append(tid)
            except Exception:
                continue
    return out


def session_usage(root: str, since: float | None, transcript: str | None, ledger_hint: str = ""):
    """(tasks finished in this session, estimated context tokens or None)."""
    done = done_since(root, since, ledger_hint) if since is not None else []
    return done, (transcript_tokens(transcript) if transcript else None)


def budget_hint(root: str, session_key: str, since: float | None, transcript: str | None,
                ledger_hint: str = "") -> str | None:
    """A one-line note for the person, at most once per budget step; the drive keeps going.

    Shown when finished tasks reach each multiple of session_max_tasks, or the
    context estimate reaches each multiple of session_max_context_tokens.
    """
    b = context_budget(root)
    done, tokens = session_usage(root, since, transcript, ledger_hint)
    t_step = len(done) // b["session_max_tasks"] if b["session_max_tasks"] > 0 else 0
    c_step = (tokens or 0) // b["session_max_context_tokens"] if b["session_max_context_tokens"] > 0 else 0
    if not t_step and not c_step:
        return None
    flag = os.path.join(root, ".project", "telemetry", f".budget-hint-{re.sub(r'[^A-Za-z0-9_-]', '', session_key)[:64]}")
    try:
        last = json.load(open(flag)) if os.path.isfile(flag) else {}
    except Exception:
        last = {}
    if t_step <= last.get("tasks", 0) and c_step <= last.get("context", 0):
        return None
    try:
        os.makedirs(os.path.dirname(flag), exist_ok=True)
        json.dump({"tasks": max(t_step, last.get("tasks", 0)), "context": max(c_step, last.get("context", 0))},
                  open(flag, "w"))
    except Exception:
        return None
    parts = [f"{len(done)} tasks finished in this session"] if done else []
    if tokens:
        parts.append(f"about {tokens // 1000}k tokens of context")
    return ("Praxis: good moment to start a fresh session (" + ", ".join(parts) + "). The drive keeps "
            "going on its own; if you want a clean context, press Esc, run /clear (Codex: /new) and then "
            "the drive command again. The ledger carries the state.")


def session_handoff(root: str, since: float | None, transcript: str | None,
                    ledger_hint: str = "") -> str | None:
    """Reason to stop an in-session drive and continue in a fresh session, or None.

    The ledger is the hand-off: a fresh session reads it and takes the next task,
    so starting over costs a few thousand tokens while carrying a long session
    re-reads its whole history on every tool call.
    """
    b = context_budget(root)
    reasons = []
    if since is not None and b["session_max_tasks"] > 0:
        done = done_since(root, since, ledger_hint)
        if len(done) >= b["session_max_tasks"]:
            reasons.append(f"{len(done)} tasks finished in this session ({', '.join(done[:6])})")
    if transcript and b["session_max_context_tokens"] > 0:
        t = transcript_tokens(transcript)
        if t and t >= b["session_max_context_tokens"]:
            reasons.append(f"the session context is about {t // 1000}k tokens")
    if not reasons:
        return None
    return ("PRAXIS CONTEXT BUDGET: " + " and ".join(reasons) + ". Stop here and continue in a fresh "
            "session: Claude Code `/clear`, Codex `/new`, Antigravity a new conversation, then run the "
            "drive command again. The ledger carries the state, so nothing is lost; carrying this session "
            "forward would re-read its whole history on every tool call. Before stopping, make sure the "
            "ledger is up to date and any in-progress task has `notes:` saying what was tried, what was "
            "ruled out and the next step.")


# ── CLI ─────────────────────────────────────────────────────────────────────
def _cli(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, root = argv[0], os.path.abspath(argv[1])
    if cmd == "ensure":
        pr = argv[argv.index("--plugin-root") + 1] if "--plugin-root" in argv else None
        print(json.dumps(ensure(root, pr)))
    elif cmd == "map":
        print(memory_map(root))
    elif cmd == "where":
        print(where(root, argv[2]))
    elif cmd == "fingerprint":
        print(fingerprint(root) or "")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(_cli(sys.argv[1:]))
    except Exception as exc:  # hooks must never break a session
        print(f"praxis_project: {exc}", file=sys.stderr)
        sys.exit(0)
