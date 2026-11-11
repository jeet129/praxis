#!/usr/bin/env bash
# Build the Codex plugin package from canonical Praxis content.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/plugins/praxis-codex"
SRC="$ROOT/codex-plugin-assets"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: missing Codex source directory: $SRC" >&2
  exit 2
fi

if [[ -e "$OUT" && ! -f "$OUT/.generated-by-praxis-codex-build" ]]; then
  if [[ -d "$OUT/.codex-plugin" || "$OUT" == "$ROOT/plugins/praxis-codex" ]]; then
    echo "WARN: replacing interrupted Codex plugin package: $OUT" >&2
  else
    echo "ERROR: refusing to replace non-generated directory: $OUT" >&2
    exit 3
  fi
fi

python3 - "$ROOT" "$SRC" "$OUT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = Path(sys.argv[2])
out = Path(sys.argv[3])

# The generated Codex package is a PUBLIC artifact. Correctness beats sandbox
# convenience: this build refreshes every file in place, then reconciles OUT
# against the exact set of files it produced and REMOVES anything left over.
# If a stale file cannot be removed (e.g. a delete-restricted filesystem), the
# build FAILS rather than publish a mirror that still contains a since-deleted
# skill/hook. (The authoritative build runs in pre-commit/CI on an unrestricted
# filesystem; there the removal always succeeds.)
expected = set()  # POSIX-rel paths, from OUT, that this build intends to exist


def place_tree(source: Path, dest: Path):
    """Copy source -> dest (overwriting file contents in place, which is
    allowed even where unlink is blocked) and record every file it places
    relative to OUT, so reconciliation below knows exactly what belongs."""
    for p in source.rglob("*"):
        if p.name == ".DS_Store" or p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue  # never ship python bytecode
        rel = p.relative_to(source)
        target = dest / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            expected.add(target.relative_to(out).as_posix())


def record(target: Path):
    expected.add(target.relative_to(out).as_posix())


out.mkdir(parents=True, exist_ok=True)
(out / ".codex-plugin").mkdir(exist_ok=True)

for name in ("skills", "agents", "workflows", "governance", "references", "patterns", "scripts", "hooks"):
    source = root / name
    if source.exists():
        place_tree(source, out / name)

# Only the front door, drive/DoD contracts, and Codex command skills appear in
# the plugin's advertised skill path. Keep the full canonical library under
# skills/ for direct, on-demand reads by roles without loading 100+ skill
# descriptions into every Codex session.
for name in ("using-praxis", "autonomous-drive", "definition-of-done"):
    place_tree(root / "skills" / name, out / "codex-skills" / name)
command_skills = src / "skills"
if command_skills.exists():
    for skill in command_skills.iterdir():
        if skill.is_dir():
            # Preserve the established direct-reference path for existing
            # agents and docs; only codex-skills is advertised to the loader.
            place_tree(skill, out / "skills" / skill.name)
            place_tree(skill, out / "codex-skills" / skill.name)

for doc in (out / "codex-skills").rglob("*.md"):
    content = doc.read_text()
    doc.write_text(content.rstrip("\n") + "\n")

codex_agents = src / "codex-agents"
if codex_agents.exists():
    place_tree(codex_agents, out / "codex-agents")

codex_hooks = src / "hooks"
if codex_hooks.exists():
    place_tree(codex_hooks, out / "hooks")

codex_scripts = src / "scripts"
if codex_scripts.exists():
    place_tree(codex_scripts, out / "scripts")

