#!/usr/bin/env bash
# factory-frequency.sh — aggregate telemetry into per-artifact usage frequency
#
# Reads .project/operational/factory-metrics/ and reports:
#   - usage count per artifact (skill, agent, workflow, command)
#   - breakdown by invocation type (read, apply, preload, spawn, invoke)
#   - sessions per artifact
#   - per-period filtering (--since YYYY-MM-DD)
#
# Used by:
#   - System Steward at quarterly review
#   - CI / dashboard to surface "top SKILLs used" + "unused SKILLs"
#   - Per-project retros
#
# Usage:
#   ./scripts/factory-frequency.sh                                # all-time, all types
#   ./scripts/factory-frequency.sh --type skill                   # only skills
#   ./scripts/factory-frequency.sh --since 2026-04-01             # this quarter
#   ./scripts/factory-frequency.sh --format json                  # JSON output (for dashboards)
#   ./scripts/factory-frequency.sh --top 10                       # only top 10
#   ./scripts/factory-frequency.sh --project-dir <path>

set -u

PROJECT_DIR=""
TYPE_FILTER=""
SINCE=""
FORMAT="text"
TOP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT_DIR="$2"; shift 2 ;;
    --type)        TYPE_FILTER="$2"; shift 2 ;;
    --since)       SINCE="$2"; shift 2 ;;
    --format)      FORMAT="$2"; shift 2 ;;
    --top)         TOP="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
fi

METRICS_ROOT="$PROJECT_DIR/.project/operational/factory-metrics"

if [[ ! -d "$METRICS_ROOT" ]]; then
  if [[ "$FORMAT" == "json" ]]; then
    echo "[]"
  else
    echo "No telemetry found at $METRICS_ROOT"
  fi
  exit 0
fi

# --------------------------------------------------------------------
# Use Python for the aggregation — bash + awk gets clunky here
# --------------------------------------------------------------------
python3 << PYEOF
import os, re, sys, json, glob
from collections import defaultdict
from datetime import datetime

METRICS_ROOT = "$METRICS_ROOT"
TYPE_FILTER  = "$TYPE_FILTER"
SINCE        = "$SINCE"
FORMAT       = "$FORMAT"
TOP          = int("$TOP")

# Walk all telemetry files
records = []
type_dirs = ["skills", "agents", "workflows", "commands", "hooks", "gates", "references"]
for type_dir in type_dirs:
    artifact_type = type_dir[:-1]  # strip trailing s
    if TYPE_FILTER and artifact_type != TYPE_FILTER:
        continue
    base = os.path.join(METRICS_ROOT, type_dir)
    if not os.path.isdir(base):
        continue
    for artifact_name in sorted(os.listdir(base)):
        art_dir = os.path.join(base, artifact_name)
        if not os.path.isdir(art_dir):
            continue
        for f in glob.glob(os.path.join(art_dir, "*.md")):
            content = open(f).read()
            m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if not m:
                continue
            # parse minimal fields
            fields = {}
            for line in m.group(1).split("\n"):
                kv = line.split(":", 1)
                if len(kv) == 2:
                    fields[kv[0].strip()] = kv[1].strip()
            records.append({
                "type":       fields.get("artifact_type", artifact_type),
                "name":       fields.get("artifact_name", artifact_name),
                "state":      fields.get("artifact_state", "unknown"),
                "date":       fields.get("date", ""),
                "session":    fields.get("session", ""),
                "tool":       fields.get("tool", ""),
                "trigger":    fields.get("trigger", ""),
                "invocation": fields.get("invocation", ""),
                "outcome":    fields.get("outcome", ""),
            })

# Filter by --since
if SINCE:
    try:
        since_dt = datetime.fromisoformat(SINCE)
        records = [r for r in records if r["date"] and datetime.fromisoformat(r["date"].replace("Z","+00:00")).replace(tzinfo=None) >= since_dt]
    except Exception as e:
        print(f"Bad --since '{SINCE}': {e}", file=sys.stderr)
        sys.exit(1)

# Aggregate
agg = defaultdict(lambda: {"total": 0, "by_invocation": defaultdict(int), "sessions": set(), "state": "unknown"})
for r in records:
    key = (r["type"], r["name"])
    agg[key]["total"] += 1
    agg[key]["by_invocation"][r["invocation"]] += 1
    if r["session"]:
        agg[key]["sessions"].add(r["session"])
    if r["state"] and r["state"] != "unknown":
        agg[key]["state"] = r["state"]

# Sort by total descending
sorted_keys = sorted(agg.keys(), key=lambda k: -agg[k]["total"])
if TOP > 0:
    sorted_keys = sorted_keys[:TOP]

if FORMAT == "json":
    out = []
    for k in sorted_keys:
        a = agg[k]
        out.append({
            "type":          k[0],
            "name":          k[1],
            "state":         a["state"],
            "total":         a["total"],
            "sessions":      len(a["sessions"]),
            "by_invocation": dict(a["by_invocation"]),
        })
    print(json.dumps(out, indent=2))
else:
    # Text table
    print(f"Praxis factory frequency report")
    print(f"  Project: {os.path.dirname(METRICS_ROOT.rsplit('/.project/',1)[0])}")
    if SINCE: print(f"  Since:   {SINCE}")
    if TYPE_FILTER: print(f"  Type:    {TYPE_FILTER}")
    print(f"  Records: {len(records)}")
    print()
    print(f"{'TYPE':<10} {'NAME':<32} {'STATE':<14} {'TOTAL':>6} {'SESSIONS':>9}  {'BREAKDOWN'}")
    print("-" * 100)
    for k in sorted_keys:
        a = agg[k]
        breakdown = ", ".join(f"{inv}:{cnt}" for inv, cnt in sorted(a["by_invocation"].items()))
        print(f"{k[0]:<10} {k[1]:<32} {a['state']:<14} {a['total']:>6} {len(a['sessions']):>9}  {breakdown}")
PYEOF
