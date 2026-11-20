#!/usr/bin/env python3
"""praxis_commit_trailer.py — git prepare-commit-msg hook: say how a commit was verified.

Adds one trailer to every commit message:
  Praxis-Verified: verify (T1, T2)        a passing praxis-verify run saw exactly
                                          the committed content of every changed file
  Praxis-Verified: verify (T1); review    ...and a recorded review passed on it
  Praxis-Verified: review                 review only
  Praxis-Verified: none                   nothing on record matches this commit

`git log --grep "Praxis-Verified: none"` then lists unverified commits. The hook
never blocks a commit and never edits a message that already has the trailer.
Installed by session start into .git/hooks/prepare-commit-msg only when no
other hook is there. Opt out: PRAXIS_COMMIT_TRAILER=off.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import praxis_project as pp  # noqa: E402

MAX_SUMMARIES = 300


def matches(root, verified_tree, commit_tree, paths):
    if not verified_tree or not paths:
        return False
    r = pp.git(root, "diff", "--quiet", verified_tree, commit_tree, "--", *paths, env=pp.object_env(root), timeout=20)
    return r.returncode == 0


def trailer_for(root):
    commit_tree = pp.staged_fingerprint(root)
    if not commit_tree:
        return None
    head = pp.git(root, "rev-parse", "--verify", "-q", "HEAD^{tree}", timeout=5).stdout.strip()
    # (commit_tree's objects live in the alternate store; changed_paths adds it)
    if head:
        paths = pp.changed_paths(root, head, commit_tree, 5000) or []
        # changed_paths compares trees that both exclude .project only if HEAD does; filter.
        paths = [p for p in paths if not p.startswith(pp.EXCLUDE)]
    else:
        r = pp.git(root, "ls-tree", "-r", "--name-only", commit_tree, env=pp.object_env(root), timeout=20)
        paths = r.stdout.splitlines()
    if not paths:
        return "Praxis-Verified: none (no code changes)" if head else None
    tasks, reviewed = [], False
    for s in pp.summaries(root)[:MAX_SUMMARIES]:
        trees = [t for t in (s.get("tree_after"), s.get("tree_before")) if t]
        if not any(matches(root, t, commit_tree, paths) for t in trees):
            continue
        if s.get("kind") == "review":
            reviewed = reviewed or s.get("verdict") == "pass"
        elif s.get("exit_code") == 0 and s.get("task") not in tasks:
            tasks.append(s["task"])
    parts = []
    if tasks:
        parts.append("verify (" + ", ".join(sorted(tasks)[:12]) + ")")
    if reviewed:
        parts.append("review")
    return "Praxis-Verified: " + ("; ".join(parts) if parts else "none")


def main(argv):
    if os.environ.get("PRAXIS_COMMIT_TRAILER", "on") == "off" or not argv:
        return 0
    msg_file, source = argv[0], (argv[1] if len(argv) > 1 else "")
    if source == "merge":
        return 0
    try:
        text = open(msg_file, errors="replace").read()
    except Exception:
        return 0
    if "Praxis-Verified:" in text:
        return 0
    root = pp.find_root(os.getcwd())
    if not root:
        return 0
    line = trailer_for(root)
    if not line:
        return 0
    key, value = line.split(": ", 1)
    r = subprocess.run(["git", "interpret-trailers", "--in-place", "--if-exists", "doNothing",
                        "--trailer", f"{key}: {value}", msg_file], capture_output=True, text=True)
    if r.returncode != 0:
        with open(msg_file, "a") as fh:
            fh.write(("\n" if text.endswith("\n") else "\n\n") + line + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        sys.exit(0)
