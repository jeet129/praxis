# Praxis

**Production-grade skill library + agent personas + workflows + governance for end-to-end software delivery with AI coding agents.**

Spans the full lifecycle — discovery, architecture, UX, implementation, release, ops, data, ML / agentic AI, maintenance, self-improvement. 79 skills, 16 role agents, 5 workflows, 7 active governance gates, 8 supported AI coding tools.

> **Status:** Alpha — maturing in private testing. Opening up for external use as it validates against real projects. Use it for your own projects today; expect change.

---

## What's inside

| Layer | Content |
|---|---|
| **Skills** | 79 active SKILLs covering 16 capability areas: foundation, lifecycle, discovery, architecture, UX, stacks, quality + security, build + deploy, ops, data, ML, agentic AI, maintenance. Each with an anti-rationalization table + verification checklist. |
| **Agents** | 16 role personas: Delivery Lead, PM, Solution Architect, Architecture Challenger, Lead Dev, BE / FE / Data / ML-AI specialists, Code Reviewer, Security Reviewer, QA Engineer, Tech Writer, Platform / SRE, UX Designer, System Steward. |
| **Workflows** | 5 named compositions: `greenfield-api-service`, `greenfield-saas`, `brownfield-enhancement`, `implementation-slice`, `production-release`. |
| **Governance** | 7 active gates with evidence packs + approver matrix: `requirements_freeze`, `architecture_sign_off`, `production_go_live`, `responsible_ai_review`, `steward_promotion`, + 2 conditional. |
| **Slash commands** | 7 Claude Code commands: `/start /discover /architect /slice /release /audit /steward`. |
| **Session hook** | Surfaces project state at session start: charter flags, recent ADRs, debt items, quarterly cadence reminder. |
| **References** | 26 tool-specific reference docs (stack frameworks, data tools, observability, ML / RAG / LLM, compliance regimes, secrets, deploy patterns). Inventory of 98 more tracked at `references/MISSING-INVENTORY.md`. |
| **Validator** | `scripts/validate-skills.sh` — checks frontmatter, dependency graph, broken refs. 80/80 pass. |
| **Memory taxonomy** | Six-type project memory under `.project/` (semantic / episodic / procedural / decision / operational / working). |

For the typical project flow visualization, see [`docs/lifecycle.md`](docs/lifecycle.md). For the full operating manual, see [`PLAYBOOK.md`](PLAYBOOK.md).

---

## Installation

Three paths. Pick the one that matches your tool + workflow.

### Path 1 — Plugin-dir loading (recommended for first test)

The library is structured as a Claude Code plugin. Point Claude Code at the directory directly — no copying, no install.

```bash
# Clone or download the library
git clone https://github.com/YOUR-ORG/praxis.git ~/dev/praxis

# Launch Claude Code with the library loaded as a plugin
cd ~/dev/your-test-project
~/dev/praxis/try-as-plugin.sh --init .
```

The bundled `try-as-plugin.sh` validates the library + Claude CLI, creates the `.project/` memory tree if `--init`, and runs `claude --plugin-dir <library>`. Library updates propagate immediately — no re-install.

### Path 2 — File install (8 supported tools)

The bundled `install.sh` copies the library into a target project in the right layout for any of 8 AI coding tools:

