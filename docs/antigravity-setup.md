# Antigravity CLI Setup

> **Status — Tier A (interactive), spec-grounded.** This adapter is built to the
> **documented** Antigravity plugin format (antigravity.google/docs/cli/plugins):
> a minimal `plugin.json`, skills-as-slash-commands, and the `.agents/plugins/`
> workspace layout. The installer output is validated structurally (manifest
> shape, plugin location, 12 command-skills, AGENTS.md front door). Verified
> against a live `agy` build: **`agy` discovers only nested `skills/<name>/SKILL.md`
> and ignores flat `skills/*.md`**, so the 12 command-skills ship nested (like the
> 91 library skills). They register as `praxis:<name>` and are listed under
> `/skills` — Antigravity has no native plugin slash commands. The **AGENTS.md
> front-door path is reliable**
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
| Slash commands | `commands/*.md` | command-skills | **nested `skills/<name>/SKILL.md` with `name:`** → `praxis:<name>` via `/skills` (no `commands/` dir) |
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
    │   └── <name>/SKILL.md             ← 91 library skills + 12 command-skills
    │                                      (praxis:start praxis:discover …, via /skills)
    ├── agents/*.md                     ← 18 role agents
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

## Workflow commands (as skills)

The 12 workflow commands ship as nested `skills/<command>/SKILL.md` (each carries
a `name:`, so `agy` registers each as a `praxis:<command>` skill listed under
`/skills`). Antigravity has no native plugin slash commands, so invoke them by
name or prompt (e.g. "run praxis:start"):

`praxis:start` `praxis:intake` `praxis:discover` `praxis:refine-idea` `praxis:architect` `praxis:slice`
`praxis:review` `praxis:audit` `praxis:release` `praxis:steward` `praxis:factory-record` `praxis:drive`

> `/drive` is present but drive mode isn't supported on Antigravity yet (see the
> status note). Safe to run interactively; don't rely on unattended `agy -p`.

## Verify your install

```
1. ls AGENTS.md .agents/plugins/praxis/plugin.json     → both exist
2. ls -d .agents/plugins/praxis/skills/{start,intake,discover,refine-idea,architect,slice,review,audit,release,steward,factory-record,drive}/ | wc -l  → 12
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

## New in this build (cache-aware routing + infra-security)

The Antigravity package now carries the latest cross-harness work — it lands
automatically because Antigravity reads the same canonical `agents/`, `skills/`,
and `governance/`:

- **`database-engineer` agent (18th role)** — the transactional-DB specialist; `agy` reads it like any other markdown agent.
- **`iac_plan_review` gate (19th gate)** — infrastructure plan review before apply; in `governance/governance.yaml`, activated per the `has_infrastructure` charter flag.
- **Cache-aware routing guidance** — the `adaptive-model-routing` skill carries the prompt-cache economics and the down-route rubric.

**Present as guidance vs. hook/CI-enforced.** The *deterministic* enforcement pieces — the `PreToolUse(Task)` cache-aware guard, `routing-preflight.py`, the `iac-plan-classify.py` destructive-change fail-closed check, and the `validate-review-coverage.py` CI guard — are hook/CI-driven and live under `scripts/`, which this package does not ship. Antigravity now HAS hook wiring (telemetry, below), but its hooks expose no token/cost data and no spawn interception comparable to Claude Code's `PreToolUse(Task)`, so these guards stay guidance on Antigravity On Antigravity these operate as **agent-followed guidance**: the skill and the gate tell the assistant what to do, but nothing intercepts a spawn or fails a plan closed the way the Claude Code hook / CI does. Same policy, advisory rather than enforced, until Antigravity's hook schema is confirmed.

## Telemetry (hooks) — wired, scoped to what `agy` exposes

The package now ships `hooks.json` at its root — a self-contained `agy`
lifecycle-hooks manifest (verified against the `agy` hooks schema and a live
`agy` run). On every session it appends telemetry under the workspace's
`.project/telemetry/`:

- `model-routing.jsonl` (**shared canonical stream**) — the model serving each
  invocation (`PreInvocation` / `PostInvocation`), written as `event:
  "model_invocation"`, `harness: "antigravity"`. This is the SAME file the Claude
  Code / Codex tap writes tier-routing decisions into; the canonical `harness`
  field partitions them, and the `factory-*-report.py` scripts filter to
  `claude-code`/`codex` so these observational rows never skew the decision counts.
- `sessions.jsonl` (**shared canonical stream**) — a session-stop record
  (`Stop` -> `event: "session_stop"`, `harness: "antigravity"`), alongside the
  Claude/Codex session boundaries in the same file.
- `antigravity-activity.jsonl` (**agy-specific**) — tool-level audit
  (`PreToolUse` / `PostToolUse`): tool name, step index, `error` on failures.
  Stays agy-scoped: raw agy tool calls have no cross-harness equivalent
  (Claude/Codex tool activity lives in the factory-metrics *markdown* store, and
  agy tool calls are not praxis artifacts), so folding them into the shared
  `agent-spawns.jsonl` would corrupt that stream's spawn/complete schema.

The hook is inline (no sibling script), never blocks the loop (it always emits
the correct stdout contract and falls back cleanly if `python3` is absent), and
scopes itself to the workspace via the payload's `workspacePaths`. Every record carries the canonical envelope (`ts`, `harness`, `event`, `session`) defined in `docs/telemetry.md`, so shared-stream rows stay attributable and mergeable by `harness`.

**What `agy` does NOT expose — and therefore is NOT logged.** Unlike the Claude
Code / Codex `hooks/tap.sh` (which taps per-model token counts and cache
read/write), `agy`'s hook payloads and its `transcript_full.jsonl` carry **no
token counts, no cache read/write breakdown, no dollar cost, and no
subagent-spawn events**. So the cache-economics story the `adaptive-model-routing`
skill tells is *unmeasurable* on Antigravity: you can log which model ran and
what it did, but not what it cost. Antigravity telemetry is **routing +
activity, not cost** — by platform limitation, not by choice.

Format: the manifest is authored at `antigravity-plugin-assets/hooks.json`,
copied verbatim into the package by `scripts/build-antigravity-plugin.sh`, and
its shape (top-level named hooks; only `agy`'s five events —
`PreToolUse`/`PostToolUse` grouped, `PreInvocation`/`PostInvocation`/`Stop`
flat) is asserted by `scripts/validate-antigravity-plugin.sh`, which rejects a
Claude-format `{"hooks": {…}}` leak (that shape makes `agy` report
`hooks: 1 processed` but silently register no handlers).

## Cache-aware routing on Antigravity — why it's guidance-only

The `adaptive-model-routing` skill carries the cache-aware routing policy
(prompt-cache economics + the down-route rubric), and on Antigravity it runs
as **agent-followed guidance**, not enforcement. That is a platform
limitation, not a choice: the break-even math the policy rests on needs real
input / output / cache-read / cache-write token counts, and `agy` exposes
**none of them anywhere**. This was verified exhaustively (Sep 2026, `agy`
1.1.24) so the next person does not have to re-investigate:

- **Hook payloads** — no token fields on any of the five events (confirmed
  against a live `Stop` payload capture, not just the docs).
- **Transcripts** — `transcript.jsonl` and `transcript_full.jsonl` (and their
  `chunks/`) carry no `UsageMetadata` / token keys on a deep scan.
- **CLI logs** (`~/.gemini/antigravity-cli/log/`) — no `usageMetadata`,
  `tokenCount`, or `cachedContentTokenCount`.
- **Local databases** — `conversation_summaries.db` and `conversations/*.db`
  persist only turn/step counts (`step_count`, `gen_metadata` protobuf), no
  token columns.
- **`/usage` command** — an interactive quota TUI (model quota percentages)
  with no per-call tokens and no machine-readable output.
- **Official + community sources agree.** The Google AI Developers Forum
  thread [*How to check Token usage in Antigravity Hooks*](https://discuss.ai.google.dev/t/how-to-check-token-usage-in-antigravity-hooks/172967)
  is an unresolved feature request with no official support (and OpenTelemetry
  export reported unavailable); the community tool
  [`antigravity-usage`](https://github.com/gigaprakosa/antigravity-usage)
  states outright that "the JSONL transcripts carry no `UsageMetadata`" and
  "token counts are not persisted" — it *estimates* tokens as
  turn-count × an assumed per-turn size.

**Why we do not ship a token estimator.** The only available proxy is
turn/step counts (which our hooks already record as `invocationNum` / `stepIdx`
and the routing telemetry as `model_invocation` rows). Multiplying those by an
assumed per-turn token size — what the community tool does — is a guess, not a
measurement, and feeding guessed tokens into a routing *decision* would produce
exactly the dishonest telemetry the rest of this design avoids. So on
Antigravity the policy stays advisory: the skill tells the assistant what to
do, and nothing computes a break-even or intercepts a spawn.

**The exact signal we're waiting on.** If Google adds `UsageMetadata`
(`promptTokenCount` / `candidatesTokenCount` / `cachedContentTokenCount`) to
`agy` hook payloads or the JSONL transcripts, cache-aware routing becomes
implementable with **no restructuring** here: the telemetry hooks already emit
harness-tagged `model_invocation` rows carrying the model per invocation, so we
would only add the token fields to those rows and turn on the break-even math.
Until then, Claude Code / Codex remain the harnesses where cache economics are
measured and enforced (`hooks/tap.sh` + `scripts/routing-preflight.py`).

**Agent definitions ship tier-only on agy.** Because agy applies no per-agent model, the packaged agents carry only `capability_tier:` (deep/standard/light) — the build strips the Claude `model:`/`effort:` frontmatter the canonical agents use, so the agy package never advertises a model it cannot select. Resolve a tier to a concrete agy model by hand via `/model` using the mapping above.
