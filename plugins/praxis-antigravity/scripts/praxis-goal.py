#!/usr/bin/env python3
"""praxis-goal.py — turn a slice ledger into a goal statement for the tool's own
long-run feature (Claude Code `/goal`, Codex `/goal`, Antigravity `/goal`).

The goal is phrased so it can be checked from files, not from the agent's say-so:
every task done, each with verify evidence, and the slice state closed.

  praxis-goal.py --slice S9 [--project-dir DIR]      prints the goal text
  praxis-goal.py --slice S9 --arm                    also writes .project/working/.drive-active
                                                     (arms the Antigravity Stop-hook continuation)
  praxis-goal.py --disarm                            removes the marker
"""
import argparse
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice")
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--arm", action="store_true")
    ap.add_argument("--disarm", action="store_true")
    a = ap.parse_args()
    work = os.path.join(os.path.abspath(a.project_dir), ".project", "working")
    marker = os.path.join(work, ".drive-active")
    if a.disarm:
        if os.path.exists(marker):
            os.remove(marker)
        print("drive marker removed")
        return 0
    if not a.slice:
        ap.error("--slice is required")
    ledger = os.path.join(work, f"slice-{a.slice}-tasks.yaml")
    if not os.path.isfile(ledger):
        print(f"no ledger at {ledger}", file=sys.stderr)
        return 2
    rel = f".project/working/slice-{a.slice}-tasks.yaml"
    print(
        f"Finish slice {a.slice}. Done means ALL of these are true, checked from files: "
        f"(1) every task in {rel} has status done, or blocked with a written reason; "
        f"(2) every done task has its verify log at .project/working/verify-<task-id>.log from a "
        f"run that exited 0; (3) the ledger's gates are pass or n/a; (4) the ledger state is closed. "
        f"Work one task at a time: implement, run its verify command, record the result, update the "
        f"ledger. Stop and report if .project/STOP exists, if a decision is needed, or if a task "
        f"fails {os.environ.get('PRAXIS_MAX_TASK_ATTEMPTS', '3')} times."
    )
    if a.arm:
        os.makedirs(work, exist_ok=True)
        with open(marker, "w") as fh:
            fh.write(a.slice + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
