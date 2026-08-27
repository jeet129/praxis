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
PLUGIN_ROOT="${PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}}"
RECORDER="$PLUGIN_ROOT/scripts/factory-record.sh"
# Preserve any caller-supplied PROJECT_DIR/CODEX_PROJECT_DIR BEFORE we set our
# own last-resort default below — used as an explicit fallback in the cwd
# priority chain further down.
EXPLICIT_PROJECT_DIR="${PROJECT_DIR:-${CODEX_PROJECT_DIR:-}}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${PROJECT_DIR:-$(pwd)}}"

# Harness detection — which tool is invoking this hook. Defaults to
# claude-code; flips to codex when Codex-specific env vars are present or
# the plugin root path itself is under a codex install. Explicit override
# via PRAXIS_TAP_TOOL always wins (set by tests/harnesses that need to force
# a value).
TAP_TOOL="claude-code"
if [[ -n "${CODEX_HOME:-}" || -n "${CODEX_SESSION_ID:-}" || "$PLUGIN_ROOT" == *codex* ]]; then
  TAP_TOOL="codex"
fi
TAP_TOOL="${PRAXIS_TAP_TOOL:-$TAP_TOOL}"

# Telemetry must never break the user's session.
trap 'exit 0' ERR

# Bail if recorder is missing
if [[ ! -x "$RECORDER" ]]; then
  exit 0
fi

# Read stdin payload (Claude Code passes hook payload as JSON on stdin)
payload=$(cat 2>/dev/null || echo "{}")

# jq is required for payload parsing of tool events — but SessionStart/End
# (governance seeding, session logging) must work WITHOUT jq: degrade the
# session id instead of dying, and only bail on jq-dependent events.
HAVE_JQ=1
command -v jq >/dev/null 2>&1 || HAVE_JQ=0

if [[ $HAVE_JQ -eq 1 ]]; then
  session_id=$(echo "$payload" | jq -r '.session_id // .sessionId // .id // empty' 2>/dev/null)
else
  session_id="nojq-$(date +%s)"
  case "$EVENT" in
    SessionStart|SessionEnd) : ;;   # proceed — these branches don't need jq
    *) exit 0 ;;                    # tool-event parsing needs jq; bail soft
  esac
fi

# Resolve the workspace root for telemetry writes.
# Priority:
#   1. CLAUDE_PROJECT_DIR — Claude Code sets this to the workspace root.
#      Always correct even when the tool ran from a subdirectory.
#   2. PROJECT_DIR / CODEX_PROJECT_DIR — same idea, generic/Codex-style env
#      vars a harness or wrapper may set instead of CLAUDE_PROJECT_DIR.
#   3. Walk up from payload.cwd to find a .project/ or .git/ marker.
#      This handles monorepo cases where payload.cwd is a service subdir
#      (e.g., services/java-core) — without the walk, telemetry would
#      create stray .project/ trees under each service subdir.
#   4. Fall back to payload.cwd as-is.
#   5. Last resort: $PROJECT_DIR (recorder's default: hook-caller pwd).
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
  cwd="$CLAUDE_PROJECT_DIR"
elif [[ -n "$EXPLICIT_PROJECT_DIR" ]]; then
  cwd="$EXPLICIT_PROJECT_DIR"