# Codex's unattended runner must drain a completed task ledger through review,
# QA and closeout. Keep this overlay in the generated Codex package only: the
# canonical runner and Claude distribution retain their existing behavior.
runner = out / "scripts" / "praxis-drive.sh"
if runner.exists():
    source = runner.read_text()
    old = '''  if [[ -z "$NEXT_TASK_ID" ]]; then
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
'''
    new = '''  DRAIN_MODE=0
  if [[ -z "$NEXT_TASK_ID" ]]; then
    if [[ "$LEDGER_STATE" == "closed" && "${PRAXIS_CODEX_CLOSEOUT_REPAIR:-0}" == "1" ]]; then
      DRAIN_MODE=1
      NEXT_TASK_ID="slice-closeout-repair"
      NEXT_TASK_AGENT="delivery-lead"
      NEXT_TASK_TIER="standard"
    elif [[ "$LEDGER_STATE" == "closed" ]]; then
      STOP_REASON="queue drained (slice already closed)"
      EXIT_CODE=0
      break
    fi
    if [[ "$TOTAL_COUNT" -gt 0 && "$DONE_COUNT" == "$TOTAL_COUNT" && "$FAILED_COUNT" == "0" && -z "$INTERACTIVE_ONLY_TASKS" ]]; then
      DRAIN_MODE=1
      NEXT_TASK_ID="slice-drain"
      NEXT_TASK_AGENT="delivery-lead"
      NEXT_TASK_TIER="standard"
    else
      STOP_REASON="blocked: slice is open but no drive-eligible task remains in $LEDGER_PATH"
      [[ -n "$INTERACTIVE_ONLY_TASKS" ]] && STOP_REASON="$STOP_REASON; interactive-only tasks: $INTERACTIVE_ONLY_TASKS"
      EXIT_CODE=5
      break
    fi
  fi

  HAD_ANY_ITERATION=1
  PROCESSED_TASK_ID="$NEXT_TASK_ID"
  PROCESSED_TASK_AGENT="$NEXT_TASK_AGENT"
  PROCESSED_TASK_TIER="$NEXT_TASK_TIER"

  if [[ "${PRAXIS_CODEX_CLOSEOUT_REPAIR:-0}" == "1" ]]; then
    PROMPT="You are the Praxis Delivery Lead repairing closeout evidence for ${LEDGER_PATH}. Read .project/working/codex-active-index.json and the ledger closeout_evidence mapping. The controller found a closed state with missing or unverified evidence. In exactly one pass, produce only the missing legitimate review, tests, acceptance, and summary records; never invent a pass or overwrite a failing verdict. If evidence cannot be produced, change state back to draining or set a precise stop flag. Do not re-implement the slice."
  elif (( DRAIN_MODE == 1 )); then
    PROMPT="You are the Praxis Delivery Lead operating under the drive protocol (skills/autonomous-drive). The implementation tasks in ${LEDGER_PATH} are all done, but the slice is NOT closed. Execute exactly ONE slice-drain pass: launch one formal Code/UX/Security/QA review round for the integrated slice; on a blocker, return it to the owner and re-review only affected surfaces. Check acceptance and record evidence file paths under closeout_evidence for code_review, qa, tests, acceptance, summary and applicable security_review or visual_review. Set state: closed ONLY when the files exist and verdicts pass. Record local acceptance separately from integrated closure and release readiness. If a governance gate or human decision is required, set stop_flags honestly and stop. Do not claim queue drained while state is open."
  else
    PROMPT="You are the Praxis Delivery Lead operating under the drive protocol (skills/autonomous-drive). Read .project/working/codex-active-index.json, the task ledger at ${LEDGER_PATH}, and only the named task context. Execute exactly ONE drive iteration: take the next eligible task, inspect any partial work if its status is in_progress, complete it, run its focused verify command, update status/attempts, set stop_flags honestly. Do not launch formal Code/UX/Security/QA review while implementation tasks remain. Do not wait for user input."
  fi
'''
    if source.count(old) != 1:
        raise SystemExit("Codex runner overlay anchor changed; update the build patch")
    source = source.replace(old, new)

    # An interrupted controller may resume the one in-progress task after it
    # reacquires the project lock. The agent inspects partial artifacts first.
    anchor = '    open_count = len(open_tasks)\n'
    resume = '''    if next_task is None and os.environ.get("PRAXIS_CODEX_RESUME") == "1":
        next_task = next((t for t in tasks if t.get("status") == "in_progress"), None)

    open_count = len(open_tasks)
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner resume anchor changed")
    source = source.replace(anchor, resume)

    # A future governance review recorded as pending must not strand runnable
    # work. Reached gates and every other stop flag still block that lane.
    anchor = '  eval "$LEDGER_ENV"\n'
    if source.count(anchor) != 2:
        raise SystemExit("Codex runner ledger-stop anchors changed")
    filter_pending = '''  eval "$LEDGER_ENV"
  if [[ "${PRAXIS_CODEX_CONTROLLER:-0}" == "1" ]]; then
    LEDGER_STOP_FLAGS=",${LEDGER_STOP_FLAGS},"
    LEDGER_STOP_FLAGS="${LEDGER_STOP_FLAGS//,governance_gate_pending,/,}"
    LEDGER_STOP_FLAGS="${LEDGER_STOP_FLAGS#,}"
    LEDGER_STOP_FLAGS="${LEDGER_STOP_FLAGS%,}"
  fi
