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


def _no_evidence(root, tid, task, ledger):
    """True when a done task has neither a praxis-verify run nor (pre-0.3.0) legacy files."""
    if not evidence_problem(root, tid, task, ledger=ledger):
        return False
    try:
        import praxis_project as _pp
        return _pp.legacy_problem(root, tid) is not None
    except Exception:
        return True


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
                   if t.get("status") == "done" and evidence_problem and _no_evidence(root, tid, t, ledger)]
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

    # Context budget: context tokens read per drive task (one row per iteration).
    alert = 2000000
    try:
        _here = os.path.dirname(os.path.abspath(__file__))
        for _cand in (os.path.join(_here, "..", "hooks"), _here):
            if os.path.isfile(os.path.join(_cand, "praxis_project.py")):
                sys.path.insert(0, os.path.abspath(_cand))
                break
        import praxis_project as _pp
        alert = _pp.context_budget(root)["iteration_alert_tokens"]
    except Exception:
        pass
    ctx_rows = []
    for r in tail_jsonl(os.path.join(tel, "drive.jsonl"), 400):
        def _n(k):
            v = r.get(k)
            return v if isinstance(v, int) else 0
        if not isinstance(r.get("input_tokens"), int):
            continue
        tok = _n("input_tokens") if r.get("harness") == "codex" else (
            _n("input_tokens") + _n("cache_read_input_tokens") + _n("cache_creation_input_tokens"))
        ctx_rows.append({"task": r.get("task"), "slice": r.get("slice"), "tier": r.get("tier"),
                         "outcome": r.get("outcome"), "context_tokens": tok, "ts": r.get("ts")})
    ctx_sorted = sorted(c["context_tokens"] for c in ctx_rows)
    context_budget = {
        "tasks_measured": len(ctx_rows),
        "median_context_tokens": ctx_sorted[len(ctx_sorted) // 2] if ctx_sorted else None,
        "alert_tokens": alert,
        "over_alert": sorted((c for c in ctx_rows if c["context_tokens"] > alert),
                             key=lambda c: -c["context_tokens"])[:5],
    }

    status = {
        "project": root,
        "context_budget": context_budget,
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
    cb = status["context_budget"]
    if cb["tasks_measured"]:
        print(f"  context per drive task: median {cb['median_context_tokens'] // 1000}k tokens over "
              f"{cb['tasks_measured']} tasks; {len(cb['over_alert'])} over {cb['alert_tokens'] // 1000}k")
        for c in cb["over_alert"]:
            print(f"    {c['context_tokens'] // 1000}k  {c['slice']}/{c['task']}  {c['tier']}  {c['outcome']}")
    print(f"  guard events: {status['guard_events'] or 'none'}")
    print(f"  io delegation: {status['io_delegation_events'] or 'none'}")
    for r in review_rows:
        print(f"  review: {r['role']} -> {r['verdict']} ({r['findings']} findings)  {r['file']}")
    for name, v in last.items():
        print(f"  last {name}: {v['updated']}" + (f" ({v['harness']})" if v["harness"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