else
  payload_cwd=""
  [[ $HAVE_JQ -eq 1 ]] && payload_cwd=$(echo "$payload" | jq -r '.cwd // empty' 2>/dev/null)
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
    --tool        "$TAP_TOOL" \
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

  PreToolUse)
    # Cache-aware routing guard (INTERACTIVE path). Before a sub-agent spawns,
    # run the pre-flight and DENY a cache-forfeiting model-DOWN with a corrective
    # instruction, so the model re-issues the spawn with the effort-down
    # model/effort. Deterministic enforcement — no human, and no explicit call
    # from the agent. claude-code only (codex effort-only tiers cannot forfeit a
    # separate model cache). Fail-open: any missing field / error just allows.
    tool_name=$(echo "$payload" | jq -r '.tool_name // empty' 2>/dev/null)
    if [[ "$tool_name" == "Task" && "$TAP_TOOL" == "claude-code" ]]; then
      pf_script="$PLUGIN_ROOT/scripts/routing-preflight.py"
      sub=$(echo "$payload" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null); sub="${sub#praxis:}"
      spawn_model=$(echo "$payload" | jq -r '.tool_input.model // empty' 2>/dev/null)
      # to_tier from the pinned model, else the agent's frontmatter capability_tier
      to_tier=""
      case "$spawn_model" in
        *opus*)   to_tier=deep ;;
        *sonnet*) to_tier=standard ;;
        *haiku*)  to_tier=light ;;
      esac
      if [[ -z "$to_tier" && -n "$sub" && -f "$PLUGIN_ROOT/agents/${sub}.md" ]]; then
        to_tier=$(grep -m1 -E '^capability_tier:' "$PLUGIN_ROOT/agents/${sub}.md" 2>/dev/null | sed -E 's/^[^:]*: *//; s/ *$//' || true)
      fi
      warm_file="$cwd/.project/telemetry/.warm-tier-${session_id}"
      from_tier=$(head -1 "$warm_file" 2>/dev/null || true)
      if [[ -n "$to_tier" && -n "$from_tier" && "$to_tier" != "$from_tier" && -f "$pf_script" ]]; then
        # this call also APPENDS the routing_preflight audit record to model-routing.jsonl
        # device routing-preflight.py emits a JSON record on stdout (and also
        # appends it to model-routing.jsonl); read the verdict from that JSON.
        pf_json=$(python3 "$pf_script" --from-tier "$from_tier" --to-tier "$to_tier" \
               --project-dir "$cwd" \
               --session "$session_id" --agent "${sub:-unknown}" 2>/dev/null | tail -1 || true)
        action=$(printf '%s' "$pf_json" | jq -r '.action // empty' 2>/dev/null || true)
        if [[ "$action" == "enforce_effort_down" ]]; then
          pmodel=$(printf '%s' "$pf_json" | jq -r '.applied.model // empty' 2>/dev/null || true)
          peffort=$(printf '%s' "$pf_json" | jq -r '.applied.effort // empty' 2>/dev/null || true)
          reason="Cache-aware routing (praxis, enforce mode): spawning ${sub:-this agent} on '${spawn_model:-$to_tier}' (${to_tier} tier) would forfeit the warm ${from_tier}-tier prompt cache. Switching model family cold-writes the whole prefix on the new model and loses the ~10x-cheaper cache reads on the bulk of the tokens; a one-off down-route never reuses the prefix enough to pay that back. Re-spawn KEEPING the warm model and lowering effort instead: set model='${pmodel}' and effort='${peffort}'. Do not switch the model family down mid-session."
          jq -cn --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
          exit 0
        fi
      fi
      # allow: record this spawn's tier as the new warm tier (best-effort)
      if [[ -n "$to_tier" ]]; then
        mkdir -p "$cwd/.project/telemetry" 2>/dev/null && printf '%s\n' "$to_tier" > "$warm_file" 2>/dev/null || true
      fi
    fi
    ;;

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
          # Correlation for the next SubagentStop, whose payload omits the name.
          _atdir="$cwd/.project/telemetry"; mkdir -p "$_atdir" 2>/dev/null || true
          printf '%s\n' "$subagent" > "$_atdir/.token-agent-${session_id}" 2>/dev/null || true
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
    subagent=$(echo "$payload" | jq -r '.subagent_type // .agent_name // .agent // empty' 2>/dev/null); subagent="${subagent#praxis:}"
    if [[ -n "$subagent" ]]; then
      record agent "$subagent" spawn
    fi
    ;;

  SubagentStop)
    # Optional: record completion outcome.
    # The payload should include the subagent's name and result status.
    subagent=$(echo "$payload" | jq -r '.subagent_type // .agent_name // .agent // empty' 2>/dev/null); subagent="${subagent#praxis:}"
    # Claude Code's SubagentStop payload omits the agent name; fall back to the
    # last subagent recorded at Task-spawn. Transcript extraction in the miner
    # below takes precedence when a Task tool_use is present in the delta.
    if [[ -z "$subagent" ]]; then
      # NB: a missing .token-agent file makes head exit 1, which trips the
      # `trap 'exit 0' ERR` above and silently skips the whole miner — guard
      # with || true so a missing stash just yields an empty fallback.
      subagent=$(head -1 "$cwd/.project/telemetry/.token-agent-${session_id}" 2>/dev/null || true); subagent="${subagent#praxis:}"
    fi
    status=$(echo "$payload" | jq -r '.status // .outcome // "unknown"' 2>/dev/null)

    # LIVE per-invocation token delta: sum the usage lines the session
    # transcript gained since the last cursor position and attribute the
    # delta to the subagent that just finished. Deterministic, zero model
    # tokens. Honest caveat encoded in the record: when subagents ran
    # concurrently since the last event, the delta spans all of them
    # (concurrent: true) — exact per-agent split needs sidechain mining.
    if [[ -n "$session_id" && "$session_id" != nojq-* ]]; then
      transcript=""
      if [[ -d "$HOME/.claude/projects" ]]; then
        transcript=$(find "$HOME/.claude/projects" -maxdepth 2 -name "${session_id}*.jsonl" 2>/dev/null | head -1)
      fi
      if [[ -z "$transcript" && -d "$HOME/.codex/sessions" ]]; then
        transcript=$(find "$HOME/.codex/sessions" -maxdepth 4 -name "*${session_id}*.jsonl" 2>/dev/null | head -1)
      fi
      if [[ -n "$transcript" ]]; then
        tdir="$cwd/.project/telemetry"
        mkdir -p "$tdir" 2>/dev/null || true
        python3 - "$transcript" "$tdir/.token-cursor-${session_id}" "$subagent" "$session_id" >> "$tdir/agent-spawns.jsonl" 2>/dev/null <<'PYEOF' || true
