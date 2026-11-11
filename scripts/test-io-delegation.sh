#!/usr/bin/env bash
# test-io-delegation.sh — contract tests for the IO-delegation hooks.
# Feeds sample hook payloads to each hook and asserts the decision and the
# exact output shape each harness accepts. No model is called.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0; pass=0
ok()  { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL: $1"; }
export CLAUDE_PLUGIN_ROOT="$ROOT"; unset PRAXIS_NESTED PRAXIS_IO_DELEGATE_DISABLED PRAXIS_IO_DELEGATE_MIN_LINES

mkdir -p "$T/src" "$T/.project/working"
seq 1 400 | sed 's/^/const x = /' > "$T/src/big.ts"
seq 1 50  | sed 's/^/const x = /' > "$T/src/small.ts"
seq 1 400 > "$T/src/NOTES.md"
seq 1 400 > "$T/.project/working/ledger.ts"

read_hook() { printf '%s' "$1" | bash "$ROOT/hooks/io-delegate-read.sh"; }
bash_hook() { printf '%s' "$1" | bash "$ROOT/hooks/io-delegate-bash.sh"; }
agy_hook()  { printf '%s' "$1" | PLUGIN_ROOT="$ROOT" python3 -I "$ROOT/antigravity-plugin-assets/hooks/io-delegate-read-agy.py"; }
is_claude_deny() { python3 -c '
import json,sys
d=json.loads(sys.argv[1]); h=d["hookSpecificOutput"]
assert set(d)=={"hookSpecificOutput"}, "no top-level decision allowed"
assert h["hookEventName"]=="PreToolUse" and h["permissionDecision"]=="deny"
assert "bulk-read.sh" in h["permissionDecisionReason"] and "offset" in h["permissionDecisionReason"]
' "$1" 2>/dev/null; }

p() { printf '{"session_id":"s1","cwd":"%s","tool_name":"Read","tool_input":%s}' "$T" "$1"; }
out=$(read_hook "$(p "{\"file_path\":\"$T/src/big.ts\"}")");            is_claude_deny "$out" && ok || bad "Read big file should deny in documented shape: $out"
out=$(read_hook "$(p "{\"file_path\":\"$T/src/small.ts\"}")");          [[ -z "$out" ]] && ok || bad "Read small file should allow"
out=$(read_hook "$(p "{\"file_path\":\"$T/src/big.ts\",\"offset\":10,\"limit\":40}")"); [[ -z "$out" ]] && ok || bad "targeted Read should allow"
out=$(read_hook "$(p "{\"file_path\":\"$T/src/NOTES.md\"}")");          [[ -z "$out" ]] && ok || bad "Markdown should never be blocked"
out=$(read_hook "$(p "{\"file_path\":\"$T/.project/working/ledger.ts\"}")"); [[ -z "$out" ]] && ok || bad ".project files should never be blocked"
out=$(read_hook "$(p "{\"file_path\":\"$ROOT/hooks/tap.sh\"}")");       [[ -z "$out" ]] && ok || bad "plugin files should never be blocked"
out=$(PRAXIS_IO_DELEGATE_DISABLED=1 read_hook "$(p "{\"file_path\":\"$T/src/big.ts\"}")"); [[ -z "$out" ]] && ok || bad "disabled flag should allow"
out=$(read_hook 'not json');                                             [[ -z "$out" ]] && ok || bad "garbage payload should fail open"
grep -q '"reason": "targeted_reread"' "$T/.project/telemetry/io-delegation.jsonl" && ok || bad "re-read of a blocked file should be logged"

b() { printf '{"session_id":"s1","cwd":"%s","tool_name":"Bash","tool_input":{"command":"%s"}}' "$T" "$1"; }
out=$(bash_hook "$(b "cat $T/src/big.ts")");            is_claude_deny "$out" && ok || bad "cat big file should deny: $out"
out=$(bash_hook "$(b "cat -n src/big.ts")");            is_claude_deny "$out" && ok || bad "relative cat should deny"
out=$(bash_hook "$(b "cat $T/src/big.ts | grep x")");   [[ -z "$out" ]] && ok || bad "piped cat should allow"
out=$(bash_hook "$(b "head -20 $T/src/big.ts")");       [[ -z "$out" ]] && ok || bad "bounded head should allow"
out=$(bash_hook "$(b "head -n 380 $T/src/big.ts")");    is_claude_deny "$out" && ok || bad "head beyond threshold should deny"
out=$(bash_hook "$(b "cat $T/src/small.ts")");          [[ -z "$out" ]] && ok || bad "cat small file should allow"
out=$(bash_hook "$(b "npm test")");                     [[ -z "$out" ]] && ok || bad "unrelated command should allow"

a() { printf '{"conversationId":"c1","workspacePaths":["%s"],"toolCall":{"name":"%s","args":%s}}' "$T" "$1" "$2"; }
dec() { python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("decision",""))' "$1" 2>/dev/null; }
out=$(agy_hook "$(a view_file "{\"AbsolutePath\":\"$T/src/big.ts\"}")");   [[ "$(dec "$out")" == deny ]] && [[ "$out" == *bulk-read.sh* ]] && ok || bad "agy view_file big should deny: $out"
out=$(agy_hook "$(a view_file "{\"AbsolutePath\":\"$T/src/big.ts\",\"StartLine\":1,\"EndLine\":80}")"); [[ "$(dec "$out")" == allow ]] && ok || bad "agy ranged view should allow"
out=$(agy_hook "$(a view_file "{\"AbsolutePath\":\"$T/src/small.ts\"}")"); [[ "$(dec "$out")" == allow ]] && ok || bad "agy small should allow"
out=$(agy_hook "$(a run_command "{\"CommandLine\":\"ls\"}")");            [[ "$(dec "$out")" == allow ]] && ok || bad "agy other tool should allow"
out=$(agy_hook 'garbage');                                                 [[ "$(dec "$out")" == allow ]] && ok || bad "agy garbage should allow"

out=$(bash "$ROOT/skills/io-delegation/scripts/bulk-read.sh" --paths "$T/src/big.ts" 2>&1); [[ $? -ne 0 && "$out" == *question* ]] && ok || bad "bulk-read needs --question"
out=$(bash "$ROOT/skills/io-delegation/scripts/bulk-read.sh" --question q --paths "$T/nope" 2>&1); [[ $? -ne 0 ]] && ok || bad "bulk-read rejects missing file"

echo "io-delegation tests: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
