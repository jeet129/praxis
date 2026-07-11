#!/usr/bin/env bash
# tap.sh — universal plugin-artifact tap for praxis
#
# Routes hook events to scripts/factory-record.sh based on which event fired
# and what the event's payload contains. Captures invocations of all praxis
# artifacts (skills, agents, workflows, commands, references) without
# requiring any change to the artifacts themselves.
#
# Invoked from hooks/hooks.json with the event name as argv[1]:
#   bash tap.sh PostToolUse
#   bash tap.sh UserPromptSubmit
#   bash tap.sh SubagentStart
#   bash tap.sh SubagentStop
#   bash tap.sh SessionStart       # delegates to session-start.sh
#
# This script reads the event's JSON payload from stdin (per Claude Code
# hook contract), extracts relevant fields, and calls factory-record.sh.
#
# Designed to fail soft — telemetry must NEVER break the user's workflow.
# All errors swallowed; exit 0 always (except for argument parse failures).

set -u

EVENT="${1:-PostToolUse}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
RECORDER="$PLUGIN_ROOT/scripts/factory-record.sh"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Telemetry must never break the user's session.
trap 'exit 0' ERR

# Bail if recorder is missing
if [[ ! -x "$RECORDER" ]]; then
  exit 0
fi

# Read stdin payload (Claude Code passes hook payload as JSON on stdin)
payload=$(cat 2>/dev/null || echo "{}")

# jq is required for payload parsing. Fall back silently if absent.
if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

# Extract common fields
session_id=$(echo "$payload" | jq -r '.session_id // empty' 2>/dev/null)

# Resolve the workspace root for telemetry writes.
# Priority:
#   1. CLAUDE_PROJECT_DIR — Claude Code sets this to the workspace root.
#      Always correct even when the tool ran from a subdirectory.
#   2. Walk up from payload.cwd to find a .project/ or .git/ marker.
#      This handles monorepo cases where payload.cwd is a service subdir
#      (e.g., services/java-core) — without the walk, telemetry would
#      create stray .project/ trees under each service subdir.
#   3. Fall back to payload.cwd as-is.
#   4. Last resort: $PROJECT_DIR (recorder's default: hook-caller pwd).
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
  cwd="$CLAUDE_PROJECT_DIR"
else
  payload_cwd=$(echo "$payload" | jq -r '.cwd // empty' 2>/dev/null)
  if [[ -n "$payload_cwd" ]]; then
    probe="$payload_cwd"
    cwd=""
    while [[ "$probe" != "/" && -n "$probe" ]]; do
      if [[ -d "$probe/.project" || -d "$probe/.git" ]]; then
        cwd="$probe"
        break
      fi
      probe=$(dirname "$probe")
    done
    [[ -z "$cwd" ]] && cwd="$payload_cwd"
  else
    cwd="$PROJECT_DIR"
  fi
fi

# --------------------------------------------------------------------
# Helper: record an artifact invocation
# --------------------------------------------------------------------
record() {
  local artifact_type="$1"
  local artifact_name="$2"
  local invocation="${3:-read}"
  local extra_arg="${4:-}"

  [[ -z "$artifact_name" ]] && return 0

  "$RECORDER" \
    --type        "$artifact_type" \
    --name        "$artifact_name" \
    --tool        claude-code \
    --trigger     auto-hook \
    --invocation  "$invocation" \
    --mode        auto-stub \
    --session     "$session_id" \
    --project-dir "$cwd" \
    $extra_arg \
    >/dev/null 2>&1 || true
}


# --------------------------------------------------------------------
# Helper: append a structured event to .project/telemetry/agent-spawns.jsonl
# This is the DETERMINISTIC half of routing telemetry: it captures what
# actually happened (spawn + model, completion + status/usage) regardless
# of whether the delivery-lead remembered to write its routing decision.
# --------------------------------------------------------------------
telemetry_event() {
  local json="$1"
  local tdir="$cwd/.project/telemetry"
  mkdir -p "$tdir" 2>/dev/null || return 0
  echo "$json" >> "$tdir/agent-spawns.jsonl" 2>/dev/null || true
}

