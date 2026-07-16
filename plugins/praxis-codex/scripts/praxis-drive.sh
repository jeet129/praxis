#!/usr/bin/env bash
# praxis-drive.sh — the Ralph-style outer drive runner.
#
# Enforces, outside the agent's own context, everything the drive protocol
# (skills/autonomous-drive) is not allowed to enforce on itself: iteration
# caps, run budgets, stall detection, and the non-negotiable stop contract
# defined in governance/autonomy.yaml + references/loop-contracts.md.
#
# Usage:
#   scripts/praxis-drive.sh [--project-dir DIR] [--harness claude-code|codex|gemini-cli]
#                            [--slice ID] [--dry-run] [--max-iterations N]
#
# Defaults: --project-dir = cwd, --harness = claude-code.
#
# Exit codes:
#   0  natural stop (gate_reached / decision_required / queue drained / stop_after boundary)
#   2  no active ledger found and none named via --slice — nothing to drive
#   3  stalled (ledger hash unchanged for stall.max_iterations_without_ledger_change iterations)
#   4  run budget hit (max_iterations_per_run, cost_ceiling_proxy, or max_slices_per_run)
#   5  blocked / exhausted (a task hit max_task_attempts, or no eligible next task)
#
# --dry-run: does everything except invoke the harness (prints the command it
# would run instead). This is what CI exercises.

set -euo pipefail

# --------------------------------------------------------------------------
# Resolve the praxis library root (governance/*.yaml, references/*.md live
# here). Relative to this script by default; overridable for testing/vendoring.
# --------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRAXIS_ROOT="${PRAXIS_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

AUTONOMY_YAML="$PRAXIS_ROOT/governance/autonomy.yaml"
MODEL_ROUTING_YAML="$PRAXIS_ROOT/governance/model-routing.yaml"
# Project-level overrides win over the plugin-shipped defaults, so an
# engagement can tune stop_after / budgets / force_tier / cost_weights
# without editing the installed plugin (which updates would overwrite).
# Resolved after --project-dir parsing below.

# --------------------------------------------------------------------------
# Defaults + arg parsing
# --------------------------------------------------------------------------
PROJECT_DIR="$(pwd)"
HARNESS="claude-code"
SLICE_ID=""
DRY_RUN=0
MAX_ITERATIONS_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage: praxis-drive.sh [--project-dir DIR] [--harness claude-code|codex|gemini-cli]
                        [--slice ID] [--dry-run] [--max-iterations N]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)   PROJECT_DIR="$2"; shift 2 ;;
    --harness)       HARNESS="$2"; shift 2 ;;
    --slice)         SLICE_ID="$2"; shift 2 ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --max-iterations) MAX_ITERATIONS_OVERRIDE="$2"; shift 2 ;;
    -h|--help)       usage; exit 0 ;;
    *) echo "praxis-drive.sh: unknown argument: $1" >&2; usage >&2; exit 1 ;;
  esac
done

case "$HARNESS" in
  claude-code|codex|gemini-cli) ;;
  *) echo "praxis-drive.sh: unsupported --harness '$HARNESS' (want claude-code|codex|gemini-cli)" >&2; exit 1 ;;
esac

# Apply project-level overrides now that PROJECT_DIR is resolved.
if [[ -f "$PROJECT_DIR/.project/governance/autonomy.yaml" ]]; then
  AUTONOMY_YAML="$PROJECT_DIR/.project/governance/autonomy.yaml"
  echo "praxis-drive: using project override $AUTONOMY_YAML"
fi
if [[ -f "$PROJECT_DIR/.project/governance/model-routing.yaml" ]]; then
  MODEL_ROUTING_YAML="$PROJECT_DIR/.project/governance/model-routing.yaml"
  echo "praxis-drive: using project override $MODEL_ROUTING_YAML"
fi

if [[ ! -f "$AUTONOMY_YAML" ]]; then
  echo "praxis-drive.sh: missing governance/autonomy.yaml at $AUTONOMY_YAML (PRAXIS_ROOT=$PRAXIS_ROOT)" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"
