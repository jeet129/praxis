# Claude Code Setup

The primary target — best UX for the platform.

Status: tested end-to-end on real engagements.

## Install as a plugin (recommended)

Praxis is a Claude Code plugin — `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` sit at the repo root, so Claude Code installs it directly. Nothing is copied into your project; updates arrive by updating the plugin.

Published (default branch):

```text
/plugin marketplace add jeet129/praxis
/plugin install praxis@praxis
```

`praxis@praxis` is `<plugin-name>@<marketplace-name>` (both are `praxis`). That's the whole install — you now have all slash commands, agents, skills, workflows, and the SessionStart hook. **Restart Claude Code (start a new session) so everything loads.** `/reload-plugins` can pick up changes mid-session, but a fresh session is the reliable way to activate a newly installed plugin.

### From a specific branch (e.g. `features/improvements`)

Claude Code takes an `@ref` on the `owner/repo` shorthand (or `#ref` on a full git URL):

```text
/plugin marketplace add jeet129/praxis@features/improvements
/plugin install praxis@praxis
```

This pulls the branch **as pushed to GitHub** — commit and push first, or the install won't include un-pushed local work.

### From a local clone

Point Claude Code at a checkout; it reads `.claude-plugin/marketplace.json` there:

```bash
git clone -b features/improvements https://github.com/jeet129/praxis.git
```
```text
/plugin marketplace add ./praxis
/plugin install praxis@praxis
```

For updating/removing plugins and the copy-based `install.sh` alternative (frozen `.claude/` snapshot, needed for multi-tool installs), see `INSTALLATION.md`.

## How to use it — the workflows

Once installed, you drive the platform through slash commands that run workflows. Start with `/start` to bootstrap the project charter, then route by intent. The full guide to all 9 workflows — what each is for, how to invoke it, its gates, and how to run it autonomously — is in **`docs/workflows.md`**. Quick map:

| You want to… | Command | Workflow |
|---|---|---|
| Bootstrap a project | `/start` | (sets charter; picks greenfield/brownfield) |
| Handle any new requirement (steady state) | `/intake` | triages & routes it for you — no manual choice |
| Build something new | `/discover` → `/architect` → `/slice` | greenfield-saas / greenfield-api-service |
| Change an existing system | `/audit` → `/slice` | brownfield-enhancement |
| Ship one slice | `/slice` | implementation-slice |
| Release to production | `/release` | production-release |
| Fix a P0/P1 now | describe the incident | expedited-change |
| Prove feasibility | "can we even do X?" | spike |
| Replace a legacy system | "modernize this" | modernization |
| Refine an idea | `/refine-idea` | ideation-refinement-loop |
| Run autonomously | `/drive` | autonomous-drive (any of the above) |

## What the plugin gives you

Installed as a plugin, the content lives in the plugin (nothing is copied into your repo) — 17 role agents, 91 SKILLs, 9 workflows, `governance.yaml` (6 core + 12 conditional gates), 12 slash commands, the SessionStart hook, plus scripts, patterns, and references. The only thing created in your project is the `.project/` memory tree (populated as you work).

The copy-based `install.sh` alternative instead writes that same content into a `your-project/.claude/` directory (frozen snapshot) — see `INSTALLATION.md` for when to prefer it (multi-tool installs, offline/CI, pinned team versions).

## Slash commands

| Command | Action |
|---|---|
| `/start` | Bootstrap project (run delivery-planner, set charter) |
| `/intake` | Steady-state front door — triage & route any new requirement (no manual workflow choice) |
| `/discover` | Phase A (PM + requirements_freeze gate) |
| `/architect` | Phase B (SA + Architecture Challenger + architecture_sign_off) |
| `/slice` | One implementation slice |
| `/release` | Production release + production_go_live gate |
| `/audit` | Brownfield first-week kickoff |
| `/steward` | Quarterly library review |
| `/review` | On-demand review of an artifact outside a gate (Challenger + Code + Security reviewers) |
| `/refine-idea` | Run the `ideation-refinement-loop` creator/reviewer/enhancer loop over an ideation artifact |
| `/factory-record` | Record a rich factory-metrics observation for telemetry |
| `/drive` | Autonomous iteration — run the drive loop between human touchpoints |

## SessionStart hook

Automatically fires on session open. Surfaces:
- Project charter from `.project/semantic/project-charter.md`
- Library counts (skills / agents / workflows)
- Recent ADRs
- Open debt items
- Quarterly steward cadence alarm (if >90 days)

## Dev loading (no install)

To test an in-progress working tree without adding a marketplace, load the plugin directory directly:

```bash
claude --plugin-dir ./praxis
```

For maintainer build and release details, see `docs/plugin-builds.md`.

## Verify your install

Type:
```
"Confirm you can see the Praxis. List the agents and skills
available. Read governance.yaml and summarize active gates."
```

You should see: 17 agents, 91 SKILLs, 6 core gates + 12 conditional. If a slash command isn't recognized, run `/plugin` and confirm `praxis` shows as installed and enabled.

Then type `/start` — you should see the delivery-planner interview begin (mode, data plane, ML, compliance, scale, stack questions). See `docs/quickstart.md` for the full 5-minute path.