'''
    source = source.replace(anchor, filter_pending)

    # Resolve nested start directories before selecting governance or telemetry.
    anchor = 'export PRAXIS_HARNESS="$HARNESS"\n'
    root_check = '''export PRAXIS_HARNESS="$HARNESS"
if [[ "$HARNESS" == "codex" ]]; then
  if ! PROJECT_DIR="$(python3 "$SCRIPT_DIR/../hooks/project_root.py" --project-dir "$PROJECT_DIR" --require-agents --check-write)"; then
    echo "praxis-drive.sh: Codex project preflight failed before dispatch" >&2
    exit 2
  fi
  echo "praxis-drive: Codex project root $PROJECT_DIR"
fi
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner root-preflight anchor changed")
    source = source.replace(anchor, root_check)

    # codex exec defaults to a read-only sandbox; explicit workspace-write is
    # required for the delivery lead to update the ledger and implementation.
    anchor = 'if [[ -n "$MAX_ITERATIONS_OVERRIDE" ]]; then\n'
    sandbox = '''if [[ "$HARNESS" == "codex" && "$HARNESS_COMMAND" != *"--sandbox"* ]]; then
  HARNESS_COMMAND="$HARNESS_COMMAND --sandbox workspace-write"
fi

if [[ -n "$MAX_ITERATIONS_OVERRIDE" ]]; then
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner sandbox anchor changed")
    source = source.replace(anchor, sandbox)

    # Keep full JSONL for usage accounting, but show only concise live events
    # to avoid feeding large tool payloads back into the supervising context.
    for before, after in (
        ('eval "$cmd" > "$iter_stdout"',
         'eval "$cmd" | tee "$iter_stdout" | python3 "$SCRIPT_DIR/../hooks/codex_stream.py"'),
        ('      cat "$iter_stdout"\n', ''),
        ('eval "$CMD" > "$ITER_STDOUT"',
         'eval "$CMD" | tee "$ITER_STDOUT" | python3 "$SCRIPT_DIR/../hooks/codex_stream.py"'),
        ('    cat "$ITER_STDOUT"\n', ''),
    ):
        if source.count(before) != 1:
            raise SystemExit(f"Codex runner stream anchor changed: {before}")
        source = source.replace(before, after)

    # A small durable status file lets a resumed Codex session see the current
    # iteration without re-reading a large workflow document or raw JSONL.
    anchor = 'RUN_ID="drive-$(date -u +%Y%m%d-%H%M%S)"\n'
    checkpoint = '''codex_checkpoint() {
  python3 - "$PROJECT_DIR" "$RUN_ID" "$ITERATION" "$1" "$2" "$3" <<'PYCODEX'
import json, os, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
root, run_id, iteration, slice_id, task_id, status = sys.argv[1:]
target = Path(root) / ".project" / "telemetry" / "codex-drive-progress.json"
record = {"run_id": run_id, "iteration": int(iteration), "slice": slice_id,
          "task": task_id, "status": status,
          "updated_at": datetime.now(timezone.utc).isoformat()}
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                 prefix=".codex-progress-", delete=False) as out:
    json.dump(record, out)
    out.write("\\n")
    temporary = out.name
os.replace(temporary, target)
PYCODEX
}