```bash
cd ~/dev/praxis

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

Flags: `--dry-run` preview · `--force` overwrite · `--user` Claude Code user-global install · `--skip-memory` skip `.project/` tree creation.

Per-tool setup notes live in [`docs/<tool>-setup.md`](docs/).

### Path 3 — Claude Code marketplace install (when published)

Once this repo is public on GitHub, Claude Code users can install via the marketplace:

```
/plugin marketplace add YOUR-ORG/praxis
/plugin install praxis@praxis
```

The marketplace manifest at `.claude-plugin/marketplace.json` is pre-wired; you only need to substitute `YOUR-ORG` with the real GitHub org / username.

### Full installation playbook

For step-by-step installation, sanity checks, troubleshooting, and a "first 30 minutes" walkthrough, see [`INSTALLATION.md`](INSTALLATION.md).

---

## Quick start

Once installed, in Claude Code:

```
/start
```

The Delivery Planner agent walks you through ~10 questions about your project — mode (greenfield / brownfield), data plane, ML, agentic AI, compliance regimes, scale targets, stack, cloud. It writes `.project/semantic/project-charter.md` and tells you which governance gates apply.

Then for greenfield:

```
/discover     → Phase A: Product Manager + requirements_freeze gate
/architect    → Phase B: Solution Architect + Architecture Challenger + architecture_sign_off gate
/slice        → Implementation slice (repeat per slice on the roadmap)
/release      → production-release workflow + production_go_live gate
```

For brownfield: `/audit` first (codebase comprehension + arch reconciliation + debt audit + impact analysis), then `/discover`.

Quarterly: `/steward` for the System Steward's library review (skip until you have telemetry).

For the full operating guide, see [`PLAYBOOK.md`](PLAYBOOK.md).

---

## Tool compatibility

| Tool | Layout | Setup guide |
|---|---|---|
| **Claude Code** | `.claude/` + slash commands + hooks + plugin manifests | [`docs/claude-code-setup.md`](docs/claude-code-setup.md) |
| **Codex** | `.team/` + `AGENTS.md` at repo root | [`docs/codex-setup.md`](docs/codex-setup.md) |
| **Cursor** | `.cursor/rules/` + library at `.cursor/praxis/` | [`docs/cursor-setup.md`](docs/cursor-setup.md) |
| **Gemini CLI** | `.gemini/` + skills + commands + `GEMINI.md` routing | [`docs/gemini-cli-setup.md`](docs/gemini-cli-setup.md) |
| **OpenCode** | `.team/` + `.opencode/config.json` + `AGENTS.md` | [`docs/opencode-setup.md`](docs/opencode-setup.md) |
| **GitHub Copilot** | `.github/copilot-instructions.md` + `.github/agents/` + library | [`docs/copilot-setup.md`](docs/copilot-setup.md) |
| **Kiro** | `.kiro/skills/` + `AGENTS.md` | [`docs/kiro-setup.md`](docs/kiro-setup.md) |
| **Antigravity** | `plugin.json` + library at repo root + `commands/` | [`docs/antigravity-setup.md`](docs/antigravity-setup.md) |

---

## What this is and isn't

### What this is

- A structured discipline for AI-augmented software delivery, encoding what senior engineers do.
- A library that activates conditionally — a small greenfield Node API project triggers ~20 SKILLs; an ML-heavy regulated SaaS triggers ~50.
- Tool-portable — same content works in 8 AI coding tools.
- Patterns + scaffolding for the full lifecycle, not just the coding part.

### What this isn't

- An autopilot. You're the principal; the agents do the writing; you do the judgment.
- A telemetry-driven self-improving system (yet). The discipline for self-improvement (`factory-evaluation`, `system-steward`) exists; the wired-up automation does not. Today the steward review is a structured manual cadence.
- A replacement for engineering judgment. The agents need a thoughtful human; mistakes compound otherwise.
- Battle-tested. Alpha. Validated against the kinds of projects it was designed for, but not against many real ones yet.

---

## Architecture at a glance

Four layers from invocation to evidence:

```
WORKFLOWS — named compositions (greenfield-api-service, brownfield-enhancement, ...)
       orchestrate
AGENTS — role personas (delivery-lead, product-manager, solution-architect, ...)
       consume
SKILLS — 79 SKILL.md bundles (the disciplines)
       produce evidence for
