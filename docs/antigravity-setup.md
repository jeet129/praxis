# Antigravity CLI Setup

> **Status — Tier A (interactive), spec-grounded.** This adapter is built to the
> **documented** Antigravity plugin format (antigravity.google/docs/cli/plugins):
> a minimal `plugin.json`, skills-as-slash-commands, and the `.agents/plugins/`
> workspace layout. The installer output is validated structurally (manifest
> shape, plugin location, 12 command-skills, AGENTS.md front door). It has **not
> yet been exercised end-to-end against a live `agy` build** — one thing to
> confirm on your machine is whether `agy` discovers nested `skills/<name>/SKILL.md`
> or only flat `skills/*.md` (the 12 command-skills are flat and will register;
> the 91 library skills are nested). The **AGENTS.md front-door path is reliable**
> regardless of the plugin subsystem.
>
> **Not yet supported:** unattended *drive mode* on Antigravity — its headless /
> non-TTY execution still has open upstream issues (prompt hangs, dropped
> stdout). Use Claude Code or Codex for drive mode today.

Antigravity is Google's agentic CLI (`agy`), successor to Gemini CLI (sunset
June 18 2026). It runs Gemini 3.x plus Claude Sonnet/Opus and GPT-OSS behind one
interface, reads `AGENTS.md` natively, and auto-discovers plugins under
`.agents/plugins/`.

> Praxis previously shipped a standalone Gemini CLI adapter. With Gemini CLI
> discontinued (June 18 2026), that adapter has been removed — Antigravity is
> the Google harness going forward. (Gemini *models* remain available: Antigravity
> runs Gemini 3.x.)

## How Antigravity's plugin format differs

It is **not** Claude's format and **not** Codex's:

| | Claude Code | Codex | **Antigravity** |
|---|---|---|---|
| Manifest | `.claude-plugin/plugin.json` (skills[]/agents[]/commands arrays) | `.codex-plugin/plugin.json` (`skills:"./skills/"`, `hooks:`) | `plugin.json` — **minimal**: `$schema` + `name` + optional `description`/`version` |
| Agents | markdown | **TOML** (`.toml`) | markdown |
| Slash commands | `commands/*.md` | command-skills | **`skills/*.md` with `name:` frontmatter** (no `commands/` dir) |
| Location | `.claude/` | `.agents/plugins/` marketplace → `plugins/praxis-codex/` | `.agents/plugins/<name>/` (workspace) or `~/.gemini/antigravity-cli/plugins/` (global) |

The installer handles this Antigravity-specific shaping for you.

## Install

```bash
./install.sh --tool=antigravity /path/to/your-project
```

### From a specific branch (e.g. `features/improvements`)

Unlike Claude Code (`/plugin marketplace add jeet129/praxis@features/improvements`)
and Codex (`codex plugin marketplace add … --ref features/improvements`),
Antigravity's `agy plugin install` and this installer take a **local path** — the
Antigravity plugin docs document no remote `owner/repo@ref` install. So a
feature-branch install goes through a local clone of that branch, then the normal
install:

```bash
git clone -b features/improvements https://github.com/jeet129/praxis.git
cd praxis
./install.sh --tool=antigravity /path/to/your-project     # workspace layout (recommended)
```

Or register the committed native package into your global `agy`:

```bash
agy plugin install ./plugins/praxis-antigravity
```

Either way this uses the branch **as pushed to GitHub** — commit and push first,
or the clone won't include un-pushed local work. The global-package route also
needs the branch's `plugins/praxis-antigravity/` mirror to be freshly built and
committed (the pre-commit hook rebuilds it; or run
`scripts/build-antigravity-plugin.sh` and commit before pushing) — the same
discipline as Codex's `plugins/praxis-codex/`.

### From a local checkout you already have

If you are developing on the branch and already have it checked out, skip the
clone and point the installer (or `agy plugin install`) at the checkout directly:

```bash
./install.sh --tool=antigravity /path/to/your-project     # run from the checkout root
# or, to globally install the committed native package:
agy plugin install ./plugins/praxis-antigravity
```

## What lands

