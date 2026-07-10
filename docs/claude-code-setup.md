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
│   ├── agents/             17 role agents
│   ├── skills/             88 SKILLs
│   ├── workflows/          6 workflows
│   ├── governance/         governance.yaml (6 core + 5 conditional gates)
│   ├── commands/           10 slash commands
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
| `/review` | On-demand review of an artifact outside a gate (Challenger + Code + Security reviewers) |
| `/refine-idea` | Run the `ideation-refinement-loop` creator/reviewer/enhancer loop over an ideation artifact |
| `/factory-record` | Record a rich factory-metrics observation for telemetry |

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

## Verify your install

Type:
```
"Confirm you can see the Praxis. List the agents and skills
available. Read governance.yaml and summarize active gates."
```

You should see: 17 agents, 88 SKILLs, 6 core gates + 5 conditional. If any number is off, re-run `install.sh --dry-run` and compare against the tree above.

Then type `/start` — you should see the delivery-planner interview begin (mode, data plane, ML, compliance, scale, stack questions). See `docs/quickstart.md` for the full 5-minute path.
