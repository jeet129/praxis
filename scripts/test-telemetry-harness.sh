#!/usr/bin/env bash
# Regression test for the canonical harness-tagged telemetry schema.
#
# Verifies, with NO live agy/Claude/Codex session required:
#   1. The agy hooks.json commands write canonical-envelope rows to the right
#      streams (model-routing.jsonl, sessions.jsonl, antigravity-activity.jsonl)
#      and never touch pre-existing Claude/Codex rows.
#   2. routing-preflight.py stamps `harness` (from --harness and from env).
#   3. The praxis-drive.sh helper stamps `harness` on drive.jsonl rows.
#   4. The three factory-*-report.py consumers EXCLUDE foreign-harness rows
#      (agy) from Claude/Codex aggregations instead of miscounting/crashing.
#
# Usage: scripts/test-telemetry-harness.sh   (run from the repo root)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PASS=0; FAIL=0
ok(){ echo "  PASS: $1"; PASS=$((PASS+1)); }
no(){ echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

PKG="plugins/praxis-antigravity/hooks.json"
[[ -f "$PKG" ]] || { echo "missing $PKG — run scripts/build-antigravity-plugin.sh first"; exit 2; }

echo "== 1. agy hooks write canonical rows to the right streams =="
WS="$(mktemp -d)"; T="$WS/.project/telemetry"; mkdir -p "$T"
# seed pre-existing Claude rows that must survive untouched
printf '%s\n' '{"ts":"t","harness":"claude-code","agent":"x","chosen_tier":"deep"}' > "$T/model-routing.jsonl"
printf '%s\n' '{"ts":"t","harness":"claude-code","event":"session_start","session":"c1"}' > "$T/sessions.jsonl"
# Drive the hooks from python (NOT bash mapfile — the inline commands contain
# newlines, which line-based bash extraction would mangle).
python3 - "$PKG" "$WS" <<'PY'
import json, subprocess, sys
pkg, ws = sys.argv[1], sys.argv[2]
h = json.load(open(pkg))["praxis-telemetry"]
cases = [
    (h["PreInvocation"][0]["command"],
     {"workspacePaths":[ws],"conversationId":"agy1","modelName":"gemini-3.8-flash-high","invocationNum":0}),
    (h["PreToolUse"][0]["hooks"][0]["command"],
     {"workspacePaths":[ws],"conversationId":"agy1","modelName":"gemini-3.8-flash-high","stepIdx":2,"toolCall":{"name":"run_command","args":{"toolSummary":"ls"}}}),
    (h["Stop"][0]["command"],
     {"workspacePaths":[ws],"conversationId":"agy1","executionNum":1,"terminationReason":"model_stop","fullyIdle":True}),
]
for cmd, payload in cases:
    subprocess.run(["sh","-c",cmd], input=json.dumps(payload), text=True,
                   capture_output=True)
PY

check(){ python3 - "$@"; }
# model-routing: claude row preserved + exactly one agy model_invocation row
check "$T/model-routing.jsonl" <<'PY' && ok "model-routing.jsonl: claude row preserved + agy model_invocation folded" || no "model-routing fold"
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
cl=[r for r in rows if r.get("harness")=="claude-code" and r.get("chosen_tier")=="deep"]
ag=[r for r in rows if r.get("harness")=="antigravity" and r.get("event")=="model_invocation" and r.get("model")]
assert len(cl)==1 and len(ag)==1, rows
PY
check "$T/sessions.jsonl" <<'PY' && ok "sessions.jsonl: claude row preserved + agy session_stop folded" || no "sessions fold"
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert any(r.get("harness")=="claude-code" for r in rows)
assert any(r.get("harness")=="antigravity" and r.get("event")=="session_stop" for r in rows), rows
PY
check "$T/antigravity-activity.jsonl" <<'PY' && ok "antigravity-activity.jsonl: tool audit stays agy-scoped" || no "activity stream"
import json,sys
rows=[json.loads(l) for l in open(sys.argv[1]) if l.strip()]
assert rows and rows[0].get("harness")=="antigravity" and rows[0].get("tool")=="run_command", rows
PY
# canonical envelope present on every agy row
check "$T/model-routing.jsonl" "$T/sessions.jsonl" "$T/antigravity-activity.jsonl" <<'PY' && ok "canonical envelope {ts,harness,event,session} on every agy row" || no "envelope"
import json,sys
for p in sys.argv[1:]:
    for l in open(p):
        if not l.strip(): continue
        r=json.loads(l)
        if r.get("harness")=="antigravity":
            for k in ("ts","harness","event","session"):
                assert k in r, (p,k,r)
PY
rm -rf "$WS"

echo "== 2. routing-preflight.py stamps harness =="
WS="$(mktemp -d)"; mkdir -p "$WS/.project/telemetry"
h1=$(PRAXIS_HARNESS=antigravity python3 scripts/routing-preflight.py --from-tier deep --to-tier light --project-dir "$WS" --session s --agent a 2>/dev/null | tail -1 | python3 -c "import sys,json;print(json.loads(sys.stdin.read()).get('harness'))")
h2=$(python3 scripts/routing-preflight.py --from-tier deep --to-tier light --project-dir "$WS" --harness codex --session s --agent a 2>/dev/null | tail -1 | python3 -c "import sys,json;print(json.loads(sys.stdin.read()).get('harness'))")
[[ "$h1" == "antigravity" ]] && ok "routing-preflight harness from env (antigravity)" || no "routing-preflight env harness (got '$h1')"
[[ "$h2" == "codex" ]] && ok "routing-preflight harness from --harness (codex)" || no "routing-preflight arg harness (got '$h2')"
rm -rf "$WS"

echo "== 3. praxis-drive.sh helper stamps harness on drive.jsonl =="
HELP="$(mktemp)"   # portable across GNU and BSD/macOS; python needs no .py ext
python3 - > "$HELP" <<'PY'
import re
s=open("scripts/praxis-drive.sh").read()
m=re.search(r"cat > \"\$PY_HELPER\" <<'PYEOF'\n(.*?)\nPYEOF\n", s, re.S)
import sys; sys.stdout.write(m.group(1))
PY
WS="$(mktemp -d)"
PRAXIS_HARNESS=codex python3 "$HELP" append_record "$WS/drive.jsonl" "2026-01-01T00:00:00Z" run1 1 sl t ag standard done h "" 0 >/dev/null 2>&1
dh=$(tail -1 "$WS/drive.jsonl" 2>/dev/null | python3 -c "import sys,json;print(json.loads(sys.stdin.read()).get('harness'))" 2>/dev/null)
[[ "$dh" == "codex" ]] && ok "drive.jsonl row carries harness=codex" || no "drive harness (got '$dh')"
rm -rf "$WS" "$HELP"

echo "== 4. reports EXCLUDE foreign-harness (agy) rows from claude/codex counts =="
P="$(mktemp -d)"; T="$P/.project/telemetry"; mkdir -p "$T"
cat > "$T/model-routing.jsonl" <<'EOF'
{"ts":"2026-01-01T00:00:00Z","harness":"claude-code","agent":"solution-architect","default_tier":"standard","chosen_tier":"deep","score":8,"reason":"x"}
{"ts":"2026-01-01T00:01:00Z","harness":"codex","agent":"backend-developer","default_tier":"standard","chosen_tier":"standard","score":2,"reason":"y"}
{"ts":"2026-01-01T00:02:00Z","harness":"antigravity","event":"model_invocation","session":"agy1","model":"gemini-3.8-flash-high"}
{"ts":"2026-01-01T00:03:00Z","harness":"antigravity","event":"model_invocation","session":"agy1","model":"gemini-3.8-flash-high"}
{"ts":"2026-01-01T00:04:00Z","harness":"antigravity","event":"model_invocation","session":"agy1","model":"gemini-3.8-flash-high"}
EOF
cat > "$T/sessions.jsonl" <<'EOF'
{"ts":"2026-01-01T00:00:00Z","harness":"claude-code","event":"session_start","session":"c1"}
{"ts":"2026-01-01T00:05:00Z","harness":"claude-code","event":"session_end","session":"c1"}
{"ts":"2026-01-01T00:02:00Z","harness":"antigravity","event":"session_stop","session":"agy1"}
{"ts":"2026-01-01T00:06:00Z","harness":"antigravity","event":"session_stop","session":"agy2"}
EOF
rr=$(python3 scripts/factory-routing-report.py --project-dir "$P" --format md 2>&1 | grep -ioE "structured routing decisions: [0-9]+" | grep -oE "[0-9]+")
[[ "$rr" == "2" ]] && ok "routing-report counts 2 decisions (agy 3 excluded)" || no "routing-report count (got '$rr', want 2)"
se=$(python3 scripts/factory-usage-report.py --project-dir "$P" --format md 2>&1 | grep -ioE "sessions: [0-9]+ \([0-9]+ events\)")
echo "$se" | grep -q "(2 events)" && ok "usage-report counts 2 session events (agy 2 excluded)" || no "usage-report session count (got '$se', want 2 events)"
python3 scripts/factory-token-report.py --project-dir "$P" --format md >/dev/null 2>&1 && ok "token-report runs clean on mixed data (no crash)" || no "token-report crashed on mixed data"
rm -rf "$P"

echo
echo "==== RESULT: $PASS passed, $FAIL failed ===="
[[ "$FAIL" == "0" ]] || exit 1
