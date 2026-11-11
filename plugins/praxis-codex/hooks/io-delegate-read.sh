#!/usr/bin/env bash
# hooks/io-delegate-read.sh — IO delegation for Claude Code: PreToolUse(Read).
#
# Blocks a WHOLE-FILE Read of a source file longer than
# PRAXIS_IO_DELEGATE_MIN_LINES (default 350) and tells the agent to ask the
# light-tier worker through skills/io-delegation/scripts/bulk-read.sh instead.
# The hook does not call a model. Targeted reads (offset/limit) always pass.
#
# Pattern adapted from Spotify's shunt plugin (spotify/portal-ai-plugins,
# Apache-2.0), hooks/check-file-size.
#
# Environment:
#   PRAXIS_IO_DELEGATE_MIN_LINES  line threshold (default 350)
#   PRAXIS_IO_DELEGATE_DISABLED   set to 1 to turn IO delegation off
#
# Fail-open: any error allows the Read. Telemetry: .project/telemetry/io-delegation.jsonl
# See skills/io-delegation/SKILL.md.
trap 'exit 0' ERR
command -v python3 >/dev/null 2>&1 || exit 0
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The heredoc below occupies python's stdin, so read the hook payload first
# and hand it over through the environment.
PRAXIS_HOOK_PAYLOAD="$(cat)"
export PRAXIS_HOOK_PAYLOAD
exec python3 - "$HOOK_DIR" <<'PYEOF'
import json, os, sys
sys.path.insert(0, sys.argv[1])
try:
    import io_delegate_common as c
except Exception:
    sys.exit(0)
try:
    if c.disabled():
        c.allow()
    payload = json.loads(os.environ.get("PRAXIS_HOOK_PAYLOAD") or "")
    ti = payload.get("tool_input") or {}
    path = ti.get("file_path") or ""
    ws = c.workspace_of(payload)
    session = payload.get("session_id", "")
    if not path or not os.path.isfile(path):
        c.allow()
    if ti.get("offset") or ti.get("limit"):
        # Targeted read. If this file was blocked earlier, record the re-read:
        # the re-read rate is how you tell whether delegation saves anything.
        if c.was_blocked(ws, session, path):
            c.log(ws, "claude-code", "allow", "targeted_reread", path, 0, "Read")
        c.allow()
    if c.is_exempt(path, ws):
        c.allow()
    lines = c.count_lines(path)
    if lines <= c.min_lines():
        c.allow()
    c.remember_blocked(ws, session, path)
    c.log(ws, "claude-code", "deny", "redirected", path, lines, "Read")
    c.deny_claude(c.block_reason(path, lines, "reading the whole file"))
except SystemExit:
    raise
except Exception:
    sys.exit(0)
PYEOF
