#!/usr/bin/env python3
"""Opt-in, session-scoped continuation guard for interactive Praxis drive."""

import hashlib
import json
import re
import sys
from pathlib import Path

MAX_CONTINUATIONS = 40
MAX_UNCHANGED = 2
DRIVE_PROMPT = re.compile(r"^\s*(?:\$praxis-drive|praxis drive)\b", re.I)


def marker_path(cwd: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode()).hexdigest()[:24]
    return cwd / ".project" / "working" / "codex-continuation" / f"{digest}.json"


def top_value(source: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*([^#\n]*)", source, re.M)
    return match.group(1).strip().strip("\"'") if match else ""


def autonomy(cwd: Path) -> tuple[str, int]:
    override = cwd / ".project" / "governance" / "autonomy.yaml"
    default = Path(__file__).resolve().parents[1] / "governance" / "autonomy.yaml"
    source = (override if override.is_file() else default).read_text()
    stop_after = top_value(source, "stop_after") or "gate"
    match = re.search(r"^\s+max_iterations_per_run:\s*(\d+)", source, re.M)
    maximum = min(MAX_CONTINUATIONS, int(match.group(1))) if match else MAX_CONTINUATIONS
    return stop_after, maximum


def has_stop_flags(source: str) -> bool:
    match = re.search(r"^stop_flags:\s*([^\n]*)(.*?)(?=^\S|\Z)", source, re.M | re.S)
    if not match:
        return False
    inline = match.group(1).split("#", 1)[0].strip()
    return inline not in ("", "[]") or bool(re.search(r"^\s+-\s+\w", match.group(2), re.M))


def decide(input_data: dict, event: str) -> dict:
    session_id = input_data.get("session_id")
    cwd_value = input_data.get("cwd")
    if not isinstance(session_id, str) or not session_id or not isinstance(cwd_value, str):
        return {}
    cwd = Path(cwd_value)
    marker = marker_path(cwd, session_id)

    if event == "UserPromptSubmit":
        prompt = input_data.get("prompt", "")
        if isinstance(prompt, str) and DRIVE_PROMPT.search(prompt):
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"session_id": session_id, "rounds": 0,
                                          "unchanged": 0, "fingerprint": ""}) + "\n")
        return {}

    if event != "Stop" or input_data.get("permission_mode") == "plan" or not marker.is_file():
        return {}
    try:
        state = json.loads(marker.read_text())
        if state.get("session_id") != session_id:
            return {}
        stop_after, max_rounds = autonomy(cwd)
        if stop_after not in ("gate", "slice"):
            marker.unlink(missing_ok=True)
            return {}
        ledgers = sorted((cwd / ".project" / "working").glob("slice-*-tasks.yaml"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if stop_after == "slice" and state.get("first_ledger"):
            first = cwd / ".project" / "working" / state["first_ledger"]
            if first.is_file() and top_value(first.read_text(), "state") == "closed":
                marker.unlink(missing_ok=True)
                return {}
        active = next((p for p in ledgers if top_value(p.read_text(), "state") != "closed"), None)
        if active is None:
            marker.unlink(missing_ok=True)
            return {}
        source = active.read_text()
        if has_stop_flags(source):
            marker.unlink(missing_ok=True)
            return {}
        statuses = re.findall(r"^\s+status:\s*([\w-]+)", source, re.M)
        if not statuses or any(s in ("failed", "blocked") for s in statuses):
            marker.unlink(missing_ok=True)
            return {}
        fingerprint = hashlib.sha256(source.encode()).hexdigest()
        unchanged = state.get("unchanged", 0) + 1 if state.get("fingerprint") == fingerprint else 0
        rounds = state.get("rounds", 0) + 1
        if unchanged >= MAX_UNCHANGED or rounds > max_rounds:
            marker.unlink(missing_ok=True)
            return {}
        state.update({"rounds": rounds, "unchanged": unchanged, "fingerprint": fingerprint,
                      "first_ledger": state.get("first_ledger", active.name)})
        marker.write_text(json.dumps(state) + "\n")
        return {"decision": "block", "reason":
                f"Praxis drive has unfinished work in {active.name}. Continue the next eligible task, "
                "or drain reviews and QA if implementation tasks are done. Honor stop_flags, "
                "governance gates, and the configured budget; finish only when the slice is closed."}
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        result = decide(payload, sys.argv[1] if len(sys.argv) > 1 else "")
    except (ValueError, OSError):
        result = {}
    print(json.dumps(result))
