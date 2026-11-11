#!/usr/bin/env python3
"""SessionStart hook for Antigravity (agy): inject the Praxis project summary.

agy contract (antigravity.google/docs/hooks): SessionStart fires once per new
conversation, before the first model call; the hook prints
{"injectSteps": [{"systemMessage": {"systemMessage": "<text>"}}]} to add context.
On any error this prints {} so the session starts normally.

Mirrors hooks/session-start.sh (Claude Code / Codex): charter, active workflow,
recent decisions, and the front-door reminder. Kept under 6,000 characters.
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
        ddir = os.path.join(proj, "decision")
        try:
            adrs = sorted((f for f in os.listdir(ddir) if f.endswith(".md")),
                          key=lambda f: os.path.getmtime(os.path.join(ddir, f)), reverse=True)[:5]
            if adrs:
                parts.append("Recent decisions (ADRs): " + ", ".join(adrs))
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