GOVERNANCE — 7 active gates with evidence packs + approver matrix
```

Two-tier orchestration: **Delivery Lead routes phases → Phase Leads run their phase → Specialists execute slices.** Cross-cutting agents (Code Reviewer, Security Reviewer, QA Engineer, Tech Writer, System Steward) gate.

For the lifecycle visualization, see [`docs/lifecycle.md`](docs/lifecycle.md). For the front-door routing logic, see [`skills/using-praxis/SKILL.md`](skills/using-praxis/SKILL.md).

---

## Project structure

```
praxis/
├── README.md                 this file
├── PLAYBOOK.md               operating guide (greenfield + brownfield walkthroughs)
├── INSTALLATION.md           detailed install playbook + troubleshooting
├── CONTRIBUTING.md           contribution guidelines
├── LICENSE                   MIT
├── install.sh                multi-tool installer
├── try-as-plugin.sh          Claude Code plugin-dir launcher
├── uninstall.sh              clean removal
├── plugin.json               Antigravity manifest
├── .claude-plugin/           Claude Code plugin + marketplace manifests
├── agents/                   16 role agents
├── skills/                   79 active SKILLs (+ 1 tombstone, skipped by installer)
├── workflows/                5 named workflows
├── governance/               governance.yaml (7 active + 4 conditional gates)
├── commands/                 7 slash commands (plugin-root location)
├── .claude/commands/         same 7 commands (project-install location)
├── .gemini/, .cursor/,
├── .opencode/, .github/      per-tool addressing
├── hooks/                    SessionStart hook + script
├── scripts/                  validator
├── references/               cross-cutting references + MISSING-INVENTORY.md
├── patterns/                 reusable solution shapes (extension point)
├── docs/                     per-tool setup guides + lifecycle viz
├── evaluations/              eval datasets + harnesses (extension point)
├── examples/                 worked examples (extension point)
└── library-backlog/          proposed but not-yet-promoted content
```

---

## Contributing

Contributions are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for what kinds of contributions fit, the conventions to follow, and the workflow.

In short:

- **Bug fixes + small additions** — open a PR.
- **New SKILLs** — open an issue first to discuss; must meet the four-condition Skill Creation Policy.
- **New references** — pick a missing one from `references/MISSING-INVENTORY.md`; follow the format of existing references.
- **Documentation improvements** — always welcome.

By participating, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Roadmap

The library is currently focused on **maturing through real-project validation**, not adding more SKILLs. Near-term:

- [ ] Test on at least 3 real greenfield projects + 2 brownfield engagements.
- [ ] Wire telemetry for `factory-evaluation` to actually consume real data.
- [ ] Write the highest-priority missing references as projects need them.
- [ ] Publish to Claude Code marketplace once stable.
- [ ] Add CI for validator + YAML parse + reference-existence checks.
- [ ] Sample dashboards for `observability` quick-start.

Long-term:

- [ ] Real factory-evaluation telemetry pipeline (the System Steward becomes data-driven).
- [ ] Worked examples for each workflow (greenfield-api, greenfield-saas, brownfield).
- [ ] Patterns directory populated from cross-project recurrences.
- [ ] More language stacks (Go, Rust, Kotlin where Spring isn't the right fit).

The library doesn't aim to keep growing in SKILL count — the [Knowledge Growth Policy](skills/system-steward.md) directs growth into references + patterns + examples, not new SKILLs.

---

## Credits + acknowledgments

The library's design draws from:

- Anthropic's Claude Code plugin format, slash commands, hooks, and SKILL.md convention.
- Addy Osmani's [`agent-skills`](https://github.com/addyosmani/agent-skills) — particularly the anti-rationalization pattern, verification discipline, and the realization that process discipline matters more than tool capability.
- C4 model (Simon Brown) for architecture documentation.
- DORA research for trunk-based development norms.
- Google's [Software Engineering at Google](https://abseil.io/resources/swe-book) and [engineering practices](https://google.github.io/eng-practices/).
- The OpenTelemetry, CNCF, and OpenAI/Anthropic AI safety communities for the agentic-AI domain conventions.

---

## License

MIT — see [`LICENSE`](LICENSE). Use it in your projects, teams, and products.

---

## Contact

Built by [Jitesh](mailto:jitesh921@gmail.com). File issues, ideas, or feedback through GitHub Issues.