import json, os, sys, datetime
path, cursor_path, passed_agent, sid = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    offset = int(open(cursor_path).read().strip())
except Exception:
    offset = 0
FIELDS = ("input_tokens","output_tokens","cache_read_input_tokens","cache_creation_input_tokens","reasoning_output_tokens")
tot = {k:0 for k in FIELDS}
by_model = {}

def _extract_usage(d):
    if not isinstance(d, dict):
        return {}
    # Claude Code: message.usage
    u = (d.get("message") or {}).get("usage")
    if isinstance(u, dict) and u:
        return u
    # Codex CLI: event_msg -> payload.info.last_token_usage (per-turn delta;
    # total_token_usage is the cumulative session running total -- do NOT sum that).
    info = (d.get("payload") or {}).get("info")
    if isinstance(info, dict):
        lu = info.get("last_token_usage")
        if isinstance(lu, dict) and lu:
            mapped = dict(lu)
            if "cached_input_tokens" in mapped:
                mapped["cache_read_input_tokens"] = mapped.pop("cached_input_tokens")
            return mapped
    # Other shapes: top-level usage / turn.completed / payload.usage
    u = d.get("usage")
    if isinstance(u, dict) and u:
        if d.get("type") == "turn.completed":
            mapped = dict(u)
            if "cached_input_tokens" in mapped:
                mapped["cache_read_input_tokens"] = mapped.pop("cached_input_tokens")
            return mapped
        return u
    u = (d.get("payload") or {}).get("usage")
    if isinstance(u, dict) and u:
        return u
    return {}

def _extract_model(d):
    if not isinstance(d, dict):
        return None
    m = (d.get("message") or {}).get("model")
    if m:
        return m
    m = d.get("model")
    if m:
        return m
    return (d.get("payload") or {}).get("model") or None


def _extract_agent(d):
    # Claude Code: an assistant turn spawns a subagent via a Task tool_use whose
    # input.subagent_type names it. That block appears in this delta before the
    # spawned agent's turns, so the last one seen labels the delta.
    if not isinstance(d, dict):
        return None
    msg = d.get("message")
    content = msg.get("content") if isinstance(msg, dict) else d.get("content")
    if isinstance(content, list):
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") == "Task":
                st = (blk.get("input") or {}).get("subagent_type")
                if isinstance(st, str) and st:
                    return st.split(":")[-1]
    return None


