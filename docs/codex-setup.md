# Codex Setup

Praxis ships to Codex as a repo-backed plugin package. The Claude Code plugin remains separate and unchanged.

Status: tested end-to-end on real engagements.

## Install From GitHub Marketplace

Add this repo as a Codex plugin marketplace:

```bash
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
```

Then open Codex and install the plugin:

```text
/plugins
```

Select `praxis-codex`.

## What The Codex Plugin Contains

```text
plugins/praxis-codex/
├── .codex-plugin/plugin.json
├── skills/                  # canonical Praxis skills plus Codex command-entry skills
├── workflows/               # Praxis workflow YAML
├── codex-agents/            # Codex subagent TOML templates
├── agents/                  # original role markdown references
├── governance/
├── references/
├── patterns/
└── scripts/
```

## First Use

After installing the plugin, start with:

```text
$praxis-setup-subagents
$praxis-start
```

`$praxis-setup-subagents` copies the bundled Codex subagent profiles into the target repo's `.codex/agents/` directory. Restart Codex or start a new session after installing subagents.

Then use:

```text
$praxis-discover
$praxis-architect
$praxis-audit
$praxis-slice
$praxis-release
$praxis-steward
$praxis-review
```

## Development Workflow

Root folders remain the canonical source:

```text
skills/
agents/
workflows/
governance/
references/
patterns/
scripts/
```

Codex-only source lives in:

```text
codex-plugin-assets/
```

Rebuild the plugin package after changing canonical or Codex-only source:

```bash
scripts/build-codex-plugin.sh
scripts/validate-codex-plugin.sh
```

## Non-Interference With Claude Code

Codex uses:

```text
.agents/plugins/marketplace.json
plugins/praxis-codex/
codex-plugin-assets/
```

Claude Code continues to use:

```text
.claude-plugin/
.claude/commands/
commands/
```

Do not move or rename the Claude Code plugin files when updating the Codex plugin.

For maintainer build and release details, see `docs/plugin-builds.md`.

## Legacy Installer

`install.sh --tool=codex` is the older `.team/` + `AGENTS.md` copy-based setup. Prefer the plugin marketplace path above for Codex distribution.

## Verify your install

```text
/plugins
```

Confirm `praxis-codex` shows as installed. Then, in a Codex session:

```text
$praxis-start
```

You should see the delivery-planner bootstrap questions (mode, data plane, ML, compliance, scale, stack) — the same interview Claude Code's `/start` runs. If `$praxis-*` commands aren't recognized, re-run `$praxis-setup-subagents` and start a new Codex session (subagent profiles only load at session start).