mkdir -p "$PROJECT_DIR/.project/telemetry" 2>/dev/null || {
  echo "praxis-drive.sh: cannot create $PROJECT_DIR/.project/telemetry" >&2
  exit 1
}
DRIVE_JSONL="$PROJECT_DIR/.project/telemetry/drive.jsonl"

# --------------------------------------------------------------------------
# Embedded python3 helper (written once to a tempfile, invoked per-subcommand).
# Keeps the outer loop in bash; strict-subset YAML parsing lives here rather
# than pulling in pyyaml.
# --------------------------------------------------------------------------
PY_HELPER="$(mktemp -t praxis-drive-helper.XXXXXX.py)"
cleanup() { rm -f "$PY_HELPER"; }
trap cleanup EXIT

cat > "$PY_HELPER" <<'PYEOF'
import json
import re
import shlex
import sys
from pathlib import Path

VALID_TIERS = ("deep", "standard", "light")


def sh(name, value):
    print(f"{name}={shlex.quote(str(value))}")


def parse_scalar_block(path, indent_zero_only=True):
    """Generic tolerant parser for the 2-level nested structure shared by
    autonomy.yaml and model-routing.yaml: top-level key -> (scalar | nested
    map at indent+2, one level deep, occasionally two)."""
    tree = {}
    stack = [(0, tree)]
    for raw in Path(path).read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip("\n")
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()
        while stack and indent < stack[-1][0]:
            stack.pop()
        # If indent matches the current frame, add to it; if deeper, the
        # previous key must become a dict we can descend into.
        parent_indent, parent = stack[-1]
        if indent > parent_indent and not stack[-1][1]:
            pass
        parent[key] = val if val else {}
        if not val:
            stack.append((indent + 2, parent[key]))
    return tree


def cmd_autonomy(autonomy_path, model_routing_path, harness):
    tree = parse_scalar_block(autonomy_path)

    stop_after = tree.get("stop_after", "gate")
    if isinstance(stop_after, dict):
        stop_after = "gate"

    run_budget = tree.get("run_budget", {}) or {}
    stall = tree.get("stall", {}) or {}
    harnesses = tree.get("harnesses", {}) or {}
    summaries = tree.get("summaries", {}) or {}

    h = harnesses.get(harness, {}) or {}
    harness_command = h.get("command", "")
    harness_budget_flag = h.get("budget_flag", "null") or "null"
    if isinstance(harness_command, dict):
        harness_command = ""

    gov = {"cost_weights": {}}
    mr_path = Path(model_routing_path)
    if mr_path.exists():
        mr_tree = parse_scalar_block(mr_path)
        cw = mr_tree.get("cost_weights", {}) or {}
        for tier in VALID_TIERS:
            if tier in cw:
                gov["cost_weights"][tier] = cw[tier]

    sh("STOP_AFTER", stop_after)
    sh("MAX_SLICES_PER_RUN", run_budget.get("max_slices_per_run", 3))
    sh("MAX_ITERATIONS_PER_RUN", run_budget.get("max_iterations_per_run", 40))
    sh("MAX_TASK_ATTEMPTS", run_budget.get("max_task_attempts", 3))
    sh("COST_CEILING_PROXY", run_budget.get("cost_ceiling_proxy", 120))
    sh("MAX_BUDGET_USD", run_budget.get("max_budget_usd", "null") or "null")
    sh("STALL_MAX_NO_CHANGE", stall.get("max_iterations_without_ledger_change", 2))
    sh("HARNESS_COMMAND", harness_command)
    sh("HARNESS_BUDGET_FLAG", harness_budget_flag)
    sh("COST_WEIGHT_DEEP", gov["cost_weights"].get("deep", 5.0))
    sh("COST_WEIGHT_STANDARD", gov["cost_weights"].get("standard", 1.0))
    sh("COST_WEIGHT_LIGHT", gov["cost_weights"].get("light", 0.25))
    sh("SUMMARIES_SLICE_CLOSE_DIR", summaries.get("slice_close", ".project/telemetry/summaries/"))
    sh("SUMMARIES_NOTIFY", summaries.get("notify", "terminal"))
    # Optional per-harness real-usage-capture keys. Not required in
    # governance/autonomy.yaml — when absent, claude-code gets a documented
    # default (see below in the bash driver); other harnesses stay opt-in.
    sh("HARNESS_JSON_OUTPUT_FLAG", h.get("json_output_flag", "null") or "null")
    sh("HARNESS_USAGE_PARSE", h.get("usage_parse", "null") or "null")


