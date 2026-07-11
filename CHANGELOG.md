# Changelog

All notable changes to Praxis are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres, loosely, to [Semantic Versioning](https://semver.org/) —
loosely because the library is pre-1.0 and alpha; expect breaking reshuffles between
minor versions until it stabilizes.

---

## [Unreleased]

### Added

- Telemetry redesigned around checkpoint records — the universal aggregation point at EVERY closure boundary (gate, phase end, slice close, loop convergence, disposition, workflow end), covering discovery/architecture/ideation/release phases that have no slice: structured episodic entries (agents_dispatched, skills_consumed, artifacts, cost_proxy, human touchpoints) written by delivery-lead at the AOP Document step; new scripts/factory-usage-report.py mines checkpoints + packets/ledgers/routing/commands/sessions into per-skill/agent/workflow usage analytics; hooks/tap.sh slimmed (retired the ~5%-capture per-Read and preload stub files and per-session stub files — sessions now one JSONL line each); factory-frequency/aging marked legacy; factory-evaluation and docs/telemetry.md updated to the mined-artifacts model. Zero incremental token cost: analytics ride on artifacts the workflow already produces.


- Brownfield parity for governance seeding: /audit (all copies + Codex praxis-audit) gains a Day-0 setup step — initialize the .project tree, seed .project/governance/ overrides, and ask the same routing/autonomy tuning question as /start, with a brownfield-specific suggestion of stop_after: slice until characterization-test coverage is trusted.


- Governance overrides now seed automatically: the SessionStart hook copies model-routing.yaml + autonomy.yaml into `.project/governance/` on first session (project copies win, survive plugin updates), and `/start` (all harnesses incl. Codex praxis-start) asks the user once whether to keep default adaptive routing/autonomy or tune force_tier / cost_weights / stop_after / run_budget for the engagement — answers applied to project copies only. build-registry.py now also maintains the /start count line.


- Per-project governance overrides: `.project/governance/model-routing.yaml` and `.project/governance/autonomy.yaml` now win over the plugin-shipped copies (consumed by praxis-drive.sh, factory-routing-report.py, and delivery-lead's runtime routing) — engagements can tune force_tier / cost_weights / stop_after / budgets without editing the installed plugin; documented in docs/model-routing.md.


- UI-quality enforcement wired end-to-end: `visual_review` branch in the pre-merge gate of `implementation-slice.yaml` (ux-designer reviews implementation screenshots against the design plan/tokens/frontend-design calibration; fires only on UI-bearing slices; blockers feed the same fix loop), UX hand-off now emits `design_tokens` + `design_plan`, FE/mobile branches capture `ui_screenshots` as evidence, task ledgers gain a `visual_review` gate key and token-lint in FE task `verify`, ux-designer produces `.project/semantic/design-brief.md` at first engagement, and delivery-planner gains a `design_fidelity` flag.


- `frontend-design` skill (experimental): harness-portable visual-design craft adapted from Anthropic's open frontend-design skill — subject-grounded direction, two-pass plan-then-critique process, anti-generic calibration (the three AI-default looks), interface-copy rules, and a free-first design-tooling fallback chain (Figma MCP -> community/Penpot -> Stitch/v0 free tiers -> token-themed shadcn baseline -> text-only floor). Consumed by frontend-developer, mobile-developer, and ux-designer.


- **Three new workflows + six conditional governance gates.** `workflows/expedited-change.yaml`
  (P0/P1 incident or critical-security-patch fast path: compressed gates now —
  scope containment, blocker-only combined review, rollback readiness —
  gated by `expedited_change_approval`, repaid by a MANDATORY retroactive
  full review + blameless postmortem + tech-debt entries, gated by
  `expedited_change_retro`); `workflows/spike.yaml` (time-boxed feasibility
  exploration; a bounded build-to-learn loop with no review gate on the
  throwaway code, gated only at disposition — `spike_disposition` —
  archive or promote the report into discovery; spike code never merges);
  `workflows/modernization.yaml` (strangler-fig legacy replacement: deep
  comprehension + seam identification, target architecture + migration
  strategy sign-off at `modernization_strategy_sign_off`, a per-seam
  increment loop with characterization tests + `implementation-slice`
  sub-workflow + parallel-run comparison telemetry gated at
  `parallel_run_verification`, then a gated legacy decommission phase at
  `legacy_decommission_approval`). Total: 9 workflows, 17 gates (6 core +
  11 conditional). Plus a "Workflow composition policy" section in
  `skills/using-praxis/SKILL.md` and a workflow-selection table in
  `skills/delivery-planner/SKILL.md`: a scenario earns a new workflow file
  only when its gate topology differs, otherwise it's planner
  parameterization of an existing template — the anti-sprawl rule that
  keeps workflow-count creep a `factory-evaluation` decay signal alongside
  skill-count creep.
- **Autonomous drive mode.** `scripts/praxis-drive.sh` — a Ralph-style outer
  runner that re-invokes a fresh-context harness against the task ledger
  until a stop condition fires (exit codes: `0` natural, `3` stalled, `4`
  budget, `5` blocked); the autonomy dial (`stop_after` in
  `governance/autonomy.yaml`, the three non-negotiable stops, the
  first-slice-of-phase rule) plus run budgets and stall detection; loop
  contracts and the task ledger schema (`references/loop-contracts.md`,
  `.project/working/slice-<id>-tasks.yaml`); the `skills/autonomous-drive`
  delivery-lead protocol; the `/drive` command; drive telemetry at
  `.project/telemetry/drive.jsonl` plus a drive section in
  `scripts/factory-routing-report.py`; slice-close async summaries at
  `.project/telemetry/summaries/`; new operator docs
  `docs/autonomous-drive.md` and `docs/operating-model.md`.
- Cost/routing telemetry completed: `hooks/tap.sh` now writes deterministic spawn/completion events (with model and token fields when available) to `.project/telemetry/agent-spawns.jsonl`; `scripts/factory-routing-report.py` aggregates structured telemetry, prose routing logs, and usage records into a per-slice routing/cost report (cost proxy via `cost_weights` in `governance/model-routing.yaml`); JSONL schemas documented in `references/factory-metrics-schema.md`.
- Documentation overhaul: new `docs/quickstart.md` (5-minute path), `docs/telemetry.md`, `docs/model-routing.md`; README docs index; per-tool verify-your-install checklists; CONTRIBUTING validator/generated-surfaces/skill-authoring guides.
- Pre-commit hook now reminds the committer to double-check documentation when core artifacts change without any doc change (non-blocking).


- Four new skills (state: experimental): `feature-flags-progressive-delivery`, `schema-migration`, `caching-strategy`, `developer-experience`.

- **Abstract capability tiers.** Agents now declare a harness-agnostic `capability_tier`
  (`deep | standard | light`) in frontmatter instead of a concrete model name.
  `governance/model-routing.yaml` is the single file that maps tiers to concrete
  models per harness (Claude Code, Codex, Gemini CLI); `scripts/apply-model-routing.py`
  applies the mapping and rewrites `agents/*.md` frontmatter and
  `codex-plugin-assets/codex-agents/*.toml` accordingly (`--check` mode for CI).
- **Runtime ±1-tier adaptive routing.** `delivery-lead` scores each sub-agent spawn
  against the `adaptive-model-routing` rubric and may shift the agent's default tier
  up or down by one step; on gate failure it promotes one tier and retries once before
  escalating to the human. Every routing decision is logged to
  `.project/telemetry/model-routing.jsonl` for cost/quality analysis.
- **`definition-of-done` skill** — a shared, explicit checklist agents apply before
  declaring a slice, phase, or release complete.
- **`mobile-developer` agent** — a new specialist role for mobile-stack implementation
  work, following the existing Tier-2 specialist pattern (backend/frontend/data/ml).
- **Registry + validator scripts and CI** — scripts that build and check the
  agent/skill/workflow registry (`scripts/build-registry.py --check`), wired into CI
  so skill/agent/workflow counts and cross-references stay accurate without manual
  bookkeeping.
- **10 new reference files** — filled in from the highest-priority items tracked in
  `references/MISSING-INVENTORY.md`.
- **Repo governance docs** — `CHANGELOG.md` (this file), `SECURITY.md`, `ROADMAP.md`.

### Fixed

- Routing-decision logging made resilient: delivery-lead now embeds the tier decision (agent/default_tier/chosen_tier/score/reason) in every routing-*.md frontmatter as part of the routing-transparency discipline it demonstrably follows, with the model-routing.jsonl append folded into the same step; factory-routing-report.py recovers frontmatter decisions as decided records when the JSONL is missing; session-start hook pre-creates .project/telemetry/ so appends cannot fail on a missing directory.


- Visual review propagated to ALL harness surfaces after double-check: greenfield-saas's inline review cluster (visual_review step + FE branch screenshots + frontend-design skill), Codex praxis-slice command skill, /slice command in all four copies, autonomous-drive drain step, definition-of-done (now nine gates incl. visual review), using-praxis slice chain, output-skill-map telemetry patterns, and screenshot-capture duty in frontend/mobile developer agents. Found and fixed real drift: .claude/commands/{slice,release}.md had fallen behind the canonical commands/ copies — now synced, and CI gains a command-copy drift check so it cannot recur. Brownfield-enhancement and modernization inherit visual review via the implementation-slice sub-workflow.


- Cleared remaining line-budget warnings: Codex adaptive-model-routing overlay slimmed 369 -> 298 (examples/tables to references/), using-praxis 330 -> 299 (gate-topology and agent-mapping tables to references/); validate-skills.sh now counts `capability: command` adapter skills separately from the 70-90 knowledge-skill health band.


- Delegation-chain contradiction resolved: canonical two-tier model is now unambiguous — Lead Developer (not Delivery Lead) dispatches specialists per the ledger DAG and validates integration; Delivery Lead resumes at review gates. Harness fallback documented for environments that cannot nest agent spawns. Parallelism rule made explicit everywhere (delivery-lead, lead-developer, implementation-slice.yaml, loop-contracts, Codex praxis-slice): dependencies are on contract artifacts, not on sibling implementations — FE/test start when the contract lands.


- Drive runner stop summary no longer over-counts iterations by one; scenario operational playbook added at docs/scenarios.md; README value prop, badges, and counts brought fully current; PLAYBOOK/quickstart counts and command lists synced (11 commands incl. /drive).


- Second external review (8 findings): restored executable bits on all scripts/hooks (now CI-checked); unified the last stale routing-log path in `using-praxis`; fixed `install.sh` Cursor rule filename; added the 3 missing Gemini command TOMLs (`review`, `refine-idea`, `factory-record` — Gemini now has all 10); `using-praxis` routing tree/table now covers `/refine-idea`, `/review`, `/factory-record` and describes Markdown commands; `/start` counts corrected and now auto-routes to the next phase instead of prompting; CI now rebuilds and freshness-checks the Codex package, verifies exec bits, telemetry-path consistency, and installer path references; gate count (11) now derived from `governance.yaml` by `build-registry.py` and corrected in both manifests.

### Changed

- External-review fixes: `.claude/commands/` now carries all 10 Markdown commands and `install.sh`/`INSTALLATION.md` describe the `.md` command format; routing telemetry unified on `.project/telemetry/model-routing.jsonl`; `ideation-refinement-loop` artifact state made explicit (`loop_state.current_artifact` / `previous_artifact` with a `state_update` step); Codex `adaptive-model-routing` overlay aligned with capability tiers (6 high / 10 medium / 1 low, generated — not hand-edited); added Codex `praxis-refine-idea` command skill; `validate-codex-plugin.sh` now requires `mobile-developer`; `build-registry.py` also maintains slash-command counts and README/install.sh count phrases; trailing whitespace cleaned.


- Library-wide progressive-disclosure pass: every SKILL.md now <=300 lines; embedded templates, worked examples, and long code blocks moved to per-skill `references/` files (19 skills slimmed this round).
- Reliability-cluster ownership boundaries clarified: `resilience-patterns` (in-process fault handling), `distributed-systems-patterns` (cross-service coordination; now owns outbox/saga), `reliability-dr` (availability architecture), `chaos-engineering` (verification practice).


- **Skill slimming** — trimmed several SKILL.md bundles to reduce redundancy and
  keep the library under its own bloat thresholds (see PLAYBOOK.md §10,
  "library is starting to feel bloated").
- `README.md` and `PLAYBOOK.md` updated to describe capability-tier routing in place
  of the previous Opus/Sonnet-hardcoded language, and to be explicit that YAML
  workflows are declarative specs interpreted by `delivery-lead`, not a deterministic
  execution engine.
- `scripts/build-codex-plugin.sh` — generated Codex package README now warns
  explicitly that the generated output is not the place to make edits.

---

## [0.1.0-alpha] — initial library

The first alpha release of Praxis: a tool-portable AI-delivery platform — skills,
role agents, workflows, and governance gates for end-to-end software delivery with
AI coding agents.

### Added

- Role-agent library covering delivery lead, product/discovery, architecture
  (+ architecture challenger), UX, backend/frontend/data/ML specialists, code
  review, security review, QA, tech writing, platform/SRE, and system-steward
  roles.
- SKILL.md library spanning foundation, lifecycle, discovery, architecture, UX,
  stack packs, quality + security, build + deploy, ops, data, ML, agentic-AI,
  and maintenance disciplines — each with an anti-rationalization table and a
  verification checklist.
- Named workflow compositions: `greenfield-api-service`, `greenfield-saas`,
  `brownfield-enhancement`, `implementation-slice`, `production-release`.
- Governance gate set (`governance/governance.yaml`) with evidence packs and an
  approver matrix, including `requirements_freeze`, `architecture_sign_off`,
  `production_go_live`, `responsible_ai_review`, and `steward_promotion`.
- Adaptive model-routing skill (5-signal scoring rubric).
- Telemetry stack: `hooks/tap.sh` PostToolUse tap + `factory-record.sh` +
  `factory-aging.sh` + `factory-frequency.sh`.
- Multi-tool install paths: Claude Code plugin-dir, Codex plugin marketplace,
  file-based install for 8 supported AI coding tools.
- Six-type project memory taxonomy under `.project/`.
- Cross-cutting reference library plus `references/MISSING-INVENTORY.md` tracking
  the remaining backlog.

[Unreleased]: https://github.com/jeet129/praxis/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/jeet129/praxis/releases/tag/v0.1.0-alpha
