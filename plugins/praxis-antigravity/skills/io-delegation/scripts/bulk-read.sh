#!/usr/bin/env bash
# bulk-read.sh — ask the light-tier worker a question about one or more files.
#
#   bash bulk-read.sh --question "what does this module export?" --paths a.ts b.ts
#
# The files are sent to the cheapest model for the current harness and only the
# ANSWER comes back, so large files never enter the calling agent's context.
# Each call is independent: to ask a follow-up, call again with the same paths.
#
# Pattern adapted from Spotify's shunt plugin (spotify/portal-ai-plugins,
# Apache-2.0), scripts/bulk-read. Praxis uses the harness's own CLI as the
# worker instead of Spotify's Portal service.
#
# Environment:
#   PRAXIS_HARNESS               claude-code | codex | antigravity (auto-detected)
#   PRAXIS_IO_DELEGATE_MODEL     override the worker model
#   PRAXIS_IO_DELEGATE_TIMEOUT   seconds (default 90)
#   PRAXIS_IO_DELEGATE_MAX_BYTES cap on bytes sent to the worker (default 400000)
set -u

question=""; paths=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --question) question="${2:-}"; shift 2 ;;
    --paths)    shift; while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do paths+=("$1"); shift; done ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *)          shift ;;
  esac
done
[[ -n "$question" ]] || { echo "Error: --question is required" >&2; exit 1; }
[[ ${#paths[@]} -gt 0 ]] || { echo "Error: --paths is required" >&2; exit 1; }
# A typo'd path would produce a confident answer about nothing — fail loudly.
for p in "${paths[@]}"; do
  [[ -f "$p" && -r "$p" ]] || { echo "Error: file not found or unreadable: $p" >&2; exit 1; }
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TIMEOUT_S="${PRAXIS_IO_DELEGATE_TIMEOUT:-90}"
MAX_BYTES="${PRAXIS_IO_DELEGATE_MAX_BYTES:-400000}"

# ── harness ─────────────────────────────────────────────────────────────
harness="${PRAXIS_HARNESS:-}"
if [[ -z "$harness" ]]; then
  if   [[ -n "${CLAUDE_PLUGIN_ROOT:-}${CLAUDECODE:-}" ]] && command -v claude >/dev/null 2>&1; then harness="claude-code"
  elif [[ -n "${CODEX_HOME:-}${CODEX_SESSION_ID:-}" ]] && command -v codex  >/dev/null 2>&1; then harness="codex"
  elif command -v claude >/dev/null 2>&1; then harness="claude-code"
  elif command -v agy    >/dev/null 2>&1; then harness="antigravity"
  elif command -v codex  >/dev/null 2>&1; then harness="codex"
  else echo "Error: no supported CLI (claude, agy, codex) found for the bulk-read worker" >&2; exit 1
  fi
fi

# ── light-tier model (project override wins, then plugin default) ────────
model="${PRAXIS_IO_DELEGATE_MODEL:-}"
if [[ -z "$model" ]] && command -v python3 >/dev/null 2>&1; then
  model="$(python3 - "$harness" "$PWD" "$PLUGIN_ROOT_DIR" <<'PY' 2>/dev/null || true
import re, sys, os
harness, proj, root = sys.argv[1:4]
for cand in (os.path.join(proj, ".project", "governance", "model-routing.yaml"),
             os.path.join(root, "governance", "model-routing.yaml")):
    if not os.path.isfile(cand):
        continue
    text = open(cand).read()
    m = re.search(r"^  " + re.escape(harness) + r":\n(.*?)(?=^  \S|\Z)", text, re.S | re.M)
    if not m:
        continue
    block = m.group(1)
    key = "model_map" if harness == "codex" else "map"
    mm = re.search(r"^    " + key + r":\n((?:      .*\n)+)", block, re.M)
    if mm:
        lm = re.search(r"^\s+light:\s*([^\s#]+)", mm.group(1), re.M)
        if lm:
            print(lm.group(1)); break
PY
)"
fi
[[ "$model" == "auto" || "$model" == "inherit" ]] && model=""
case "$harness" in
  claude-code) : "${model:=haiku}" ;;
  antigravity) : "${model:=flash}" ;;
esac

# ── build the message: question + each file in clear XML boundaries ──────
msg="$(mktemp "${TMPDIR:-/tmp}/praxis-bulk-read.XXXXXX")" || exit 1
trap 'rm -f "$msg"' EXIT
{
  echo "You are a read-only code-reading worker. Answer the QUESTION using only the files below."
  echo "Be specific and concise. Name the functions, types and files you rely on. If the files do"
  echo "not contain the answer, say so plainly. Do not invent line numbers. Do not edit anything."
  echo
  echo "QUESTION: $question"
  echo
} > "$msg"
sent=0; truncated=0
for p in "${paths[@]}"; do
  size=$(wc -c < "$p" | tr -d ' ')
  room=$(( MAX_BYTES - sent ))
  if (( room <= 0 )); then truncated=1; echo "<file path=\"$p\" omitted=\"true\"/>" >> "$msg"; continue; fi
  echo "<file path=\"$p\">" >> "$msg"
  if (( size > room )); then head -c "$room" "$p" >> "$msg"; truncated=1; sent=$MAX_BYTES
  else cat "$p" >> "$msg"; sent=$(( sent + size )); fi
  printf '\n</file>\n' >> "$msg"
done

# ── call the worker (PRAXIS_NESTED=1 keeps Praxis hooks quiet in it) ─────
run() { if command -v timeout >/dev/null 2>&1; then timeout "$TIMEOUT_S" "$@"; else "$@"; fi; }
export PRAXIS_NESTED=1 PRAXIS_IO_DELEGATE_DISABLED=1
case "$harness" in
  claude-code) answer="$(run claude -p --model "$model" --max-turns 1 < "$msg" 2>/dev/null)"; rc=$? ;;
  antigravity) answer="$(run agy --model "$model" -p "$(cat "$msg")" 2>/dev/null)"; rc=$? ;;
  codex)
    if [[ -n "$model" ]]; then answer="$(run codex exec --sandbox read-only -m "$model" - < "$msg" 2>/dev/null)"; rc=$?
    else answer="$(run codex exec --sandbox read-only -c model_reasoning_effort=low - < "$msg" 2>/dev/null)"; rc=$?; fi ;;
  *) echo "Error: unknown harness '$harness'" >&2; exit 1 ;;
esac

# ── telemetry (best-effort) ─────────────────────────────────────────────
if [[ -d "$PWD/.project" ]] && command -v python3 >/dev/null 2>&1; then
  python3 - "$harness" "${model:-default}" "$sent" "${#paths[@]}" "$rc" "${#answer}" <<'PY' 2>/dev/null || true
import json, sys, os, datetime
h, m, sent, n, rc, alen = sys.argv[1:7]
d = os.path.join(os.getcwd(), ".project", "telemetry"); os.makedirs(d, exist_ok=True)
with open(os.path.join(d, "io-delegation.jsonl"), "a") as f:
    f.write(json.dumps({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "event": "bulk_read", "harness": h, "model": m, "files": int(n),
        "bytes_sent": int(sent), "answer_chars": int(alen), "ok": rc == "0"}) + "\n")
PY
fi

if [[ $rc -ne 0 || -z "$answer" ]]; then
  echo "Error: bulk-read worker failed (harness=$harness, exit=$rc). Read the file directly with offset/limit instead." >&2
  exit 1
fi
echo "$answer"
(( truncated )) && echo "[bulk-read: input was truncated at ${MAX_BYTES} bytes; ask about fewer files for full coverage]"
exit 0