def _session_model(path):
    # Codex stamps the model in an early turn_context event, not on usage rows.
    # Scan the transcript head so those rows can still bucket under the real model.
    try:
        with open(path) as fh:
            for _ in range(120):
                ln = fh.readline()
                if not ln:
                    break
                try:
                    m = _extract_model(json.loads(ln))
                except Exception:
                    continue
                if m:
                    return m
    except Exception:
        pass
    return None

current_model = _session_model(path)
current_agent = None
new_offset = offset
try:
    size = os.path.getsize(path)
    if size < offset:
        offset = 0
    with open(path) as f:
        f.seek(offset)
        chunk = f.read()
        new_offset = f.tell()
        for line in chunk.splitlines():
            try:
                d = json.loads(line)
            except Exception:
                continue
            m = _extract_model(d)
            if m:
                current_model = m
            a = _extract_agent(d)
            if a:
                current_agent = a
            u = _extract_usage(d)
            if not u:
                continue
            model = m or current_model or "unknown"
            bucket = by_model.setdefault(model, {k: 0 for k in FIELDS})
            for k in FIELDS:
                v = u.get(k)
                if isinstance(v, (int, float)):
                    tot[k] += int(v)
                    bucket[k] += int(v)
except Exception:
    sys.exit(0)
try:
    with open(cursor_path, "w") as c:
        c.write(str(new_offset))
except Exception:
    pass
if sum(tot.values()) == 0:
    sys.exit(0)
by_model = {m: b for m, b in by_model.items() if sum(b.values()) > 0}
agent = current_agent or passed_agent or "unknown"
rec = {"ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
       "event": "invocation_usage", "session": sid,
       "agent": agent, **tot,
       "by_model": by_model,
       "note": "delta since previous cursor; spans concurrent subagents if any. agent = the subagent whose Stop triggered this capture (from the Task spawn in the delta, else last-spawned fallback), not necessarily the sole consumer. by_model splits the delta by transcript model (exact; cache-cost attributable per tier)"}
print(json.dumps(rec))
PYEOF
      fi
    fi
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
        --tool        "$TAP_TOOL" \
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

  SessionEnd|Stop)
    # `SessionEnd` is Claude Code's end-of-session event; `Stop` is Codex's
    # end-of-turn/exec event (the drive runner invokes `codex exec`, one Stop
    # per run). Both route here so end-of-session token capture works on BOTH
    # harnesses. Capture is an UPSERT keyed by session id (see the python
    # below), so if the event fires more than once for a session the total is
    # refreshed in place rather than duplicated — no double-count.
    tdir="$cwd/.project/telemetry"
    mkdir -p "$tdir" 2>/dev/null && \
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"session_end\",\"session\":\"$session_id\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
    HAVE_TRANSCRIPT_STORE=0
    [[ -d "$HOME/.claude/projects" || -d "$HOME/.codex/sessions" ]] && HAVE_TRANSCRIPT_STORE=1
    if [[ "$session_id" == nojq-* ]]; then
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"token_capture_skipped\",\"session\":\"$session_id\",\"reason\":\"jq_missing_no_session_id\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
    elif [[ $HAVE_TRANSCRIPT_STORE -eq 0 ]]; then
      echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"token_capture_skipped\",\"session\":\"$session_id\",\"reason\":\"no_claude_projects_dir\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
    fi
    rm -f "$cwd/.project/telemetry/.token-cursor-${session_id}" 2>/dev/null || true
    rm -f "$cwd/.project/telemetry/.token-agent-${session_id}" 2>/dev/null || true
    rm -f "$cwd/.project/telemetry/.warm-tier-${session_id}" 2>/dev/null || true
    # Universal token capture: sum this session's usage from its own session
    # transcript (found by session id — layout-agnostic, checked under both
    # Claude Code's ~/.claude/projects and Codex's ~/.codex/sessions stores)
    # and append one line to tokens.jsonl. Deterministic, zero model tokens;
    # works for EVERY session — interactive slices, discovery, architecture —
    # not just drive.
    if [[ -n "$session_id" && "$session_id" != nojq-* && $HAVE_TRANSCRIPT_STORE -eq 1 ]]; then
      transcript=""
      if [[ -d "$HOME/.claude/projects" ]]; then
        transcript=$(find "$HOME/.claude/projects" -maxdepth 2 -name "${session_id}*.jsonl" 2>/dev/null | head -1)
      fi
      if [[ -z "$transcript" && -d "$HOME/.codex/sessions" ]]; then
        transcript=$(find "$HOME/.codex/sessions" -maxdepth 4 -name "*${session_id}*.jsonl" 2>/dev/null | head -1)
      fi
      if [[ -z "$transcript" ]]; then
        # Telemetry failures must be observable: leave a breadcrumb instead of silence.
        echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"token_capture_skipped\",\"session\":\"$session_id\",\"reason\":\"transcript_not_found_under_claude_or_codex_stores\"}" >> "$tdir/sessions.jsonl" 2>/dev/null || true
      fi
      if [[ -n "$transcript" ]]; then
        python3 - "$transcript" "$session_id" "$tdir/tokens.jsonl" 2>/dev/null <<'PYEOF' || true
