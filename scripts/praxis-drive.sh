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
#                            [--slice ID] [--dry-run] [--max-iterations N] [--workflow]
#
# Defaults: --project-dir = cwd, --harness = claude-code.
#
# Exit codes:
#   0  natural stop (gate_reached / decision_required / queue drained / stop_after boundary)
#   2  no active ledger found and none named via --slice — nothing to drive
#   3  stalled (ledger hash unchanged for stall.max_iterations_without_ledger_change iterations)
#   4  run budget hit (max_iterations_per_run, cost_ceiling_proxy, or max_slices_per_run/max_steps_per_run)
#   5  blocked / exhausted (a task hit max_task_attempts, or no eligible next task)
#
# --dry-run: does everything except invoke the harness (prints the command it
# would run instead). This is what CI exercises.
#
# --workflow: opt-in top-level loop (references/phase-gates.md). Reads
# .project/working/workflow-state.yaml as a step ledger instead of a slice
# task ledger, and loops over workflow STEPS rather than tasks. Default OFF —
# without this flag the script is the unchanged slice-drive runner above.

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
WORKFLOW_MODE=0

usage() {
  cat <<'EOF'
Usage: praxis-drive.sh [--project-dir DIR] [--harness claude-code|codex|gemini-cli]
                        [--slice ID] [--dry-run] [--max-iterations N] [--workflow]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)   PROJECT_DIR="$2"; shift 2 ;;
    --harness)       HARNESS="$2"; shift 2 ;;
    --slice)         SLICE_ID="$2"; shift 2 ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --max-iterations) MAX_ITERATIONS_OVERRIDE="$2"; shift 2 ;;
    --workflow)      WORKFLOW_MODE=1; shift ;;
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

    gov = {"cost_weights": {}, "tier_models": {}, "tier_efforts": {}, "force_tier": "null"}
    mr_path = Path(model_routing_path)
    if mr_path.exists():
        mr_tree = parse_scalar_block(mr_path)
        # overrides.force_tier: a governance pin that forces EVERY iteration to
        # one tier (e.g. a compliance engagement mandating deep everywhere). The
        # no-drive resolver honors this too — parity depends on the runner
        # applying it, not just the static agent frontmatter.
        _ov = mr_tree.get("overrides", {}) or {}
        _ft = _ov.get("force_tier", "null")
        if isinstance(_ft, dict) or _ft in ("", "~", None):
            _ft = "null"
        gov["force_tier"] = _ft
        cw = mr_tree.get("cost_weights", {}) or {}
        for tier in VALID_TIERS:
            if tier in cw:
                gov["cost_weights"][tier] = cw[tier]
        # tier -> concrete model AND reasoning effort for THIS harness (routes
        # the router: each drive iteration runs on the model+effort its task
        # tier resolves to). A harness declares up to three (field-name -> tier
        # map) pairs, and its PRIMARY `field`/`map` differs by harness:
        # claude-code's primary field is `model`, but codex's primary field is
        # `model_reasoning_effort`. So we must resolve the two axes by the
        # FIELD NAME, not by assuming `map` is always the model map — otherwise
        # codex's effort values (high/medium/low) get mislabeled as models and
        # nothing actually routes. Rule:
        #   MODEL axis  = the map whose field is named `model`
        #   EFFORT axis = the map whose field is a reasoning-effort field
        #                 (`effort` or `model_reasoning_effort`)
        # `auto` means "omit — let the harness default", so it's skipped here.
        mr_harnesses = mr_tree.get("harnesses", {}) or {}
        mh = mr_harnesses.get(harness, {}) or {}
        axis_maps = []  # list of (field_name, tier_map)
        for fkey, mkey in (("field", "map"),
                           ("effort_field", "effort_map"),
                           ("model_field", "model_map")):
            fname = mh.get(fkey)
            tmap = mh.get(mkey, {}) or {}
            if isinstance(fname, str) and fname and isinstance(tmap, dict):
                axis_maps.append((fname, tmap))

        def _pick_axis(pred):
            for fname, tmap in axis_maps:
                if pred(fname):
                    return tmap
            return {}

        model_map = _pick_axis(lambda f: f == "model")
        effort_map = _pick_axis(lambda f: "effort" in f)
        for tier in VALID_TIERS:
            v = model_map.get(tier)
            if isinstance(v, str) and v and v != "auto":
                gov["tier_models"][tier] = v
        for tier in VALID_TIERS:
            v = effort_map.get(tier)
            if isinstance(v, str) and v and v != "auto":
                gov["tier_efforts"][tier] = v

    sh("STOP_AFTER", stop_after)
    sh("MAX_SLICES_PER_RUN", run_budget.get("max_slices_per_run", 3))
    # workflow-drive's step-per-run cap; defaults to max_slices_per_run when
    # the project hasn't set it explicitly (same run-budget "altitude").
    sh("MAX_STEPS_PER_RUN", run_budget.get("max_steps_per_run", run_budget.get("max_slices_per_run", 3)))
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
    # Per-iteration model selection: the flag the harness accepts (--model
    # for claude, -m for gemini; codex has no per-call flag -> null) and the
    # tier->model map from governance/model-routing.yaml for this harness.
    sh("HARNESS_MODEL_FLAG", h.get("model_flag", "null") or "null")
    sh("FORCE_TIER", gov.get("force_tier", "null"))
    sh("TIER_MODEL_DEEP", gov["tier_models"].get("deep", "null"))
    sh("TIER_MODEL_STANDARD", gov["tier_models"].get("standard", "null"))
    sh("TIER_MODEL_LIGHT", gov["tier_models"].get("light", "null"))
    # Per-iteration reasoning-effort selection (claude-code only today): the
    # flag the harness accepts (--effort, from governance/autonomy.yaml
    # harnesses.<harness>.effort_flag) and the tier->effort map from
    # governance/model-routing.yaml's claude-code.effort_map. Additive,
    # mirrors the model machinery above; both are "null" on harnesses that
    # don't declare them (codex/gemini-cli), same fail-soft convention.
    sh("HARNESS_EFFORT_FLAG", h.get("effort_flag", "null") or "null")
    # Some harnesses pass reasoning effort as a config token, not a bare value
    # (codex: `-c model_reasoning_effort=high`, so effort_flag=`-c` and this
    # prefix=`model_reasoning_effort=`). Empty for harnesses whose effort_flag
    # takes the value directly (claude-code: `--effort high`).
    sh("HARNESS_EFFORT_ARG_PREFIX", h.get("effort_arg_prefix", "") or "")
    sh("TIER_EFFORT_DEEP", gov["tier_efforts"].get("deep", "null"))
    sh("TIER_EFFORT_STANDARD", gov["tier_efforts"].get("standard", "null"))
    sh("TIER_EFFORT_LIGHT", gov["tier_efforts"].get("light", "null"))


def parse_inline_list(val):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [x.strip() for x in inner.split(",") if x.strip()]
    return []