RUN_ID="drive-$(date -u +%Y%m%d-%H%M%S)"
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner checkpoint anchor changed")
    source = source.replace(anchor, checkpoint)

    anchor = '  # Usage/cost fields default to null; only overwritten below when the\n'
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner iteration-start anchor changed")
    source = source.replace(anchor,
        '  codex_checkpoint "$LEDGER_SLICE" "$PROCESSED_TASK_ID" "running"\n\n' + anchor)
    anchor = '  # ---- Always-on stop checks (fire regardless of stop_after) ----\n'
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner iteration-end anchor changed")
    source = source.replace(anchor,
        '  codex_checkpoint "$LEDGER_SLICE" "$PROCESSED_TASK_ID" "$OUTCOME"\n\n' + anchor)
    anchor = '# --------------------------------------------------------------------------\n# Human summary\n# --------------------------------------------------------------------------\nREMAINING='
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner final checkpoint anchor changed")
    source = source.replace(anchor,
        'codex_checkpoint "$LAST_SLICE" "" "$STOP_REASON"\n\n' + anchor)

    # Local acceptance is a real milestone even when commit, joint QA or
    # release authorization is deliberately deferred. Do not claim closure.
    anchor = '    if [[ "$TOTAL_COUNT" -gt 0 && "$DONE_COUNT" == "$TOTAL_COUNT" && "$FAILED_COUNT" == "0" && -z "$INTERACTIVE_ONLY_TASKS" ]]; then\n'
    accepted = '''    if [[ "$TOTAL_COUNT" -gt 0 && "$DONE_COUNT" == "$TOTAL_COUNT" && "$FAILED_COUNT" == "0" ]] &&
       grep -Eq '^local_acceptance_met:[[:space:]]*true([[:space:]]|$)' "$LEDGER_PATH"; then
      STOP_REASON="local acceptance met ($LEDGER_SLICE); integrated closeout remains: $LEDGER_STATE"
      EXIT_CODE=0
      break
    fi
    if [[ "$TOTAL_COUNT" -gt 0 && "$DONE_COUNT" == "$TOTAL_COUNT" && "$FAILED_COUNT" == "0" && -z "$INTERACTIVE_ONLY_TASKS" ]]; then
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner acceptance anchor changed")
    source = source.replace(anchor, accepted)
    anchor = '  if [[ "$STOP_AFTER" == "task" ]]; then\n'
    if source.count(anchor) != 1:
        raise SystemExit("Codex runner one-iteration anchor changed")
    source = source.replace(anchor,
        '  if [[ "${PRAXIS_CODEX_ONE_ITERATION:-0}" == "1" ]]; then\n'
        '    STOP_REASON="controller iteration complete"\n'
        '    EXIT_CODE=0\n'
        '    break\n'
        '  fi\n\n' + anchor)
    # Workflow-drive's nested slice step uses the same Codex controller so
    # closeout verification and heartbeat also apply end to end.
    anchor = '''        bash "${BASH_SOURCE[0]}" "${NESTED_ARGS[@]}" || echo "praxis-drive.sh: nested slice-drive run for step $STEP_ID exited non-zero (evaluating step exit anyway)" >&2
'''
    nested = '''        if [[ "$HARNESS" == "codex" ]]; then
          CODEX_NESTED_ARGS=(--project-dir "$PROJECT_DIR" --slice "$SUB_ID")
          (( DRY_RUN == 1 )) && CODEX_NESTED_ARGS+=(--dry-run)
          python3 "$SCRIPT_DIR/codex_drive.py" "${CODEX_NESTED_ARGS[@]}" || echo "praxis-drive.sh: nested Codex controller for step $STEP_ID exited non-zero (evaluating step exit anyway)" >&2
        else
          bash "${BASH_SOURCE[0]}" "${NESTED_ARGS[@]}" || echo "praxis-drive.sh: nested slice-drive run for step $STEP_ID exited non-zero (evaluating step exit anyway)" >&2
        fi
