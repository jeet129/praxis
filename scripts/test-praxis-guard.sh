#!/usr/bin/env bash
# Contract tests for hooks/praxis_guard.py (kill switch, read-only reviewers,
# evidence store, verify freeze, evidence gate, stop audit, steering, agy goal
# continuation) and scripts/praxis-verify.py. No model calls.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G="$ROOT/hooks/praxis_guard.py"
V="$ROOT/scripts/praxis-verify.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL: $1"; echo "      got: $2"; }
expect()   { case "$2" in *"$3"*) ok ;; *) bad "$1" "$2" ;; esac; }
expect_no(){ case "$2" in *"$3"*) bad "$1" "$2" ;; *) ok ;; esac; }
run() { printf '%s' "$2" | env -u PRAXIS_NESTED -u PRAXIS_ALLOW_LEGACY_EVIDENCE python3 "$G" $1; }
verify() { (cd "$P" && env -u PRAXIS_NESTED python3 "$V" "$@" >/dev/null 2>&1); }

P="$T/proj"; W="$P/.project/working"; mkdir -p "$W"
L="$W/slice-001-tasks.yaml"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
CMD="true"
ledger() { cat > "$L" <<Y
slice: "001"
tasks:
  - id: T1
    title: first
    verify: "$CMD"
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
VS="$P/.project/operational/verification"

# ── evidence gate: Claude Code ──
edit=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'status: in_progress','new_string':'status: done'}}")
expect "claude: done without a run is denied" "$(run 'pretool --harness claude-code' "$edit")" '"permissionDecision": "deny"'
expect "claude: deny names the runner" "$(run 'pretool --harness claude-code' "$edit")" 'praxis-verify T1'
echo "1 passed" > "$W/verify-T1.log"; echo 0 > "$W/verify-T1.exit"
expect "claude: hand-written log is not evidence" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
expect_no "legacy evidence accepted only when allowed" "$(printf '%s' "$edit" | PRAXIS_ALLOW_LEGACY_EVIDENCE=1 python3 "$G" pretool --harness claude-code)" 'deny'
rm -f "$W"/verify-T1.*
CMD="exit 1"; ledger in_progress null; verify T1
expect "claude: failing run is denied" "$(run 'pretool --harness claude-code' "$edit")" 'exited 1'
CMD="true"; ledger in_progress null
expect "claude: run of an older command is denied" "$(run 'pretool --harness claude-code' "$edit")" 'verify command changed'
verify T1
expect_no "claude: passing run of the current command is allowed" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
[ -n "$(ls "$P/.project/local/evidence/T1/"*/output.log 2>/dev/null)" ] && ok || bad "runner keeps the full log in local/evidence" "missing"
t2=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'status: open','new_string':'status: done'}}")
expect_no "claude: verify:null task is exempt" "$(run 'pretool --harness claude-code' "$t2")" 'deny'
other=$(j "{'cwd':'$P','tool_name':'Write','tool_input':{'file_path':'$P/src/a.py','content':'status: done'}}")
expect_no "claude: non-ledger file is ignored" "$(run 'pretool --harness claude-code' "$other")" 'deny'
rm -rf "$VS"
expect_no "warn mode does not deny" "$(printf '%s' "$edit" | PRAXIS_EVIDENCE_GATE=warn python3 "$G" pretool --harness claude-code)" 'deny'
expect_no "nested helper session is never gated" "$(printf '%s' "$edit" | PRAXIS_NESTED=1 python3 "$G" pretool --harness claude-code)" 'deny'

# ── evidence store is written only by the runner ──
fake=$(j "{'cwd':'$P','tool_name':'Write','tool_input':{'file_path':'$VS/T1--x.json','content':'{}'}}")
expect "claude: writing a summary by hand is denied" "$(run 'pretool --harness claude-code' "$fake")" 'EVIDENCE STORE'
sh1=$(j "{'cwd':'$P','tool_name':'Bash','tool_input':{'command':'echo {} > .project/operational/verification/T1--x.json'}}")
expect "claude: shell write into the store is denied" "$(run 'pretool --harness claude-code' "$sh1")" 'EVIDENCE STORE'
sh2=$(j "{'cwd':'$P','tool_name':'Bash','tool_input':{'command':'cat .project/operational/verification/T1--x.json'}}")
expect_no "claude: reading the store is allowed" "$(run 'pretool --harness claude-code' "$sh2")" 'deny'
sh3=$(j "{'cwd':'$P','tool_name':'Bash','tool_input':{'command':'.project/local/bin/praxis-verify T1 > /tmp/out'}}")
expect_no "claude: the runner itself is allowed" "$(run 'pretool --harness claude-code' "$sh3")" 'deny'
sh4=$(j "{'workspacePaths':['$P'],'toolCall':{'name':'run_command','args':{'CommandLine':'cp x .project/local/evidence/T1/r/output.log'}}}")
expect "agy: shell write into the store is denied" "$(run 'pretool --harness antigravity' "$sh4")" '"decision": "deny"'

