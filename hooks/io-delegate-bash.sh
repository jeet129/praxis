#!/usr/bin/env bash
# hooks/io-delegate-bash.sh — IO delegation for Claude Code: PreToolUse(Bash).
#
# Closes the bypass around io-delegate-read.sh: blocks `cat`, `less`, `more`
# (and `head`/`tail` asking for more lines than the threshold) on a large source
# file. Piped or redirected commands (`cat f | grep x`, `cat f > out`) are
# targeted and pass.
#
# Pattern adapted from Spotify's shunt plugin (spotify/portal-ai-plugins,
# Apache-2.0), hooks/check-bash-read. Fail-open on any error.
trap 'exit 0' ERR
command -v python3 >/dev/null 2>&1 || exit 0
HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The heredoc below occupies python's stdin, so read the hook payload first
# and hand it over through the environment.
PRAXIS_HOOK_PAYLOAD="$(cat)"
export PRAXIS_HOOK_PAYLOAD
exec python3 - "$HOOK_DIR" <<'PYEOF'
import json, os, re, shlex, sys
sys.path.insert(0, sys.argv[1])
try:
    import io_delegate_common as c
except Exception:
    sys.exit(0)
try:
    if c.disabled():
        c.allow()
    payload = json.loads(os.environ.get("PRAXIS_HOOK_PAYLOAD") or "")
    cmd = ((payload.get("tool_input") or {}).get("command") or "").strip()
    if not cmd or re.search(r"[|><;&`]|\$\(", cmd):
        c.allow()  # pipelines, redirections and compound commands are targeted
    try:
        argv = shlex.split(cmd)
    except ValueError:
        c.allow()
    if not argv or argv[0] not in {"cat", "less", "more", "head", "tail"}:
        c.allow()
    tool, count, path = argv[0], None, ""
    i = 1
    while i < len(argv):
        a = argv[i]
        if tool in ("head", "tail") and a in ("-n", "--lines", "-c", "--bytes") and i + 1 < len(argv):
            if a in ("-n", "--lines"):
                m = re.match(r"^[+-]?(\d+)$", argv[i + 1])
                count = int(m.group(1)) if m else count
            i += 2
            continue
        m = re.match(r"^-(?:n)?(\d+)$", a)
        if m:
            count = int(m.group(1))
        elif not a.startswith("-") and not path:
            path = a
        i += 1
    if not path:
        c.allow()
    ws = c.workspace_of(payload)
    if not os.path.isabs(path) and ws:
        path = os.path.join(ws, path)
    if not os.path.isfile(path) or c.is_exempt(path, ws):
        c.allow()
    if tool in ("head", "tail") and (count is None or count <= c.min_lines()):
        c.allow()  # bounded read
    lines = c.count_lines(path)
    if lines <= c.min_lines():
        c.allow()
    c.remember_blocked(ws, payload.get("session_id", ""), path)
    c.log(ws, "claude-code", "deny", "redirected", path, lines, "Bash:" + tool)
    c.deny_claude(c.block_reason(path, lines, f"`{tool}` on the whole file"))
except SystemExit:
    raise
except Exception:
    sys.exit(0)
PYEOF