```
your-project/
├── AGENTS.md                          ← front door, repo root (agy reads natively)
└── .agents/plugins/praxis/            ← auto-discovered plugin
    ├── plugin.json                    ← minimal Antigravity manifest
    ├── skills/
    │   ├── cmd-*.md                    ← 12 workflow commands → /start /discover …
    │   └── <name>/SKILL.md             ← 91 library skills
    ├── agents/*.md                     ← 17 role agents
    ├── workflows/  governance/  patterns/  references/
    └── README.md  PLAYBOOK.md  INSTALLATION.md
```

## Two ways to use it

### 1. Workspace auto-discovery + AGENTS.md (reliable — recommended)

`agy` scans `.agents/plugins/` in the workspace and reads `AGENTS.md` at repo
root on its own. Just open the project:

```bash
cd /path/to/your-project
agy
```

### 2. Register globally (optional)

To install the plugin into your global `agy` (`~/.gemini/antigravity-cli/plugins/`):

```bash
agy plugin install ./.agents/plugins/praxis
```

(Local path — remote/git URLs are not documented.) Manage with `agy plugin list`,
`agy plugin disable praxis`, `agy plugin uninstall praxis`.

## Slash commands

The 12 workflow commands ship as `skills/cmd-*.md` (each carries a `name:` so
`agy` registers it):

`/start` `/intake` `/discover` `/refine-idea` `/architect` `/slice`
`/review` `/audit` `/release` `/steward` `/factory-record` `/drive`

> `/drive` is present but drive mode isn't supported on Antigravity yet (see the
> status note). Safe to run interactively; don't rely on unattended `agy -p`.

## Verify your install

```
1. ls AGENTS.md .agents/plugins/praxis/plugin.json     → both exist
2. ls .agents/plugins/praxis/skills/cmd-*.md | wc -l    → 12
3. agy plugin list                                      → praxis listed (if registered)
```

Then paste into `agy`:

```
Read .agents/plugins/praxis/skills/using-praxis/SKILL.md and summarize the
routing tree — which intents map to which workflows, agents, and skills.
```

## Native package (publish parity with Codex)

A committed, generated plugin package ships at `plugins/praxis-antigravity/` —
the same discipline as `plugins/praxis-codex/`:

- Built from canonical source + a hand-authored command overlay
  (`antigravity-plugin-assets/skills/`, the Antigravity analog of
  `codex-plugin-assets/`) by `scripts/build-antigravity-plugin.sh` (deterministic;
  agents stay markdown — no TOML transform).
- Checked by `scripts/validate-antigravity-plugin.sh`.
- Rebuilt, validated, and re-staged automatically by the repo pre-commit hook
  when canonical source or `.claude/commands/` changes.

Install it into a global `agy` directly from the repo:

```bash
agy plugin install ./plugins/praxis-antigravity
```

This package is a **separate artifact** from the Claude and Codex packages (its
own minimal manifest, its own directory). It is intentionally **not** listed in
`.agents/plugins/marketplace.json` — that file is consumed by Codex, and an entry
there would surface an Antigravity-shaped package to Codex users. The validator
enforces this separation.

## Coexistence — no conflicts with Claude or Codex

All three harnesses install into disjoint homes and can share one project:

| Harness | Install home (in a project) | Publish artifact (in this repo) |
|---|---|---|
| Claude Code | `.claude/` | `.claude-plugin/` |
| Codex | `.team/` + `AGENTS.md` | `plugins/praxis-codex/` + `.agents/plugins/marketplace.json` |
| Antigravity | `.agents/plugins/praxis/` + `AGENTS.md` | `plugins/praxis-antigravity/` |

The only shared file is `AGENTS.md` — the cross-harness standard both Codex and
Antigravity read. The installer writes it once (guarded); whichever tool installs
first owns it, and its content is valid for every AGENTS.md consumer. Antigravity
does not depend on it — `agy` auto-discovers `.agents/plugins/praxis/` on its own,
so even when Codex owns `AGENTS.md`, the Antigravity plugin still loads.

## Telemetry (hooks) — not yet wired

The per-model token/cache tap (`hooks/tap.sh`) is wired for Claude Code and
Codex. Antigravity's hook event schema isn't confirmed against a live `agy`
build, so no `hooks.json` ships in the Antigravity package yet — routing/cost
telemetry on Antigravity is manual until then.
