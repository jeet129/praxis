#!/usr/bin/env python3 -I
"""hooks/io-delegate-read-agy.py — Portal-style IO delegation for Antigravity.

PreToolUse hook that intercepts file-read tool calls on files exceeding
SHUNT_MIN_LINES (default 350). Shells out to a light-tier model (advisory:
flash, via model-routing.yaml) to summarize, then denies the read.

CRITICAL: agy hooks are FAIL-CLOSED — a crash/timeout blocks the tool call.
This script wraps the summarizer in an aggressive timeout (default 3s) and
emits {"decision":"allow"} on ANY failure, simulating fail-open behavior.

The outer `|| printf '{"decision":"allow"}\n'` in hooks.json is the last
resort; this script should never let an exception propagate.

Environment:
  PRAXIS_IO_DELEGATE_MIN_LINES  — line threshold (default 350)
  PRAXIS_IO_DELEGATE_TIMEOUT    — summarizer timeout in seconds (default 3)
  PRAXIS_IO_DELEGATE_DISABLED   — set to 1 to disable delegation entirely

Telemetry: logs to .project/telemetry/io-delegation.jsonl
"""

import json
import os
import sys
import subprocess
import datetime
import tempfile

SHUNT_MIN_LINES = int(os.environ.get("PRAXIS_IO_DELEGATE_MIN_LINES", "350"))
# AGGRESSIVE timeout — agy is fail-closed, so we must respond quickly.
# 3s is tight but avoids blocking the session on API latency.
TIMEOUT_S = int(os.environ.get("PRAXIS_IO_DELEGATE_TIMEOUT", "3"))


def allow():
    """Emit allow and exit. agy requires explicit {"decision":"allow"}."""
    print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def deny(reason):
    """Deny the tool call with a reason string."""
    print(json.dumps({"decision": "deny", "reason": reason}))
    sys.exit(0)


def log_decision(workspace, decision, reason, file_path, line_count,
                 summary_lines=0, model="unknown"):
    """Append to .project/telemetry/io-delegation.jsonl (best-effort)."""
    if not workspace:
        return
    try:
        d = os.path.join(workspace, ".project", "telemetry")
        os.makedirs(d, exist_ok=True)
        rec = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "event": "io_delegation",
            "harness": "antigravity",
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


def main():
    # ── disabled? ────────────────────────────────────────────────────────
    if os.environ.get("PRAXIS_IO_DELEGATE_DISABLED") == "1":
        allow()

    # ── parse payload ────────────────────────────────────────────────────
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        allow()

    # ── filter: only file-read tools ─────────────────────────────────────
    tc = payload.get("toolCall") or {}
    tool_name = (tc.get("name") or "").lower()
    args = tc.get("args") or {}

    # agy tool names vary — match common read-tool patterns
    READ_TOOLS = {"read", "read_file", "readfile", "cat", "read_text_file"}
    if tool_name not in READ_TOOLS:
        allow()

    # ── extract file path (try common arg names) ─────────────────────────
    file_path = (args.get("file_path")
                 or args.get("path")
                 or args.get("filePath")
                 or "")
    if not file_path or not os.path.isfile(file_path):
        allow()

    # ── line count gate ──────────────────────────────────────────────────
    try:
        with open(file_path, "r", errors="replace") as f:
            line_count = sum(1 for _ in f)
    except Exception:
        allow()

    if line_count <= SHUNT_MIN_LINES:
        allow()

    # ── workspace for telemetry ──────────────────────────────────────────
    workspace = ""
    wps = payload.get("workspacePaths")
    if isinstance(wps, list) and wps:
        workspace = wps[0]

    # ── resolve model ────────────────────────────────────────────────────
    # The antigravity block in model-routing.yaml is ADVISORY ONLY — agy
    # applies nothing from it. But resolve-model.py can still tell us the
    # advisory recommendation (light → flash).
    model = "flash"
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        for k in ("AGY_PLUGIN_ROOT", "ANTIGRAVITY_PLUGIN_ROOT"):
            v = os.environ.get(k)
            if v:
                plugin_root = v
                break

    resolve_script = (os.path.join(plugin_root, "scripts", "resolve-model.py")
                      if plugin_root else "")
    if resolve_script and os.path.isfile(resolve_script):
        try:
            cmd = [sys.executable, resolve_script,
                   "--harness", "antigravity", "--tier", "light",
                   "--field", "model"]
            if workspace:
                cmd += ["--project-dir", workspace]
            out = subprocess.check_output(
                cmd, stderr=subprocess.DEVNULL, timeout=3
            ).decode().strip()
            if out and out != "inherit":
                model = out
        except Exception:
            pass  # keep default

    # ── read file content (capped) ───────────────────────────────────────
    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read(50_000)
    except Exception:
        allow()

    file_name = os.path.basename(file_path)
    _, file_ext = os.path.splitext(file_name)

    prompt = (
        "You are a code summarization agent. Summarize this file concisely "
        "in structured bullets.\n\n"
        f"File: {file_name} ({line_count} lines, {file_ext})\n\n"
        "Rules:\n"
        "- List every exported function/class/type with a one-line description\n"
        "- Note key imports and dependencies\n"
        "- Identify the file's primary responsibility\n"
        "- Flag any side effects\n"
        "- Keep output under 80 lines\n"
        "- Do NOT reproduce large code blocks\n\n"
        f"---\n{content}\n---"
    )

    # ── call summarizer with AGGRESSIVE timeout ──────────────────────────
    # Try agy CLI first, then claude CLI as cross-harness fallback.
    # On ANY failure → allow (simulating fail-open on a fail-closed harness).
    summary = ""
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp:
            tmp.write(prompt)
            tmp_path = tmp.name

        # Attempt 1: agy CLI (if available)
        for cli_cmd in (["agy", "--model", model, "-p"],
                        ["claude", "--model", "haiku", "-p"]):
            try:
                with open(tmp_path, "r") as pf:
                    prompt_text = pf.read()
                summary = subprocess.check_output(
                    cli_cmd + [prompt_text],
                    stderr=subprocess.DEVNULL,
                    timeout=TIMEOUT_S,
                ).decode().strip()
                if summary:
                    break
            except FileNotFoundError:
                continue  # CLI not found, try next
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                break  # timed out or errored, don't try another CLI
            except Exception:
                continue
    except Exception:
        pass
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    if not summary:
        log_decision(workspace, "allow", "summarizer_failed", file_path,
                     line_count, 0, model)
        allow()

    # ── log + deny ───────────────────────────────────────────────────────
    summary_lines = summary.count("\n") + 1
    log_decision(workspace, "deny", "delegated", file_path, line_count,
                 summary_lines, model)

    header = (f"IO-DELEGATE: File {file_name} ({line_count} lines) "
              f"summarized by {model} tier.")
    deny(header + "\n\n" + summary)


# Wrap everything in try/except — agy is fail-closed, so ANY uncaught
# exception would block the tool call. We MUST emit allow on failure.
try:
    main()
except SystemExit:
    raise  # allow() and deny() use sys.exit
except Exception:
    # Last resort: emit allow so the read proceeds
    try:
        print(json.dumps({"decision": "allow"}))
    except Exception:
        pass
    sys.exit(0)