def parse_inline_list(val):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [x.strip() for x in inner.split(",") if x.strip()]
    return []


def parse_tasks_block(block_lines):
    tasks = []
    cur = None
    for raw in block_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        m = re.match(r"^-\s*id:\s*(.+)$", stripped)
        if m:
            if cur is not None:
                tasks.append(cur)
            cur = {"id": m.group(1).strip()}
            continue
        m2 = re.match(r"^([A-Za-z_]+):\s*(.*)$", stripped)
        if m2 and cur is not None:
            key, val = m2.group(1), m2.group(2).strip()
            if key in ("depends_on",) and val.startswith("["):
                cur[key] = parse_inline_list(val)
            else:
                cur[key] = val
    if cur is not None:
        tasks.append(cur)
    return tasks


def parse_ledger(path):
    lines = Path(path).read_text().splitlines()
    top = {}
    tasks = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent != 0:
            i += 1
            continue
        stripped = line.strip()
        if ":" not in stripped:
            i += 1
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip()

        if key == "tasks":
            i += 1
            block = []
            while i < n and (not lines[i].strip() or (len(lines[i]) - len(lines[i].lstrip(" "))) > 0):
                block.append(lines[i])
                i += 1
            tasks = parse_tasks_block(block)
            continue

        if key == "stop_flags":
            if val.startswith("["):
                top["stop_flags"] = parse_inline_list(val)
                i += 1
            else:
                flags = []
                i += 1
                while i < n and lines[i].strip().startswith("-"):
                    flags.append(lines[i].strip().lstrip("-").strip())
                    i += 1
                top["stop_flags"] = flags
            continue

        if key == "gates":
            i += 1
            while i < n and (not lines[i].strip() or (len(lines[i]) - len(lines[i].lstrip(" "))) > 0):
                i += 1
            continue

        top[key] = val
        i += 1

    return top, tasks


def cmd_ledger(ledger_path, task_id_filter=None):
    top, tasks = parse_ledger(ledger_path)

    state = top.get("state", "open")
    slice_id = top.get("slice", "unknown")
    stop_flags = top.get("stop_flags", [])
    if isinstance(stop_flags, str):
        stop_flags = [stop_flags] if stop_flags else []

    done = sum(1 for t in tasks if t.get("status") == "done")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    total = len(tasks)
    done_ids = {t["id"] for t in tasks if t.get("status") == "done"}
    open_tasks = [t for t in tasks if t.get("status") == "open"]

    next_task = None
    for t in open_tasks:
        deps = t.get("depends_on", [])
        if isinstance(deps, str):
            deps = parse_inline_list(deps) if deps.startswith("[") else ([deps] if deps else [])
        if all(d in done_ids for d in deps):
            next_task = t
            break

    open_count = len(open_tasks)

    sh("LEDGER_STATE", state)
    sh("LEDGER_SLICE", slice_id)
    sh("LEDGER_STOP_FLAGS", ",".join(stop_flags))
    sh("DONE_COUNT", done)
    sh("FAILED_COUNT", failed)
    sh("TOTAL_COUNT", total)
    sh("OPEN_COUNT", open_count)
    sh("NEXT_TASK_ID", next_task.get("id", "") if next_task else "")
    sh("NEXT_TASK_AGENT", next_task.get("agent", "") if next_task else "")
    sh("NEXT_TASK_TIER", next_task.get("tier", "standard") if next_task else "")
    sh("NEXT_TASK_ATTEMPTS", next_task.get("attempts", "0") if next_task else "0")

    if task_id_filter:
        match = next((t for t in tasks if t.get("id") == task_id_filter), None)
        sh("QUERIED_TASK_STATUS", match.get("status", "") if match else "")
        sh("QUERIED_TASK_ATTEMPTS", match.get("attempts", "") if match else "")