import json, sys, datetime, os
path, sid = sys.argv[1], sys.argv[2]
tokens_path = sys.argv[3] if len(sys.argv) > 3 else None
tot = {"input_tokens":0,"output_tokens":0,"cache_read_input_tokens":0,"cache_creation_input_tokens":0}
models = {}

def _extract_usage(d):
    """Tolerant of multiple transcript shapes: Claude Code's
    message.usage, a top-level usage, payload.usage, or Codex
    type:turn.completed events (input_tokens/cached_input_tokens/
    output_tokens, with cached_input_tokens mapped to
    cache_read_input_tokens)."""
    if not isinstance(d, dict):
        return {}, None
    msg = d.get("message") or {}
    u = msg.get("usage")
    if isinstance(u, dict) and u:
        return u, msg.get("model")
    u = d.get("usage")
    if isinstance(u, dict) and u:
        if d.get("type") == "turn.completed":
            mapped = dict(u)
            if "cached_input_tokens" in mapped:
                mapped["cache_read_input_tokens"] = mapped.pop("cached_input_tokens")
            return mapped, d.get("model")
        return u, d.get("model")
    u = (d.get("payload") or {}).get("usage")
    if isinstance(u, dict) and u:
        return u, (d.get("payload") or {}).get("model")
    return {}, None

try:
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            u, m = _extract_usage(d)
            if not u:
                continue
            for k in tot:
                v = u.get(k)
                if isinstance(v, (int, float)):
                    tot[k] += int(v)
            if m:
                models[m] = models.get(m, 0) + int(u.get("output_tokens") or 0)
except Exception:
    sys.exit(0)
if sum(tot.values()) == 0:
    sys.exit(0)
rec = {"ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
       "session": sid, "source": "session_end_hook", **tot,
       "models_by_output": models}
line = json.dumps(rec)
# UPSERT keyed by (session, source): keep exactly one session_end_hook line per
# session so a repeated end-event (e.g. codex firing Stop more than once)
# refreshes the running total in place instead of appending a duplicate the
# report scripts would double-count. Falls back to append if no path was given.
if tokens_path:
    kept = []
    if os.path.exists(tokens_path):
        with open(tokens_path) as tf:
            for ln in tf:
                s = ln.strip()
                if not s:
                    continue
                try:
                    o = json.loads(s)
                except Exception:
                    kept.append(s)      # preserve unparseable lines untouched
                    continue
                if o.get("session") == sid and o.get("source") == "session_end_hook":
                    continue            # drop the prior total for this session
                kept.append(s)
    kept.append(line)
    with open(tokens_path, "w") as tf:
        tf.write("\n".join(kept) + "\n")
else:
    print(line)
PYEOF
      fi
    fi
    # Codex's `Stop` hook "expects JSON on stdout when it exits 0; plain text is
    # invalid." Emit an empty JSON object: valid, and (crucially) WITHOUT a
    # `decision: block` — which would tell Codex to auto-continue the turn. This
    # only fires for Codex `Stop`; Claude's `SessionEnd` writes nothing to
    # stdout (unchanged). All the capture above goes to files, not stdout.
    [[ "$EVENT" == "Stop" ]] && printf '{}\n'
    ;;

esac

exit 0
