# Codex Setup

Praxis ships to Codex as a repo-backed plugin package. The Claude Code plugin remains separate and unchanged.

Status: tested end-to-end on real engagements.

## Install From GitHub Marketplace

Add this repo as a Codex plugin marketplace (default branch). `--sparse` limits the checkout to the two paths Codex needs — the marketplace manifest and the generated package:

```bash
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
```

Then open Codex and install the plugin:

```text
/plugins
```

Select `praxis-codex`.

### Install from a specific branch (e.g. `features/improvements`)

`codex plugin marketplace add` takes `--ref <branch>` (or an `owner/repo@ref` shorthand) alongside the sparse paths:

```bash
codex plugin marketplace add jeet129/praxis --ref features/improvements \
  --sparse .agents/plugins --sparse plugins/praxis-codex
```

Then `/plugins` → install `praxis-codex`.

Note: this pulls the branch **as pushed to GitHub**, and it installs the *generated* `plugins/praxis-codex/` package — so the branch must have a freshly built, committed mirror (the pre-commit hook rebuilds it; or run `scripts/build-codex-plugin.sh` and commit before pushing). Commit and push first, or the install won't include un-pushed local work.

### Install from a local clone

Codex also accepts a local marketplace root directory. Point it at a checkout that contains `.agents/plugins/marketplace.json` and `plugins/praxis-codex/`:

```bash
git clone -b features/improvements https://github.com/jeet129/praxis.git
codex plugin marketplace add ./praxis --sparse .agents/plugins --sparse plugins/praxis-codex
```

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

## How to use it — the workflows

The `$praxis-*` commands run the same 9 workflows as Claude Code's slash commands; workflows without a dedicated command (spike, expedited-change, modernization) are invoked by describing the intent in a Codex session. The full guide — what each workflow is for, how to invoke it, its gates, and autonomous execution — is in **`docs/workflows.md`**. Quick map: `$praxis-discover`→`$praxis-architect`→`$praxis-slice` to build; `$praxis-release` to ship; `$praxis-refine-idea` to refine an idea; describe an incident for the P0/P1 expedited path; "can we do X?" for a spike; "modernize this" for the strangler-fig path; `$praxis-drive` to run autonomously.

## Telemetry hooks (token capture)

The Codex package ships a hooks manifest wired to Codex's own event vocabulary — notably `Stop` (Codex's turn-scoped end event; Codex has no `SessionEnd`, which is Claude Code's event). On `Stop`, the tap writes a valid JSON acknowledgement and records this session's token totals to `.project/telemetry/tokens.jsonl` as an upsert (one line per session, refreshed — never double-counted, even though `Stop` can fire per turn). Run `/hooks` after install and confirm the Praxis hooks are trusted for the session, or capture won't run.

Per-iteration model routing for `codex exec` (in the drive loop) is applied as `-c model_reasoning_effort=<level>` from the task's capability tier; `model` stays the harness default while `governance/model-routing.yaml`'s `codex.model_map` is `auto`. See `docs/model-routing.md`.

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

## Refreshing after a Praxis update

Whenever the plugin source (canonical `skills/`/`agents/`/etc., or
`codex-plugin-assets/`) changes upstream, refresh a Codex install with this
checklist, in order:

1. **Refresh the plugin source.** Pull the latest Praxis repo / marketplace
   source so the canonical directories and `codex-plugin-assets/` are current.
2. **Update or reinstall the plugin.** In Codex: `/plugins` → update (or
   remove and re-add) `praxis-codex` so the regenerated
   `plugins/praxis-codex/` package is picked up.
3. **Start a fresh session.** Codex only reads plugin/skill/agent content at
   session start.
4. **Re-run `$praxis-setup-subagents` and ALLOW it to overwrite.** Do not
   skip the overwrite — old `.codex/agents/*.toml` files carry stale
   `model_reasoning_effort` values from before the update.
5. **Restart again.** A second restart/new session is required after
   subagent profiles are rewritten — Codex loads `.codex/agents/` only at
   session start, so the overwrite in step 4 doesn't take effect until this
   restart.
6. **Trust the hooks.** Run `/hooks` and confirm the praxis hooks are
   trusted for the session.
7. **Verify the refresh actually landed:**
   - `.codex/agents/` exists in the target repo and is non-empty.
   - Each installed `.codex/agents/*.toml` contains a
     `model_reasoning_effort` field.
   - `scripts/praxis-drive.sh --harness codex` produces a
     `.project/telemetry/drive.jsonl` record with non-null token fields
     (`input_tokens`/`output_tokens`/etc.) — confirms the `--json` capture
     and `codex-json` usage parsing are wired up end to end.

## Verify your install

```text
/plugins
```

Confirm `praxis-codex` shows as installed. Then, in a Codex session:

```text
$praxis-start
```

You should see the delivery-planner bootstrap questions (mode, data plane, ML, compliance, scale, stack) — the same interview Claude Code's `/start` runs. If `$praxis-*` commands aren't recognized, re-run `$praxis-setup-subagents` and start a new Codex session (subagent profiles only load at session start).
