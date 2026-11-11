#!/usr/bin/env python3
"""IO delegation for Antigravity (agy): PreToolUse on the file-read tool.

Blocks a WHOLE-FILE read of a source file longer than
PRAXIS_IO_DELEGATE_MIN_LINES (default 350) and points the agent at
skills/io-delegation/scripts/bulk-read.sh. The hook does not call a model.
Pattern adapted from Spotify's shunt plugin (spotify/portal-ai-plugins,
Apache-2.0).

agy contract (antigravity.google/docs/hooks): the payload carries
`toolCall.name` / `toolCall.args`; PreToolUse must print
{"decision": "allow"|"deny", "reason": ...}. agy's documented read tool is
`view_file`. This script ALWAYS prints a decision and allows on any error.

The exact argument names of `view_file` are not documented, so several
spellings are accepted; check antigravity-activity.jsonl if reads are not being
intercepted.
"""
import datetime
import json
import os
import sys

READ_TOOLS = {"view_file", "read_file", "read"}
PATH_KEYS = ("AbsolutePath", "absolutePath", "absolute_path", "file_path",
             "filePath", "path", "Path", "TargetFile", "target_file")
RANGE_KEYS = ("StartLine", "EndLine", "startLine", "endLine", "start_line",
              "end_line", "offset", "limit", "Offset", "Limit")
SKIP_EXTS = {".md", ".mdx", ".markdown", ".rst", ".txt", ".yaml", ".yml",
             ".toml", ".ini", ".cfg", ".lock", ".ipynb", ".pdf", ".png",
             ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def emit(decision, reason=None):
    out = {"decision": decision}
    if reason:
        out["reason"] = reason
    print(json.dumps(out))
    sys.exit(0)


def min_lines():
    raw = os.environ.get("PRAXIS_IO_DELEGATE_MIN_LINES", "")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 350


def plugin_root():
    return (os.environ.get("PLUGIN_ROOT")
            or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def log(workspace, decision, reason, path, lines):
    if not workspace:
        return
    try:
        d = os.path.join(workspace, ".project", "telemetry")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "io-delegation.jsonl"), "a") as fh:
            fh.write(json.dumps({
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "event": "io_delegation", "harness": "antigravity",
                "decision": decision, "reason": reason, "via": "view_file",
                "file": path, "file_lines": lines, "threshold": min_lines(),
            }) + "\n")
    except Exception:
        pass


def main():
    if (os.environ.get("PRAXIS_IO_DELEGATE_DISABLED", "0") == "1"
            or os.environ.get("PRAXIS_NESTED", "0") == "1"):
        emit("allow")
    payload = json.load(sys.stdin)
    tc = payload.get("toolCall") or {}
    if (tc.get("name") or "") not in READ_TOOLS:
        emit("allow")
    args = tc.get("args") or {}
    path = next((args[k] for k in PATH_KEYS if isinstance(args.get(k), str) and args.get(k)), "")
    if not path or not os.path.isfile(path):
        emit("allow")
    if any(args.get(k) not in (None, "", 0) for k in RANGE_KEYS):
        emit("allow")  # targeted read
    wps = payload.get("workspacePaths")
    workspace = wps[0] if isinstance(wps, list) and wps else ""
    real = os.path.realpath(path)
    root = os.path.realpath(plugin_root())
    parts = real.split(os.sep)
    if (os.path.splitext(path)[1].lower() in SKIP_EXTS
            or real.startswith(root + os.sep)
            or ".project" in parts or ".agents" in parts or ".gemini" in parts):
        emit("allow")
    with open(path, "r", errors="replace") as fh:
        lines = sum(1 for _ in fh)
    if lines <= min_lines():
        emit("allow")
    script = os.path.join(plugin_root(), "skills", "io-delegation", "scripts", "bulk-read.sh")
    log(workspace, "deny", "redirected", path, lines)
    emit("deny", (
        f"IO-DELEGATE: {os.path.basename(path)} is {lines} lines (threshold "
        f"{min_lines()}), so reading the whole file is blocked to save context. "
        "Ask the light-tier worker a specific question instead:\n"
        f"  bash \"{script}\" --question \"<your question>\" --paths \"{path}\"\n"
        "The answer has no reliable line numbers. Before you EDIT or REVIEW "
        "exact code, view the relevant line range of the file directly "
        "(ranged views are never blocked)."))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)