# --------------------------------------------------------------------
# Helper: lookup output path against output-skill-map.txt
# Returns: skill name or empty if no match
# --------------------------------------------------------------------
lookup_output_skill() {
  local path="$1"
  local map="$PLUGIN_ROOT/hooks/output-skill-map.txt"
  [[ ! -f "$map" ]] && return 0

  # Read map, skip comments and blank lines, first-match-wins
  while IFS= read -r line; do
    # Strip trailing whitespace and comments
    line="${line%%#*}"
    line="$(echo "$line" | sed 's/[[:space:]]*$//')"
    [[ -z "$line" ]] && continue

    # Split on pipe
    local pattern="${line%%|*}"
    local skill="${line##*|}"
    pattern="$(echo "$pattern" | sed 's/[[:space:]]*$//' | sed 's/^[[:space:]]*//')"
    skill="$(echo "$skill" | sed 's/[[:space:]]*$//' | sed 's/^[[:space:]]*//')"

    [[ -z "$pattern" || -z "$skill" ]] && continue

    # shellcheck disable=SC2053
    if [[ "$path" == $pattern ]]; then
      echo "$skill"
      return 0
    fi
  done < "$map"
}

# --------------------------------------------------------------------
# Helper: lookup agent's canonical skills against agent-skill-map.txt
# Returns: comma-separated skill list or empty if no match
# --------------------------------------------------------------------
lookup_agent_skills() {
  local agent_name="$1"
  local map="$PLUGIN_ROOT/hooks/agent-skill-map.txt"
  [[ ! -f "$map" ]] && return 0

  while IFS= read -r line; do
    line="${line%%#*}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*$ ]] && continue
    local name="${line%%|*}"
    local skills="${line##*|}"
    name="$(echo "$name" | sed 's/[[:space:]]*$//' | sed 's/^[[:space:]]*//')"
    skills="$(echo "$skills" | sed 's/[[:space:]]*$//' | sed 's/^[[:space:]]*//')"
    if [[ "$name" == "$agent_name" ]]; then
      echo "$skills"
      return 0
    fi
  done < "$map"
}

# --------------------------------------------------------------------
# Helper: extract artifact name from a file path
# Returns: <type>:<name>  or empty if no match
# --------------------------------------------------------------------
classify_path() {
  local path="$1"
  case "$path" in
    */skills/*/SKILL.md)
      echo "skill:$(echo "$path" | sed -E 's|.*/skills/([^/]+)/SKILL\.md$|\1|')"
      ;;
    */workflows/*.yaml|*/workflows/*.yml)
      echo "workflow:$(echo "$path" | sed -E 's|.*/workflows/([^/]+)\.(yaml|yml)$|\1|')"
      ;;
    */agents/*.md)
      echo "agent:$(echo "$path" | sed -E 's|.*/agents/([^/]+)\.md$|\1|')"
      ;;
    */commands/*.md)
      echo "command:$(echo "$path" | sed -E 's|.*/commands/([^/]+)\.md$|\1|')"
      ;;
    */references/*.md)
      echo "reference:$(echo "$path" | sed -E 's|.*/references/([^/]+)\.md$|\1|')"
      ;;
    */governance/governance.yaml)
      echo "gate:governance-snapshot"
      ;;
    *)
      echo ""
      ;;
  esac
}

