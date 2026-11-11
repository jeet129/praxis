#!/usr/bin/env python3
"""praxis-status.py — one status view for a Praxis project, whichever tool ran it.

Reads only files under .project/ (ledgers, telemetry, operator files), so it
works the same for Claude Code, Codex and Antigravity runs.

  praxis-status.py [--project-dir DIR] [--json]
"""
import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
try:
    from praxis_guard import parse_tasks, evidence_problem
except Exception:  # installed layouts keep hooks elsewhere; degrade gracefully
    parse_tasks = evidence_problem = None


def tail_jsonl(path, n=400):
    rows = []
    try:
        with open(path, errors="replace") as fh:
            for line in fh.readlines()[-n:]:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    except OSError:
        pass
    return rows


def age(path):
    try:
        s = int(time.time() - os.path.getmtime(path))
    except OSError:
        return "never"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m ago" if s >= 3600 else f"{s // 60}m ago"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.project_dir)
    proj = os.path.join(root, ".project")
    if not os.path.isdir(proj):
        print(f"no .project/ under {root}", file=sys.stderr)
        return 2
    tel, work = os.path.join(proj, "telemetry"), os.path.join(proj, "working")

    slices = []
    for ledger in sorted(glob.glob(os.path.join(work, "slice-*-tasks.y*ml"))):
        text = open(ledger, errors="replace").read()
        tasks = parse_tasks(text) if parse_tasks else {}
        counts = {}
        for t in tasks.values():
            counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
        missing = [tid for tid, t in tasks.items()
                   if t.get("status") == "done" and evidence_problem and evidence_problem(root, tid, t)]
        state = next((l.split(":", 1)[1].split("#")[0].strip() for l in text.splitlines()
                      if l.startswith("state:")), "?")
        slices.append({"ledger": os.path.basename(ledger), "state": state, "tasks": counts,
                       "done_without_evidence": missing, "updated": age(ledger)})

    guard = tail_jsonl(os.path.join(tel, "guard.jsonl"))
    io = tail_jsonl(os.path.join(tel, "io-delegation.jsonl"))
    by = lambda rows, key: {k: sum(1 for r in rows if r.get(key) == k) for k in {r.get(key) for r in rows} if k}
    reviews = sorted(glob.glob(os.path.join(work, "reviews", "*.json")))[-5:]
    review_rows = []
    for r in reviews:
        try:
            d = json.load(open(r))
            review_rows.append({"file": os.path.basename(r), "role": d.get("role"), "verdict": d.get("verdict"),
                                "findings": len(d.get("findings", []))})
        except Exception:
            pass
    last = {}
    for name in ("drive.jsonl", "sessions.jsonl", "model-routing.jsonl", "antigravity-activity.jsonl"):
        p = os.path.join(tel, name)
        if os.path.isfile(p):
            rows = tail_jsonl(p, 1)
            last[name] = {"updated": age(p), "harness": (rows[-1].get("harness") if rows else None)}

    status = {
        "project": root,
        "kill_switch": os.path.exists(os.path.join(proj, "STOP")),
        "steer_pending": os.path.isfile(os.path.join(proj, "STEER.md")),
        "drive_active_marker": os.path.isfile(os.path.join(work, ".drive-active")),
        "slices": slices,
        "guard_events": by(guard, "control"),
        "io_delegation_events": by(io, "decision") or by(io, "event"),
        "recent_reviews": review_rows,
        "last_activity": last,
    }
    if a.json:
        print(json.dumps(status, indent=2))
        return 0
    print(f"Praxis status — {root}")
    print(f"  kill switch: {'ON (.project/STOP)' if status['kill_switch'] else 'off'}"
          f"   steer note pending: {'yes' if status['steer_pending'] else 'no'}"
          f"   drive marker: {'yes' if status['drive_active_marker'] else 'no'}")
    print("  slices:" if slices else "  slices: none")
    for s in slices:
        t = ", ".join(f"{k} {v}" for k, v in sorted(s["tasks"].items())) or "no tasks parsed"
        warn = f"   !! done without evidence: {', '.join(s['done_without_evidence'])}" if s["done_without_evidence"] else ""
        print(f"    {s['ledger']}  [{s['state']}]  {t}  (updated {s['updated']}){warn}")
    print(f"  guard events: {status['guard_events'] or 'none'}")
    print(f"  io delegation: {status['io_delegation_events'] or 'none'}")
    for r in review_rows:
        print(f"  review: {r['role']} -> {r['verdict']} ({r['findings']} findings)  {r['file']}")
    for name, v in last.items():
        print(f"  last {name}: {v['updated']}" + (f" ({v['harness']})" if v["harness"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