# ── verify freeze ──
CMD="true"; ledger in_progress null
fz=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'verify: \"true\"','new_string':'verify: \"echo ok\"'}}")
expect "claude: changing a started task's verify is denied" "$(run 'pretool --harness claude-code' "$fz")" 'VERIFY FREEZE'
fzr=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'verify: \"true\"','new_string':'verify: \"pytest -q tests/x.py\"\n    verify_changed_reason: \"wrong test path\"'}}")
expect_no "claude: a change with verify_changed_reason is allowed" "$(run 'pretool --harness claude-code' "$fzr")" 'deny'
ledger open null
fzo=$(j "{'cwd':'$P','tool_name':'Edit','tool_input':{'file_path':'$L','old_string':'verify: \"true\"','new_string':'verify: \"echo ok\"'}}")
expect_no "claude: an unstarted task's verify may change" "$(run 'pretool --harness claude-code' "$fzo")" 'deny'
ledger in_progress null

# ── evidence gate: Codex apply_patch ──
patch="*** Begin Patch
*** Update File: $L
@@
     verify: \"true\"
-    status: in_progress
+    status: done
*** End Patch"
cx=$(PATCH="$patch" python3 -c "import json,os;print(json.dumps({'cwd':'$P','tool_name':'apply_patch','tool_input':{'command':os.environ['PATCH']}}))")
expect "codex: done without a run is denied" "$(run 'pretool --harness codex' "$cx")" '"permissionDecision": "deny"'
verify T1
expect_no "codex: done with a passing run is allowed" "$(run 'pretool --harness codex' "$cx")" 'deny'
cxs="*** Begin Patch
*** Add File: src/x.py
+a
*** Add File: .project/operational/verification/T1--y.json
+{}
*** End Patch"
cx2=$(PATCH="$cxs" python3 -c "import json,os;print(json.dumps({'cwd':'$P','tool_name':'apply_patch','tool_input':{'command':os.environ['PATCH']}}))")
expect "codex: a patch touching the store is denied" "$(run 'pretool --harness codex' "$cx2")" 'EVIDENCE STORE'
rm -rf "$VS"

# ── evidence gate: Antigravity ──
after=$(sed 's/status: in_progress/status: done/' "$L")
ag=$(AFTER="$after" python3 -c "import json,os;print(json.dumps({'workspacePaths':['$P'],'toolCall':{'name':'write_to_file','args':{'TargetFile':'$L','CodeContent':os.environ['AFTER']}}}))")
expect "agy: done without a run is denied" "$(run 'pretool --harness antigravity' "$ag")" '"decision": "deny"'
agok=$(j "{'workspacePaths':['$P'],'toolCall':{'name':'view_file','args':{'AbsolutePath':'$L'}}}")
expect "agy: other tools are allowed" "$(run 'pretool --harness antigravity' "$agok")" '"decision": "allow"'

# ── repeated task ids across slices: evidence is scoped to the ledger ──
L2="$W/slice-002-tasks.yaml"
printf 'slice: "002"\ntasks:\n  - id: T1\n    verify: "true"\n    status: done\n' > "$L2"
ledger in_progress null
rm -rf "$VS"
(cd "$P" && env -u PRAXIS_NESTED python3 "$V" T1 --ledger "$L2" >/dev/null 2>&1)
expect "a run for another slice's T1 does not count" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
verify T1
expect_no "the runner picks the active ledger for a shared id" "$(run 'pretool --harness claude-code' "$edit")" 'deny'
rm -f "$L2"; rm -rf "$VS"

# ── freshness: a run against older code is rejected (git projects) ──
GP="$T/gproj"; mkdir -p "$GP/.project/working" "$GP/src"
( cd "$GP" && git init -q && git config user.email t@t && git config user.name t
  echo 'a=1' > src/a.py
  printf 'slice: "g"\ntasks:\n  - id: G1\n    verify: "true"\n    status: in_progress\n' > .project/working/slice-g-tasks.yaml
  git add -A && git commit -qm init )
GL="$GP/.project/working/slice-g-tasks.yaml"
gedit=$(j "{'cwd':'$GP','tool_name':'Edit','tool_input':{'file_path':'$GL','old_string':'status: in_progress','new_string':'status: done'}}")
(cd "$GP" && env -u PRAXIS_NESTED python3 "$V" G1 >/dev/null 2>&1)
expect_no "fresh run on unchanged code is allowed" "$(run 'pretool --harness claude-code' "$gedit")" 'deny'
echo 'a=2' > "$GP/src/a.py"
expect "code changed after the run is denied" "$(run 'pretool --harness claude-code' "$gedit")" 'code changed'
expect_no "freshness can be switched off" "$(printf '%s' "$gedit" | PRAXIS_EVIDENCE_FRESHNESS=off python3 "$G" pretool --harness claude-code)" 'deny'

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
verify T1
s3=$(j "{'cwd':'$P','session_id':'s3'}")
expect_no "stop: passing run on record, no block" "$(run 'stop --harness claude-code' "$s3")" 'block'

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