# --------------------------------------------------------------------
# Event-specific routing
# --------------------------------------------------------------------
case "$EVENT" in

  PostToolUse)
    tool_name=$(echo "$payload" | jq -r '.tool_name // empty' 2>/dev/null)

    case "$tool_name" in
      Read)
        # Retired: per-Read usage stubs. Reading a SKILL.md is not applying it,
        # plugin-injected skills never surface as Reads, and the stubs produced
        # misleading near-zero usage data. Usage analytics now derive from
        # checkpoint records + packets/ledgers/routing (see
        # references/factory-metrics-schema.md "Checkpoint records").
        ;;
      Task)
        # Sub-agent spawn: tool_input.subagent_type carries the agent name.
        # The Task tool is also called for non-agent purposes; only record
        # if subagent_type is present.
        subagent=$(echo "$payload" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
        if [[ -n "$subagent" && "$subagent" != "null" ]]; then
          record agent "$subagent" spawn
          # Structured spawn event with the resolved model (if the spawner
          # passed one; empty means the agent frontmatter default applied).
          spawn_model=$(echo "$payload" | jq -r '.tool_input.model // empty' 2>/dev/null)
          telemetry_event "$(jq -cn \
            --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
            --arg session "$session_id" \
            --arg agent "$subagent" \
            --arg model "$spawn_model" \
            '{ts:$ts, event:"spawn", session:$session, agent:$agent, model:(if $model=="" then null else $model end)}')"
          # Retired: per-spawn preload stub fan-out (N files per spawn saying
          # only "this agent exists"). Skill consumption is now derived from
          # checkpoint records and packets/ledgers, which record ACTUAL use.
        fi
        ;;
      Write|Edit|NotebookEdit)
        # Layer 2: output-artifact detection.
        # When Claude writes a file, infer which SKILL was applied based on
        # the output path. Catches cached uses where the SKILL.md wasn't
        # re-Read but its discipline was applied.
        file_path=$(echo "$payload" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
        if [[ -n "$file_path" ]]; then
          inferred_skill=$(lookup_output_skill "$file_path")
          if [[ -n "$inferred_skill" ]]; then
            record skill "$inferred_skill" apply
          fi
        fi
        ;;
    esac
    ;;

  UserPromptSubmit)
    # Detect slash-command invocations.
    # Plugin commands surface as /<plugin>:<command> in autocomplete; user
    # commands as /<command>. We log both — the recorded name preserves the
    # exact form so we can see whether users invoke commands directly or
    # via the plugin prefix.
    prompt=$(echo "$payload" | jq -r '.prompt // empty' 2>/dev/null)
    # Match leading "/<word>:<word>" or "/<word>"
    if [[ "$prompt" =~ ^[[:space:]]*/([a-zA-Z][a-zA-Z0-9_.-]*)(:([a-zA-Z][a-zA-Z0-9_.-]*))?([[:space:]]|$) ]]; then
      cmd="${BASH_REMATCH[1]}"
      sub="${BASH_REMATCH[3]:-}"

      # If the prefix is "praxis", it's a plugin artifact (command or skill)
      if [[ "$cmd" == "praxis" && -n "$sub" ]]; then
        record command "$sub" invoke
      elif [[ -z "$sub" ]]; then
        # Bare command — could be ours or a built-in. Record as command;
        # the steward can filter known-built-ins at synthesis time.
        # Only record if a command file exists under our plugin root.
        if [[ -f "$PLUGIN_ROOT/commands/$cmd.md" ]]; then
          record command "$cmd" invoke
        fi
      fi
    fi
    ;;

  SubagentStart)
    # Native event — fires when any sub-agent starts.
    # Payload contains the subagent's name/type.
    subagent=$(echo "$payload" | jq -r '.subagent_type // .agent_name // .agent // empty' 2>/dev/null)
    if [[ -n "$subagent" ]]; then
      record agent "$subagent" spawn
    fi
    ;;

  SubagentStop)
    # Optional: record completion outcome.
    # The payload should include the subagent's name and result status.
    subagent=$(echo "$payload" | jq -r '.subagent_type // .agent_name // .agent // empty' 2>/dev/null)
    status=$(echo "$payload" | jq -r '.status // .outcome // "unknown"' 2>/dev/null)
    if [[ -n "$subagent" ]]; then
      # Structured completion event; includes token usage when the harness
      # provides it in the payload (fields are null otherwise).
      in_tok=$(echo "$payload" | jq -r '.usage.input_tokens // .usage.prompt_tokens // empty' 2>/dev/null)
      out_tok=$(echo "$payload" | jq -r '.usage.output_tokens // .usage.completion_tokens // empty' 2>/dev/null)
      telemetry_event "$(jq -cn \
        --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg session "$session_id" \
        --arg agent "$subagent" \
        --arg status "$status" \
        --arg itok "$in_tok" \
        --arg otok "$out_tok" \
        '{ts:$ts, event:"complete", session:$session, agent:$agent, status:$status,
          input_tokens:(if $itok=="" then null else ($itok|tonumber) end),
          output_tokens:(if $otok=="" then null else ($otok|tonumber) end)}')"
      "$RECORDER" \
        --type        agent \
        --name        "$subagent" \
        --tool        claude-code \
        --trigger     auto-hook \
        --invocation  complete \
        --outcome     "$status" \
        --mode        per-use \
        --session     "$session_id" \
        --project-dir "$cwd" \
        >/dev/null 2>&1 || true
    fi
    ;;

  SessionStart)
    # Delegate to the existing SessionStart script
    bash "$PLUGIN_ROOT/hooks/session-start.sh" 2>/dev/null || true
    # Session boundary as a single JSONL line (was: one stub .md per fire)
    tdir="$cwd/.project/telemetry"
    mkdir -p "$tdir" 2>/dev/null && \
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"session_start\",\"session\":\"$session_id\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
    ;;

  SessionEnd)
    tdir="$cwd/.project/telemetry"
    mkdir -p "$tdir" 2>/dev/null && \
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"session_end\",\"session\":\"$session_id\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
    ;;

esac

exit 0
