# OpenCode Setup

Status: adapter shipped, structurally validated, not yet exercised
end-to-end on a real engagement — expect rough edges; issues welcome.

## Install

```bash
./install.sh --tool=opencode /path/to/your-project
```

## What lands

```
your-project/
├── .opencode/
│   └── config.json         ← skillsPath / agentsPath / governance pointers
├── .team/                  ← full library (shared with Codex layout)
├── AGENTS.md               ← routing file at repo root
└── .project/               ← project memory tree
```

## How OpenCode finds the library

OpenCode uses a **skill-driven execution model** via the `skill` tool and `AGENTS.md` routing. The config at `.opencode/config.json` points at the library paths.

Core rule (per OpenCode convention): **if a task matches a SKILL, you MUST invoke it.**

## Sanity check

```
"Read AGENTS.md and .opencode/config.json. Confirm the library is loaded.
For my next task, identify which SKILL applies via the front-door SKILL
at .team/skills/using-praxis/SKILL.md."
```

## Intent → SKILL mapping (OpenCode)

OpenCode doesn't support slash commands; the agent maps intent internally:
- DEFINE → `spec-driven-development` or our `requirements-elicitation` / `nfr-definition`
- PLAN → `planning-and-task-breakdown` (we use `project-phasing` + Lead Dev decomposition)
- BUILD → implementation specialist + stack pack + `testing-strategy`
- VERIFY → `debugging-and-error-recovery` / per-skill verification
- REVIEW → `code-review` + `security-review`
- SHIP → `production-release.yaml` workflow

Front-door SKILL handles all of this.
