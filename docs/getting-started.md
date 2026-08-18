# Getting Started

The Praxis is **tool-agnostic content** (skills, agents, workflows, governance, references) wrapped in **tool-specific addressing** for 8 AI coding tools. Two (Claude Code, Codex) are tested end-to-end on real engagements; the other six adapters are shipped and structurally validated but not yet exercised end-to-end — see the status column below.

New here? Start with [`quickstart.md`](quickstart.md) instead — the 5-minute path to a first `/discover` run on Claude Code. This page is the wider tool-by-tool map.

## Choose your tool

| Tool | Status | Setup guide |
|---|---|---|
| Claude Code | Tested end-to-end on real engagements | [`claude-code-setup.md`](claude-code-setup.md) |
| Codex | Tested end-to-end on real engagements | [`codex-setup.md`](codex-setup.md) |
| Cursor | Adapter shipped, structurally validated — not yet exercised end-to-end | [`cursor-setup.md`](cursor-setup.md) |
| Gemini CLI | Adapter shipped, structurally validated — not yet exercised end-to-end | [`gemini-cli-setup.md`](gemini-cli-setup.md) |
| OpenCode | Adapter shipped, structurally validated — not yet exercised end-to-end | [`opencode-setup.md`](opencode-setup.md) |
| GitHub Copilot | Adapter shipped, structurally validated — not yet exercised end-to-end | [`copilot-setup.md`](copilot-setup.md) |
| Kiro | Adapter shipped, structurally validated — not yet exercised end-to-end | [`kiro-setup.md`](kiro-setup.md) |
| Antigravity | Adapter shipped, structurally validated — not yet exercised end-to-end | [`antigravity-setup.md`](antigravity-setup.md) |

## Plugin install first (Claude Code + Codex)

On the two primary harnesses, Praxis installs as a **plugin** — no file copying, updates arrive by updating the plugin. This is the recommended path:

```text
# Claude Code
/plugin marketplace add jeet129/praxis      # append @<branch> to pin a branch
/plugin install praxis@praxis

# Codex
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
/plugins   → install praxis-codex           # add --ref <branch> to pin a branch
```

After installing, **restart the tool (start a new session)** so its commands, skills, agents, and subagents load. On Claude Code, `/reload-skills` and `/reload-plugins` hot-reload skills/agents mid-session, but a fresh session is the reliable way to fully activate a newly installed plugin (a reload doesn't rebuild the slash-command index).

Full detail: `docs/claude-code-setup.md` · `docs/codex-setup.md`. The copy-based installer below covers the other six harnesses (and frozen-snapshot/offline installs).

## One installer for all

The bundled `install.sh` script handles every tool with a single flag:

```bash
./install.sh --tool=claude-code /path/to/your-project    # default
./install.sh --tool=codex       /path/to/your-project
./install.sh --tool=cursor      /path/to/your-project
./install.sh --tool=gemini      /path/to/your-project
./install.sh --tool=opencode    /path/to/your-project
./install.sh --tool=copilot     /path/to/your-project
./install.sh --tool=kiro        /path/to/your-project
./install.sh --tool=antigravity /path/to/your-project
./install.sh --tool=all         /path/to/your-project    # all 8 layouts side-by-side
```

Flags: `--dry-run` (preview), `--force` (overwrite), `--user` (Claude Code user-global install), `--skip-memory` (don't create `.project/`).

## What gets installed (regardless of tool)

Same content, different addressing:

- **91 SKILLs** — foundation, discovery, architecture, UX, implementation, release, ops, data, ML / agentic-AI, maintenance, self-improvement.
- **17 role agents**, each declaring an abstract `capability_tier` (`deep | standard | light`) instead of a hardcoded model — Delivery Lead, PM, Solution Architect, Architecture Challenger, Lead Dev, BE / FE / Data / ML-AI / Mobile specialists, Code / Security / QA reviewers, Tech Writer, Platform/SRE, UX Designer, System Steward.
- **9 workflows** — greenfield-api-service, greenfield-saas, brownfield-enhancement, implementation-slice, production-release, ideation-refinement-loop, expedited-change, spike, modernization.
- **Governance** — 18 gates (6 core + 12 conditional) with approver matrix and evidence packs.
- **Capability-tier model routing** — `governance/model-routing.yaml` maps each tier to a concrete model per harness (Claude Code: opus/sonnet/haiku; Codex: reasoning-effort high/medium/low; Gemini CLI: gemini-2.5-pro/-flash/-flash-lite); `adaptive-model-routing` SKILL shifts the tier ±1 per task at runtime. See [`model-routing.md`](model-routing.md).
- **12 slash commands** — `/start /discover /architect /slice /release /audit /steward /review /refine-idea /factory-record /drive`.
- **6 hook subscriptions** — SessionStart, SessionEnd, PostToolUse, UserPromptSubmit, SubagentStart, SubagentStop; drive the deterministic JSONL streams (`agent-spawns.jsonl`, `sessions.jsonl`, `drive.jsonl`) and command stubs. The old per-Read skill/agent/session stub types are retired (~5% real-world capture).
- **Telemetry, three layers** — (a) checkpoint records (`.project/episodic/checkpoint-*.md`, the primary near-100%-capture usage source, mined by `scripts/factory-usage-report.py`), (b) deterministic JSONL streams (`scripts/factory-routing-report.py`), (c) a thin legacy stub layer (`factory-aging.sh` coverage gate, `factory-frequency.sh` legacy aggregation). See [`telemetry.md`](telemetry.md).
- **Validator suite** — `validate-skills.sh`, `validate-manifests.sh`, `validate-workflows.py`, `validate-references.py`, `apply-model-routing.py --check`, `build-registry.py --check`, `validate-codex-plugin.sh`. All run in CI.
- **Pre-commit hook** — auto-rebuilds `plugins/praxis-codex/` when canonical source changes and reminds you to update docs when core artifacts change without a doc change. Install with `scripts/install-git-hooks.sh`.
- **Project memory tree** — 17 directories under `.project/` for six-type memory taxonomy.
- **README.md** + **PLAYBOOK.md** — operating documentation.

## Operating model

Universal across all tools. See [`PLAYBOOK.md`](../PLAYBOOK.md):

1. `delivery-planner` sets the project charter.
2. `using-praxis` front-door SKILL routes intent → workflow → agent → skill.
3. Phase agents (PM / SA / Lead Dev / Platform-SRE / UX) run their phases.
4. Specialist agents (BE / FE / Data / ML-AI) implement slices.
5. Cross-cutting agents (Code Reviewer / Security Reviewer / QA Engineer / Tech Writer) gate.
6. Governance gates route approvals to the principal.
7. System Steward runs quarterly via `/steward`.

## What to do after install

1. Open the project in your tool.
2. Paste the sanity check from the installer's output.
3. Run `/start` (or the equivalent prompt) to bootstrap.
4. Read `PLAYBOOK.md` for the full operating guide.
