# Codex Setup

## Install

```bash
./install.sh --tool=codex /path/to/your-project
```

## What lands

```
your-project/
├── .team/                  ← full library
├── AGENTS.md               ← routing file at repo root
└── .project/               ← project memory tree
```

## How Codex finds the library

Codex reads `AGENTS.md` at the repo root. The installer writes a complete routing table covering every task type, mapping to the right workflow or SKILL.

## Sanity check

```
"Read AGENTS.md and confirm you can navigate to .team/agents/ and .team/skills/.
List the 16 agents and the 80 SKILLs you can see. Read governance.yaml and
summarize active gates."
```

## Differences from Claude Code

- No slash commands (Codex doesn't support them); use the routing table in AGENTS.md.
- No SessionStart hook (use `using-praxis` SKILL as first read).
- Same content; different addressing.
