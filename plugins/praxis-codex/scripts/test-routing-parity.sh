#!/usr/bin/env bash
# Parity test: the no-drive resolver (resolve-model.py) must resolve every
# tier to the SAME model/effort the drive runner (praxis-drive.sh) applies —
# for both harnesses, and it must honor a project override the same way.
#
# This is the machine check behind the "drive or no-drive, same behavior" rule.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILS=0
pass() { echo "  ✓ $*"; }
fail() { echo "  ✗ $*" >&2; FAILS=$((FAILS + 1)); }

TMP="${TMPDIR:-/tmp}/praxis-parity.$$"
mkdir -p "$TMP/bin"
# fake harnesses that just emit a usage record (drive records the model it chose)
cat > "$TMP/bin/claude" <<'EOF'
#!/usr/bin/env bash
echo '{"usage":{"input_tokens":1,"output_tokens":1},"total_cost_usd":0}'
EOF
cat > "$TMP/bin/codex" <<'EOF'
#!/usr/bin/env bash
echo '{"usage":{"input_tokens":1,"output_tokens":1}}'
EOF
chmod +x "$TMP/bin/claude" "$TMP/bin/codex"

# Resolve via the no-drive resolver.
resolve() { python3 "$ROOT/scripts/resolve-model.py" --harness "$1" --tier "$2" --field "$3" ${4:+--project-dir "$4"}; }

# Run ONE slice-drive iteration for a task of the given tier and read back the
# model/effort the runner recorded — that is what drive actually applies.
drive_field() {  # harness tier field project-dir
  local harness="$1" tier="$2" field="$3" proj="$4"
  local w="$TMP/d-$harness-$tier"
  rm -rf "$w"; mkdir -p "$w/.project/working"
  if [[ -n "$proj" ]]; then mkdir -p "$w/.project/governance"; cp "$proj/.project/governance/model-routing.yaml" "$w/.project/governance/"; fi
  printf 'slice: T\ntasks:\n  - id: T1\n    summary: x\n    agent: backend-developer\n    tier: %s\n    ac: ["a"]\n    verify: "true"\n    depends_on: []\n    status: open\n    attempts: 0\ngates: {code_review: pending}\nstate: open\nstop_flags: []\n' "$tier" > "$w/.project/working/slice-T-tasks.yaml"
  PATH="$TMP/bin:$PATH" bash "$ROOT/scripts/praxis-drive.sh" --project-dir "$w" --harness "$harness" --max-iterations 1 >/dev/null 2>&1
  python3 - "$w/.project/telemetry/drive.jsonl" "$field" <<'PY'
import json, sys
key = "iteration_model" if sys.argv[2] == "model" else "iteration_effort"
val = None
for ln in open(sys.argv[1]):
    try: d = json.loads(ln)
    except Exception: continue
    if key in d: val = d[key]
print(val if val is not None else "inherit")
PY
}

echo "== plugin-default parity (resolver vs drive runner) =="
for h in claude-code codex; do
  for t in deep standard light; do
    for f in model effort; do
      r="$(resolve "$h" "$t" "$f")"
      d="$(drive_field "$h" "$t" "$f" "")"
      # drive records null -> our resolver prints 'inherit' for auto; normalise
      [[ "$d" == "null" || -z "$d" ]] && d="inherit"
      if [[ "$r" == "$d" ]]; then pass "$h/$t $f = $r"; else fail "$h/$t $f: resolver=$r drive=$d"; fi
    done
  done
done

echo "== override parity (project override changes BOTH the same way) =="
OV="$TMP/proj"; mkdir -p "$OV/.project/governance"
sed -e 's/      deep: auto/      deep: gpt-5.4/' -e 's/  force_tier: null/  force_tier: deep/' "$ROOT/governance/model-routing.yaml" > "$OV/.project/governance/model-routing.yaml"
# force_tier: deep -> a 'standard' task should resolve to the deep row on both.
r_model="$(resolve codex standard model "$OV")"        # codex deep model_map -> gpt-5.4
r_eff="$(resolve claude-code standard effort "$OV")"    # claude deep effort -> high
d_model="$(drive_field codex standard model "$OV")"
d_eff="$(drive_field claude-code standard effort "$OV")"
[[ "$r_model" == "gpt-5.4" && "$d_model" == "gpt-5.4" ]] && pass "override codex model = gpt-5.4 (both)" || fail "override codex model: resolver=$r_model drive=$d_model"
[[ "$r_eff" == "high" && "$d_eff" == "high" ]] && pass "override claude effort = high (both)" || fail "override claude effort: resolver=$r_eff drive=$d_eff"

echo
if [[ $FAILS -eq 0 ]]; then echo "routing parity: PASS"; else echo "routing parity: $FAILS FAILURE(S)"; fi
rm -rf "$TMP" 2>/dev/null || true
exit $(( FAILS > 0 ? 1 : 0 ))