def parse_inline_dict(val):
    """Tolerant parser for the single-line {key: value, key2: "quoted: value"}
    shape used by workflow-state.yaml's `exit.args`. Splits on commas that
    are not inside quotes, then each part on the FIRST colon (so a quoted
    value that itself contains a colon, e.g. must_contain: "VERDICT:
    SATISFIED", survives intact)."""
    val = val.strip()
    if not (val.startswith("{") and val.endswith("}")):
        return {}
    inner = val[1:-1].strip()
    if not inner:
        return {}
    parts = []
    cur = ""
    in_quote = None
    for ch in inner:
        if in_quote:
            cur += ch
            if ch == in_quote:
                in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            cur += ch
            continue
        if ch == ",":
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur)
    d = {}
    for p in parts:
        if ":" not in p:
            continue
        k, _, v = p.partition(":")
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
            v = v[1:-1]
        d[k] = v
    return d


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

    VALID_STATUSES = {"open", "in_progress", "done", "failed", "blocked"}
    unknown_status = [f"{t.get('id','?')}={t.get('status')}" for t in tasks
                      if t.get("status") not in VALID_STATUSES]

    done = sum(1 for t in tasks if t.get("status") == "done")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    total = len(tasks)
    done_ids = {t["id"] for t in tasks if t.get("status") == "done"}
    # Drive-eligible = open AND has a runnable verify command; open tasks
    # without verify are interactive-only (loop-contracts rule) — skipped by
    # the runner and surfaced at drain, never silently ignored.
    all_open = [t for t in tasks if t.get("status") == "open"]
    open_tasks = [t for t in all_open if str(t.get("verify") or "").strip() not in ("", "null", "None", "~")]
    interactive_only = [t.get("id", "?") for t in all_open if t not in open_tasks]

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
    sh("UNKNOWN_STATUS_TASKS", ",".join(unknown_status))
    sh("INTERACTIVE_ONLY_TASKS", ",".join(interactive_only))
    sh("NEXT_TASK_ID", next_task.get("id", "") if next_task else "")
    sh("NEXT_TASK_AGENT", next_task.get("agent", "") if next_task else "")
    sh("NEXT_TASK_TIER", next_task.get("tier", "standard") if next_task else "")
    sh("NEXT_TASK_ATTEMPTS", next_task.get("attempts", "0") if next_task else "0")

    if task_id_filter:
        match = next((t for t in tasks if t.get("id") == task_id_filter), None)
        sh("QUERIED_TASK_STATUS", match.get("status", "") if match else "")
        sh("QUERIED_TASK_ATTEMPTS", match.get("attempts", "") if match else "")


def parse_steps_block(block_lines):
    """Tolerant parser for workflow-state.yaml's `steps:` block
    (references/phase-gates.md §3). Each step is a `- id: ...` list item;
    fields are flat scalars/inline-lists EXCEPT `exit:`, which nests one
    level (name, check, args {..}, on_fail, fallback_gate). Indentation is
    detected relative to the `- id:` line rather than hard-coded, so 2- or
    4-space step blocks both parse."""
    steps = []
    cur = None
    field_indent = None      # indent of a step's own fields (dash_indent + 2)
    in_exit = False          # inside the `exit:` sub-block (indent == field_indent + 2)
    in_args = False          # inside a block-form `args:` under exit (indent == field_indent + 4)
    for raw in block_lines:
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        m = re.match(r"^-\s*id:\s*(.+)$", stripped)
        if m:
            if cur is not None:
                steps.append(cur)
            cur = {"id": m.group(1).strip(), "exit": {}}
            field_indent = indent + 2
            in_exit = False
            in_args = False
            continue

        if cur is None:
            continue

        # Leaving nested scopes when indentation returns to a shallower level.
        if in_args and indent <= field_indent + 2:
            in_args = False
        if in_exit and indent <= field_indent:
            in_exit = False

        m2 = re.match(r"^([A-Za-z_]+):\s*(.*)$", stripped)
        if not m2:
            continue
        key, val = m2.group(1), m2.group(2).strip()

        # --- inside exit.args (block form): args children ---
        if in_args and indent == field_indent + 4:
            cur["exit"].setdefault("args", {})[key] = _unquote(val)
            continue

        # --- inside exit: check/name/on_fail/fallback_gate/args ---
        if in_exit and indent == field_indent + 2:
            if key == "args":
                if val.startswith("{"):
                    cur["exit"]["args"] = parse_inline_dict(val)
                    in_args = False
                else:
                    cur["exit"].setdefault("args", {})   # block form follows
                    in_args = True
            else:
                cur["exit"][key] = _unquote(val)
            continue

        # --- step-level fields ---
        if key == "exit" and val == "":
            in_exit = True
            in_args = False
            continue
        if key in ("depends_on", "outputs") and val.startswith("["):
            cur[key] = parse_inline_list(val)
        else:
            cur[key] = _unquote(val)
    if cur is not None:
        steps.append(cur)
    return steps


