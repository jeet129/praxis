#!/usr/bin/env python3
"""SessionStart hook for Antigravity (agy): inject the Praxis project summary.

agy contract (antigravity.google/docs/hooks): SessionStart fires once per new
conversation, before the first model call; the hook prints
{"injectSteps": [{"systemMessage": {"systemMessage": "<text>"}}]} to add context.
On any error this prints {} so the session starts normally.

Mirrors hooks/session-start.sh (Claude Code / Codex): charter, active workflow,
the memory map (hooks/praxis_project.py), and the front-door reminder. It also
creates the v0.3.0 storage layout (gitignored .project/local/, shims). Kept under 6,000 characters.
"""
import json
import os
import sys

LIMIT = 6000


def head(path, n):
    try:
        with open(path, "r", errors="replace") as fh:
            return "".join(line for _, line in zip(range(n), fh)).rstrip()
    except Exception:
        return ""


def main():
    payload = json.load(sys.stdin)
    wps = payload.get("workspacePaths")
    ws = wps[0] if isinstance(wps, list) and wps else ""
    proj = os.path.join(ws, ".project") if ws else ""
    parts = ["Praxis is installed. Front-door skill: using-praxis (read it first when "
             "unsure which workflow, agent or skill applies). Commands: /start /intake "
             "/discover /architect /slice /drive /review /release /audit /steward."]
    if proj and os.path.isdir(proj):
        charter = head(os.path.join(proj, "semantic", "project-charter.md"), 40)
        if charter:
            parts.append("Project charter (.project/semantic/project-charter.md):\n" + charter)
        else:
            parts.append("No project charter found. Run /start to bootstrap the project.")
        wf = head(os.path.join(proj, "working", "active-workflow.md"), 10)
        if wf:
            parts.append("Active workflow (.project/working/active-workflow.md):\n" + wf)
        # Storage layout + memory map, shared with Claude Code and Codex.
        try:
            here = os.path.dirname(os.path.abspath(__file__))
            sys.path.insert(0, here)
            import praxis_project as pp
            pp.ensure(ws, os.path.dirname(here))
            mm = pp.memory_map(ws)
            if mm:
                parts.append(mm)
        except Exception:
            pass
    else:
        parts.append("No .project/ directory yet. Run /start (new project) or /audit (existing codebase).")
    text = "\n\n".join(parts)[:LIMIT]
    print(json.dumps({"injectSteps": [{"systemMessage": {"systemMessage": text}}]}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("{}")
    sys.exit(0)
