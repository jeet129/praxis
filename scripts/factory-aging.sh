#!/usr/bin/env bash
# factory-aging.sh — telemetry coverage audit
#
# DEPRECATION NOTE: this script reads the legacy factory-metrics stub layer
# (.project/operational/factory-metrics/<type>s/<name>/*.md), which no longer
# receives skill-read / preload / session records — that capture path was
# retired after real-world capture ratio proved ~5% (plugin-injected skills
# never fire a Read event; main-session orchestration produces no Task
# event). Primary usage analytics now come from `scripts/factory-usage-report.py`,
# which mines checkpoint records (.project/episodic/checkpoint-*.md) and other
# mandatory workflow artifacts instead of tool-event side effects. This script
# remains useful for command-stub aging (the tap still records those) and for
# human /factory-record observations — not as the primary source of skill/
# agent usage counts. Behavior below is unchanged.
#
# Reports which praxis artifacts (skills, agents, workflows, commands, hooks)
# have stale or missing telemetry. Run by the System Steward at quarterly
# review and by CI as a gate on experimental skills.
#
# Exit codes:
#   0  all checks pass
#   1  at least one experimental artifact has no telemetry within --strict-window
#   2  at least one active artifact has no telemetry within --warn-window (warning only)
#
# Usage:
#   ./scripts/factory-aging.sh                            # default thresholds
#   ./scripts/factory-aging.sh --strict-window 30         # experimental must have telemetry within N days
#   ./scripts/factory-aging.sh --warn-window 90           # active warn if no telemetry within N days
#   ./scripts/factory-aging.sh --project-dir <path>
#   ./scripts/factory-aging.sh --quiet                    # only output if there are failures

set -u

STRICT_WINDOW=30   # days — experimental skills MUST have telemetry within this
WARN_WINDOW=90     # days — active skills WARN if no telemetry within this
PROJECT_DIR=""
QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict-window)  STRICT_WINDOW="$2"; shift 2 ;;
    --warn-window)    WARN_WINDOW="$2"; shift 2 ;;
    --project-dir)    PROJECT_DIR="$2"; shift 2 ;;
    --quiet)          QUIET=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "$PROJECT_DIR" ]]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
METRICS_ROOT="$PROJECT_DIR/.project/operational/factory-metrics"

# Don't fail if the project hasn't been initialized; there's nothing to audit
if [[ ! -d "$PROJECT_DIR/.project" ]]; then
  [[ $QUIET -eq 0 ]] && echo "factory-aging: no .project/ in $PROJECT_DIR — skipping"
  exit 0
fi

now=$(date +%s)

# --------------------------------------------------------------------
# Read all experimental skills from the plugin
# --------------------------------------------------------------------
declare -a experimental_skills=()
declare -a active_skills=()

for skill_md in "$PLUGIN_ROOT/skills"/*/SKILL.md; do
  [[ -f "$skill_md" ]] || continue
  name=$(basename "$(dirname "$skill_md")")
  state=$(awk '/<!-- praxis:metadata:begin -->/,/<!-- praxis:metadata:end -->/' "$skill_md" 2>/dev/null \
            | grep -E "^state:" | head -1 | awk '{print $2}')
  case "$state" in
    experimental) experimental_skills+=("$name") ;;
    active|"")    active_skills+=("$name") ;;
  esac
done

# --------------------------------------------------------------------
# Helper: most recent telemetry file age in days for an artifact
# Returns "MISSING" if no files exist, otherwise integer days
# --------------------------------------------------------------------
age_days() {
  local artifact_type="$1"
  local artifact_name="$2"
  local dir="$METRICS_ROOT/${artifact_type}s/$artifact_name"

  if [[ ! -d "$dir" ]]; then
    echo "MISSING"
    return
  fi

  # Find newest file's mtime
  local newest_mtime
  newest_mtime=$(find "$dir" -type f -name '*.md' -exec stat -f %m {} \; 2>/dev/null \
                  | sort -nr | head -1)
  if [[ -z "$newest_mtime" ]]; then
    # Fallback for Linux stat
    newest_mtime=$(find "$dir" -type f -name '*.md' -exec stat -c %Y {} \; 2>/dev/null \
                    | sort -nr | head -1)
  fi

  if [[ -z "$newest_mtime" ]]; then
    echo "MISSING"
    return
  fi

  echo $(( (now - newest_mtime) / 86400 ))
}

# --------------------------------------------------------------------
# Check experimental skills (STRICT)
# --------------------------------------------------------------------
exit_code=0
strict_failures=()
warn_failures=()

for s in "${experimental_skills[@]}"; do
  age=$(age_days skill "$s")
  if [[ "$age" == "MISSING" ]]; then
    strict_failures+=("$s (no telemetry ever)")
  elif [[ "$age" -gt "$STRICT_WINDOW" ]]; then
    strict_failures+=("$s ($age days since last telemetry, > $STRICT_WINDOW)")
  fi
done

# --------------------------------------------------------------------
# Check active skills (WARN)
# --------------------------------------------------------------------
for s in "${active_skills[@]}"; do
  age=$(age_days skill "$s")
  if [[ "$age" == "MISSING" ]]; then
    warn_failures+=("$s (no telemetry ever)")
  elif [[ "$age" -gt "$WARN_WINDOW" ]]; then
    warn_failures+=("$s ($age days since last telemetry, > $WARN_WINDOW)")
  fi
done

# --------------------------------------------------------------------
# Report
# --------------------------------------------------------------------
if [[ ${#strict_failures[@]} -eq 0 && ${#warn_failures[@]} -eq 0 ]]; then
  [[ $QUIET -eq 0 ]] && echo "✓ Factory telemetry coverage OK (${#experimental_skills[@]} experimental, ${#active_skills[@]} active)"
  exit 0
fi

if [[ $QUIET -eq 1 && ${#strict_failures[@]} -eq 0 ]]; then
  exit 0
fi

echo "Praxis — factory telemetry aging report"
echo "========================================"
echo "  Project: $PROJECT_DIR"
echo "  Strict window: $STRICT_WINDOW days (experimental skills)"
echo "  Warn window:   $WARN_WINDOW days (active skills)"
echo ""

if [[ ${#strict_failures[@]} -gt 0 ]]; then
  echo "✗ FAIL — experimental skills with stale/missing telemetry:"
  for f in "${strict_failures[@]}"; do
    echo "  ✗ $f"
  done
  echo ""
  echo "  These skills are experimental and cannot be promoted without telemetry."
  echo "  Either: (a) use them and record observations, (b) demote to deprecated, or (c) remove."
  echo ""
  exit_code=1
fi

if [[ ${#warn_failures[@]} -gt 0 ]]; then
  echo "⚠ WARN — active skills with stale/missing telemetry:"
  for f in "${warn_failures[@]}"; do
    echo "  ⚠ $f"
  done
  echo ""
  echo "  These skills are active but unused or untracked. Steward should investigate"
  echo "  whether they're still needed, or whether the telemetry capture is broken."
  echo ""
  [[ $exit_code -eq 0 ]] && exit_code=2
fi

exit $exit_code
