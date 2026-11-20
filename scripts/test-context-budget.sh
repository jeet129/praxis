#!/usr/bin/env bash
# Contract tests for the context budget: in-session drive hand-off (Claude Code,
# Antigravity via praxis_guard.py; Codex via codex-continuation.py), transcript
# size estimate, autonomy.yaml parsing, per-tier --max-turns and the per-task
# context alert in praxis-drive.sh, maxTurns in agent frontmatter, and
# praxis-memory context-setup. No model calls.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="$ROOT/hooks/praxis_guard.py"; PPY="$ROOT/hooks/praxis_project.py"; M="$ROOT/scripts/praxis-memory.py"
CC="$ROOT/codex-plugin-assets/hooks/codex-continuation.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL: $1"; echo "      got: $2"; }
expect()   { case "$2" in *"$3"*) ok ;; *) bad "$1" "$2" ;; esac; }
expect_no(){ case "$2" in *"$3"*) bad "$1" "$2" ;; *) ok ;; esac; }
run() { printf '%s' "$2" | env -u PRAXIS_NESTED python3 "$G" $1; }
j() { python3 -c 'import json,sys; print(json.dumps(eval(sys.argv[1])))' "$1"; }
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

P="$T/p"; W="$P/.project/working"; mkdir -p "$W" "$P/.project/governance"
ledger() {  # $1 = number of tasks done now; one open task always remains
  { echo 'slice: "001"'; echo 'state: open'; echo 'tasks:'
    for i in $(seq 1 "$1"); do printf '  - id: D%s\n    verify: null\n    status: done\n    completed_at: %s\n' "$i" "$NOW"; done
    printf '  - id: OPEN1\n    verify: null\n    status: open\n'; } > "$W/slice-001-tasks.yaml"
}

# ── autonomy.yaml parsing ──
cat > "$P/.project/governance/autonomy.yaml" <<'Y'
run_budget:
  max_iterations_per_run: 40
context_budget:
  max_turns_by_tier:
    deep: 41
    standard: 31
    light: 21
  iteration_alert_tokens: 123000
  session_max_tasks: 2
  session_max_context_tokens: 1000
Y
cb=$(python3 -c "import sys; sys.path.insert(0,'$ROOT/hooks'); import praxis_project as p; print(p.context_budget('$P'))")
expect "per-tier turns parsed" "$cb" "'max_turns_deep': 41"
expect "session tasks parsed" "$cb" "'session_max_tasks': 2"
expect "env overrides yaml" "$(PRAXIS_SESSION_MAX_TASKS=7 python3 -c "import sys; sys.path.insert(0,'$ROOT/hooks'); import praxis_project as p; print(p.context_budget('$P')['session_max_tasks'])")" '7'
expect "default mode is continue" "$cb" "'on_session_budget': 'continue'"

# ── Default (continue): never stops, hints once per budget step ──
cat > "$P/.project/governance/autonomy.yaml" <<'Y'
context_budget:
  session_max_tasks: 2
  session_max_context_tokens: 0
Y
ledger 0; touch "$W/.drive-active"; sleep 1
sc=$(j "{'cwd':'$P','session_id':'cont1'}")
out=$(run 'stop --harness claude-code' "$sc")
expect "under budget: continues" "$out" 'OPEN1'
expect_no "under budget: no hint" "$out" 'systemMessage'
expect "continuation briefs a fresh subagent" "$out" 'fresh specialist subagent'
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 2
out=$(run 'stop --harness claude-code' "$sc")
expect "at the budget step: still continues" "$out" '"decision": "block"'
expect "at the budget step: hint for the person" "$out" 'good moment to start a fresh session'
out=$(run 'stop --harness claude-code' "$sc")
expect "hint shown once per step" "$out" 'OPEN1'
expect_no "no repeat at the same step" "$out" 'systemMessage'
[ -e "$W/.drive-active" ] && ok || bad "drive stays armed in continue mode" "marker removed"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 4
expect "hint again at the next step" "$(run 'stop --harness claude-code' "$sc")" '4 tasks finished'
ag0=$(j "{'workspacePaths':['$P'],'conversationId':'agc'}")
expect "agy continue mode keeps going" "$(run 'stop --harness antigravity' "$ag0")" '"decision": "continue"'
expect "agy logs the hint" "$(cat "$P/.project/telemetry/guard.jsonl")" 'context_hint'

