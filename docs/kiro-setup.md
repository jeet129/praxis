# Kiro IDE & CLI Setup

## Install

```bash
./install.sh --tool=kiro /path/to/your-project
```

## What lands

```
your-project/
├── .kiro/
│   ├── skills/             84 SKILLs (Kiro auto-discovers under .kiro/skills/)
│   ├── agents/, workflows/, governance/, references/, patterns/
│   └── README.md, PLAYBOOK.md
├── AGENTS.md               ← Kiro also supports AGENTS.md
└── .project/               ← project memory tree
```

## How Kiro finds the library

Kiro auto-discovers skills under `.kiro/skills/`. AGENTS.md provides additional routing.

Project-scope vs global:
- `.kiro/skills/` — project-only (what install.sh does)
- `~/.kiro/skills/` — global (rerun with `--user` if Kiro supports it)

See https://kiro.dev/docs/skills/ for Kiro's official skill documentation.

## Sanity check

```
"Confirm Kiro has loaded the Praxis skills. List the front-door
SKILL and the 16 agent personas."
```
