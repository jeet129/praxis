#!/usr/bin/env python3
"""Render a compact live progress stream from codex exec --json output."""

import json
import sys


def concise(value: object, limit: int = 360) -> str:
    text = " ".join(str(value).split())
    return text[:limit] + ("…" if len(text) > limit else "")


def render(event: dict) -> str | None:
    kind = event.get("type", "")
    item = event.get("item", {})
    if kind == "item.completed" and isinstance(item, dict):
        if item.get("type") == "agent_message":
            message = concise(item.get("text", ""))
            return f"[codex] {message}" if message else None
        if item.get("type") == "command_execution":
            code = item.get("exit_code")
            return f"[codex] command finished (exit {code})" if code is not None else None
    if kind == "turn.completed":
        usage = event.get("usage", {})
        if isinstance(usage, dict):
            return ("[codex] turn complete "
                    f"(input {usage.get('input_tokens', '?')}, "
                    f"output {usage.get('output_tokens', '?')} tokens)")
        return "[codex] turn complete"
    if kind in ("turn.failed", "error"):
        detail = event.get("error", event.get("message", kind))
        return f"[codex] {kind}: {concise(detail)}"
    return None


def main() -> None:
    for line in sys.stdin:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            summary = render(event)
            if summary:
                print(summary, flush=True)


if __name__ == "__main__":
    main()
