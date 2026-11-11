#!/usr/bin/env bash
# Contract tests for hooks/praxis_guard.py (kill switch, read-only reviewers,
# evidence gate, stop audit, steering, agy goal continuation). No model calls.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="$ROOT/hooks/praxis_guard.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL: $1"; echo "      got: $2"; }
expect()   { case "$2" in *"$3"*) ok ;; *) bad "$1" "$2" ;; esac; }
expect_no(){ case "$2" in *"$3"*) bad "$1" "$2" ;; *) ok ;; esac; }
run() { printf '%s' "$2" | env -u PRAXIS_NESTED python3 "$G" $1; }

P="$T/proj"; W="$P/.project/working"; mkdir -p "$W"
L="$W/slice-001-tasks.yaml"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ledger() { cat > "$L" <<Y
slice: "001"
tasks:
  - id: T1
    title: first
    verify: "pytest -q > .project/working/verify-T1.log 2>&1"
    status: $1
    completed_at: $2
  - id: T2
    title: human checked
    verify: null
    status: open
Y
}
ledger in_progress null
j() { python3 -c 'import json,sys; print(json.dumps(eval(sys.argv[1])))' "$1"; }

# ── evidence gate: Claude Code ──
edit=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'status: in_progress','new_string':'status: done'}}")
expect "claude: done without evidence is denied" "$(run 'pretool --harness claude-code' "$edit")" '"permissionDecision": "deny"'
echo "1 passed" > "$W/verify-T1.log"
expect_no "claude: done with log is allowed" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
echo 1 > "$W/verify-T1.exit"
expect "claude: non-zero exit file is denied" "$(run 'pretool --harness claude-code' "$edit")" 'exit code 1'
echo 0 > "$W/verify-T1.exit"
expect_no "claude: exit 0 is allowed" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
rm -f "$W"/verify-T1.*
t2=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'status: open','new_string':'status: done'}}")
expect_no "claude: verify:null task is exempt" "$(run 'pretool --harness claude-code' "$t2")" 'deny'
other=$(j "{'cwd':'$P','tool_name':'Write','tool_input':{'file_path':'$P/src/a.py','content':'status: done'}}")
expect_no "claude: non-ledger file is ignored" "$(run 'pretool --harness claude-code' "$other")" 'deny'
expect_no "warn mode does not deny" "$(printf '%s' "$edit" | PRAXIS_EVIDENCE_GATE=warn python3 "$G" pretool --harness claude-code)" 'deny'
expect_no "nested helper session is never gated" "$(printf '%s' "$edit" | PRAXIS_NESTED=1 python3 "$G" pretool --harness claude-code)" 'deny'

# ── evidence gate: Codex apply_patch ──
patch="*** Begin Patch
*** Update File: $L
@@
     verify: \"pytest -q > .project/working/verify-T1.log 2>&1\"
-    status: in_progress
+    status: done
*** End Patch"
cx=$(PATCH="$patch" python3 -c "import json,os;print(json.dumps({'cwd':'$P','tool_name':'apply_patch','tool_input':{'command':os.environ['PATCH']}}))")
expect "codex: done without evidence is denied" "$(run 'pretool --harness codex' "$cx")" '"permissionDecision": "deny"'
echo ok > "$W/verify-T1.log"
expect_no "codex: done with evidence is allowed" "$(run 'pretool --harness codex' "$cx")" 'deny'
rm -f "$W"/verify-T1.*

# ── evidence gate: Antigravity ──
after=$(sed 's/status: in_progress/status: done/' "$L")
ag=$(AFTER="$after" python3 -c "import json,os;print(json.dumps({'workspacePaths':['$P'],'toolCall':{'name':'write_to_file','args':{'TargetFile':'$L','CodeContent':os.environ['AFTER']}}}))")
expect "agy: done without evidence is denied" "$(run 'pretool --harness antigravity' "$ag")" '"decision": "deny"'
agok=$(j "{'workspacePaths':['$P'],'toolCall':{'name':'view_file','args':{'AbsolutePath':'$L'}}}")
expect "agy: other tools are allowed" "$(run 'pretool --harness antigravity' "$agok")" '"decision": "allow"'

# ── read-only reviewers ──
rv=$(j "{'cwd':'$P','agent_type':'praxis:code-reviewer','tool_name':'Write','tool_input':{'file_path':'$P/src/a.py','content':'x'}}")
expect "claude: reviewer edit is denied" "$(run 'pretool --harness claude-code' "$rv")" 'read-only reviewer'
rc=$(j "{'cwd':'$P','agent_type':'security-reviewer','tool_name':'apply_patch','tool_input':{'command':'*** Begin Patch\n*** Add File: x\n+hi\n*** End Patch'}}")
expect "codex: reviewer apply_patch is denied" "$(run 'pretool --harness codex' "$rc")" 'read-only reviewer'
dv=$(j "{'cwd':'$P','agent_type':'backend-developer','tool_name':'Write','tool_input':{'file_path':'$P/src/a.py','content':'x'}}")
expect_no "developer edit is allowed" "$(run 'pretool --harness claude-code' "$dv")" 'deny'