cat > "$P/.project/governance/autonomy.yaml" <<'Y'
context_budget:
  on_session_budget: ask
  session_max_tasks: 2
  session_max_context_tokens: 0
Y

# ── ask mode, Claude Code: hand-off after N finished tasks ──
ledger 1; touch "$W/.drive-active"; sleep 1
st=$(j "{'cwd':'$P','session_id':'s1'}")
expect "under the task budget the drive continues" "$(run 'stop --harness claude-code' "$st")" 'OPEN1'
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 2
out=$(run 'stop --harness claude-code' "$st")
expect "at the task budget the agent is asked to hand off" "$out" 'PRAXIS CONTEXT BUDGET'
expect "hand-off asks for task notes" "$out" 'notes:'
out=$(run 'stop --harness claude-code' "$st")
expect "next stop ends the drive with a notice" "$out" 'systemMessage'
[ ! -e "$W/.drive-active" ] && ok || bad "drive marker removed after hand-off" "still there"
expect_no "after hand-off nothing continues" "$(run 'stop --harness claude-code' "$st")" 'block'

# ── transcript size estimate ──
python3 - "$T/big.jsonl" "$T/compacted.jsonl" <<'PY'
import sys
line = '{"type":"assistant","message":{"content":"' + "x" * 1000 + '"}}\n'
open(sys.argv[1], "w").write(line * 2000)                     # ~2 MB -> ~400k tokens
open(sys.argv[2], "w").write(line * 2000 + '{"type":"system","subtype":"compact_boundary"}\n' + line * 10)
PY
est=$(python3 -c "import sys; sys.path.insert(0,'$ROOT/hooks'); import praxis_project as p; print(p.transcript_tokens('$T/big.jsonl'), p.transcript_tokens('$T/compacted.jsonl'))")
set -- $est
[ "$1" -gt 300000 ] && [ "$2" -lt 5000 ] && ok || bad "estimate counts only what follows the last compaction" "$est"
cat > "$P/.project/governance/autonomy.yaml" <<'Y'
context_budget:
  on_session_budget: ask
  session_max_tasks: 0
  session_max_context_tokens: 300000
Y
ledger 0; touch "$W/.drive-active"
s2=$(j "{'cwd':'$P','session_id':'s2','transcript_path':'$T/big.jsonl'}")
expect "large transcript triggers a hand-off" "$(run 'stop --harness claude-code' "$s2")" 'session context is about'
rm -f "$P/.project/telemetry/.handoff-s2"; touch "$W/.drive-active"
s3=$(j "{'cwd':'$P','session_id':'s3','transcript_path':'$T/compacted.jsonl'}")
expect "compacted transcript does not" "$(run 'stop --harness claude-code' "$s3")" 'OPEN1'

# ── Antigravity ──
cat > "$P/.project/governance/autonomy.yaml" <<'Y'
context_budget:
  on_session_budget: ask
  session_max_tasks: 1
Y
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; touch "$W/.drive-active"; sleep 1; NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 1
ag=$(j "{'workspacePaths':['$P'],'conversationId':'c9'}")
expect "agy: hand-off continues once with the request" "$(run 'stop --harness antigravity' "$ag")" 'PRAXIS CONTEXT BUDGET'
expect "agy: then stops with a reason" "$(run 'stop --harness antigravity' "$ag")" '"decision": "stop"'

# ── Codex continuation ──
rm -f "$W/.drive-active"
arm=$(j "{'cwd':'$P','session_id':'cx1','prompt':'\$praxis-drive continue'}")
printf '%s' "$arm" | python3 "$CC" UserPromptSubmit >/dev/null
sleep 1; NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 1
cst=$(j "{'cwd':'$P','session_id':'cx1'}")
expect "codex: hand-off requested at the budget" "$(printf '%s' "$cst" | python3 "$CC" Stop)" 'PRAXIS CONTEXT BUDGET'
expect "codex: next stop ends the drive" "$(printf '%s' "$cst" | python3 "$CC" Stop)" '{}'
cat > "$P/.project/governance/autonomy.yaml" <<'Y'
context_budget:
  session_max_tasks: 1