'''
    if source.count(anchor) != 1:
        raise SystemExit("Codex workflow nested-runner anchor changed")
    source = source.replace(anchor, nested)
    runner.write_text(source)

# Codex supports SessionEnd as well as turn-scoped Stop. Keep the canonical
# SessionEnd tap and add Stop for in-session continuation and turn telemetry.
# tap.sh upserts by session id, so the two events cannot double-count.
hooks_json = out / "hooks" / "hooks.json"
if hooks_json.exists():
    data = json.loads(hooks_json.read_text())
    hooks = data.get("hooks", {})
    tap_cmd = 'TAP="${CLAUDE_PLUGIN_ROOT}/hooks/tap.sh"; [ -f "$TAP" ] && bash "$TAP" Stop || true'
    guard_cmd = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/codex-continuation.py" Stop'
    arm_cmd = 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/codex-continuation.py" UserPromptSubmit'
    hooks["Stop"] = [{"hooks": [
        {"type": "command", "command": tap_cmd},
        {"type": "command", "command": guard_cmd},
    ]}]
    hooks.setdefault("UserPromptSubmit", []).append({"hooks": [{"type": "command", "command": arm_cmd}]})
    # Env robustness for the MIRROR: the canonical commands resolve tap.sh via
    # ${CLAUDE_PLUGIN_ROOT}; if the Codex runtime exposes a different var the
    # [ -f "$TAP" ] guard silently no-ops every hook. Rewrite all commands to a
    # fallback chain so either var works.
    chain = "${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-}}"
    def _rewrite(node):
        if isinstance(node, dict):
            if isinstance(node.get("command"), str):
                node["command"] = node["command"].replace("${CLAUDE_PLUGIN_ROOT}", chain)
            for v in node.values():
                _rewrite(v)
        elif isinstance(node, list):
            for v in node:
                _rewrite(v)
    _rewrite(hooks)
    data["hooks"] = hooks
    hooks_json.write_text(json.dumps(data, indent=2) + "\n")

# Generated files (also part of the expected set).
manifest = out / ".codex-plugin" / "plugin.json"
manifest.write_text(json.dumps({
    "name": "praxis-codex",
    "version": "0.2.1",
    "description": "Praxis for Codex: agentic development platform for end-to-end software and product delivery.",
    "skills": "./codex-skills/",
    "hooks": "./hooks/hooks.json",
}, indent=2) + "\n")
record(manifest)
readme = out / "README.md"
readme.write_text(
    "# Praxis Codex Plugin\n\n"
    "**GENERATED PACKAGE — DO NOT EDIT. Edit the repository root and rebuild.**\n\n"
    "Generated package for installing Praxis as a Codex plugin.\n\n"
    "Source of truth lives at the repository root. Rebuild this package with:\n\n"
    "```bash\nscripts/build-codex-plugin.sh\n```\n"
)
record(readme)
marker = out / ".generated-by-praxis-codex-build"
marker.write_text("")
record(marker)

# Reconcile: remove any file in OUT this build did not produce. Fail loudly if
# a stale file cannot be removed — never silently ship an orphan.
stale = []
for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
    if p.is_file():
        if p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue  # bytecode is gitignored cruft, not a tracked orphan
        if p.relative_to(out).as_posix() not in expected:
            stale.append(p)
failed = []
for p in stale:
    try:
        p.unlink()
    except OSError:
        failed.append(p)
# Best-effort prune of now-empty directories (ignore failures — empty dirs are
# harmless; a leftover orphan FILE is the real hazard and is handled above).
for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
    if p.is_dir():
        try:
            next(p.iterdir())
        except StopIteration:
            try:
                p.rmdir()
            except OSError:
                pass
if failed:
    sys.stderr.write(
        "ERROR: build-codex-plugin cannot remove stale file(s) from the mirror "
        "on this filesystem; refusing to publish a dirty package. Rebuild on an "
        "unrestricted filesystem (pre-commit/CI does this). Offending files:\n"
        + "\n".join("  " + str(p) for p in failed) + "\n"
    )
    sys.exit(4)
PY

echo "Built Codex plugin package: $OUT"
