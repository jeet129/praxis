#!/usr/bin/env bash
# hooks/io-delegate-read.sh — Portal-style IO delegation for Claude Code.
#
# PreToolUse hook on the `Read` tool. When a file exceeds SHUNT_MIN_LINES
# (default 350), the hook shells out to a light-tier subagent (resolved via
# model-routing.yaml) to produce a structured bullet summary, then DENIES
# the original Read — feeding the summary as the deny reason so the
# expensive model never sees the raw file.
#
# Fail-open: any error (missing deps, API failure, timeout) allows the
# original Read to proceed normally.
#
# Environment:
#   PRAXIS_IO_DELEGATE_MIN_LINES  — line threshold (default 350)
#   PRAXIS_IO_DELEGATE_TIMEOUT    — summarizer timeout in seconds (default 30)
#   PRAXIS_IO_DELEGATE_DISABLED   — set to 1 to disable delegation entirely
#   CLAUDE_PLUGIN_ROOT            — set by Claude Code (path to plugin root)
#
# Telemetry: logs each delegation decision to
#   .project/telemetry/io-delegation.jsonl
#
# See also: skills/io-delegation/SKILL.md

set -euo pipefail
trap 'exit 0' ERR    # fail-open: any error → allow the read

# ── tunables ──────────────────────────────────────────────────────────────
SHUNT_MIN_LINES="${PRAXIS_IO_DELEGATE_MIN_LINES:-350}"
TIMEOUT_S="${PRAXIS_IO_DELEGATE_TIMEOUT:-30}"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-}"

# ── early exit ────────────────────────────────────────────────────────────
[[ "${PRAXIS_IO_DELEGATE_DISABLED:-0}" == "1" ]] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# ── parse stdin + gate + summarize + emit — all in one Python call ────────
# Single Python process avoids repeated shell↔python round-trips and handles
# JSON encoding of the deny payload safely. Fail-open on any exception.
exec python3 -I - "$SHUNT_MIN_LINES" "$TIMEOUT_S" "$PLUGIN_ROOT" <<'PYEOF'
import json, os, sys, subprocess, datetime, tempfile, signal, shlex

SHUNT_MIN_LINES = int(sys.argv[1])
TIMEOUT_S = int(sys.argv[2])
PLUGIN_ROOT = sys.argv[3]

def allow():
    """Exit without output → Claude Code allows the Read."""
    sys.exit(0)

def deny(reason):
    """Deny the Read with a reason string."""
    print(json.dumps({"decision": "deny", "reason": reason}))
    sys.exit(0)

def log_decision(workspace, decision, reason, file_path, line_count,
                 summary_lines, model):
    """Append to .project/telemetry/io-delegation.jsonl (best-effort)."""
    if not workspace:
        return
    try:
        d = os.path.join(workspace, ".project", "telemetry")
        os.makedirs(d, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": "io_delegation",
            "harness": "claude-code",
            "decision": decision,
            "reason": reason,
            "file": file_path,
            "file_lines": line_count,
            "summary_lines": summary_lines,
            "threshold": SHUNT_MIN_LINES,
            "model": model,
        }
        with open(os.path.join(d, "io-delegation.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass

try:
    payload = json.load(sys.stdin)
except Exception:
    allow()

# ── extract file path and workspace ──────────────────────────────────────
tool_input = payload.get("tool_input") or {}
file_path = tool_input.get("file_path", "")
workspace_paths = payload.get("workspacePaths")
workspace = ""
if isinstance(workspace_paths, list) and workspace_paths:
    workspace = workspace_paths[0]
elif isinstance(payload.get("cwd"), str):
    workspace = payload["cwd"]

if not file_path or not os.path.isfile(file_path):
    allow()

# ── partial read bypass ──────────────────────────────────────────────────
# If the caller requests a specific offset or limit, they already know what
# they want — let the read through without delegation.
if tool_input.get("offset") or tool_input.get("limit"):
    allow()

# ── line count gate ──────────────────────────────────────────────────────
try:
    with open(file_path, "r", errors="replace") as f:
        line_count = sum(1 for _ in f)
except Exception:
    allow()

if line_count <= SHUNT_MIN_LINES:
    allow()

# ── resolve light-tier model ─────────────────────────────────────────────
resolve_script = os.path.join(PLUGIN_ROOT, "scripts", "resolve-model.py")
if not os.path.isfile(resolve_script):
    log_decision(workspace, "allow", "no_resolve_script", file_path,
                 line_count, 0, "unknown")
    allow()

resolve_cmd = [
    sys.executable, resolve_script,
    "--harness", "claude-code", "--tier", "light", "--field", "model",
]
if workspace:
    resolve_cmd += ["--project-dir", workspace]

try:
    model = subprocess.check_output(resolve_cmd, stderr=subprocess.DEVNULL,
                                     timeout=5).decode().strip()
except Exception:
    model = ""

if not model or model == "inherit":
    model = "haiku"

# ── build the summarizer prompt ──────────────────────────────────────────
file_name = os.path.basename(file_path)
_, file_ext = os.path.splitext(file_name)

# Read up to 50K chars to cap summarizer input
try:
    with open(file_path, "r", errors="replace") as f:
        content = f.read(50_000)
except Exception:
    allow()

prompt = f"""You are a code summarization agent. Summarize the following file concisely in structured bullets.

File: {file_name} ({line_count} lines, {file_ext})

Rules:
- List every exported function/class/type with a one-line description
- Note key imports and dependencies
- Identify the file's primary responsibility
- Flag any side effects (global state, I/O, env var reads)
- Keep total output under 80 lines
- Do NOT reproduce large code blocks — describe them

---
{content}
---"""

# ── call light-tier subagent via claude CLI ──────────────────────────────
# claude -p "<prompt>" is one-shot print mode.
# Write prompt to a temp file and pass via subcommand to avoid ARG_MAX.
try:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(prompt)
        tmp_path = tmp.name

    # Read prompt from file and pass as argument (no shell=True)
    with open(tmp_path, "r") as pf:
        prompt_text = pf.read()
    summary = subprocess.check_output(
        ["claude", "--model", model, "-p", prompt_text],
        stderr=subprocess.DEVNULL, timeout=TIMEOUT_S,
    ).decode().strip()
except (subprocess.TimeoutExpired, subprocess.CalledProcessError, Exception):
    summary = ""
finally:
    try:
        os.unlink(tmp_path)
    except Exception:
        pass

if not summary:
    log_decision(workspace, "allow", "summarizer_failed", file_path,
                 line_count, 0, model)
    allow()

# ── log + deny ───────────────────────────────────────────────────────────
summary_lines = summary.count("\n") + 1
log_decision(workspace, "deny", "delegated", file_path, line_count,
             summary_lines, model)

header = (f"IO-DELEGATE: File {file_name} ({line_count} lines) "
          f"summarized by {model} tier.")
deny(header + "\n\n" + summary)
PYEOF