# ── kill switch ──
touch "$P/.project/STOP"
rd=$(j "{'cwd':'$P/.project','tool_name':'Read','tool_input':{'file_path':'$L'}}")
expect "kill switch denies any tool (found from a subdir)" "$(run 'pretool --harness claude-code' "$rd")" 'KILL SWITCH'
expect "kill switch denies on agy" "$(run 'pretool --harness antigravity' "$agok")" '"decision": "deny"'
rm -f "$P/.project/STOP"
expect_no "no kill switch, no deny" "$(run 'pretool --harness claude-code' "$rd")" 'deny'

# ── stop audit ──
ledger done "$NOW"
st=$(j "{'cwd':'$P','session_id':'s1'}")
expect "stop: done without evidence blocks" "$(run 'stop --harness claude-code' "$st")" '"decision": "block"'
expect "stop: second round still blocks" "$(run 'stop --harness codex' "$st")" '"decision": "block"'
expect_no "stop: third round gives up (no infinite loop)" "$(run 'stop --harness claude-code' "$st")" 'block'
sa=$(j "{'cwd':'$P','session_id':'s2','stop_hook_active':True}")
expect_no "stop: stop_hook_active is respected" "$(run 'stop --harness claude-code' "$sa")" 'block'
ags=$(j "{'workspacePaths':['$P'],'conversationId':'c1'}")
expect "agy stop: continue on missing evidence" "$(run 'stop --harness antigravity' "$ags")" '"decision": "continue"'
echo ok > "$W/verify-T1.log"
s3=$(j "{'cwd':'$P','session_id':'s3'}")
expect_no "stop: evidence present, no block" "$(run 'stop --harness claude-code' "$s3")" 'block'

# ── agy goal continuation ──
ag2=$(j "{'workspacePaths':['$P'],'conversationId':'c2'}")
expect "agy: no drive marker, stops" "$(run 'stop --harness antigravity' "$ag2")" '"decision": "stop"'
echo 001 > "$W/.drive-active"
expect "agy: drive active with open task continues" "$(run 'stop --harness antigravity' "$ag2")" 'T2 (open)'
expect "agy: continuation budget is honoured" "$(printf '%s' "$ag2" | PRAXIS_GOAL_MAX_CONTINUES=1 python3 "$G" stop --harness antigravity)" '"decision": "stop"'
expect "claude: armed drive continues too" "$(run 'stop --harness claude-code' "$s3")" 'T2 (open)'
sc=$(j "{'cwd':'$P','session_id':'s9','stop_hook_active':True}")
expect "claude: continues on a continuation turn (bounded)" "$(run 'stop --harness claude-code' "$sc")" '"decision": "block"'
expect_no "claude: continuation budget is honoured" "$(printf '%s' "$sc" | PRAXIS_GOAL_MAX_CONTINUES=1 python3 "$G" stop --harness claude-code)" 'block'
expect_no "codex: guard leaves continuation to codex-continuation.py" "$(run 'stop --harness codex' "$s3")" 'block'
expect_no "unattended runner owns its own loop" "$(printf '%s' "$s3" | PRAXIS_DRIVE_RUNNER=1 python3 "$G" stop --harness claude-code)" 'block'
touch "$P/.project/STOP"
expect_no "kill switch beats an armed drive" "$(run 'stop --harness claude-code' "$s3")" 'block'
rm -f "$P/.project/STOP"
rm -f "$W/.drive-active"
expect_no "disarmed drive stops" "$(run 'stop --harness claude-code' "$s3")" 'block'

# ── steering ──
echo "Skip the export feature; fix login first." > "$P/.project/STEER.md"
up=$(j "{'cwd':'$P','hook_event_name':'UserPromptSubmit'}")
expect "steer: note is injected" "$(run 'steer --harness claude-code' "$up")" 'fix login first'
expect_no "steer: note is delivered once" "$(run 'steer --harness claude-code' "$up")" 'fix login first'
[ -n "$(ls "$P/.project"/STEER.delivered-*.md 2>/dev/null)" ] && ok || bad "steer: note archived" "missing"
echo "agy note" > "$P/.project/STEER.md"
expect "steer: agy uses injectSteps" "$(run 'steer --harness antigravity' "$ag2")" 'injectSteps'

# ── fail-open ──
expect_no "garbage payload allows" "$(run 'pretool --harness claude-code' 'not json')" 'deny'
expect "garbage payload allows on agy" "$(run 'pretool --harness antigravity' 'not json')" '"decision": "allow"'

echo "praxis-guard tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
