# Getting Started

The Praxis is **tool-agnostic content** (skills, agents, workflows, governance, references) wrapped in **tool-specific addressing** for 8 AI coding tools.

## Choose your tool

| Tool | Setup guide |
|---|---|
| Claude Code | [`claude-code-setup.md`](claude-code-setup.md) |
| Codex | [`codex-setup.md`](codex-setup.md) |
| Cursor | [`cursor-setup.md`](cursor-setup.md) |
| Gemini CLI | [`gemini-cli-setup.md`](gemini-cli-setup.md) |
| OpenCode | [`opencode-setup.md`](opencode-setup.md) |
| GitHub Copilot | [`copilot-setup.md`](copilot-setup.md) |
| Kiro | [`kiro-setup.md`](kiro-setup.md) |
| Antigravity | [`antigravity-setup.md`](antigravity-setup.md) |

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

- **83 active SKILLs** — foundation, discovery, architecture, UX, implementation, release, ops, data, ML / agentic-AI, maintenance, self-improvement.
- **16 role agents** with per-role model defaults (7 Opus / 9 Sonnet) — Delivery Lead, PM, Solution Architect, Architecture Challenger, Lead Dev, BE / FE / Data / ML/AI specialists, Code / Security / QA reviewers, Tech Writer, Platform/SRE, UX Designer, System Steward.
- **5 workflows** — greenfield-api-service, greenfield-saas, brownfield-enhancement, implementation-slice, production-release.
- **Governance** — 7 active gates + 4 conditional gates with approver matrix and evidence packs.
- **Adaptive model routing** — `adaptive-model-routing` SKILL uses a 5-signal complexity rubric to route each specialist to Opus / Sonnet / Haiku (Claude Code) or high / medium / low reasoning effort (Codex).
- **8 slash commands** — `/start /discover /architect /slice /release /audit /steward /factory-record`.
- **6 hook subscriptions** — SessionStart, SessionEnd, PostToolUse, UserPromptSubmit, SubagentStart, SubagentStop; drive a universal artifact tap that captures ~97% of plugin-artifact invocations to `.project/operational/factory-metrics/`.
- **Telemetry helpers** — `factory-record.sh`, `factory-aging.sh` (coverage gate), `factory-frequency.sh` (usage aggregation).
- **Skill validator** — checks all SKILL.md frontmatter; passes 83/83.
- **Pre-commit hook** — auto-rebuilds `plugins/praxis-codex/` when canonical source changes. Install with `scripts/install-git-hooks.sh`.
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
