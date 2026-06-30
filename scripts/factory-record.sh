#!/usr/bin/env bash
# factory-record.sh — universal telemetry recorder for praxis plugin artifacts
#
# Writes a single telemetry file capturing the invocation of one artifact
# (skill, agent, workflow, command, hook, gate, or reference). Tool-agnostic:
# called from hooks (Claude Code), workflow steps (any tool), slash commands,
# or directly from any of the 8 supported coding tools.
#
# Usage:
#   factory-record.sh --type <type> --name <name> [options]
#
# Required:
#   --type     skill | agent | workflow | command | hook | gate | reference
#   --name     artifact name (e.g., requirements-intake, delivery-lead)
#
# Optional:
#   --tool         claude-code (default) | codex | cursor | gemini | opencode
#                  | copilot | kiro | antigravity
#   --trigger      auto-hook (default) | workflow-step | manual | slash-command
#                  | session-end | validator
#   --invocation   read (default) | spawn | fire | evaluate
#   --outcome      success | failure | partial | null (default: null)
#   --slice        current slice id (if applicable)
#   --agent        agent that invoked (if known)
#   --session      session id (auto-generated if not provided)
#   --observation  free-text observation (or path to a file containing it)
#   --duration     seconds spent (if measurable)
#   --mode         per-use (default) | aggregate-slice | auto-stub
#   --project-dir  project dir (default: CLAUDE_PROJECT_DIR or pwd)
#
# Output:
#   .project/operational/factory-metrics/<type>s/<name>/<date>-<rand>.md
#
# Exit codes:
#   0  success (file written)
#   1  bad args
#   2  filesystem error (non-fatal — hooks should still continue)

set -u

# --------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------
type=""
name=""
tool="claude-code"
trigger="auto-hook"
invocation="read"
outcome="null"
slice=""
agent=""
session=""
observation=""
duration=""
mode="per-use"
project_dir="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# --------------------------------------------------------------------
# Parse args
# --------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --type)         type="$2"; shift 2 ;;
    --name)         name="$2"; shift 2 ;;
    --tool)         tool="$2"; shift 2 ;;
    --trigger)      trigger="$2"; shift 2 ;;
    --invocation)   invocation="$2"; shift 2 ;;
    --outcome)      outcome="$2"; shift 2 ;;
    --slice)        slice="$2"; shift 2 ;;
    --agent)        agent="$2"; shift 2 ;;
    --session)      session="$2"; shift 2 ;;
    --observation)  observation="$2"; shift 2 ;;
    --duration)     duration="$2"; shift 2 ;;
    --mode)         mode="$2"; shift 2 ;;
    --project-dir)  project_dir="$2"; shift 2 ;;
    *)              echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# --------------------------------------------------------------------
# Validate
# --------------------------------------------------------------------
if [[ -z "$type" || -z "$name" ]]; then
  echo "factory-record.sh: --type and --name are required" >&2
  exit 1
fi

case "$type" in
  skill|agent|workflow|command|hook|gate|reference) ;;
  *) echo "factory-record.sh: invalid --type '$type'" >&2; exit 1 ;;
esac

# Sanitize name (no path traversal)
if [[ "$name" =~ [/\.\.[:space:]] ]]; then
  echo "factory-record.sh: invalid --name '$name'" >&2
  exit 1
fi

# --------------------------------------------------------------------
# Session id (read from arg, env, or generate)
# --------------------------------------------------------------------
if [[ -z "$session" ]]; then
  session="${CLAUDE_SESSION_ID:-$(date +%s)-$$}"
fi

# --------------------------------------------------------------------
# Build output path
# --------------------------------------------------------------------
metrics_root="$project_dir/.project/operational/factory-metrics"
artifact_dir="$metrics_root/${type}s/$name"

mkdir -p "$artifact_dir" 2>/dev/null || {
  echo "factory-record.sh: cannot create $artifact_dir" >&2
  exit 2
}

date_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
date_short=$(date -u +%Y-%m-%d)
rand=$(LC_ALL=C tr -dc 'a-z0-9' < /dev/urandom 2>/dev/null | head -c 6 || echo "$$")
out_file="$artifact_dir/${date_short}-${rand}.md"

# --------------------------------------------------------------------
# Dedup within session — ONLY for 'read' invocations.
#
# Why: when Claude re-reads the same SKILL.md multiple times in a long
# conversation, each Read fires a PostToolUse hook. Without dedup, we'd
# get N noisy 'read' entries that just mean "the conversation lasted a
# long time," not "this SKILL was used N times."
#
# All other invocations (apply, preload, invoke, spawn, complete, fire,
# evaluate) represent distinct events — every Write of a new ADR file is
# a separate application; every agent spawn is a separate event. Those
# we count. Dedup ONLY suppresses re-Read noise.
#
# Result: per-session usage frequency for any SKILL X =
#   1 (if Read at all) + count(apply) + count(preload) + count(invoke)
# All of which are tractable from the file count.
# --------------------------------------------------------------------
if [[ "$mode" == "auto-stub" && "$invocation" == "read" ]]; then
  dedup_dir="$project_dir/.project/working/.factory-tap"
  mkdir -p "$dedup_dir" 2>/dev/null || true
  dedup_file="$dedup_dir/$session"
  dedup_key="${type}:${name}:read"
  if [[ -f "$dedup_file" ]] && grep -qxF "$dedup_key" "$dedup_file"; then
    exit 0  # already recorded this read this session
  fi
  echo "$dedup_key" >> "$dedup_file"
fi

# --------------------------------------------------------------------
# Handle observation: if it's a path to a file, read it. Otherwise inline.
# --------------------------------------------------------------------
observation_body=""
if [[ -n "$observation" ]]; then
  if [[ -f "$observation" ]]; then
    observation_body=$(cat "$observation")
  else
    observation_body="$observation"
  fi
fi

# --------------------------------------------------------------------
# Look up artifact state (if known) for skills — read state: field
# from the SKILL.md body's metadata block. Best-effort.
# --------------------------------------------------------------------
artifact_state="unknown"
if [[ "$type" == "skill" ]]; then
  skill_file="$project_dir/skills/$name/SKILL.md"
  # Try plugin install cache locations if not found
  if [[ ! -f "$skill_file" ]] && [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
    skill_file="$CLAUDE_PLUGIN_ROOT/skills/$name/SKILL.md"
  fi
  if [[ -f "$skill_file" ]]; then
    artifact_state=$(grep -E "^state:" "$skill_file" 2>/dev/null | head -1 | awk '{print $2}' || echo "unknown")
    : "${artifact_state:=unknown}"
  fi
fi

# --------------------------------------------------------------------
# Write the file
# --------------------------------------------------------------------
{
  echo "---"
  echo "artifact_type: $type"
  echo "artifact_name: $name"
  echo "artifact_state: $artifact_state"
  echo "date: $date_iso"
  echo "session: $session"
  echo "tool: $tool"
  echo "trigger: $trigger"
  echo "invocation: $invocation"
  echo "outcome: $outcome"
  [[ -n "$slice" ]]    && echo "slice: $slice"
  [[ -n "$agent" ]]    && echo "agent: $agent"
  [[ -n "$duration" ]] && echo "duration_seconds: $duration"
  echo "mode: $mode"
  echo "---"
  echo ""
  if [[ -n "$observation_body" ]]; then
    echo "## Observation"
    echo ""
    echo "$observation_body"
  fi
} > "$out_file" 2>/dev/null || {
  echo "factory-record.sh: write failed to $out_file" >&2
  exit 2
}

# Stdout the path so callers can pipeline it
echo "$out_file"
exit 0