def _num_or_null(s):
    """Parse a shell-passed 'null' | int | float string into a Python number or None."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "" or s.lower() == "null":
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def cmd_append_record(jsonl_path, ts, run_id, iteration, slice_id, task_id, agent, tier, outcome, ledger_hash, stop_flags_csv, cost_proxy,
                       input_tokens="null", output_tokens="null", cache_read_input_tokens="null",
                       cache_creation_input_tokens="null", total_cost_usd="null"):
    flags = [f for f in stop_flags_csv.split(",") if f]
    record = {
        "ts": ts,
        "run_id": run_id,
        "iteration": int(iteration),
        "slice": slice_id,
        "task": task_id,
        "agent": agent,
        "tier": tier,
        "outcome": outcome,
        "ledger_hash": ledger_hash,
        "stop_flags": flags,
        "cost_proxy": float(cost_proxy),
        # Real usage, when the harness invocation exposed it (see cmd_parse_usage).
        # null, never a guessed value, when unavailable (--dry-run, non-JSON
        # harness output, or a parse failure — fail-soft by design).
        "input_tokens": _num_or_null(input_tokens),
        "output_tokens": _num_or_null(output_tokens),
        "cache_read_input_tokens": _num_or_null(cache_read_input_tokens),
        "cache_creation_input_tokens": _num_or_null(cache_creation_input_tokens),
        "total_cost_usd": _num_or_null(total_cost_usd),
    }
    with open(jsonl_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def _extract_claude_json_usage(text):
    """Tolerant extraction of usage/cost fields from `claude -p --output-format
    json` stdout. Handles the plain single-JSON-object shape and, defensively,
    a line-delimited/stream-json shape (multiple JSON objects, one per line) —
    picks the last object that looks like a final result record (carries
    `usage` or `total_cost_usd`, or `type: result`). Returns a dict of
    possibly-None values; never raises (caller is already inside a try/except,
    but this is written to be safe to call directly too)."""
    text = (text or "").strip()
    if not text:
        return None
    candidates = []
    try:
        obj = json.loads(text)
        candidates.append(obj)
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    result_obj = None
    for c in reversed(candidates):
        if isinstance(c, dict) and (
            "usage" in c or "total_cost_usd" in c or "cost_usd" in c or c.get("type") == "result"
        ):
            result_obj = c
            break
    if result_obj is None:
        for c in reversed(candidates):
            if isinstance(c, dict):
                result_obj = c
                break
    if result_obj is None:
        return None

    usage = result_obj.get("usage")
    if not isinstance(usage, dict):
        usage = {}

    def _pick(d, *keys):
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return v
        return None

    return {
        "input_tokens": _pick(usage, "input_tokens"),
        "output_tokens": _pick(usage, "output_tokens"),
        "cache_read_input_tokens": _pick(usage, "cache_read_input_tokens"),
        "cache_creation_input_tokens": _pick(usage, "cache_creation_input_tokens"),
        "total_cost_usd": _pick(result_obj, "total_cost_usd", "cost_usd"),
    }


def cmd_parse_usage(stdout_path, usage_parse):
    """Fail-soft usage extraction: emits USAGE_* shell vars, always — 'null'
    on any parse problem, missing file, empty output, or unsupported
    usage_parse strategy. Never raises past this function."""
    fields = ("input_tokens", "output_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens", "total_cost_usd")
    values = {f: None for f in fields}
    try:
        if usage_parse == "claude-json":
            text = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
            parsed = _extract_claude_json_usage(text)
            if parsed:
                values.update(parsed)
        # Unknown/other usage_parse strategies: leave everything null — this
        # is the documented "tolerant of shape variations and missing
        # fields" contract, not an error.
    except Exception:
        values = {f: None for f in fields}
    for f in fields:
        sh(f"USAGE_{f.upper()}", "null" if values[f] is None else values[f])


def main():
    action = sys.argv[1]
    if action == "autonomy":
        cmd_autonomy(sys.argv[2], sys.argv[3], sys.argv[4])
    elif action == "ledger":
        task_filter = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_ledger(sys.argv[2], task_filter)
    elif action == "append_record":
        cmd_append_record(*sys.argv[2:19])
    elif action == "parse_usage":
        cmd_parse_usage(sys.argv[2], sys.argv[3])
    else:
        print(f"unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF

# --------------------------------------------------------------------------
# Load autonomy config (fail-safe: bad/missing config is a hard stop, not a
# silent default-everything).
# --------------------------------------------------------------------------
if ! AUTONOMY_ENV="$(python3 "$PY_HELPER" autonomy "$AUTONOMY_YAML" "$MODEL_ROUTING_YAML" "$HARNESS")"; then
  echo "praxis-drive.sh: failed to parse $AUTONOMY_YAML" >&2
  exit 1
fi
eval "$AUTONOMY_ENV"

if [[ -z "${HARNESS_COMMAND:-}" ]]; then
  echo "praxis-drive.sh: no harnesses.$HARNESS.command found in $AUTONOMY_YAML" >&2
  exit 1
fi

if [[ -n "$MAX_ITERATIONS_OVERRIDE" ]]; then
  MAX_ITERATIONS_PER_RUN="$MAX_ITERATIONS_OVERRIDE"
fi

# --------------------------------------------------------------------------
# Real-usage capture: which flag (if any) gets appended to the harness
# command to request machine-readable output, and how to parse it.
# Both keys are read from governance/autonomy.yaml harnesses.<harness>.* if
# present (json_output_flag, usage_parse); governance/autonomy.yaml itself is
# not owned/edited here. claude-code gets a built-in default when the
# project's harness command doesn't already request a --output-format:
# `claude -p "{prompt}" --max-turns 30` becomes ...--max-turns 30 --output-format json,
# and usage_parse defaults to "claude-json" (the `claude -p --output-format
# json` result-object shape: top-level `usage` + `total_cost_usd`).
# --------------------------------------------------------------------------
JSON_OUTPUT_FLAG="$HARNESS_JSON_OUTPUT_FLAG"
USAGE_PARSE="$HARNESS_USAGE_PARSE"
if [[ "$HARNESS" == "claude-code" ]]; then
  if [[ "$JSON_OUTPUT_FLAG" == "null" && "$HARNESS_COMMAND" != *"--output-format"* ]]; then
    JSON_OUTPUT_FLAG="--output-format json"
  fi
  if [[ "$USAGE_PARSE" == "null" ]]; then
    USAGE_PARSE="claude-json"
  fi
fi

# --------------------------------------------------------------------------
# Locate the active ledger
# --------------------------------------------------------------------------
find_ledger() {
  if [[ -n "$SLICE_ID" ]]; then
    local candidate="$PROJECT_DIR/.project/working/slice-${SLICE_ID}-tasks.yaml"
    [[ -f "$candidate" ]] && { echo "$candidate"; return 0; }
    return 1
  fi
  local newest="" newest_mtime=-1
  shopt -s nullglob
  for f in "$PROJECT_DIR"/.project/working/slice-*-tasks.yaml; do
    [[ -f "$f" ]] || continue
    local state
    state="$(awk -F': *' '/^state:/{print $2; exit}' "$f" | tr -d '[:space:]')"
    [[ "$state" == "closed" ]] && continue
    local mtime
    mtime="$(stat -f %m "$f" 2>/dev/null)"
    if [[ ! "$mtime" =~ ^[0-9]+$ ]]; then
      mtime="$(stat -c %Y "$f" 2>/dev/null)"
    fi
    [[ "$mtime" =~ ^[0-9]+$ ]] || mtime=0
    if (( mtime > newest_mtime )); then
      newest_mtime=$mtime
      newest="$f"
    fi
  done
  shopt -u nullglob
  [[ -n "$newest" ]] && { echo "$newest"; return 0; }
  return 1
}

hash_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

RUN_ID="drive-$(date -u +%Y%m%d-%H%M%S)"
ITERATION=0
STALL_COUNT=0
SLICES_CLOSED=0
COST_ACCUM=0
COST_USD_ACCUM=0
HAVE_COST_USD_DATA=0
LAST_DONE_COUNT=0
LAST_FAILED_COUNT=0
LAST_TOTAL_COUNT=0
LAST_SLICE="unknown"
STOP_REASON=""
EXIT_CODE=0
HAD_ANY_ITERATION=0

while true; do
  ITERATION=$((ITERATION + 1))

  if (( ITERATION > MAX_ITERATIONS_PER_RUN )); then
    ITERATION=$((ITERATION - 1))   # this iteration never ran; report only completed ones
    STOP_REASON="budget: max_iterations_per_run ($MAX_ITERATIONS_PER_RUN) reached"
    EXIT_CODE=4
    break
  fi

  if ! LEDGER_PATH="$(find_ledger)"; then
    if (( HAD_ANY_ITERATION == 0 )); then
      echo "praxis-drive.sh: no active task ledger found under $PROJECT_DIR/.project/working/"
      echo "Run /slice to open one (or pass --slice ID if a specific ledger should exist)."
      exit 2
    else
      STOP_REASON="queue drained (no further open slice ledgers)"
      EXIT_CODE=0
      break
    fi
  fi

  HASH_BEFORE="$(hash_of "$LEDGER_PATH")"

  if ! LEDGER_ENV="$(python3 "$PY_HELPER" ledger "$LEDGER_PATH")"; then
    echo "praxis-drive.sh: failed to parse ledger $LEDGER_PATH" >&2
    STOP_REASON="blocked: ledger $LEDGER_PATH failed to parse"
    EXIT_CODE=5
    break
  fi
  eval "$LEDGER_ENV"
  LAST_DONE_COUNT=$DONE_COUNT
  LAST_FAILED_COUNT=$FAILED_COUNT
  LAST_TOTAL_COUNT=$TOTAL_COUNT
  LAST_SLICE=$LEDGER_SLICE

  if [[ -n "$LEDGER_STOP_FLAGS" ]]; then
    STOP_REASON="stop_flags present before iteration: $LEDGER_STOP_FLAGS"
    case ",$LEDGER_STOP_FLAGS," in
      *,stalled,*)         EXIT_CODE=3 ;;
      *,budget_exceeded,*) EXIT_CODE=4 ;;
      *,blocked,*)         EXIT_CODE=5 ;;
      *)                   EXIT_CODE=0 ;;
    esac
    break
  fi

  if [[ -z "$NEXT_TASK_ID" ]]; then
    if [[ "$LEDGER_STATE" == "closed" || "$OPEN_COUNT" == "0" ]]; then
      STOP_REASON="queue drained (no open tasks remain in $LEDGER_PATH)"
      EXIT_CODE=0
    else
      STOP_REASON="blocked: no drive-eligible task in $LEDGER_PATH (dependencies unmet, or all remaining tasks exhausted)"
      EXIT_CODE=5
    fi
    break
  fi

  HAD_ANY_ITERATION=1
  PROCESSED_TASK_ID="$NEXT_TASK_ID"
  PROCESSED_TASK_AGENT="$NEXT_TASK_AGENT"
  PROCESSED_TASK_TIER="$NEXT_TASK_TIER"

  PROMPT="You are the Praxis Delivery Lead operating under the drive protocol (skills/autonomous-drive). Read the task ledger at ${LEDGER_PATH} and .project/working/workflow-state.yaml. Execute exactly ONE drive iteration per the protocol: take the next open task (dependencies done), complete it, run its verify command, update the ledger status/attempts, set stop_flags honestly. Do not wait for user input."

  CMD="${HARNESS_COMMAND//\{prompt\}/$PROMPT}"
  if [[ "$MAX_BUDGET_USD" != "null" && "$HARNESS_BUDGET_FLAG" != "null" ]]; then
    CMD="$CMD $HARNESS_BUDGET_FLAG $MAX_BUDGET_USD"
  fi
  if [[ -n "$JSON_OUTPUT_FLAG" && "$JSON_OUTPUT_FLAG" != "null" ]]; then
    CMD="$CMD $JSON_OUTPUT_FLAG"
  fi

  # Usage/cost fields default to null; only overwritten below when the
  # harness actually ran and produced parseable JSON (fail-soft: --dry-run,
  # a non-JSON harness, or a parse error all leave these null, never break
  # the loop).
  USAGE_INPUT_TOKENS="null"
  USAGE_OUTPUT_TOKENS="null"
  USAGE_CACHE_READ_INPUT_TOKENS="null"
  USAGE_CACHE_CREATION_INPUT_TOKENS="null"
  USAGE_TOTAL_COST_USD="null"

  if (( DRY_RUN == 1 )); then
    echo "[dry-run] iteration $ITERATION — would invoke: $CMD"
  else
    ITER_STDOUT="$(mktemp -t praxis-drive-iter-stdout.XXXXXX)"
    if ! ( cd "$PROJECT_DIR" && eval "$CMD" > "$ITER_STDOUT" ); then
      echo "praxis-drive.sh: harness invocation exited non-zero on iteration $ITERATION" >&2
    fi
    cat "$ITER_STDOUT"
    if USAGE_ENV="$(python3 "$PY_HELPER" parse_usage "$ITER_STDOUT" "$USAGE_PARSE")"; then
      eval "$USAGE_ENV"
    else
      echo "praxis-drive.sh: usage parse failed on iteration $ITERATION (non-fatal — recording nulls)" >&2
    fi
    rm -f "$ITER_STDOUT"
    if [[ "$USAGE_TOTAL_COST_USD" != "null" ]]; then
      COST_USD_ACCUM="$(awk "BEGIN{printf \"%.6f\", $COST_USD_ACCUM + $USAGE_TOTAL_COST_USD}")"
      HAVE_COST_USD_DATA=1
    fi
  fi

  HASH_AFTER="$(hash_of "$LEDGER_PATH")"
  if ! LEDGER_ENV="$(python3 "$PY_HELPER" ledger "$LEDGER_PATH" "$PROCESSED_TASK_ID")"; then
    echo "praxis-drive.sh: failed to parse ledger $LEDGER_PATH after iteration $ITERATION" >&2
    STOP_REASON="blocked: ledger $LEDGER_PATH failed to parse after iteration $ITERATION"
    EXIT_CODE=5
    break
  fi
  eval "$LEDGER_ENV"
  LAST_DONE_COUNT=$DONE_COUNT
  LAST_FAILED_COUNT=$FAILED_COUNT
  LAST_TOTAL_COUNT=$TOTAL_COUNT
  LAST_SLICE=$LEDGER_SLICE

  if [[ "$HASH_AFTER" == "$HASH_BEFORE" ]]; then
    STALL_COUNT=$((STALL_COUNT + 1))
  else
    STALL_COUNT=0
  fi

  case "$PROCESSED_TASK_TIER" in
    deep)     WEIGHT="$COST_WEIGHT_DEEP" ;;
    light)    WEIGHT="$COST_WEIGHT_LIGHT" ;;
    *)        WEIGHT="$COST_WEIGHT_STANDARD" ;;
  esac
  COST_ACCUM="$(awk "BEGIN{printf \"%.4f\", $COST_ACCUM + $WEIGHT}")"

  OUTCOME="${QUERIED_TASK_STATUS:-unknown}"
  [[ -z "$OUTCOME" ]] && OUTCOME="unknown"

  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 "$PY_HELPER" append_record "$DRIVE_JSONL" "$TS" "$RUN_ID" "$ITERATION" "$LEDGER_SLICE" "$PROCESSED_TASK_ID" "$PROCESSED_TASK_AGENT" "$PROCESSED_TASK_TIER" "$OUTCOME" "$HASH_AFTER" "$LEDGER_STOP_FLAGS" "$WEIGHT" \
    "$USAGE_INPUT_TOKENS" "$USAGE_OUTPUT_TOKENS" "$USAGE_CACHE_READ_INPUT_TOKENS" "$USAGE_CACHE_CREATION_INPUT_TOKENS" "$USAGE_TOTAL_COST_USD"

  # ---- Always-on stop checks (fire regardless of stop_after) ----
  if [[ -n "$LEDGER_STOP_FLAGS" ]]; then
    STOP_REASON="stop_flags raised: $LEDGER_STOP_FLAGS"
    case ",$LEDGER_STOP_FLAGS," in
      *,stalled,*)         EXIT_CODE=3 ;;
      *,budget_exceeded,*) EXIT_CODE=4 ;;
      *,blocked,*)         EXIT_CODE=5 ;;
      *)                   EXIT_CODE=0 ;;
    esac
    break
  fi

  if (( STALL_COUNT >= STALL_MAX_NO_CHANGE )); then
    STOP_REASON="stalled: ledger hash unchanged for $STALL_COUNT consecutive iterations (cap: $STALL_MAX_NO_CHANGE)"
    EXIT_CODE=3
    break
  fi

  if [[ "$LEDGER_STATE" == "closed" ]]; then
    SLICES_CLOSED=$((SLICES_CLOSED + 1))
    if (( SLICES_CLOSED >= MAX_SLICES_PER_RUN )); then
      STOP_REASON="budget: max_slices_per_run ($MAX_SLICES_PER_RUN) reached at slice close"
      EXIT_CODE=4
      break
    fi
    if [[ "$STOP_AFTER" == "slice" ]]; then
      STOP_REASON="slice closed ($LEDGER_SLICE) — stop_after=slice"
      EXIT_CODE=0
      break
    fi
    # phase/gate: fall through to keep driving into the next ledger.
  fi

  if awk "BEGIN{exit !($COST_ACCUM > $COST_CEILING_PROXY)}"; then
    STOP_REASON="budget: cost_ceiling_proxy ($COST_CEILING_PROXY) exceeded (accrued $COST_ACCUM)"
    EXIT_CODE=4
    break
  fi

  if [[ "$STOP_AFTER" == "task" ]]; then
    STOP_REASON="stop_after=task boundary (one task per iteration)"
    EXIT_CODE=0
    break
  fi

  # stop_after in {phase, gate}: rely on stop_flags/budget/stall only — keep looping.
done

# --------------------------------------------------------------------------
# Human summary
# --------------------------------------------------------------------------
REMAINING=$(( LAST_TOTAL_COUNT - LAST_DONE_COUNT - LAST_FAILED_COUNT ))
(( REMAINING < 0 )) && REMAINING=0

echo ""
echo "praxis-drive — run $RUN_ID stopped"
echo "=================================="
echo "  reason:            $STOP_REASON"
echo "  iterations run:    $ITERATION"
echo "  last slice:        $LAST_SLICE"
echo "  tasks done/failed/remaining (last ledger read): $LAST_DONE_COUNT/$LAST_FAILED_COUNT/$REMAINING"
echo "  slices closed:     $SLICES_CLOSED"
echo "  cost proxy consumed: $COST_ACCUM (ceiling: $COST_CEILING_PROXY)"
if (( HAVE_COST_USD_DATA == 1 )); then
  echo "  real cost (sum of harness total_cost_usd): \$$COST_USD_ACCUM"
else
  echo "  real cost: n/a (harness did not report total_cost_usd this run)"
fi
echo "  slice-close summaries: $PROJECT_DIR/$SUMMARIES_SLICE_CLOSE_DIR"
echo "  telemetry:          $DRIVE_JSONL"
echo "  exit code:          $EXIT_CODE"

exit $EXIT_CODE
