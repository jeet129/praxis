# Scenario Playbook

The operational playbook by scenario — when it applies, what to type, what
runs underneath, where you have to make a call, and what lands on disk. Read
this when you know *what kind of moment you're in* but not *which command or
prompt to reach for*. For the phase-by-phase prose walkthrough see
[`lifecycle.md`](lifecycle.md); for the full hands-on operating guide
(prompt library, cadences, troubleshooting) see [`../PLAYBOOK.md`](../PLAYBOOK.md).

## Scenario picker

| If you want to... | Go to |
|---|---|
| Turn a vague idea into a scoped, buildable brief | [Scenario 1](#1-brand-new-product-from-a-vague-idea) |
| Start a new API service where requirements are already clear | [Scenario 2](#2-greenfield-api-service-with-clear-requirements) |
| Get oriented on a codebase you just inherited | [Scenario 3](#3-adopting-an-existing-codebase--first-week-on-brownfield) |
| Add a feature to a system that already exists | [Scenario 4](#4-adding-a-feature-to-a-brownfield-system) |
| Run one slice of work interactively, watching each step | [Scenario 5](#5-one-implementation-slice-interactive) |
| Let slices run unattended overnight | [Scenario 6](#6-running-slices-autonomously-overnightunattended) |
| Figure out why a drive run stopped and get it moving again | [Scenario 7](#7-resuming-a-stalled-or-budget-stopped-drive-run) |
| Handle a production incident or ship a hotfix | [Scenario 8](#8-hotfix--production-incident) |
| Ship a release to production | [Scenario 9](#9-production-release) |
| Get a second opinion on a contract, ADR, or roadmap | [Scenario 10](#10-on-demand-review-of-a-contractadrroadmap) |
| Run the quarterly library health check | [Scenario 11](#11-quarterly-library-stewardship) |
| Understand or reduce what a project is spending on models | [Scenario 12](#12-cost-review--tuning-model-routing) |
| Switch to a new model family or add a new AI coding tool | [Scenario 13](#13-switching-or-adding-a-model-familyharness) |
| Prove feasibility before committing to a build | [Scenario 14](#14-prove-feasibility-before-committing-spike) |
| Replace a legacy system incrementally | [Scenario 15](#15-replace-a-legacy-system-modernization) |

---

## 1. Brand-new product from a vague idea

**When it applies:** you have a concept, not a spec — "an app that helps X do Y," nothing scoped yet.

**Entry point:** `/refine-idea "<topic>"` (or `/refine-idea <path-to-notes>`), then `/start` once the concept has converged.

**What runs:** `ideation-refinement-loop.yaml` — a bounded creator/reviewer/enhancer/arbiter loop (harnesses swappable, default creator=`claude`, reviewer=`codex`) iterating the concept up to `--max-passes` (default 5). Once it converges, `/start` runs `delivery-planner`, then routes automatically into `greenfield-api-service.yaml` or `greenfield-saas.yaml` per the charter, which in turn runs `/discover` → `/architect` → `/slice` (×N) → `/release`.

**Where humans intervene:** at each refinement pass's convergence check (approve now / another pass), at the `ideation_refinement_approval` gate, then at every downstream gate (`requirements_freeze`, `architecture_sign_off`, per-slice reviews, `production_go_live`).

**Recommended autonomy setting:** N/A for ideation (it's a foreground loop you watch); once slices start, `stop_after: task` until the first slice has run cleanly by hand.

**Expected artifacts:** `.project/working/ideation/` (refined artifact + run log), then `.project/semantic/project-charter.md`, and the standard greenfield artifact set per Scenario 2.

**Watch out for:** don't let the arbiter call something "100% perfect" — the command enforces convergence language (`ready for approval` / `needs another pass` / `blocked on user decision`); if you see the former, push back.

---

## 2. Greenfield API service with clear requirements

**When it applies:** you already know what you're building — skip ideation, start straight into planning.

**Entry point:** `/start`, then `/discover`.

**What runs:** `delivery-planner` writes `.project/semantic/project-charter.md`; `using-praxis` routes to `workflows/greenfield-api-service.yaml` (entry criteria: `mode == greenfield`, `target_repo_identified`, `principal_intent_captured`). Phase A: Product Manager runs `product-discovery` → `requirements-elicitation` → `requirements-interrogation` → `nfr-definition`. Phase B: Solution Architect + Architecture Challenger. Phase C/D: `/slice` per Lead Developer's decomposition. Phase E: `/release`.

**Where humans intervene:** the KUACQ block mid-Phase-A; `requirements_freeze` gate; `architecture_sign_off` gate (Challenger report is mandatory evidence); per-slice review gates; `production_go_live`.

**Recommended autonomy setting:** interactive (`/discover`, `/architect`, `/slice` one at a time) until the first slice closes cleanly, then consider `/drive` at `stop_after: task`.

**Expected artifacts:** `.project/semantic/` (charter, requirements brief, NFR register), `.project/decision/` (ADRs), `.project/working/architecture/` (C4 diagrams, roadmap), per-slice packets at `.project/working/slice-<id>-packet.md`.

**Watch out for:** don't skip `product-discovery` even when requirements feel obvious — every downstream phase reads its artifacts, not your mental model of them.

---

## 3. Adopting an existing codebase / first week on brownfield

**When it applies:** you're picking up a codebase you didn't write, before any specific change is scoped.

**Entry point:** `/audit`.

**What runs:** the brownfield first-week sequence in order — Day 1 `codebase-comprehension` (Tech Writer + Lead Developer, output to `.repo-intel/` and `.project/semantic/codebase-overview.md`), Day 2 `architecture-documentation` reconciliation (deployed reality vs existing C4/ADRs), Day 3 `tech-debt-management` initial audit (triaged register, 20-50 items), Day 4 `impact-analysis` (all four lenses) for whatever change you're about to propose, Day 5+ into `/discover`.

**Where humans intervene:** none of `/audit` itself gates formally, but you're interviewed during the Day 3 debt audit, and the Day 4 impact-analysis recommendation (proceed / proceed-with-conditions / scope-blocker) is yours to accept.

**Recommended autonomy setting:** fully interactive — this is comprehension work, not drive-eligible (no `verify` command applies to "understand the system").

**Expected artifacts:** `.repo-intel/` (system map, data flows, build/deploy story, hot paths), `.project/semantic/codebase-overview.md`, `.project/working/architecture/overview.md` (reconciled), `.project/operational/debt-register.md`, `.project/operational/impact-analyses/<change>-<date>.md`.

**Watch out for:** skipping comprehension is the single biggest brownfield failure mode — don't jump straight to the change. A 200-item, untouched debt register is worse than none; triage to 20-50.

---

## 4. Adding a feature to a brownfield system

**When it applies:** the system is understood (Scenario 3 already ran, or ran previously) and you have a specific, scoped enhancement.

**Entry point:** `/discover` (light discovery, delta-framed), then `/architect`, then `/slice` (×N).

**What runs:** `workflows/brownfield-enhancement.yaml` (entry criteria: `mode == brownfield`, `source_repo_accessible`). Phase A is a lighter discovery pass framed as deltas from the current system. Phase B mandatorily re-runs `impact-analysis` (four lenses) plus `architecture-pattern-selection` for the delta, then Architecture Challenger review. Implementation slices run identically to greenfield, plus `tech-debt-management` boy-scout fixes each slice.

**Where humans intervene:** same gate set as Scenario 2 (`requirements_freeze`, `architecture_sign_off`, per-slice reviews, `production_go_live`), evaluated against the existing system rather than a blank slate.

**Recommended autonomy setting:** interactive through Phase A/B; `/drive` at `stop_after: task` once slices are decomposed and the team trusts the workflow on this codebase.

**Expected artifacts:** `.project/operational/impact-analyses/<change>-<date>.md` (mandatory before Phase B proceeds), delta ADRs in `.project/decision/`, updated `.project/operational/debt-register.md`.

**Watch out for:** don't propose `legacy-modernization` for what's really `tech-debt-management` work — modernization is rare and expensive; reach for it only with an unambiguous business case. Run all four impact-analysis lenses — teams that skip the contract lens ship partner-integration incidents.

---

## 5. One implementation slice, interactive

**When it applies:** architecture is signed off, you want to build (or rebuild) exactly one slice, watching every step.

**Entry point:** `/slice`.

**What runs:** `/slice` delegates the whole thing to `delivery-lead`, which runs `workflows/implementation-slice.yaml`: spawns `lead-developer` first to produce the slice packet (`.project/working/slice-<id>-packet.md`) and task ledger, then dispatches the named specialist(s) (`backend-developer` / `frontend-developer` / `data-engineer` / `ml-ai-engineer`) per the decomposition, then in parallel `code-reviewer`, `security-reviewer` (if security-bearing), and `qa-engineer`. Fix loops repeat until every reviewer passes.

**Where humans intervene:** you confirm the slice choice/size/AC before it starts; you're the fix-loop's final stop only if a reviewer keeps blocking. `/drive`'s `stop_after: task` setting (see `governance/autonomy.yaml`) is what makes this genuinely one-task-at-a-time if you layer drive on top; without drive, `/slice` alone already stops at each reviewer verdict for your visibility.

**Recommended autonomy setting:** N/A — this is the manual mode Scenario 6/7 build trust toward. Use plain `/slice`, not `/drive`, until you've watched the full loop at least once.

**Expected artifacts:** `.project/working/slice-<id>-packet.md`, `.project/working/slice-<id>-tasks.yaml` (task ledger — carries the slice's `ceremony` decision and rationale, scored at open per `skills/autonomous-drive`), review/QA reports, an episodic slice-close entry.

**Watch out for:** `/slice` never spawns a specialist directly from the command — if you see that shortcut taken because "the slice is small," that's a protocol violation; the packet is what reviewers consume, no packet means broken review flow.

---

## 6. Running slices autonomously overnight/unattended

**When it applies:** you've watched `/slice` run cleanly by hand at least once and want the loop to keep going without you re-prompting each task.

**Entry point:** `/drive` (in-session, supervised) or `praxis-drive.sh (in the PLUGIN dir — see "Locating the runner" in docs/autonomous-drive.md)` (headless, unattended).

**What runs:** the drive protocol (`skills/autonomous-drive/SKILL.md`) executed one task per iteration against the active task ledger — fresh context each time, only disk state (ledger, `.project/working/`, telemetry) survives between iterations. `scripts/praxis-drive.sh` is the outer loop that invokes the harness headlessly (`claude -p` or `codex exec` per `governance/autonomy.yaml`'s `harnesses:` block) and enforces iteration caps, run budgets, and stall detection — the runner, not the agent, is what can't be talked out of the guardrails.

**Where humans intervene:** three non-negotiable stops fire regardless of the autonomy dial — decision points/ADRs, governance gates, and budget/stall/exhaustion. The optional dial (`stop_after` in `governance/autonomy.yaml`: `task` / `slice` / `phase` / `gate`) sets how often you're paused beyond that. Read `.project/telemetry/summaries/slice-<id>-summary.md` the next morning — at `stop_after: gate` the loop doesn't wait for you to read it.

**Recommended autonomy setting:** start at `stop_after: task` or `stop_after: slice` until you trust the workflow/harness; relax toward `gate` afterward. Run in a sandboxed environment (container, disposable VM, or worktree) with everything committed before the run starts.

**Expected artifacts:** `.project/telemetry/drive.jsonl` (per-iteration record: tier, cost_proxy, outcome), `.project/telemetry/summaries/slice-<id>-summary.md` (per slice close), updated `.project/working/slice-<id>-tasks.yaml`.

**Watch out for:** a task with no `verify` command is not drive-eligible and must run interactively — don't fabricate a ledger or a verify command just to make a task appear automatable. A slow or flaky `verify` wastes the iteration budget and can trigger false stalls. The ledger's `ceremony` (full/expedited/spike) only scales pre-merge review intensity at drain — governance gates still fire exactly as declared, and `governance/autonomy.yaml`'s ceremony switches can force everything to full for compliance engagements.

---

## 7. Resuming a stalled or budget-stopped drive run

**When it applies:** `scripts/praxis-drive.sh` exited with a non-zero code and you need to know why before restarting.

**Entry point:** read the exit code, then check the ledger/telemetry named below, then re-run `scripts/praxis-drive.sh` or resume `/drive` in-session.

**What runs:** diagnosis against `.project/working/slice-<id>-tasks.yaml` (the ledger — `notes` field per task) and `.project/telemetry/drive.jsonl` (per-iteration history), per exit code:

| Exit code | Meaning | What to check | How to resume |
|---|---|---|---|
| `3` | Stalled — ledger hash unchanged for `stall.max_iterations_without_ledger_change` (default 2) iterations | The current task's `verify` command achievability, or repeated identical attempts in `notes` | Fix the ambiguity or split the task, reset `attempts`, restart |
| `4` | Budget — a `run_budget` ceiling hit (iterations/slices/task attempts/cost proxy) | `scripts/factory-routing-report.py`'s drive section for where the cost proxy went | Raise the specific `run_budget` field that's legitimately too tight (don't raise all of them), re-run |
| `5` | Blocked — task exhaustion (`max_task_attempts` hit) or a non-negotiable stop (decision/gate/ADR/required KUACQ) | The attempt trail in the ledger's `notes`, or which gate/decision fired | Task exhaustion needs a human to unblock (bad spec, missing dependency, wrong verify command); a gate/decision stop is expected behavior — approve/resolve it, then resume |

**Where humans intervene:** by definition, every one of these exit codes is a human touchpoint — that's what they're for.

**Recommended autonomy setting:** unchanged from the run that stopped; only shift `stop_after` if the diagnosis reveals the dial itself was set wrong for this workflow's maturity.

**Expected artifacts:** no new artifacts beyond what the failed run already wrote; you're reading `.project/telemetry/drive.jsonl` and the ledger, and optionally producing a fresh `factory-routing-report.py` output.

**Watch out for:** exit `5` from a gate or decision point is not a failure — don't treat it as something to "fix"; it's the guardrail working as designed. Don't blanket-raise every `run_budget` field after a `4` — find the actual bottleneck first.

---

## 8. Hotfix / production incident

**When it applies:** something is broken in production, or you're shipping an urgent fix.

**Entry point:** the `incident-runbook` skill's severity taxonomy classifies the incident first; P0/P1 (or a critical security patch) is expedited-path eligible and routes into `workflows/expedited-change.yaml`; anything below that bar reroutes to `brownfield-enhancement.yaml` and Scenario 4 applies instead.

**What runs:** `expedited-change.yaml` — compressed gates now: scope containment (smallest viable change, blast radius named), a single combined blocker-only review pass, rollback readiness armed before deploy, then the `expedited_change_approval` gate (single approver). Deploy runs. The MANDATORY retroactive half then fires within the declared retro window (default 5 business days): a full normal-bar code + security review pass, a blameless postmortem, tech-debt entries for every shortcut taken, and the `expedited_change_retro` gate.

**Where humans intervene:** `expedited_change_approval` (compressed evidence: fix diff, blast radius, tests passing, rollback plan) before deploy; `expedited_change_retro` (full review, postmortem, action items, tech-debt entries) after — this second gate is not optional.

**Recommended autonomy setting:** interactive — incident response and hotfix review are exactly the kind of judgment-heavy work drive mode's loop-contract rule excludes ("looks good" is not an exit condition; incident triage rarely reduces to one).

**Expected artifacts:** postmortem doc (per `incident-runbook`'s template), tech-debt entries in `.project/operational/debt-register.md` for every shortcut and deferred major finding, the retro review verdicts, and — once eligible for a full release — the standard release evidence pack in `.project/operational/releases/`.

**Watch out for:** skipping the retroactive half is a governance violation, not a shortcut worth taking twice — missing the declared retro window escalates to the principal immediately rather than slipping quietly. Compressed gates now are a loan, not a discount.

---

## 9. Production release

**When it applies:** a milestone of slices is ready to ship.

**Entry point:** `/release`.

**What runs:** `workflows/production-release.yaml`, led by Platform/SRE, assembling the evidence pack for `production_go_live`: always-required baseline (all pre-prod gates cleared, DR drill recent pass, capacity sizing verified, SLO observability live, rollback plan documented, supply-chain attestation) plus conditional items evaluated by `delivery-planner` per change characteristics (chaos-engineering pass if resilience-critical, performance soak if NFR-bearing, compliance evidence if a regulated regime applies, threat-model update if architecture/trust boundaries changed). If `has_ml` or `has_agentic_ai`, `responsible_ai_review`'s own evidence pack also gates.

**Where humans intervene:** `production_go_live` itself — the principal reviews the full evidence pack (not just "approve?") and approves, rejects, or sends back with rationale.

**Recommended autonomy setting:** interactive — `production_go_live` is one of the three non-negotiable stops even under `/drive`; it will pause regardless of the dial.

**Expected artifacts:** `.project/operational/releases/<release>-record.md` (evidence pack + DR attestation), release notes (per `technical-documentation`), post-release SLO observation window notes.

**Watch out for:** if `production_go_live` keeps failing on first submission, that's a signal the evidence-gathering has an upstream gap — diagnose which item is missing each time rather than treating each failure as a one-off.

---

## 10. On-demand review of a contract/ADR/roadmap

**When it applies:** an architecture-significant artifact was produced or revised *outside* a governance gate — a contract baseline authored after `architecture_sign_off`, a roadmap revised mid-build — and needs a structured second look.

**Entry point:** `/review <contracts|roadmap|adrs|path>`.

**What runs:** `architecture-challenger`, `code-reviewer` (Dimension 6: API/data contracts), and `security-reviewer` run in parallel against the scoped artifact plus its governing inputs (project charter, relevant ADRs, NFR register). Findings are classified BLOCK/FIX/ACCEPT, mapped to an owner agent (usually `solution-architect`; `ml-ai-engineer` for AI-safety surfaces), dispatched, fixed, and re-reviewed — the loop repeats until no BLOCK remains.

**Where humans intervene:** disputed findings or accept-rather-than-fix decisions route to the principal (mirrors `challenger_objection_override`); safety/privacy BLOCKs specifically require explicit principal sign-off and can't be accepted by the owner alone.

**Recommended autonomy setting:** interactive — this command's whole purpose is a closed remediation loop with an owner and a status, not something to run unattended.

**Expected artifacts:** `.project/operational/reviews/<artifact>-<YYYY-MM-DD>.md` with a findings table (id, severity, surface, ADR/NFR, owner, disposition, status) and a top-line OPEN → IN-REMEDIATION → CLOSED status.

**Watch out for:** "the SA generated it, so it's reviewed" is explicitly called out as a rationalization to ignore — generation isn't review. While status ≠ CLOSED, BLOCK findings on a contract surface gate any slice that consumes that surface.

---

## 11. Quarterly library stewardship

**When it applies:** every ~90 days (the SessionStart hook reminds you when overdue), independent of any single project.

**Entry point:** `/steward`.

**What runs:** `scripts/factory-usage-report.py` mines the quarter's checkpoint records (`.project/episodic/checkpoint-*.md`, the primary usage source) for per-skill/agent/workflow/command usage; `scripts/factory-routing-report.py` aggregates the JSONL telemetry streams for tier/cost/routing-discipline figures; `factory-evaluation` synthesizes both into a factory report covering library health, skill efficacy, agent performance, workflow completion, and gate-clearance times; `system-steward` reads it end-to-end and drafts the quarterly report (findings, proposals — lifecycle changes, trigger tunings, reference/pattern additions, consolidations, deprecations — with evidence + risk + rollback plan per proposal, plus an explicit "items NOT proposed" section).

**Where humans intervene:** `steward_promotion` gate, per-proposal granularity — the principal approves or rejects each proposal individually within the same report; rejected proposals become ADRs.

**Recommended autonomy setting:** interactive, run as a single 1-2 day block, not more often (over-tweaking) and not less (drift).

**Expected artifacts:** `.project/telemetry/reports/usage-report-<date>.md` and `routing-report-<date>.md`, the steward report itself, per-proposal evidence under `.project/operational/library-evolution/`.

**Watch out for:** "nothing changed this quarter, skip it" is called out as a rationalization to ignore — telemetry exists, review it. Skill count above ~90 is review zone, above 101 is mandatory consolidation; growth is supposed to flow into references/patterns/examples, not new SKILLs.

---

## 12. Cost review / tuning model routing

**When it applies:** you want to know what a project is actually spending tier-wise, or `deep`-tier usage feels high and needs tightening.

**Entry point:** `python3 scripts/factory-routing-report.py --project-dir <path>`.

**What runs:** the report aggregates layer (b)'s JSONL telemetry streams — deterministic `agent-spawns.jsonl` and `drive.jsonl`, plus discipline-dependent `model-routing.jsonl` (with `routing-*.md` frontmatter as its recovery fallback) — cross-referenced against layer (c)'s supplementary factory-metrics records, producing per-slice dispatches, per-agent activity, tier & cost-proxy breakdown (each figure labeled `default`/`observed`/`decided`), routing-discipline coverage %, and heuristic recommendations. See [`telemetry.md`](telemetry.md) for the full three-layer definitions.

**Where humans intervene:** you decide what to change based on the report — e.g., adjust `governance/model-routing.yaml`'s `cost_weights` (relative proxies, not dollars) or a project-local fast-path override in `.project/procedural/model-routing-overrides.md` — then re-apply via `scripts/apply-model-routing.py`.

**Recommended autonomy setting:** N/A — this is an analysis + tuning step, always human-driven.

**Expected artifacts:** `.project/telemetry/reports/routing-report-<YYYY-MM-DD>.md` (default output path), unchanged unless you `--out` elsewhere.

**Watch out for:** the cost figures are tier-weighted proxies (`deep: 5.0`, `standard: 1.0`, `light: 0.25`), not dollar amounts — use them for quarter-over-quarter relative comparison, not absolute accounting. Low routing-discipline coverage % means `delivery-lead` is routing off defaults without logging why — a steward-review flag, not necessarily a cost problem.

---

## 13. Switching or adding a model family/harness

**When it applies:** a vendor ships a new flagship model, or you're onboarding a harness Praxis doesn't yet support.

**Entry point:** edit `governance/model-routing.yaml` directly (one file), then run `scripts/apply-model-routing.py`.

**What runs:** for an existing harness, editing the relevant tier's model name in `harnesses.<harness>.map` and running `apply-model-routing.py` rewrites every `agents/*.md` frontmatter `model:` field (and `codex-plugin-assets/codex-agents/*.toml` for Codex) to match — no agent-by-agent hand edits. `--check` mode (also run in CI) verifies nothing is left stale. For a wholly new harness, add a `harnesses:` block naming its `field` and tier map, extend `apply-model-routing.py` with a writer function for its config format, add an `install.sh --tool=<name>` layout if needed, and add a `docs/<tool>-setup.md`.

**Where humans intervene:** the edit itself is manual and reviewed like any config change; nothing here is a gate, but a compliance-critical engagement can force every agent to one tier via `overrides.force_tier` as a deliberate governance decision.

**Recommended autonomy setting:** N/A — this is a one-file maintainer edit, not a workflow to run autonomously.

**Expected artifacts:** the diff to `governance/model-routing.yaml`, the regenerated `agents/*.md` frontmatter (and Codex TOML), and — for a new harness — a new `docs/<tool>-setup.md` plus a row in `README.md`'s tool compatibility table.

**Watch out for:** never hand-edit a `model:` field directly in an agent file — CI's `apply-model-routing.py --check` will flag it as drifted from the routing table and fail the build.

---

## 14. Prove feasibility before committing (spike)

**When it applies:** you have a question to answer or a bet to test — "will users do X," "can this library sustain our throughput" — before committing to a full build.

**Entry point:** address `workflows/spike.yaml` directly through `using-praxis` routing (no dedicated slash command yet); name the question and declare a time box (default 3 days) in `principal_intent`.

**What runs:** a spike brief (Product Manager for market/product questions, Solution Architect for technical/feasibility questions) names the question and what evidence would answer it. The `build_to_learn_loop` (Lead Developer dispatching whichever specialist fits) writes throwaway code — no PR, no code-review or security-review gate — bounded by `max_iterations: 5` and exiting the moment the question is answered or the time box expires, whichever comes first. Tech Writer then produces the spike report (answer, evidence, what production-grade would cost).

**Where humans intervene:** the `spike_disposition` gate — an explicit archive-or-promote call, evidence-backed by the spike report. There is no gate inside the build-to-learn loop itself; that's deliberate.

**Recommended autonomy setting:** interactive for the brief and disposition call; the build-to-learn loop can run under `/drive`-style iteration but stops hard at its loop contract regardless.

**Expected artifacts:** the spike report (the one artifact allowed to outlive the spike), the evidence artifact backing it, and either an archived-path record or a `discovery_entry_point` handoff into greenfield/brownfield discovery.

**Watch out for:** spike code NEVER merges to a production branch — promotion means the *report* becomes an input to discovery, not that the throwaway implementation enters the codebase. An inconclusive spike (time box expired, question unanswered) still gets a report — force the write-up honestly rather than treating it as a failure to hide.

---

## 15. Replace a legacy system (modernization)

**When it applies:** a legacy system has a documented driver to go (EOL, cost, or risk) and you want an incremental, strangler-fig replacement rather than a big-bang rewrite.

**Entry point:** address `workflows/modernization.yaml` directly through `using-praxis` routing, normally after `/audit`'s brownfield comprehension has run or is scheduled.

**What runs:** Phase 1 deep comprehension (deeper than standard brownfield `codebase-comprehension`) plus seam identification, ranked by risk. Phase 2 target architecture + migration strategy (per-seam data-migration approach, a coexistence contract for parallel-run) plus a deep-tier Architecture Challenger pass scoped to migration-specific failure modes, gated at `modernization_strategy_sign_off`. Phase 3 is a bounded per-seam increment loop: carve the seam, write characterization tests against *legacy* behavior, build the replacement as an `implementation-slice` sub-workflow, run old and new in parallel with comparison telemetry, clear the `parallel_run_verification` gate, then shift traffic. Phase 4/5 cut over and decommission the legacy system behind its own `legacy_decommission_approval` gate.

**Where humans intervene:** `modernization_strategy_sign_off` before any seam is touched; `parallel_run_verification` per increment (comparison telemetry + delta report + characterization suite as evidence); `legacy_decommission_approval` after cutover is clean, before infra teardown.

**Recommended autonomy setting:** interactive through Phases 1-2 and every gate; the per-increment build-replacement-slice step can run under `/drive` once the migration plan and coexistence contract are signed off.

**Expected artifacts:** `.repo-intel/` (deep pass), `migration_plan` + `increment_sequence` + `coexistence_contract` in `.project/working/`, an architecture ADR, per-seam characterization test suites and delta reports, and a `data_archival_record` + `teardown_record` at decommission.

**Watch out for:** don't reach for this workflow for what's really `tech-debt-management` work — modernization is the replacement of the system itself, not a feature within it. Traffic never shifts on a seam without a clean `parallel_run_verification` — a divergent delta freezes that seam on legacy and routes back to the replacement slice, it doesn't get waved through.

---

## See also

- [`../PLAYBOOK.md`](../PLAYBOOK.md) — the full operating guide: prompt library, cadences, troubleshooting, Codex addendum.
- [`lifecycle.md`](lifecycle.md) — the six-phase project lifecycle, gate-by-gate.
- [`operating-model.md`](operating-model.md) — the big-picture diagrams (operating model, layer stack, drive loop, slice lifecycle).
- [`autonomous-drive.md`](autonomous-drive.md) — the full drive-mode operator guide behind Scenarios 6 and 7.
- [`model-routing.md`](model-routing.md) and [`telemetry.md`](telemetry.md) — the mechanics behind Scenario 12.
- `skills/using-praxis/SKILL.md` — the intent-routing table this playbook is grounded in.