def _unquote(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def parse_workflow_state(path):
    """Top-level analogue of parse_ledger for workflow-state.yaml — same
    tolerant, single-pass, 2-level-nesting-aware style, one altitude up
    (steps, not tasks)."""
    lines = Path(path).read_text().splitlines()
    top = {}
    steps = []
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

        if key == "steps":
            i += 1
            block = []
            while i < n and (not lines[i].strip() or (len(lines[i]) - len(lines[i].lstrip(" "))) > 0):
                block.append(lines[i])
                i += 1
            steps = parse_steps_block(block)
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

        if key == "autonomy_zone":
            top[key] = parse_inline_list(val) if val.startswith("[") else ([val] if val else [])
            i += 1
            continue

        top[key] = val
        i += 1

    return top, steps


def cmd_workflow(state_path, step_id_filter=None):
    top, steps = parse_workflow_state(state_path)

    state = top.get("state", "open")
    stop_flags = top.get("stop_flags", [])
    if isinstance(stop_flags, str):
        stop_flags = [stop_flags] if stop_flags else []
    autonomy_zone = top.get("autonomy_zone", [])
    if isinstance(autonomy_zone, str):
        autonomy_zone = [autonomy_zone] if autonomy_zone else []

    VALID_STATUSES = {"open", "in_progress", "done", "failed", "blocked"}
    VALID_KINDS = {"phase", "gate", "decision_node"}
    unknown_status = [f"{s.get('id','?')}={s.get('status')}" for s in steps
                      if s.get("status") not in VALID_STATUSES]
    unknown_kind = [f"{s.get('id','?')}={s.get('kind')}" for s in steps
                     if s.get("kind") not in VALID_KINDS]

    done = sum(1 for s in steps if s.get("status") == "done")
    failed = sum(1 for s in steps if s.get("status") == "failed")
    total = len(steps)
    done_ids = {s["id"] for s in steps if s.get("status") == "done"}
    open_steps = [s for s in steps if s.get("status") == "open"]

    next_step = None
    for s in open_steps:
        deps = s.get("depends_on", [])
        if isinstance(deps, str):
            deps = parse_inline_list(deps) if deps.startswith("[") else ([deps] if deps else [])
        if all(d in done_ids for d in deps):
            next_step = s
            break

    sh("WF_STATE", state)
    sh("WF_WORKFLOW_NAME", top.get("workflow", "unknown"))
    sh("WF_STOP_FLAGS", ",".join(stop_flags))
    sh("WF_AUTONOMY_ZONE", ",".join(autonomy_zone))
    sh("WF_DONE_COUNT", done)
    sh("WF_FAILED_COUNT", failed)
    sh("WF_TOTAL_COUNT", total)
    sh("WF_OPEN_COUNT", len(open_steps))
    sh("WF_UNKNOWN_STATUS_STEPS", ",".join(unknown_status))
    sh("WF_UNKNOWN_KIND_STEPS", ",".join(unknown_kind))

    exit_ = (next_step or {}).get("exit", {}) or {}
    args = exit_.get("args", {}) or {}
    sh("WF_NEXT_STEP_ID", next_step.get("id", "") if next_step else "")
    sh("WF_NEXT_STEP_KIND", next_step.get("kind", "") if next_step else "")
    sh("WF_NEXT_STEP_PHASE", next_step.get("phase", "") if next_step else "")
    sh("WF_NEXT_STEP_AGENT", next_step.get("agent", "") if next_step else "")
    sh("WF_NEXT_STEP_TIER", next_step.get("tier", "standard") if next_step else "")
    sh("WF_NEXT_STEP_GATE", next_step.get("gate", "") if next_step else "")
    sh("WF_NEXT_STEP_SUB_LEDGER", next_step.get("sub_ledger", "") if next_step else "")
    sh("WF_NEXT_STEP_FALLBACK_GATE", next_step.get("fallback_gate", "") if next_step else "")
    sh("WF_NEXT_STEP_EXIT_CHECK", exit_.get("check", ""))
    sh("WF_NEXT_STEP_EXIT_NAME", exit_.get("name", ""))
    sh("WF_NEXT_STEP_EXIT_ON_FAIL", exit_.get("on_fail", ""))
    sh("WF_NEXT_STEP_EXIT_PATH", args.get("path", ""))
    sh("WF_NEXT_STEP_EXIT_MUST_CONTAIN", args.get("must_contain", ""))
    sh("WF_NEXT_STEP_EXIT_CMD", args.get("cmd", args.get("command", "")))
    sh("WF_NEXT_STEP_EXIT_FIELD", args.get("field", ""))
    sh("WF_NEXT_STEP_EXIT_EXPECT", args.get("expect", ""))

    if step_id_filter:
        match = next((s for s in steps if s.get("id") == step_id_filter), None)
        sh("QUERIED_STEP_STATUS", match.get("status", "") if match else "")


def cmd_set_step_fields(state_path, step_id, *field_value_pairs):
    """Surgical single-step field update — same single-writer discipline as
    the task ledger, minus a full YAML round-trip (the tolerant parser above
    is read-only by design). Finds the `- id: <step_id>` block by indentation
    (from the `-` marker to the next line at or above that indent), then
    replaces each named field's value in place or appends it as a new line
    directly under the id line when absent. field_value_pairs is a flat
    key1 value1 key2 value2 ... list (values already shell-safe strings;
    empty string means 'delete this field's stamped value' is NOT supported
    here — callers pass concrete values only)."""
    if len(field_value_pairs) % 2 != 0:
        print("cmd_set_step_fields: odd number of field/value args", file=sys.stderr)
        sys.exit(1)
    updates = {}
    for i in range(0, len(field_value_pairs), 2):
        updates[field_value_pairs[i]] = field_value_pairs[i + 1]

    lines = Path(state_path).read_text().splitlines()
    n = len(lines)
    start = None
    dash_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^-\s*id:\s*(\S+)\s*$", stripped)
        if m and m.group(1) == step_id:
            start = i
            dash_indent = len(line) - len(line.lstrip(" "))
            break
    if start is None:
        print(f"cmd_set_step_fields: step not found: {step_id}", file=sys.stderr)
        sys.exit(1)

    field_indent = dash_indent + 2
    end = n
    for j in range(start + 1, n):
        line = lines[j]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= dash_indent:
            end = j
            break

    block = lines[start:end]
    remaining = dict(updates)
    new_block = []
    for line in block:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        matched_key = None
        if indent == field_indent and ":" in stripped:
            k = stripped.split(":", 1)[0].strip()
            if k in remaining:
                matched_key = k
        if matched_key:
            new_block.append(" " * field_indent + f"{matched_key}: {remaining.pop(matched_key)}")
            continue
        new_block.append(line)
    if remaining:
        extra = [" " * field_indent + f"{k}: {v}" for k, v in remaining.items()]
        new_block = new_block[:1] + extra + new_block[1:]

    lines[start:end] = new_block
    Path(state_path).write_text("\n".join(lines) + "\n")
    print("OK")


def cmd_set_top_field(state_path, field, value):
    """Set/append a TOP-LEVEL field in workflow-state.yaml. For `stop_flags`
    (a flow list) the value is appended if absent; other fields are scalar
    replace/insert. Fail-soft single-writer edit, no full YAML round-trip."""
    try:
        lines = Path(state_path).read_text().splitlines()
    except OSError:
        print("OK"); return
    out, found = [], False
    for line in lines:
        m = re.match(rf"^{re.escape(field)}:\s*(.*)$", line)
        if m and (len(line) - len(line.lstrip(" "))) == 0:
            found = True
            if field == "stop_flags":
                cur = m.group(1).strip()
                items = []
                if cur.startswith("[") and cur.endswith("]"):
                    inner = cur[1:-1].strip()
                    items = [x.strip() for x in inner.split(",") if x.strip()]
                if value not in items:
                    items.append(value)
                out.append(f"{field}: [{', '.join(items)}]")
            else:
                out.append(f"{field}: {value}")
        else:
            out.append(line)
    if not found:
        out.append(f"{field}: [{value}]" if field == "stop_flags" else f"{field}: {value}")
    Path(state_path).write_text("\n".join(out) + "\n")
    print("OK")


def _looks_like_regex(s):
    return any(c in s for c in ".^$*+?{}[]\\|()")


def _extract_dotted_field(path, field):
    """Read a yaml/json/plain file and pull a dotted key (a.b.c). Tolerant:
    tries json first, then a shallow line-based yaml scan for the final key.
    Returns the value as a string, or None."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    import json as _json
    try:
        obj = _json.loads(text)
        for part in field.split("."):
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                obj = None
                break
        if obj is not None:
            return str(obj)
    except Exception:
        pass
    # Line-based fallback: match the LAST segment as `key: value` anywhere.
    last = field.split(".")[-1]
    m = re.search(rf"^\s*{re.escape(last)}:\s*(.+?)\s*$", text, re.M)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


def _check_artifact_contains(path, must_contain):
    p = Path(path)
    if not path or not p.exists() or p.stat().st_size == 0:
        return False
    text = p.read_text(encoding="utf-8", errors="replace")
    if not must_contain:
        return False
    if _looks_like_regex(must_contain):
        try:
            if re.search(must_contain, text):
                return True
        except re.error:
            pass
    return must_contain in text


def _check_verdict_file(path):
    p = Path(path)
    if not path or not p.exists() or p.stat().st_size == 0:
        return False
    text = p.read_text(encoding="utf-8", errors="replace")
    lines_ = text.splitlines()
    status_lines = [l for l in lines_ if re.search(r"\b(status|verdict)\b", l, re.IGNORECASE)]
    scan = status_lines if status_lines else lines_
    for l in scan:
        if re.search(r"\bBLOCK\b", l) or re.search(r"\bFAIL\b", l):
            return False
    return True


def cmd_eval_exit(check, path_or_cmd, must_contain, log_path, field="", expect=""):
    """Deterministic phase-exit evaluation per references/phase-gates.md §2.
    Prints PASS or FAIL on stdout — the only contract the bash caller reads.
    `command` runs path_or_cmd quiet, output captured to log_path, exit 0 =
    pass. artifact_exists / artifact_contains / verdict_file all read
    path_or_cmd as the artifact path. `status_field` reads a dotted `field`
    from the file at path_or_cmd and string-compares it to `expect`."""
    import subprocess
    ok = False
    if check == "command":
        try:
            with open(log_path, "w", encoding="utf-8") as lf:
                r = subprocess.run(path_or_cmd, shell=True, stdout=lf, stderr=subprocess.STDOUT)
            ok = (r.returncode == 0)
        except Exception:
            ok = False
    elif check == "artifact_exists":
        p = Path(path_or_cmd) if path_or_cmd else None
        ok = bool(p) and p.exists() and p.stat().st_size > 0
    elif check == "artifact_contains":
        ok = _check_artifact_contains(path_or_cmd, must_contain)
    elif check == "verdict_file":
        ok = _check_verdict_file(path_or_cmd)
    elif check == "status_field":
        got = _extract_dotted_field(path_or_cmd, field) if (path_or_cmd and field) else None
        ok = got is not None and str(got).strip() == str(expect).strip()
    else:
        ok = False
    print("PASS" if ok else "FAIL")


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
                       cache_creation_input_tokens="null", total_cost_usd="null", iteration_model="null",
                       mode="slice", step="null", phase="null", exit_check="null",
                       iteration_effort="null", reasoning_output_tokens="null"):
    flags = [f for f in stop_flags_csv.split(",") if f]

    def _none_if_null(v):
        return None if v in ("", "null") else v

    record = {
        "ts": ts,
        "run_id": run_id,
        "iteration": int(iteration),
        "mode": mode,   # "slice" (default, matches pre-workflow-drive records) | "workflow"
        "slice": slice_id,
        "task": task_id,
        # workflow-drive-only fields; null on slice-drive records (additive,
        # non-breaking — see references/phase-gates.md §4).
        "step": _none_if_null(step),
        "phase": _none_if_null(phase),
        "exit_check": _none_if_null(exit_check),
        "agent": agent,
        "tier": tier,
        "iteration_model": None if iteration_model in ("", "null") else iteration_model,
        # Per-iteration reasoning effort (claude-code only today; additive,
        # mirrors iteration_model — null when the harness/tier doesn't map one).
        "iteration_effort": _none_if_null(iteration_effort),
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
        # Codex-only additive field: reasoning_output_tokens broken out from
        # turn.completed usage (see _extract_codex_json_usage). Null for
        # claude-code (folded into output_tokens there) and whenever the
        # harness invocation didn't expose it.
        "reasoning_output_tokens": _num_or_null(reasoning_output_tokens),
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


def _extract_codex_json_usage(text):
    """Tolerant extraction of usage/cost fields from `codex exec --json`
    stdout — a JSONL event stream. Scans every line for events carrying a
    usage object, summing across the stream since a single `codex exec`
    invocation may run multiple turns. Recognized shapes (in order of
    preference per line):
      - `type: "turn.completed"` with `usage: {input_tokens,
        cached_input_tokens, output_tokens}` (cached_input_tokens maps to
        cache_read_input_tokens) — the documented Codex JSONL event.
      - a bare top-level `usage` object (other event types that happen to
        carry one).
      - `token_count` / `info.usage` shapes, when trivially present.
    Codex's `--json` stream has no dollar-cost figure — total_cost_usd stays
    None always. Never raises; returns None when nothing usage-shaped is
    found anywhere in the stream."""
    text = (text or "").strip()
    if not text:
        return None
    tot = {"input_tokens": 0, "output_tokens": 0,
           "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
           "reasoning_output_tokens": 0}
    found = False

    def _pick(d, *keys):
        for k in keys:
            v = d.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return v
        return None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(d, dict):
            continue

        usage = None
        if d.get("type") == "turn.completed" and isinstance(d.get("usage"), dict):
            usage = dict(d["usage"])
            if "cached_input_tokens" in usage:
                usage["cache_read_input_tokens"] = usage.pop("cached_input_tokens")
        elif isinstance(d.get("usage"), dict):
            usage = d["usage"]
        elif isinstance(d.get("token_count"), dict):
            usage = d["token_count"]
        elif isinstance(d.get("info"), dict) and isinstance(d["info"].get("usage"), dict):
            usage = d["info"]["usage"]

        if not usage:
            continue

        found = True
        for field, keys in (
            ("input_tokens", ("input_tokens",)),
            ("output_tokens", ("output_tokens",)),
            ("cache_read_input_tokens", ("cache_read_input_tokens", "cached_input_tokens")),
            ("cache_creation_input_tokens", ("cache_creation_input_tokens",)),
            # Reasoning tokens reported separately from output_tokens on
            # turn.completed's usage object (Codex-specific; absent on other
            # event shapes, which is fine — _pick returns None and the sum
            # just doesn't grow for that line).
            ("reasoning_output_tokens", ("reasoning_output_tokens",)),
        ):
            v = _pick(usage, *keys)
            if v is not None:
                tot[field] += v

    if not found:
        return None

    return {
        "input_tokens": tot["input_tokens"] or None,
        "output_tokens": tot["output_tokens"] or None,
        "cache_read_input_tokens": tot["cache_read_input_tokens"] or None,
        "cache_creation_input_tokens": tot["cache_creation_input_tokens"] or None,
        "total_cost_usd": None,
        "reasoning_output_tokens": tot["reasoning_output_tokens"] or None,
    }


def cmd_parse_usage(stdout_path, usage_parse):
    """Fail-soft usage extraction: emits USAGE_* shell vars, always — 'null'
    on any parse problem, missing file, empty output, or unsupported
    usage_parse strategy. Never raises past this function."""
    fields = ("input_tokens", "output_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens", "total_cost_usd", "reasoning_output_tokens")
    values = {f: None for f in fields}
    try:
        if usage_parse == "claude-json":
            text = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
            parsed = _extract_claude_json_usage(text)
            if parsed:
                values.update(parsed)
        elif usage_parse == "codex-json":
            text = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
            parsed = _extract_codex_json_usage(text)
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
    elif action == "workflow":
        step_filter = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_workflow(sys.argv[2], step_filter)
    elif action == "set_top_field":
        cmd_set_top_field(sys.argv[2], sys.argv[3], sys.argv[4])
    elif action == "set_step":
        cmd_set_step_fields(sys.argv[2], sys.argv[3], *sys.argv[4:])
    elif action == "eval_exit":
        cmd_eval_exit(*sys.argv[2:8])
    elif action == "append_record":
        cmd_append_record(*sys.argv[2:26])
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
elif [[ "$HARNESS" == "codex" ]]; then
  if [[ "$JSON_OUTPUT_FLAG" == "null" && "$HARNESS_COMMAND" != *"--json"* ]]; then
    JSON_OUTPUT_FLAG="--json"
  fi
  if [[ "$USAGE_PARSE" == "null" ]]; then
    USAGE_PARSE="codex-json"
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

# ==========================================================================
# --workflow mode: the top-level loop over workflow STEPS (references/
# phase-gates.md). Opt-in, additive — everything below runs ONLY when
# --workflow was passed, and `exit`s before falling through to the unchanged
# slice-drive loop beneath this block. See references/phase-gates.md §1-4
# for the autonomy zone, predicate registry, ledger schema, and telemetry
# shape this section implements.
# ==========================================================================
if (( WORKFLOW_MODE == 1 )); then
  WORKFLOW_STATE_PATH="$PROJECT_DIR/.project/working/workflow-state.yaml"
  if [[ ! -f "$WORKFLOW_STATE_PATH" ]]; then
    echo "praxis-drive.sh: --workflow: no workflow-state ledger found at $WORKFLOW_STATE_PATH"
    echo "A workflow instance must be opened (delivery-planner) before --workflow can drive it."
    exit 2
  fi

  # Launches the named step's agent headlessly on its phase-tier-resolved
  # model (SAME TIER_MODEL_*/HARNESS_MODEL_FLAG machinery slice-drive uses —
  # this is how the orchestrator/phase leads get per-step routing). Sets the
  # global ITER_MODEL and USAGE_* vars for the caller's telemetry record.
  # --dry-run prints the command instead of running it, exactly like the
  # slice-drive iteration below.
  invoke_step_agent() {
    local step_id="$1" step_phase="$2" step_agent="$3" step_tier="$4" purpose="$5"
    local prompt="You are the Praxis ${step_agent:-delivery-lead}, operating under workflow-drive (references/phase-gates.md) for workflow step ${step_id} (phase ${step_phase}). Read .project/working/workflow-state.yaml for this step's declared outputs and named context, and produce them. ${purpose} Do not wait for user input."
    local cmd="${HARNESS_COMMAND//\{prompt\}/$prompt}"
    if [[ "$MAX_BUDGET_USD" != "null" && "$HARNESS_BUDGET_FLAG" != "null" ]]; then
      cmd="$cmd $HARNESS_BUDGET_FLAG $MAX_BUDGET_USD"
    fi
    # governance force_tier pin overrides the step's declared tier (compliance
    # engagements mandating one tier everywhere) — honored here so drive matches
    # the no-drive resolver.
    [[ -n "${FORCE_TIER:-}" && "$FORCE_TIER" != "null" ]] && step_tier="$FORCE_TIER"
    case "$step_tier" in
      deep)  ITER_MODEL="$TIER_MODEL_DEEP" ;;
      light) ITER_MODEL="$TIER_MODEL_LIGHT" ;;
      *)     ITER_MODEL="$TIER_MODEL_STANDARD" ;;
    esac
    if [[ -n "$ITER_MODEL" && "$ITER_MODEL" != "null" && -n "$HARNESS_MODEL_FLAG" && "$HARNESS_MODEL_FLAG" != "null" ]]; then
      cmd="$cmd $HARNESS_MODEL_FLAG $ITER_MODEL"
    fi
    # Per-iteration reasoning effort — same tier-resolution pattern as
    # ITER_MODEL, via TIER_EFFORT_*/HARNESS_EFFORT_FLAG. claude-code renders it
    # as `--effort high`; codex as `-c model_reasoning_effort=high` (flag `-c` +
    # prefix `model_reasoning_effort=`).
    case "$step_tier" in
      deep)  ITER_EFFORT="$TIER_EFFORT_DEEP" ;;
      light) ITER_EFFORT="$TIER_EFFORT_LIGHT" ;;
      *)     ITER_EFFORT="$TIER_EFFORT_STANDARD" ;;
    esac
    if [[ -n "$ITER_EFFORT" && "$ITER_EFFORT" != "null" && -n "$HARNESS_EFFORT_FLAG" && "$HARNESS_EFFORT_FLAG" != "null" ]]; then
      cmd="$cmd $HARNESS_EFFORT_FLAG ${HARNESS_EFFORT_ARG_PREFIX:-}$ITER_EFFORT"
    fi
    if [[ -n "$JSON_OUTPUT_FLAG" && "$JSON_OUTPUT_FLAG" != "null" ]]; then
      cmd="$cmd $JSON_OUTPUT_FLAG"
    fi

    USAGE_INPUT_TOKENS="null"; USAGE_OUTPUT_TOKENS="null"
    USAGE_CACHE_READ_INPUT_TOKENS="null"; USAGE_CACHE_CREATION_INPUT_TOKENS="null"
    USAGE_TOTAL_COST_USD="null"; USAGE_REASONING_OUTPUT_TOKENS="null"

    if (( DRY_RUN == 1 )); then
      echo "[dry-run] workflow step $step_id — would invoke: $cmd"
    else
      local iter_stdout
      iter_stdout="$(mktemp -t praxis-drive-wf-stdout.XXXXXX)"
      if ! ( cd "$PROJECT_DIR" && eval "$cmd" > "$iter_stdout" ); then
        echo "praxis-drive.sh: harness invocation exited non-zero for workflow step $step_id" >&2
      fi
      cat "$iter_stdout"
      local usage_env
      if usage_env="$(python3 "$PY_HELPER" parse_usage "$iter_stdout" "$USAGE_PARSE")"; then
        eval "$usage_env"
      else
        echo "praxis-drive.sh: usage parse failed for workflow step $step_id (non-fatal — recording nulls)" >&2
      fi
      rm -f "$iter_stdout"
      if [[ "$USAGE_TOTAL_COST_USD" != "null" ]]; then
        COST_USD_ACCUM="$(awk "BEGIN{printf \"%.6f\", $COST_USD_ACCUM + $USAGE_TOTAL_COST_USD}")"
        HAVE_COST_USD_DATA=1
      fi
    fi
  }

  RUN_ID="wfdrive-$(date -u +%Y%m%d-%H%M%S)"
  ITERATION=0
  STEPS_PROCESSED=0
  STALL_COUNT=0
  COST_ACCUM=0
  COST_USD_ACCUM=0
  HAVE_COST_USD_DATA=0
  STOP_REASON=""
  EXIT_CODE=0
  LAST_DONE_COUNT=0
  LAST_TOTAL_COUNT=0
  LAST_STEP_ID="unknown"

  while true; do
    ITERATION=$((ITERATION + 1))

    if (( ITERATION > MAX_ITERATIONS_PER_RUN )); then
      ITERATION=$((ITERATION - 1))
      STOP_REASON="budget: max_iterations_per_run ($MAX_ITERATIONS_PER_RUN) reached"
      EXIT_CODE=4
      break
    fi

    HASH_BEFORE="$(hash_of "$WORKFLOW_STATE_PATH")"

    if ! WF_ENV="$(python3 "$PY_HELPER" workflow "$WORKFLOW_STATE_PATH")"; then
      echo "praxis-drive.sh: failed to parse workflow ledger $WORKFLOW_STATE_PATH" >&2
      STOP_REASON="blocked: workflow ledger $WORKFLOW_STATE_PATH failed to parse"
      EXIT_CODE=5
      break
    fi
    eval "$WF_ENV"
    LAST_DONE_COUNT=$WF_DONE_COUNT
    LAST_TOTAL_COUNT=$WF_TOTAL_COUNT

    if [[ -n "$WF_STOP_FLAGS" ]]; then
      STOP_REASON="stop_flags present before iteration: $WF_STOP_FLAGS"
      case ",$WF_STOP_FLAGS," in
        *,stalled,*)         EXIT_CODE=3 ;;
        *,budget_exceeded,*) EXIT_CODE=4 ;;
        *,blocked,*)         EXIT_CODE=5 ;;
        *)                   EXIT_CODE=0 ;;
      esac
      break
    fi

    if [[ -n "$WF_UNKNOWN_STATUS_STEPS" || -n "$WF_UNKNOWN_KIND_STEPS" ]]; then
      STOP_REASON="blocked: workflow ledger $WORKFLOW_STATE_PATH contains steps with unknown status/kind tokens (status: ${WF_UNKNOWN_STATUS_STEPS:-none}; kind: ${WF_UNKNOWN_KIND_STEPS:-none}) — canonical status vocabulary is open|in_progress|done|failed|blocked, canonical kind vocabulary is phase|gate|decision_node (references/phase-gates.md §3). Fix the tokens, then resume."
      EXIT_CODE=5
      break
    fi

    if [[ -z "$WF_NEXT_STEP_ID" ]]; then
      if [[ "$WF_STATE" == "closed" || "$WF_OPEN_COUNT" == "0" ]]; then
        STOP_REASON="workflow drained (no drive-eligible steps remain in $WORKFLOW_STATE_PATH)"
        EXIT_CODE=0
      else
        STOP_REASON="blocked: no drive-eligible step in $WORKFLOW_STATE_PATH (dependencies unmet, or remaining steps exhausted)"
        EXIT_CODE=5
      fi
      break
    fi

    STEP_ID="$WF_NEXT_STEP_ID"
    STEP_KIND="$WF_NEXT_STEP_KIND"
    STEP_PHASE="$WF_NEXT_STEP_PHASE"
    STEP_AGENT="$WF_NEXT_STEP_AGENT"
    STEP_TIER="${WF_NEXT_STEP_TIER:-standard}"
    LAST_STEP_ID="$STEP_ID"

    case "$STEP_TIER" in
      deep)  WEIGHT="$COST_WEIGHT_DEEP" ;;
      light) WEIGHT="$COST_WEIGHT_LIGHT" ;;
      *)     WEIGHT="$COST_WEIGHT_STANDARD" ;;
    esac

    TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    # ---- kind: gate — ALWAYS a human stop. Governance is never machine-
    # cleared, regardless of the autonomy dial. ----
    if [[ "$STEP_KIND" == "gate" ]]; then
      GATE_NAME="${WF_NEXT_STEP_GATE:-$STEP_ID}"
      STOP_REASON="gate_reached: $GATE_NAME (workflow step $STEP_ID, phase $STEP_PHASE) — governance gate, non-negotiable human stop"
      ITER_MODEL="null"
      python3 "$PY_HELPER" append_record "$DRIVE_JSONL" "$TS" "$RUN_ID" "$ITERATION" "$WF_WORKFLOW_NAME" "$STEP_ID" "$STEP_AGENT" "$STEP_TIER" "gate_reached" "$HASH_BEFORE" "gate_reached" "0" \
        "null" "null" "null" "null" "null" "null" "workflow" "$STEP_ID" "$STEP_PHASE" "gate"
      EXIT_CODE=0
      break
    fi

    # Autonomy zone + machine-exit checks (references/phase-gates.md §1-2).
    IN_ZONE=0
    IFS=',' read -ra _ZONE_PHASES <<< "$WF_AUTONOMY_ZONE"
    for _zp in "${_ZONE_PHASES[@]}"; do
      [[ "$_zp" == "$STEP_PHASE" ]] && IN_ZONE=1
    done
    HAS_MACHINE_CHECK=0
    [[ -n "$WF_NEXT_STEP_EXIT_CHECK" ]] && HAS_MACHINE_CHECK=1

    # ---- Outside the autonomy zone, OR the exit has only a fallback_gate
    # (no machine check) — run the step's agent once, then ALWAYS stop for a
    # human. Never self-assert the boundary. `phase` and `decision_node` steps
    # WITH a machine-verifiable exit inside the zone fall through to the
    # deterministic-eval path below; only a boundary the runner cannot resolve
    # deterministically is a human stop. ----
    if [[ $IN_ZONE -eq 0 || $HAS_MACHINE_CHECK -eq 0 ]]; then
      if [[ $IN_ZONE -eq 0 ]]; then
        REASON_TAIL="phase $STEP_PHASE is outside the autonomy_zone (${WF_AUTONOMY_ZONE:-none}) — human boundary${WF_NEXT_STEP_FALLBACK_GATE:+ (fallback_gate: $WF_NEXT_STEP_FALLBACK_GATE)}"
      else
        REASON_TAIL="fallback_gate: ${WF_NEXT_STEP_FALLBACK_GATE:-$STEP_ID} (boundary not machine-verifiable)"
      fi
      invoke_step_agent "$STEP_ID" "$STEP_PHASE" "$STEP_AGENT" "$STEP_TIER" \
        "This step's phase boundary is NOT machine-verifiable here — do the work, then STOP; a human evaluates the boundary ($REASON_TAIL) and resumes the workflow. Do not attempt to clear it yourself."
      STOP_REASON="$REASON_TAIL (workflow step $STEP_ID)"
      python3 "$PY_HELPER" append_record "$DRIVE_JSONL" "$TS" "$RUN_ID" "$ITERATION" "$WF_WORKFLOW_NAME" "$STEP_ID" "$STEP_AGENT" "$STEP_TIER" "fallback_stop" "$(hash_of "$WORKFLOW_STATE_PATH")" "fallback_gate" "$WEIGHT" \
        "$USAGE_INPUT_TOKENS" "$USAGE_OUTPUT_TOKENS" "$USAGE_CACHE_READ_INPUT_TOKENS" "$USAGE_CACHE_CREATION_INPUT_TOKENS" "$USAGE_TOTAL_COST_USD" "${ITER_MODEL:-null}" "workflow" "$STEP_ID" "$STEP_PHASE" "${WF_NEXT_STEP_EXIT_CHECK:-none}"
      EXIT_CODE=0
      break
    fi

    # ---- kind: phase, in-zone, machine-verifiable exit. ----
    if [[ -n "$WF_NEXT_STEP_SUB_LEDGER" ]]; then
      # This step's work IS a slice-drive run (references/phase-gates.md
      # §3): nest a call to this same script, WITHOUT --workflow, against
      # the sub_ledger. Fail-soft — a nonzero nested exit does not abort the
      # workflow loop; the step's own `exit` is still evaluated below (a
      # slice that closed abnormally will typically also fail its exit
      # predicate, which is the correct signal).
      SUB_ID="$(basename "$WF_NEXT_STEP_SUB_LEDGER" | sed -n 's/^slice-\(.*\)-tasks\.yaml$/\1/p')"
      if [[ -n "$SUB_ID" ]]; then
        echo "praxis-drive.sh: workflow step $STEP_ID delegates to slice-drive over sub_ledger $WF_NEXT_STEP_SUB_LEDGER (slice $SUB_ID)"
        NESTED_ARGS=(--project-dir "$PROJECT_DIR" --harness "$HARNESS" --slice "$SUB_ID")
        (( DRY_RUN == 1 )) && NESTED_ARGS+=(--dry-run)
        bash "${BASH_SOURCE[0]}" "${NESTED_ARGS[@]}" || echo "praxis-drive.sh: nested slice-drive run for step $STEP_ID exited non-zero (evaluating step exit anyway)" >&2
        ITER_MODEL="null"; ITER_EFFORT="null"
        USAGE_INPUT_TOKENS="null"; USAGE_OUTPUT_TOKENS="null"
        USAGE_CACHE_READ_INPUT_TOKENS="null"; USAGE_CACHE_CREATION_INPUT_TOKENS="null"
        USAGE_TOTAL_COST_USD="null"; USAGE_REASONING_OUTPUT_TOKENS="null"
      else
        echo "praxis-drive.sh: could not parse a slice id out of sub_ledger '$WF_NEXT_STEP_SUB_LEDGER' for step $STEP_ID — skipping delegation, evaluating exit as-is (fail-soft)" >&2
        ITER_MODEL="null"; ITER_EFFORT="null"
        USAGE_INPUT_TOKENS="null"; USAGE_OUTPUT_TOKENS="null"
        USAGE_CACHE_READ_INPUT_TOKENS="null"; USAGE_CACHE_CREATION_INPUT_TOKENS="null"
        USAGE_TOTAL_COST_USD="null"; USAGE_REASONING_OUTPUT_TOKENS="null"
      fi
    elif [[ "$STEP_KIND" == "decision_node" ]]; then
      # A decision_node is a pure predicate branch point — no agent runs; the
      # runner evaluates its machine check directly and branches. Since no agent
      # ran, there is no usage to record — but the telemetry append below reads
      # these vars bare (not `${x:-null}`), so they MUST be initialized here or
      # `set -u` aborts before the record is written (same init as the
      # sub_ledger branch above).
      python3 "$PY_HELPER" set_step "$WORKFLOW_STATE_PATH" "$STEP_ID" status in_progress started_at "$TS" \
        || echo "praxis-drive.sh: warning: could not stamp started_at on decision_node $STEP_ID (non-fatal)" >&2
      ITER_MODEL="null"; ITER_EFFORT="null"
      USAGE_INPUT_TOKENS="null"; USAGE_OUTPUT_TOKENS="null"
      USAGE_CACHE_READ_INPUT_TOKENS="null"; USAGE_CACHE_CREATION_INPUT_TOKENS="null"
      USAGE_TOTAL_COST_USD="null"; USAGE_REASONING_OUTPUT_TOKENS="null"
    else
      python3 "$PY_HELPER" set_step "$WORKFLOW_STATE_PATH" "$STEP_ID" status in_progress started_at "$TS" \
        || echo "praxis-drive.sh: warning: could not stamp started_at on step $STEP_ID (non-fatal)" >&2
      invoke_step_agent "$STEP_ID" "$STEP_PHASE" "$STEP_AGENT" "$STEP_TIER" \
        "Do NOT set this step's status to done or evaluate its own exit yourself — the runner verifies the exit deterministically once you finish."
    fi

    # ---- Deterministic exit evaluation (references/phase-gates.md §2). The
    # runner decides, not the agent — silent self-assertion of a phase
    # boundary is a protocol violation. ----
    CHECK="$WF_NEXT_STEP_EXIT_CHECK"
    if [[ "$CHECK" == "command" ]]; then
      # Run project-relative, like a task's `verify` command.
      PATH_OR_CMD="cd $(printf '%q' "$PROJECT_DIR") && $WF_NEXT_STEP_EXIT_CMD"
    else
      PATH_OR_CMD="$WF_NEXT_STEP_EXIT_PATH"
      # status_field also reads a file path; resolve it below like the others.
      # exit.args.path is project-relative (.project/working/...); resolve
      # against --project-dir so this sees the same file the step wrote,
      # regardless of the runner's own cwd.
      if [[ -n "$PATH_OR_CMD" && "$PATH_OR_CMD" != /* ]]; then
        PATH_OR_CMD="$PROJECT_DIR/$PATH_OR_CMD"
      fi
    fi
    LOG_PATH="$PROJECT_DIR/.project/working/verify-${STEP_ID}.log"
    mkdir -p "$(dirname "$LOG_PATH")" 2>/dev/null || true
    EXIT_RESULT="$(python3 "$PY_HELPER" eval_exit "$CHECK" "$PATH_OR_CMD" "$WF_NEXT_STEP_EXIT_MUST_CONTAIN" "$LOG_PATH" "$WF_NEXT_STEP_EXIT_FIELD" "$WF_NEXT_STEP_EXIT_EXPECT" 2>/dev/null || echo FAIL)"

    HASH_AFTER="$(hash_of "$WORKFLOW_STATE_PATH")"

    if [[ "$EXIT_RESULT" == "PASS" ]]; then
      TS2="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      python3 "$PY_HELPER" set_step "$WORKFLOW_STATE_PATH" "$STEP_ID" status done completed_at "$TS2" \
        || echo "praxis-drive.sh: warning: could not stamp completed_at on step $STEP_ID (non-fatal)" >&2
      HASH_AFTER="$(hash_of "$WORKFLOW_STATE_PATH")"
      STEPS_PROCESSED=$((STEPS_PROCESSED + 1))
      COST_ACCUM="$(awk "BEGIN{printf \"%.4f\", $COST_ACCUM + $WEIGHT}")"
      python3 "$PY_HELPER" append_record "$DRIVE_JSONL" "$TS" "$RUN_ID" "$ITERATION" "$WF_WORKFLOW_NAME" "$STEP_ID" "$STEP_AGENT" "$STEP_TIER" "done" "$HASH_AFTER" "" "$WEIGHT" \
        "$USAGE_INPUT_TOKENS" "$USAGE_OUTPUT_TOKENS" "$USAGE_CACHE_READ_INPUT_TOKENS" "$USAGE_CACHE_CREATION_INPUT_TOKENS" "$USAGE_TOTAL_COST_USD" "${ITER_MODEL:-null}" "workflow" "$STEP_ID" "$STEP_PHASE" "$CHECK" "${ITER_EFFORT:-null}" "${USAGE_REASONING_OUTPUT_TOKENS:-null}"
    else
      ON_FAIL="$WF_NEXT_STEP_EXIT_ON_FAIL"
      TS_FAIL="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      # Always resolve the failed step out of in_progress: stamp it failed +
      # completed_at so resume is unambiguous (the reviewer's finding — a
      # failed exit must never leave a step stuck in_progress).
      python3 "$PY_HELPER" set_step "$WORKFLOW_STATE_PATH" "$STEP_ID" status failed completed_at "$TS_FAIL" \
        || echo "praxis-drive.sh: warning: could not stamp failed status on step $STEP_ID (non-fatal)" >&2
      if [[ "$ON_FAIL" == route_back* ]]; then
        TARGET="$(awk '{print $2}' <<< "$ON_FAIL")"
        [[ -z "$TARGET" ]] && TARGET="$STEP_ID"
        # Reopen the route-back target (may be the current step or an upstream
        # one) — this supersedes the failed stamp above when TARGET == STEP_ID.
        python3 "$PY_HELPER" set_step "$WORKFLOW_STATE_PATH" "$TARGET" status open \
          || echo "praxis-drive.sh: warning: could not route back step $TARGET (non-fatal)" >&2
        STOP_REASON="on_fail=route_back: step $STEP_ID failed its exit check ($CHECK) — $TARGET reset to open"
      elif [[ "$ON_FAIL" == escalate_to_human* ]]; then
        STOP_REASON="on_fail=escalate_to_human: step $STEP_ID failed its exit check ($CHECK) — human escalation required"
      else
        STOP_REASON="on_fail=stop_and_flag: step $STEP_ID failed its exit check ($CHECK)"
      fi
      # Raise a stop flag on the workflow state so resume is unambiguous.
      python3 "$PY_HELPER" set_top_field "$WORKFLOW_STATE_PATH" stop_flags "blocked" 2>/dev/null || true
      HASH_AFTER="$(hash_of "$WORKFLOW_STATE_PATH")"
      python3 "$PY_HELPER" append_record "$DRIVE_JSONL" "$TS" "$RUN_ID" "$ITERATION" "$WF_WORKFLOW_NAME" "$STEP_ID" "$STEP_AGENT" "$STEP_TIER" "failed" "$HASH_AFTER" "blocked" "$WEIGHT" \
        "$USAGE_INPUT_TOKENS" "$USAGE_OUTPUT_TOKENS" "$USAGE_CACHE_READ_INPUT_TOKENS" "$USAGE_CACHE_CREATION_INPUT_TOKENS" "$USAGE_TOTAL_COST_USD" "${ITER_MODEL:-null}" "workflow" "$STEP_ID" "$STEP_PHASE" "$CHECK" "${ITER_EFFORT:-null}" "${USAGE_REASONING_OUTPUT_TOKENS:-null}"
      EXIT_CODE=5
      break
    fi

    # ---- Always-on stop checks (stall / budget) ----
    if [[ "$HASH_AFTER" == "$HASH_BEFORE" ]]; then
      STALL_COUNT=$((STALL_COUNT + 1))
    else
      STALL_COUNT=0
    fi
    if (( STALL_COUNT >= STALL_MAX_NO_CHANGE )); then
      STOP_REASON="stalled: workflow ledger hash unchanged for $STALL_COUNT consecutive iterations (cap: $STALL_MAX_NO_CHANGE)"
      EXIT_CODE=3
      break
    fi

    if (( STEPS_PROCESSED >= MAX_STEPS_PER_RUN )); then
      STOP_REASON="budget: max_steps_per_run ($MAX_STEPS_PER_RUN) reached at step $STEP_ID"
      EXIT_CODE=4
      break
    fi

    if awk "BEGIN{exit !($COST_ACCUM > $COST_CEILING_PROXY)}"; then
      STOP_REASON="budget: cost_ceiling_proxy ($COST_CEILING_PROXY) exceeded (accrued $COST_ACCUM)"
      EXIT_CODE=4
      break
    fi

    # ---- stop_after: step | phase | gate (task/slice fall through as
    # "gate" — continuous — since they have no workflow-drive meaning). ----
    if [[ "$STOP_AFTER" == "step" ]]; then
      STOP_REASON="stop_after=step boundary (step $STEP_ID done)"
      EXIT_CODE=0
      break
    fi

    if [[ "$STOP_AFTER" == "phase" ]]; then
      if PEEK_ENV="$(python3 "$PY_HELPER" workflow "$WORKFLOW_STATE_PATH" 2>/dev/null)"; then
        eval "$PEEK_ENV"
      fi
      if [[ -z "$WF_NEXT_STEP_ID" || "$WF_NEXT_STEP_PHASE" != "$STEP_PHASE" ]]; then
        STOP_REASON="stop_after=phase boundary (step $STEP_ID closed phase $STEP_PHASE)"
        EXIT_CODE=0
        break
      fi
    fi

    # stop_after in {gate, task, slice}: rely on stop_flags/budget/stall
    # only — keep looping (matches slice-drive's stop_after=gate fallthrough).
  done

  REMAINING=$(( LAST_TOTAL_COUNT - LAST_DONE_COUNT ))
  (( REMAINING < 0 )) && REMAINING=0

  echo ""
  echo "praxis-drive (--workflow) — run $RUN_ID stopped"
  echo "=================================="
  echo "  reason:            $STOP_REASON"
  echo "  iterations run:    $ITERATION"
  echo "  last step:         $LAST_STEP_ID"
  echo "  steps done/remaining (last ledger read): $LAST_DONE_COUNT/$REMAINING"
  echo "  steps processed this run: $STEPS_PROCESSED"
  echo "  cost proxy consumed: $COST_ACCUM (ceiling: $COST_CEILING_PROXY)"
  if (( HAVE_COST_USD_DATA == 1 )); then
    echo "  real cost (sum of harness total_cost_usd): \$$COST_USD_ACCUM"
  else
    echo "  real cost: n/a (harness did not report total_cost_usd this run)"
  fi
  echo "  telemetry:          $DRIVE_JSONL"
  echo "  exit code:          $EXIT_CODE"

  exit $EXIT_CODE
fi

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

  # Vocabulary enforcement: unknown status tokens are a factory defect the
  # runner must surface, never silently drain past ("pending" was observed
  # in the wild — the canonical vocabulary is open|in_progress|done|failed|blocked).
  if [[ -n "$UNKNOWN_STATUS_TASKS" ]]; then
    STOP_REASON="blocked: ledger $LEDGER_PATH contains tasks with UNKNOWN status tokens ($UNKNOWN_STATUS_TASKS) — canonical vocabulary is open|in_progress|done|failed|blocked (references/loop-contracts.md §2). Fix the tokens, then resume."
    EXIT_CODE=5
    break
  fi

  if [[ -z "$NEXT_TASK_ID" ]]; then
    if [[ "$LEDGER_STATE" == "closed" || "$OPEN_COUNT" == "0" ]]; then
      STOP_REASON="queue drained (no drive-eligible tasks remain in $LEDGER_PATH)"
      [[ -n "$INTERACTIVE_ONLY_TASKS" ]] && STOP_REASON="$STOP_REASON; interactive-only tasks awaiting a human/session: $INTERACTIVE_ONLY_TASKS"
      EXIT_CODE=0
    else
      STOP_REASON="blocked: no drive-eligible task in $LEDGER_PATH (dependencies unmet, or all remaining tasks exhausted)"
      [[ -n "$INTERACTIVE_ONLY_TASKS" ]] && STOP_REASON="$STOP_REASON; interactive-only (no verify): $INTERACTIVE_ONLY_TASKS"
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

  # Route the router: run this iteration on the model its TASK TIER resolves
  # to (governance/model-routing.yaml map for this harness). Mechanical
  # light/standard tasks no longer pay deep-tier rates just because the
  # orchestrator's static default is deep. Falls back to the harness default
  # model when the tier or flag is unmapped. Also recorded in drive.jsonl.
  ITER_TIER="${NEXT_TASK_TIER:-standard}"
  # governance force_tier pin overrides the task's declared tier (honored here
  # so drive matches the no-drive resolver — parity).
  [[ -n "${FORCE_TIER:-}" && "$FORCE_TIER" != "null" ]] && ITER_TIER="$FORCE_TIER"
  case "$ITER_TIER" in
    deep)     ITER_MODEL="$TIER_MODEL_DEEP" ;;
    light)    ITER_MODEL="$TIER_MODEL_LIGHT" ;;
    *)        ITER_MODEL="$TIER_MODEL_STANDARD" ;;
  esac
  if [[ -n "$ITER_MODEL" && "$ITER_MODEL" != "null" && -n "$HARNESS_MODEL_FLAG" && "$HARNESS_MODEL_FLAG" != "null" ]]; then
    CMD="$CMD $HARNESS_MODEL_FLAG $ITER_MODEL"
  fi
  # Route the effort too: the cheaper cost lever — deep thinking on a
  # standard model — resolved from the task tier via TIER_EFFORT_* +
  # HARNESS_EFFORT_FLAG. Rendered as `--effort high` (claude-code) or
  # `-c model_reasoning_effort=high` (codex). Recorded as iteration_effort.
  case "$ITER_TIER" in
    deep)     ITER_EFFORT="$TIER_EFFORT_DEEP" ;;
    light)    ITER_EFFORT="$TIER_EFFORT_LIGHT" ;;
    *)        ITER_EFFORT="$TIER_EFFORT_STANDARD" ;;
  esac
  if [[ -n "$ITER_EFFORT" && "$ITER_EFFORT" != "null" && -n "$HARNESS_EFFORT_FLAG" && "$HARNESS_EFFORT_FLAG" != "null" ]]; then
    CMD="$CMD $HARNESS_EFFORT_FLAG ${HARNESS_EFFORT_ARG_PREFIX:-}$ITER_EFFORT"
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
  USAGE_REASONING_OUTPUT_TOKENS="null"

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
    "$USAGE_INPUT_TOKENS" "$USAGE_OUTPUT_TOKENS" "$USAGE_CACHE_READ_INPUT_TOKENS" "$USAGE_CACHE_CREATION_INPUT_TOKENS" "$USAGE_TOTAL_COST_USD" "${ITER_MODEL:-null}" "slice" "null" "null" "none" "${ITER_EFFORT:-null}" "${USAGE_REASONING_OUTPUT_TOKENS:-null}"

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
