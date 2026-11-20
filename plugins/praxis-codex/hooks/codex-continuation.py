#!/usr/bin/env python3
"""Opt-in, session-scoped continuation guard for interactive Praxis drive."""

import hashlib
import json
import re
import sys
from pathlib import Path

from project_root import find_project_root

# Shared context-budget logic (hooks/praxis_project.py). In the built plugin it
# sits next to this file; in the source tree it is two levels up.
_here = Path(__file__).resolve().parent
for _cand in (_here, _here.parents[1] / "hooks"):
    if (_cand / "praxis_project.py").is_file():
        sys.path.insert(0, str(_cand))
        break
try:
    import praxis_project as pp
except ImportError:  # budget check is optional; continuation still works
    pp = None

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
    cwd = find_project_root(Path(cwd_value))
    if cwd is None:
        return {}
    marker = marker_path(cwd, session_id)
    if event == "Stop" and (cwd / ".project" / "STOP").exists():
        return {}  # operator kill switch: never continue a stopped drive

    if event == "UserPromptSubmit":
        prompt = input_data.get("prompt", "")
        if isinstance(prompt, str) and DRIVE_PROMPT.search(prompt):
            marker.parent.mkdir(parents=True, exist_ok=True)
            import time
            marker.write_text(json.dumps({"session_id": session_id, "rounds": 0,
                                          "unchanged": 0, "fingerprint": "",
                                          "armed_at": time.time()}) + "\n")
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
        active = next((p for p in ledgers
                       if top_value(p.read_text(), "state") != "closed"
                       and not has_stop_flags(p.read_text())), None)
        if active is None:
            marker.unlink(missing_ok=True)
            return {}
        # Context budget: hand off to a fresh session after N finished tasks or
        # a large transcript. First stop asks for current ledger + notes; the
        # next stop ends the drive (marker removed).
        if state.get("handoff_requested"):
            marker.unlink(missing_ok=True)
            return {}
        hint = None
        if pp is not None:
            hint_ledger = active.name.replace("-tasks.yaml", "").replace("slice-", "")
            if pp.context_budget(str(cwd))["on_session_budget"] == "ask":
                reason = pp.session_handoff(str(cwd), state.get("armed_at"), input_data.get("transcript_path"),
                                            hint_ledger)
                if reason:
                    state["handoff_requested"] = True
                    marker.write_text(json.dumps(state) + "\n")
                    return {"decision": "block", "reason": reason}
            else:
                # Default: keep driving; tell the person once per budget step.
                hint = pp.budget_hint(str(cwd), session_id, state.get("armed_at"),
                                      input_data.get("transcript_path"), hint_ledger)
        source = active.read_text()
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
        out = {"decision": "block", "reason":
               f"Praxis drive has unfinished work in {active.name}. Continue the next eligible task: "
               "hand it to a fresh subagent (spawn_agent, brief by path: task id, ac, verify command, "
               "packet, notes) and take back only its short report, or drain reviews and QA if "
               "implementation tasks are done. Honor stop_flags, governance gates, and the configured "
               "budget; finish only when the slice is closed."}
        if hint:
            out["systemMessage"] = hint  # shown to the person; the drive continues
        return out
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        result = decide(payload, sys.argv[1] if len(sys.argv) > 1 else "")
    except (ValueError, OSError):
        result = {}
    print(json.dumps(result))
