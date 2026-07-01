# Claude Code Setup

The primary target — best UX for the platform.

## Install

```bash
./install.sh /path/to/your-project           # project-local (recommended for first test)
./install.sh --user                          # user-global at ~/.claude/
```

## What lands in your project

```
your-project/
├── .claude/                ← Claude Code reads this automatically
│   ├── agents/             16 role agents
│   ├── skills/             80 SKILLs
│   ├── workflows/          5 workflows
│   ├── governance/         governance.yaml (7+4 gates)
│   ├── commands/           7 slash commands
│   ├── hooks/              SessionStart hook
│   ├── scripts/            skill validator
│   ├── patterns/           reusable solution shapes
│   ├── references/         cross-cutting references
│   ├── .claude-plugin/     marketplace + plugin manifests
│   ├── README.md
│   └── PLAYBOOK.md
└── .project/               project memory tree (17 subdirs)
```

## Slash commands

| Command | Action |
|---|---|
| `/start` | Bootstrap project (run delivery-planner, set charter) |
| `/discover` | Phase A (PM + requirements_freeze gate) |
| `/architect` | Phase B (SA + Architecture Challenger + architecture_sign_off) |
| `/slice` | One implementation slice |
| `/release` | Production release + production_go_live gate |
| `/audit` | Brownfield first-week kickoff |
| `/steward` | Quarterly library review |

## SessionStart hook

Automatically fires on session open. Surfaces:
- Project charter from `.project/semantic/project-charter.md`
- Library counts (skills / agents / workflows)
- Recent ADRs
- Open debt items
- Quarterly steward cadence alarm (if >90 days)

## Marketplace install (when published)

```
/plugin marketplace add your-org/praxis
/plugin install praxis@praxis
```

For maintainer build and release details, see `docs/plugin-builds.md`.

## Sanity check

```
"Confirm you can see the Praxis. List the agents and skills
available. Read governance.yaml and summarize active gates."
```

Expected: 16 agents, 80 SKILLs, 7 active gates + 4 conditional.
