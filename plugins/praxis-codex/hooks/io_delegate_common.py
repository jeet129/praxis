#!/usr/bin/env python3
"""Shared logic for the Praxis IO-delegation hooks (Claude Code).

Pattern adapted from Spotify's `shunt` plugin (spotify/portal-ai-plugins,
Apache-2.0): the hook only BLOCKS a whole-file read of a large file and points
the agent at the bulk-read script; it never calls a model itself. The agent then
asks a specific question through skills/io-delegation/scripts/bulk-read.sh, and
the file contents go to the light-tier worker instead of the agent's context.

Fail-open everywhere: any error allows the original tool call.
"""
import datetime
import json
import os
import sys

MIN_LINES_DEFAULT = 350
# Prose/config is what agents are told to read (skills, references, ledgers);
# summarising it with a code-reading worker loses the instructions. Never shunt.
SKIP_EXTS = {
    ".md", ".mdx", ".markdown", ".rst", ".txt", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".lock", ".ipynb", ".pdf", ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".svg",
}


def min_lines():
    raw = os.environ.get("PRAXIS_IO_DELEGATE_MIN_LINES", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else MIN_LINES_DEFAULT


def disabled():
    return (os.environ.get("PRAXIS_IO_DELEGATE_DISABLED", "0") == "1"
            or os.environ.get("PRAXIS_NESTED", "0") == "1")


def plugin_root():
    return (os.environ.get("CLAUDE_PLUGIN_ROOT")
            or os.environ.get("PLUGIN_ROOT")
            or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def workspace_of(payload):
    wps = payload.get("workspacePaths")
    if isinstance(wps, list) and wps:
        return wps[0]
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def is_exempt(path, workspace):
    """Files that must reach the agent verbatim."""
    ext = os.path.splitext(path)[1].lower()
    if ext in SKIP_EXTS:
        return True
    real = os.path.realpath(path)
    root = os.path.realpath(plugin_root())
    if real == root or real.startswith(root + os.sep):
        return True  # Praxis's own skills/references/governance
    parts = real.split(os.sep)
    return ".project" in parts or ".claude" in parts or ".agents" in parts


def count_lines(path):
    with open(path, "r", errors="replace") as fh:
        return sum(1 for _ in fh)


def bulk_read_path():
    return os.path.join(plugin_root(), "skills", "io-delegation", "scripts",
                        "bulk-read.sh")


def block_reason(path, lines, how):
    return (
        f"IO-DELEGATE: {os.path.basename(path)} is {lines} lines "
        f"(threshold {min_lines()}), so {how} is blocked to save context. "
        "To find out what it contains, ask the light-tier worker a specific "
        f"question:\n  bash \"{bulk_read_path()}\" --question \"<your question>\" "
        f"--paths \"{path}\"\n"
        "The worker's answer has no reliable line numbers. Before you EDIT or "
        "REVIEW exact code, read the relevant part directly with the Read tool "
        "using offset and limit (targeted reads are never blocked)."
    )


def log(workspace, harness, decision, reason, path, lines, via):
    if not workspace:
        return
    try:
        d = os.path.join(workspace, ".project", "telemetry")
        os.makedirs(d, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": "io_delegation",
            "harness": harness,
            "decision": decision,
            "reason": reason,
            "via": via,
            "file": path,
            "file_lines": lines,
            "threshold": min_lines(),
        }
        with open(os.path.join(d, "io-delegation.jsonl"), "a") as fh:
            fh.write(json.dumps(rec) + "\n")
    except Exception:
        pass


def _seen_file(workspace, session):
    safe = "".join(c for c in str(session) if c.isalnum() or c in "-_")[:64]
    return os.path.join(workspace, ".project", "telemetry",
                        f".io-delegated-{safe or 'nosession'}")


def remember_blocked(workspace, session, path):
    if not workspace:
        return
    try:
        os.makedirs(os.path.join(workspace, ".project", "telemetry"), exist_ok=True)
        with open(_seen_file(workspace, session), "a") as fh:
            fh.write(os.path.realpath(path) + "\n")
    except Exception:
        pass


def was_blocked(workspace, session, path):
    try:
        with open(_seen_file(workspace, session)) as fh:
            return os.path.realpath(path) in {l.strip() for l in fh}
    except Exception:
        return False


def allow():
    """No output + exit 0 = the harness proceeds normally."""
    sys.exit(0)


def deny_claude(reason):
    """Documented PreToolUse deny shape (Claude Code and Codex share it).

    NOTE: the top-level {"decision": ...} form is deprecated for PreToolUse and
    only accepts "approve"/"block" — a top-level "deny" is invalid and does not
    block. Always use hookSpecificOutput.permissionDecision.
    """
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)