Y
arm2=$(j "{'cwd':'$P','session_id':'cx2','prompt':'\$praxis-drive go'}")
printf '%s' "$arm2" | python3 "$CC" UserPromptSubmit >/dev/null
sleep 1; NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; ledger 1
cst2=$(j "{'cwd':'$P','session_id':'cx2'}")
out=$(printf '%s' "$cst2" | python3 "$CC" Stop)
expect "codex continue mode: keeps driving" "$out" '"decision": "block"'
expect "codex continue mode: hint via systemMessage" "$out" 'systemMessage'
expect "codex continuation briefs a fresh subagent" "$out" 'spawn_agent'

# ── praxis-drive.sh: per-tier --max-turns and the context alert ──
D="$T/drive"; mkdir -p "$D/.project/working" "$D/.project/governance" "$T/bin"
cat > "$D/.project/working/slice-T1-tasks.yaml" <<'Y'
slice: T1
packet: .project/working/slice-T1-packet.md
tasks:
  - id: T1-1
    summary: "fixture"
    agent: backend-developer
    tier: deep
    ac: ["x"]
    verify: "true"
    depends_on: []
    status: open
    attempts: 0
    notes: ""
gates:
  code_review: pending
state: open
stop_flags: []
Y
cat > "$T/bin/claude" <<'SH'
#!/bin/sh
echo "$@" >> "$STUB_ARGS"
echo '{"type":"result","usage":{"input_tokens":10,"output_tokens":5,"cache_read_input_tokens":2500000,"cache_creation_input_tokens":0},"total_cost_usd":1.0}'
SH
chmod +x "$T/bin/claude"
STUB_ARGS="$T/args" PATH="$T/bin:$PATH" bash "$ROOT/scripts/praxis-drive.sh" --project-dir "$D" --max-iterations 1 >"$T/drive.out" 2>&1
expect "deep task runs with the deep turn cap" "$(cat "$T/args" 2>/dev/null)" '--max-turns 40'
expect "an over-budget task is flagged" "$(cat "$T/drive.out")" 'context budget: task T1-1'
expect "and logged" "$(cat "$D/.project/telemetry/budget-alerts.jsonl" 2>/dev/null)" '"context_tokens":2500010'

# ── maxTurns written from the routing table ──
expect "deep agent has maxTurns 80" "$(sed -n '1,12p' "$ROOT/agents/architecture-challenger.md")" 'maxTurns: 80'
expect "light agent has maxTurns 30" "$(sed -n '1,12p' "$ROOT/agents/tech-writer.md")" 'maxTurns: 30'
[ -d "$ROOT/plugins/praxis-antigravity/agents" ] && { expect_no "agy agents drop maxTurns" "$(cat "$ROOT"/plugins/praxis-antigravity/agents/*.md)" 'maxTurns'; }

# ── context-setup ──
C="$T/c"; mkdir -p "$C/.project"; printf '# Project\n\nRules.\n' > "$C/CLAUDE.md"
mkdir -p "$C/.codex"; printf '[profiles.x]\nmodel = "m"\n' > "$C/.codex/config.toml"
dry=$(cd "$C" && python3 "$M" context-setup)
expect "dry run lists both files" "$dry" '.codex/config.toml'
expect_no "dry run writes nothing" "$(cat "$C/CLAUDE.md")" 'Compact instructions'
(cd "$C" && python3 "$M" context-setup --apply >/dev/null)
expect "CLAUDE.md gets the managed block" "$(cat "$C/CLAUDE.md")" '# Compact instructions'
head -1 "$C/.codex/config.toml" | grep -q 'praxis-managed' && ok || bad "codex block goes before any [table]" "$(head -3 "$C/.codex/config.toml")"
if python3 -c "import tomllib" 2>/dev/null; then   # Python 3.11+
  python3 -c "import tomllib; d=tomllib.load(open('$C/.codex/config.toml','rb')); assert 'compact_prompt' in d and 'profiles' in d" 2>/dev/null \
    && ok || bad "config.toml still parses with compact_prompt at top level" "$(cat "$C/.codex/config.toml")"
fi
(cd "$C" && python3 "$M" context-setup --apply >/dev/null)
[ "$(grep -c 'praxis:compact:begin' "$C/CLAUDE.md")" = 1 ] && ok || bad "idempotent" "$(cat "$C/CLAUDE.md")"
expect_no "map stops nagging once set" "$(python3 "$PPY" map "$C")" 'no compaction instructions'

echo "context-budget tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
