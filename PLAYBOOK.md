# Praxis — Operating Playbook

How to actually use this library in real projects. Greenfield and brownfield, on Claude Code first, with a Codex addendum at the end. Practical: real prompts, real directory layout, real cadences.

This playbook assumes you've read the `README.md` at least once.

---

## 0. Looking for a specific scenario?

If you already know which situation you're in — greenfield from an idea,
brownfield first week, overnight drive run, hotfix, release, quarterly
review, cost tuning, and so on — go straight to
[`docs/scenarios.md`](docs/scenarios.md). It's a scenario-by-scenario index:
entry point, what runs, where you approve something, and what lands where.
This playbook is the deeper narrative version of the same material; the
scenario doc is the fast lookup.

---

## 1. What this playbook is

A hands-on operating guide. It answers questions you'll have during use:

- "I'm starting a new project — what do I do first?"
- "How do I make Claude Code actually invoke the right skill at the right moment?"
- "When should I let the Delivery Lead orchestrate vs invoke a specialist directly?"
- "I'm picking up an existing codebase — what changes?"
- "It's quarterly review time — what do I run?"

If you find yourself doing something this playbook doesn't cover, that's a signal to extend it. The playbook is itself a working artifact; treat it like one.

---

## 2. Installation

Two paths: the bundled installer script (recommended) or manual copy. Both produce the same result.

### 2.1 The fast path — `install.sh`

The library ships with an `install.sh` script that copies everything to the right place and creates the `.project/` memory tree in one shot.

From inside the `praxis/` directory:

```bash
cd /path/to/praxis

# Most common: install into a project repo for Claude Code
./install.sh /path/to/your-project-repo

# Or: user-global Claude Code install
./install.sh --user

# Or: Codex install (writes .team/ + AGENTS.md routing file)
./install.sh --codex /path/to/your-project-repo

# Or: both Claude Code AND Codex layouts side by side
./install.sh --both /path/to/your-project-repo

# Always safe to preview before committing
./install.sh --dry-run /path/to/your-project-repo
```

What it does:

- Validates the library root looks right (refuses to run from the wrong place).
- Copies `agents/`, `skills/`, `workflows/`, `governance/`, `patterns/`, `references/` to the right subdirectory (`.claude/` for Claude Code; `.team/` for Codex).
- Brings `README.md` and `PLAYBOOK.md` along so they travel with the install.
- For Codex: writes an `AGENTS.md` at the repo root that routes Codex to the library.
- Creates the full `.project/` memory tree (17 directories) with seeded index files.
- Refuses to overwrite an existing install (use `--force` to override).
- Prints next-steps when done.

Flags:

| Flag | Effect |
|---|---|
| `--user` | Install user-global (`~/.claude/`) instead of project-local. |
| `--codex` | Codex addressing (`.team/` + `AGENTS.md` at repo root). |
| `--both` | Alias for `--tool=all`: installs EVERY harness layout side by side (all 8), not just Claude Code + Codex. |
| `--dry-run` | Print what would happen; change nothing. |
| `--force` | Overwrite existing install. |
| `--skip-memory` | Skip `.project/` memory tree creation. |
| `--help` | Show usage. |

There's also an `uninstall.sh` companion (preserves `.project/` memory by default; pass `--purge-memory` to wipe it).

### 2.2 The manual path

If you'd rather not run scripts, the install is just file copies. From inside `praxis/`:

```bash
# Claude Code, project-local
TARGET=/path/to/your-project-repo
mkdir -p "$TARGET/.claude"
cp -R agents skills workflows governance patterns references README.md PLAYBOOK.md "$TARGET/.claude/"

# Memory tree
mkdir -p "$TARGET"/.project/{semantic,episodic,procedural,decision,working/architecture}
mkdir -p "$TARGET"/.project/operational/{runbooks,releases,ml-models,impact-analyses,factory-metrics,library-evolution,risk-acceptances,doc-audit,modernization,architecture-reconciliation}
touch "$TARGET/.project/decision/INDEX.md"
touch "$TARGET/.project/operational/debt-register.md"
```

For Codex, substitute `.team/` for `.claude/` and add an `AGENTS.md` routing file at the repo root (see §9 for the template).

### 2.3 The polished path — plugin install (RECOMMENDED, available now)

Praxis IS a plugin on both primary harnesses — this is the recommended install, ahead of the copy paths above:

```text
# Claude Code (marketplace + plugin manifests ship at the repo root)
/plugin marketplace add jeet129/praxis          # append @<branch> to pin a branch
/plugin install praxis@praxis

# Codex (generated package under plugins/praxis-codex/)
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
/plugins   → install praxis-codex               # add --ref <branch> to pin a branch
```

Nothing is copied into your repo; updates arrive by updating the plugin. Full detail: `docs/claude-code-setup.md` and `docs/codex-setup.md`. The `install.sh` copy paths above remain for the other six harnesses, frozen snapshots, and offline/CI use.

### 2.4 Sanity check

After install, open the project in your tool and paste:

```
You: I just installed the Praxis. Confirm you can see the agents
and skills, and tell me which roles and which skills are available. Then read
the governance.yaml and summarize the active gates.
```

You should see Claude Code list **17 agents**, **91 skills**, and the **6 core governance gates** (plus 12 conditional project-specific gates). If it can't see them, the install scope is wrong — re-run `install.sh --dry-run` to confirm the destination.

---

## 3. The mental model (one screen)

Four layers. Each invocation flows top-down.

```
┌─────────────────────────────────────────────────────────┐
│ WORKFLOWS — named compositions (greenfield-api-service, │
│   brownfield-enhancement, greenfield-saas,              │
│   implementation-slice, production-release)             │
└────────────────────────┬────────────────────────────────┘
                         │ orchestrated by
┌────────────────────────▼────────────────────────────────┐
│ AGENTS — role agents that DO the work                   │
│   Tier 0: delivery-lead                                 │
│   Tier 1: product-manager, solution-architect,          │
│           lead-developer, platform-sre, ux-designer     │
│   Tier 2: backend-dev, frontend-dev, data-engineer,     │
│           ml-ai-engineer                                │
│   Cross-cutting: architecture-challenger, code-reviewer,│
│           security-reviewer, qa-engineer, tech-writer,  │
│           system-steward                                │
└────────────────────────┬────────────────────────────────┘
                         │ consume
┌────────────────────────▼────────────────────────────────┐
│ SKILLS — the 91 SKILL.md bundles                        │
│   (foundation, lifecycle, discovery, architecture,      │
│    stack packs, quality+security, build+deploy,         │
│    infra, ops, data, ml, agentic-ai, maintenance, ...)  │
└────────────────────────┬────────────────────────────────┘
                         │ produce evidence for
┌────────────────────────▼────────────────────────────────┐
│ GOVERNANCE — gates that route through governance.yaml   │
│   (requirements_freeze, architecture_sign_off,          │
│    production_go_live, responsible_ai_review,           │
│    steward_promotion, ...)                              │
└─────────────────────────────────────────────────────────┘
```

Two cross-cutting layers wrap around these four:

```
       ↕ before every sub-agent spawn: adaptive-model-routing
         (5-signal score → ±1 shift from the agent's default capability_tier:
          deep / standard / light, resolved to a concrete model per harness
          via governance/model-routing.yaml)

       ↕ at every closure boundary: delivery-lead writes a checkpoint record
         (.project/episodic/checkpoint-<timestamp>-<label>.md — the
          universal telemetry aggregation point, mined by
          scripts/factory-usage-report.py)
```

Both fire automatically as part of the workflow, without you invoking them explicitly. The routing SKILL picks the model on each spawn; the checkpoint record is a mandatory AOP deliverable at every gate/phase/slice/loop closure — not a hook riding on a tool event — so the Steward has real, near-complete data at quarterly review. A slimmer hook layer (`hooks/tap.sh`) still writes deterministic JSONL streams (`agent-spawns.jsonl`, `sessions.jsonl`, `drive.jsonl`) plus command stubs; the old per-Read skill/agent/session stub types are retired. See [`docs/telemetry.md`](docs/telemetry.md) for the full three-layer breakdown.

### When to invoke which layer

- **Workflow** when starting a new project, new slice, or release.
- **Agent (by name)** when you want a specific role's perspective: "Architecture Challenger, review this." "Security Reviewer, audit this PR." For most work, the Delivery Lead picks the agent.
- **Skill (by name)** when you want a specific discipline applied: "Apply `threat-modeling` to this design." For most work, the agent picks the skill.
- **Governance gate** never invoked directly — gates fire from workflow steps; you approve when they reach you.
- **Model routing** never invoked directly — the Delivery Lead runs `adaptive-model-routing` before each spawn. Reach into it only when: (a) you're opening a session and need to pick a tier up-front, (b) a spawn's route looks wrong, (c) `deep`-tier usage is running high and needs to be conserved for the work that actually needs it.
- **Telemetry** never invoked directly — delivery-lead writes a checkpoint record at every closure boundary as part of the workflow itself. Reach in only when: (a) writing a rich per-use observation via `/praxis:factory-record`, (b) running `scripts/factory-usage-report.py` / `scripts/factory-routing-report.py` for weekly / quarterly review.

Default: invoke the workflow. Let it orchestrate. Model routing + telemetry fire underneath. Specialize only when needed.

---

## 4. The first 30 minutes

Before starting real work, do this once per project:

### 4.1 Install (5 min)

Per §2.1 + §2.3.

### 4.2 Bootstrap the planner (10 min)

Run `delivery-planner` to evaluate the project and set activation flags:

```
You: Run delivery-planner on this project. The project is [describe it in
1-2 sentences]. Decide: mode (G/B), has_data_plane, has_ml, has_agentic_ai,
compliance_regimes, scale_target_qps, availability_target, is_multi_tenant,
plus any flags I'm forgetting. Write the output to
.project/semantic/project-charter.md.
```

The planner's output is a small but consequential file — it's what every other agent reads to know which skills to activate.

### 4.3 Establish the architecture documentation skeleton (10 min)

Even if you have nothing yet:

```
You: Apply architecture-documentation to establish the doc skeleton:
.project/working/architecture/overview.md (with TODO placeholders for now)
and INDEX.md in .project/decision/. We'll fill these as decisions are made.
```

### 4.4 Confirm governance routing (5 min)

```
You: Read governance/governance.yaml and tell me which gates apply to this
project based on the project-charter flags. List which gates are always-on
and which are conditional.
```

You now have an active project setup. Real work starts.

---

## 5. Greenfield playbook

A new project from scratch. The library's primary use case.

### 5.1 The flow at a glance

```
Workflow: greenfield-api-service.yaml (or greenfield-saas.yaml)

Phase A: Discovery & Requirements
  └─ product-manager + skills:
     product-discovery → requirements-elicitation →
     requirements-interrogation → nfr-definition
     [Gate: requirements_freeze]

Phase B: Architecture & Design
  └─ solution-architect + skills:
     domain-discovery → architecture-pattern-selection →
     api-design → data-modeling → resilience-patterns →
     threat-modeling → project-phasing
  └─ architecture-challenger reviews (5 sub-personas)
     [Gate: architecture_sign_off, including challenger report]

Phase B+: UX & Design (if has_frontend)
  └─ ux-designer + skills:
     ux-journey-mapping → wireframing-prototyping → design-system

Phase C/D: Implementation slices
  └─ lead-developer decomposes; per-slice workflow:
     implementation-slice.yaml
     └─ backend-developer, frontend-developer, data-engineer, ml-ai-engineer
        (whichever applies per slice)
        + skills: stack-X → secure-coding → testing-strategy →
          observability → ... → code-review → security-review → QA
     [Gates per slice: review approvals + QA acceptance]

Phase E: Release
  └─ workflow: production-release.yaml
     [Gate: production_go_live with 10-item evidence pack]
```

### 5.2 Concrete walkthrough — building a new API service

Project: a customer-facing order API for a mid-sized retailer. No ML, no LLM, multi-tenant SaaS.

**Step 1 — Kick off.**

```
You: Start a greenfield API service. Use workflow greenfield-api-service.yaml.

Project: order API for a mid-sized retailer SaaS. Multi-tenant. Compliance:
SOC 2 + PCI-DSS (handles payment metadata, not card data). Stack preference:
Node/TS. Cloud: AWS-first but cloud-agnostic on Kubernetes. Scale target:
2000 QPS sustained, 8000 peak. Availability target: 99.95%.

Activate: PM + SA. Begin Phase A with product-discovery + requirements-
elicitation. Output the discovery artifacts to .project/semantic/.
```

What happens: Delivery Lead loads greenfield-api-service.yaml, invokes Product Manager. PM runs through product-discovery, then requirements-elicitation, building the user-story set + scope boundary. Then `requirements-interrogation` is applied — the KUACQ block surfaces unknowns. The PM may turn back to you with questions.

**Step 2 — Interrogation.** PM hits you with the KUACQ block — typically 5-15 questions you must answer before requirements_freeze. Answer them. The PM updates the artifacts.

**Step 3 — NFR-definition + requirements_freeze.**

```
You: Tell PM to finalize the NFR register and prep the requirements_freeze
gate. Include scope_boundary and assumptions_register. Show me the evidence
pack before I approve.
```

The gate fires. You see a structured approval request: brief + stories + scope + NFRs + assumptions + open-questions. Approve, reject (with reason), or send back for revision.

**Step 4 — Architecture phase.**

```
You: Phase A approved. Move to Phase B. Spawn Solution Architect; have them
produce the candidate architecture using architecture-pattern-selection,
api-design, data-modeling, resilience-patterns, distributed-systems-patterns,
multi-tenancy, threat-modeling, and project-phasing. NFR-driven decisions
explicit in ADRs.
```

SA produces:
- C4 Level 1 + 2 diagrams (`architecture-documentation` skill).
- ADRs for the major decisions (`adr-decision-records`).
- API design (OpenAPI spec scaffolded).
- Data model with multi-tenant scoping.
- Threat model with STRIDE walk.
- Phased roadmap.

**Step 5 — Architecture Challenger.**

```
You: Spawn Architecture Challenger. Run all 5 sub-personas (scale / security
/ cost / operations / reliability). Produce the challenge report.
```

The Challenger pushes back on the SA's choices. Findings are categorized: accepted (SA updates), overridden (SA writes ADR with rationale → `challenger_objection_override` gate), needs more info.

**Step 6 — architecture_sign_off gate.**

```
You: Show me the architecture_sign_off evidence pack: architecture decision,
ADR, C4 diagrams, challenge report (mandatory), phased roadmap. I'll approve
or send back.
```

You see it; approve.

**Step 7 — Implementation slices.**

```
You: Phase B approved. Lead Developer takes over. Decompose Phase 1 of the
roadmap into slices (each slice is 2-5 days; vertical; has clear
acceptance). Show me the slice list before starting.
```

Lead Dev decomposes. You scan: 6-12 slices for Phase 1. Approve.

```
You: Start slice 1. Use implementation-slice.yaml workflow.
```

Per slice: BE Dev (or FE / Data / ML) implements; consumes stack pack +
testing-strategy + secure-coding + observability + per-domain skills. Code Reviewer + Security Reviewer + QA Engineer each run; gates per slice.

**Step 8 — Release.**

Once N slices accumulate into a milestone:

```
You: Run production-release.yaml on commit SHA <commit>. Assemble the
production_go_live evidence pack (all 10 items where applicable; conditional
items per the delivery-planner flags).
```

Evidence assembled; gate fires; you review the pack; approve; deploy executes; release record archived.

### 5.3 Greenfield gotchas

- **Don't skip product-discovery.** PM agents are good at it; the temptation is to skip to architecture. Resist. The discovery artifacts are what every other phase reads.
- **Architecture Challenger is non-negotiable.** Architecture without challenge is architecture without review. The gate doesn't clear without it.
- **Slice size discipline.** If a slice grows past 5 days, decompose. Lead Dev should refuse oversized slices.
- **Memory hygiene from day one.** Every artifact carries the seven-field memory frontmatter; otherwise `memory-management` can't index them.

---

## 6. Brownfield playbook

You're picking up an existing codebase. Different starting point; different first moves.

### 6.1 The flow at a glance

```
Workflow: brownfield-enhancement.yaml

Phase H (pre-phase): Comprehension
  └─ tech-writer + lead-developer + skills:
     codebase-comprehension → architecture-documentation
     (reconcile) → impact-analysis (for first proposed change)
     → tech-debt-management (initial audit; build register)

Phase A: Discovery & Requirements (for the enhancement)
  └─ product-manager + skills:
     product-discovery (light; what's the change?) →
     requirements-elicitation → requirements-interrogation →
     nfr-definition (delta vs current)
     [Gate: requirements_freeze]

Phase B: Architecture & Design (delta)
  └─ solution-architect + skills:
     architecture-pattern-selection (does the change fit?) →
     impact-analysis (four lenses; mandatory) →
     api-design / data-modeling (delta) →
     resilience-patterns / threat-modeling (delta)
  └─ architecture-challenger reviews
     [Gate: architecture_sign_off]

Phase C/D: Implementation slices (same as greenfield)
  └─ Plus: tech-debt-management each cycle
  └─ Plus: legacy-modernization if the enhancement IS replacing
     a legacy subsystem

Phase E: Release (same as greenfield)
```

### 6.2 First-week activities (brownfield)

This is where brownfield diverges most.

**Day 1: Comprehension.**

```
You: Brownfield engagement. Run codebase-comprehension on this repo.
Produce .repo-intel/ outputs: the system map, the data flows, the build
+ deploy story, the runtime model, the hot paths. Use Tech Writer to
narrate; Lead Dev to structure.

Output: .project/semantic/codebase-overview.md plus per-service notes.
```

Comprehension is the prerequisite. Skipping it = changes blind.

**Day 2: Architecture documentation reconciliation.**

```
You: Apply architecture-documentation. Compare what's actually deployed
against any existing C4 diagrams + ADRs. Surface discrepancies. Decide
per item: fix the docs (default), or open a tech-debt-management entry if
the docs reflect the intended target. Update overview.md.
```

Common finding: docs are 6-24 months stale. The reconciliation IS the work.

**Day 3: Initial debt audit.**

```
You: Apply tech-debt-management's brownfield audit procedure. Interview
me about what feels hard in this codebase; run static analysis (complexity,
duplication, coverage); produce a triaged register at
.project/operational/debt-register.md. Limit to 20-50 items; classify each
per Fowler's quadrants; prioritize by payoff × risk × cost.
```

The first register is the most informative artifact of the brownfield engagement.

**Day 4: Impact analysis for the enhancement.**

```
You: The enhancement we're about to make is [describe]. Run impact-analysis
with all four lenses (static / runtime / contract / historical). Surface the
blast radius. Recommend proceed / proceed-with-conditions / scope-blocker.
```

This output drives sizing the actual enhancement work.

**Day 5: Then start Phase A** (per the greenfield flow but lighter, since the system already exists).

### 6.3 Brownfield concrete walkthrough — adding a feature to an existing system

Project: existing customer support chatbot (Node/TS + Postgres). Need to add a new "escalation to human agent" feature.

```
You: Start brownfield-enhancement workflow. Project context: existing
customer support chatbot (Node/TS + Postgres). Enhancement: add escalation-
to-human-agent flow. No new infra; no new compliance regime; existing data
model extended.

First: codebase-comprehension (we haven't done it yet). Then architecture-
documentation reconciliation. Then tech-debt-management audit. Then
impact-analysis for the proposed change. Then Phase A.
```

Day 1-4 happen per §6.2. Day 5+:

```
You: Phase A. PM runs product-discovery (light) + requirements-elicitation
+ requirements-interrogation. NFRs: define them as DELTAS from current
system. What changes? What stays?
```

PM produces a small, focused requirements brief (escalation flow + integration with existing routing + agent dashboard contribution).

```
You: requirements_freeze gate evidence please.
```

You approve. Continue to Phase B:

```
You: Phase B. SA does architecture-pattern-selection (is this an event-driven
add? a sync handoff?) and impact-analysis (mandatory; brownfield). Then api-
design (delta) + data-modeling (delta) + threat-modeling (delta — new trust
boundary?).
```

```
You: Architecture Challenger review. Then architecture_sign_off.
```

Approve. Implementation slices:

```
You: Lead Dev decomposes into slices. Each slice consumes
tech-debt-management — boy-scout fixes IN the slice; bigger items added
to register without bundling.
```

Standard implementation-slice workflow per slice. Release per production-release workflow when the milestone is ready.

### 6.4 Brownfield-only skills (B-mode triggers)

These don't activate in greenfield:

- **codebase-comprehension** (Wave 1) — required first move.
- **tech-debt-management** (Wave 7) — mandatory for B; optional for G after 6 months.
- **legacy-modernization** (Wave 7) — only fires if the enhancement IS a replacement.

These activate in both, but B-mode increases their priority:

- **impact-analysis** (Wave 7) — mandatory for any B change; lighter for G changes.
- **architecture-documentation** (Wave 7) — reconciliation is the B-mode first move.

### 6.5 Brownfield gotchas

- **Don't skip comprehension.** Single biggest brownfield failure mode.
- **Initial debt audit must triage.** A 200-item register that nobody touches is worse than no register. 20-50 items, prioritized.
- **Impact analysis 4 lenses — all of them.** Pattern: team uses static lens only; misses the partner integration in the contract lens; ships an incident.
- **Architecture docs vs reality — fix one or the other.** Document both options for each discrepancy.
- **Don't propose modernization too early.** Most brownfield work is `tech-debt-management`, not `legacy-modernization`. Modernization is rare and expensive; reach for it only when the business case is unambiguous.

---

## 7. Operating cadences

The library has rhythms beyond per-slice work. Knowing them prevents drift.

### 7.0 Session discipline: one slice, one session

Clear the session (or start a new one) after each slice closes — AFTER the
slice-close checkpoint is written, never before. The memory layer makes
sessions disposable by design: state lives in `.project/`, and re-opening
costs only the context floor (cache-priced). What a long-lived session costs
you instead: repeated history re-reads every turn, an eventual
auto-compaction at an uncontrolled moment (possibly mid-review, lossy), and
measurable quality dilution from stale context. Never clear mid-slice —
in-flight reasoning is the one thing not on disk; if a long slice bloats
context, `/compact` at a task boundary instead. Bonus: with one session per
slice, `telemetry/tokens.jsonl` records read directly as cost-per-slice.
(Drive mode already enforces the stronger form — fresh context per task.)

### 7.1 Per slice (every 2-5 days)

- `implementation-slice.yaml` runs end to end.
- Code Review + Security Review + QA gates fire.
- Slice DoD checked.
- Boy-scout fixes go in the slice; bigger items go in `debt-register.md`.
- Memory artifacts updated per `memory-management`.

The steps above describe the manual, one-slice-at-a-time cadence (`/slice`,
watched by hand). It isn't the only mode: once a slice has run cleanly this
way at least once, `/drive` (or `scripts/praxis-drive.sh` headless) automates
the loop between human touchpoints — it still stops at every governance gate,
decision point, and budget/stall condition, just without you re-prompting
each task in between. See [`docs/autonomous-drive.md`](docs/autonomous-drive.md)
for the autonomy dial and run budgets, and [`docs/scenarios.md`](docs/scenarios.md)
scenarios 6-7 for the overnight-run and resume-after-stop walkthroughs.

### 7.2 Per cycle (every 2-4 weeks)

- Cycle planning: feature slices + debt-payoff allocation (15-25% default).
- `tech-debt-management` register reviewed; items selected for the cycle.
- Cycle retro reviewed against AOP.

### 7.3 Per release (when milestone ready)

- `production-release.yaml` runs.
- Evidence pack assembled; gate fires; principal approves.
- Release notes (per `technical-documentation`) generated + curated.
- Post-release: SLO observation window; release record archived.

### 7.4 Monthly

- Architecture documentation reconciliation (per `architecture-documentation`).
- Runbook freshness check.
- ADR archive walk.

### 7.5 Per session — model routing

Every session now interacts with the model-routing layer at least twice: on entry (pick session tier) and on each sub-agent spawn (pick specialist tier).

Agents carry an abstract `capability_tier` (`deep | standard | light`) in
frontmatter, not a hardcoded model name. `governance/model-routing.yaml` is
the one file that resolves a tier to a concrete model per harness — `opus /
sonnet / haiku` on Claude Code, `model_reasoning_effort: high / medium / low`
on Codex, `gemini-2.5-pro / -flash / -flash-lite` on Gemini CLI —
and `scripts/apply-model-routing.py` applies that mapping into agent
frontmatter / Codex TOML. Nothing below should be read as Claude-specific;
substitute your harness's tier mapping.

- **Session start:** Read the session's title / first task. If it fires an "always-`deep`" trigger (architecture, threat model, cross-cutting ADR, P0 post-mortem), open at the `deep` tier. Otherwise, open at `standard`. `adaptive-model-routing`'s "Session-level model selection" section gives the shortlist.
- **Each `Task` sub-agent spawn:** The Delivery Lead consults `adaptive-model-routing` before spawning. The routing SKILL scores 5 signals, honors fast-path rules, and shifts the agent's default tier by at most ±1 step. The Delivery Lead resolves the chosen tier to the harness's concrete model/effort setting via `governance/model-routing.yaml` and passes that as the `model:` argument to the Agent tool call.
- **Escalation:** If a `standard`-tier attempt fails a quality check, the Delivery Lead does NOT retry at the same tier. It re-scores with `prior_failure = 2`, promotes one tier (typically to `deep`) with the failure context, and logs the escalation at `.project/episodic/model-escalations.md`.
- **Logging:** Every routing decision writes one entry to `.project/telemetry/model-routing.jsonl` (agent, default tier, chosen tier, rubric score, reason). That log feeds the weekly review below.

If usage at the `deep` tier is running high, the Delivery Lead reads the routing log to identify `deep`-tier tasks that were probably `standard`-worthy in retrospect — those become future fast-path corrections.

### 7.6 Weekly — telemetry review (10 minutes)

Praxis captures usage primarily through checkpoint records
(`.project/episodic/checkpoint-*.md`) written by delivery-lead at every
gate/phase/slice/loop closure — a mandatory workflow deliverable, not a
hook riding on a tool event. A quick weekly pass catches drift before it
compounds.

```bash
# Per-skill / per-agent / per-workflow / per-command usage this week.
python3 scripts/factory-usage-report.py --project-dir . --format md

# Routing, cost-proxy, and drive-run aggregation.
python3 scripts/factory-routing-report.py --project-dir . --format md

# Any experimental SKILL missing telemetry? (legacy stub-layer aging check)
scripts/factory-aging.sh --strict-window 30
```

Read the output for three signals:
- Frequency imbalance — is one SKILL disproportionately over/under-used vs. expectation for this project's phase?
- Missing experimental telemetry — the aging gate flags them. If a SKILL has zero uses in 30 days but is still marked `experimental`, ask whether the project actually needs it, or whether the SKILL's triggers are wrong.
- Model routing surprises — the routing report's tier & cost-proxy section, or `.project/telemetry/model-routing.jsonl` directly. Any `deep`-tier routes for tasks that scored low on the rubric? Any escalations that recurred on the same task type?

Any of these warrant a note in `.project/operational/library-evolution/YYYY-MM-DD-observations.md` for the next quarterly steward pass. Full detail on what feeds each report: [`docs/telemetry.md`](docs/telemetry.md).

### 7.7 Quarterly — the library's own rhythm

This is what makes the platform self-improving. Now that telemetry is captured automatically via checkpoint records, the Steward reads real data — no more "your observations."

- Run `python3 scripts/factory-usage-report.py --project-dir . --format md --out <file>` for the quarter's per-skill/agent/workflow/command usage picture.
- Run `python3 scripts/factory-routing-report.py --project-dir . --format md --out <file>` for tier, cost-proxy, and routing-discipline coverage.
- Run `scripts/factory-aging.sh` to identify experimental SKILLs stale enough to promote / demote / kill.
- `factory-evaluation` SKILL synthesizes all of the above into a factory report covering library health, skill efficacy, agent performance, workflow completion, gate-clearance times.
- `system-steward` reads the factory report + the accumulated `library-evolution/` observations; drafts the quarterly steward report.
- Steward proposals route through `steward_promotion` gate.
- Principal approves per-proposal.
- Documentation audit (per `technical-documentation`).
- Debt-rate-of-change report.

Run quarterly cadence as a single block of work — 1-2 days every 3 months. Don't run more often (over-tweaking); don't run less (drift). The captured telemetry means you have real data to ground decisions on — not gut feel from "which SKILLs felt useful."

---

## 8. Prompt library

Paste-ready prompts for common moments. Substitute `<...>` per project.

### 8.1 Kickoff prompts

**Project bootstrap:**

```
You: Bootstrap a new project at this repo. Run delivery-planner; capture the
project-charter at .project/semantic/project-charter.md. Then establish
architecture-documentation skeleton. Project context: <1-2 sentences>.
Compliance regimes: <list or "none">. Stack preference: <stack>. Cloud:
<aws|azure|gcp|k8s>. Scale target: <qps>. Availability: <pct>.
```

**Greenfield API service start:**

```
You: Start greenfield-api-service.yaml workflow. Project per charter.
Activate Product Manager for Phase A.
```

**Greenfield SaaS start:**

```
You: Start greenfield-saas.yaml workflow. Project per charter. Activate PM
+ UX Designer in parallel for Phase A + Phase B+.
```

**Brownfield kickoff:**

```
You: Brownfield engagement. First: codebase-comprehension on this repo
(write to .repo-intel/). Then architecture-documentation reconciliation
(write to .project/working/architecture/). Then tech-debt-management initial
audit (write to .project/operational/debt-register.md). Then summarize for
me before we start Phase A.
```

### 8.2 Phase prompts

**Phase A — requirements:**

```
You: Phase A. PM runs product-discovery + requirements-elicitation +
requirements-interrogation + nfr-definition. Output to .project/semantic/.
Stop at the KUACQ block; bring questions to me.
```

**Phase B — architecture:**

```
You: Phase B. SA runs architecture-pattern-selection + api-design +
data-modeling + resilience-patterns + threat-modeling + project-phasing.
Output ADRs to .project/decision/. C4 diagrams to .project/working/
architecture/. Then spawn architecture-challenger; run all 5 sub-personas;
produce challenge report. Prep architecture_sign_off evidence.
```

**Implementation slice:**

```
You: Run implementation-slice.yaml on slice <N>: <slice title>. Acceptance
criteria: <list>. Lead Dev decomposes; Backend Dev implements; Code Review +
Security Review + QA gates. Stop at each gate for my approval.
```

**Production release:**

```
You: Run production-release.yaml on commit <SHA>. Assemble the
production_go_live evidence pack. Show me the pack before the gate fires.
```

### 8.3 Specialist prompts

**Architecture Challenger spot-review:**

```
You: Architecture Challenger, run a scale sub-persona review on this design:
<paste design or @file>. What breaks at 10x current load? What breaks at
sustained 80% capacity? Are the bottlenecks identified?
```

**Security Reviewer ad-hoc:**

```
You: Security Reviewer, audit this PR per the standard 7-dimension review.
Threat model delta if architecture changed. Output findings; classify each
as block / accept-with-mitigation / risk-accept (with rationale).
```

**ML/AI Engineer kickoff:**

```
You: ML/AI Engineer activated (has_ml=true OR has_agentic_ai=true per
charter). Phase: <which one>. Run ml-problem-framing FIRST — including the
"is ML actually the right tool" honest check. Then proceed per AOP.
```

**System Steward quarterly:**

```
You: System Steward, run quarterly cadence. First run:
  python3 scripts/factory-usage-report.py --project-dir . --format md
  python3 scripts/factory-routing-report.py --project-dir . --format md
  scripts/factory-aging.sh --strict-window 30
Read the aggregates + the accumulated `.project/operational/library-evolution/`
observations. Draft the quarterly steward report. Identify lifecycle
changes, trigger tunings, reference / pattern additions, consolidations,
promotions of experimental SKILLs. Route through steward_promotion gate
evidence pack.
```

**Model routing decision (before a sub-agent spawn):**

```
You: Delivery Lead, apply adaptive-model-routing before spawning the
next specialist. Task: <what you're about to delegate>. Score all 5
signals (novelty / interdependency / stakes / ambiguity / prior_failure),
check fast-path rules, decide the ±1 tier shift from the agent's default
capability_tier. Resolve the chosen tier to a concrete model via
governance/model-routing.yaml. Log the decision to
.project/telemetry/model-routing.jsonl. Then spawn with the resolved
model: string.
```

**Model routing for a whole session:**

```
You: About to open a new session on <task>. Before I choose the session
tier, apply adaptive-model-routing's session-level rules. Which triggers
fire? Which capability_tier (deep / standard / light) should I open on?
Resolve it to this harness's concrete model via governance/model-routing.yaml
and give me the specific command to open with it.
```

**Escalation after a standard-tier failure:**

```
You: A standard-tier attempt on <task> just failed with <failure reason>.
Apply adaptive-model-routing's escalation protocol: score prior_failure = 2,
re-score, log the escalation to .project/episodic/model-escalations.md.
Then open the next tier up (typically deep) with the failure context
prepended so it doesn't start cold.
```

### 8.4 Telemetry review prompts

**Weekly frequency scan:**

```
You: Run python3 scripts/factory-usage-report.py --project-dir . --format md
and read the per-skill usage section. Identify: (a) unexpectedly
frequent SKILLs, (b) unexpectedly infrequent SKILLs given the current
phase, (c) any SKILL on the "never observed" list that should have fired.
If (c) appears, either the trigger phrases need refinement or my project
needed a SKILL I forgot to invoke. Write findings to .project/operational/
library-evolution/YYYY-MM-DD-weekly.md.
```

**Coverage gap check (experimental SKILLs):**

```
You: Run scripts/factory-aging.sh --strict-window 30. For each
experimental SKILL that failed the strict window, decide: promote,
demote, refactor triggers, or kill. Write a mini-proposal per SKILL for
the next quarterly steward review. Save to library-backlog/
proposed-skills/aging-review-YYYY-MM-DD.md.
```

**Rich telemetry observation (after an experimental SKILL fires):**

```
You: /praxis:factory-record — I just used <skill-name> to <what>. Capture
observation: what worked, friction, edge cases, suggested refinements.
Add slice + outcome + duration. Write to .project/operational/
factory-metrics/skills/<skill-name>/<date>-<rand>.md.
```

### 8.5 Skill-specific prompts

**Apply threat-modeling:**

```
You: Apply threat-modeling to this design: <design or @file>. Use STRIDE.
For each finding, suggest a mitigation. Output to .project/operational/
threat-model-<feature>.md.
```

**Apply impact-analysis (mandatory before brownfield changes):**

```
You: Apply impact-analysis to this proposed change: <change description>.
All four lenses (static + runtime + contract + historical). Recommend
proceed / proceed-with-conditions / scope-blocker. Output to .project/
operational/impact-analyses/<change>-<date>.md.
```

**Trigger memory reconciliation:**

```
You: Memory volume has grown N% this quarter (per factory-eval). Run
memory-management reconciliation. Identify episodic memory candidates for
consolidation or pruning; surface stale semantic entries; refresh
procedural memory against current toolchain.
```

### 8.5 Governance prompts

**Approval evidence inspection:**

```
You: A <gate-name> gate is pending. Show me the full evidence pack with
each item explicitly. Then your recommendation. I'll approve, reject, or
send back.
```

**Recording a rejection as an ADR:**

```
You: I'm rejecting <gate-name> for <reason>. Record this as an ADR under
.project/decision/ with the rationale. Schedule the rework path.
```

---

## 9. Codex addendum

The library is portable; addressing differs.

### 9.1 Installation

Codex reads from the repo root + a routing file. Layout:

```bash
cd /path/to/your-project-repo
mkdir -p .team
cp -R /path/to/praxis/{agents,skills,workflows,governance,patterns,references} .team/
```

Then create the routing file at the repo root:

```bash
# AGENTS.md at repo root
```

Sample `AGENTS.md`:

```markdown
# Agents and Skills Index

This repo ships with the Praxis at `.team/`. Codex agents
should consult the files below per task type.

## Where things live
- Role agents:    .team/agents/
- Skills:         .team/skills/<skill-name>/SKILL.md
- Workflows:      .team/workflows/
- Governance:     .team/governance/governance.yaml
- Patterns:       .team/patterns/
- References:     .team/references/

## Routing by task type

| Task type | Start here |
|---|---|
| New API service from scratch | .team/workflows/greenfield-api-service.yaml |
| New SaaS product | .team/workflows/greenfield-saas.yaml |
| Enhancement to existing system | .team/workflows/brownfield-enhancement.yaml |
| Per-slice implementation | .team/workflows/implementation-slice.yaml |
| Release to production | .team/workflows/production-release.yaml |
| Quarterly library review | .team/agents/system-steward.md |

## Project memory
- All artifacts under .project/.
- Memory taxonomy: semantic, episodic, procedural, decision, operational,
  working. Per memory-management skill.

## Activation flags
- See .project/semantic/project-charter.md for the planner's flags.

## Governance
- All gates per .team/governance/governance.yaml.
- Solo mode (mode: solo): every gate routes to the principal.
```

### 9.2 Codex-specific operating differences

- Codex doesn't auto-discover; the `AGENTS.md` is what gives it the map.
- Prompts substitute `.team/` for `.claude/` (or `~/.claude/`).
- The mental model + the playbook flow are identical otherwise.

### 9.3 First sanity check on Codex

```
You: Read AGENTS.md and confirm you can navigate to .team/agents/ and
.team/skills/. Then list the 17 agents and the 91 skills you can see.
Read governance.yaml and summarize active gates.
```

If it works, you're set.

---

## 10. Troubleshooting

### "Claude Code isn't invoking the right skill"

**Diagnosis order:**

1. Is the project-charter set? `cat .project/semantic/project-charter.md`. Without it, agents don't know which skills are activated.
2. Does the skill's frontmatter include a trigger phrase matching what you said? Read `<skill>/SKILL.md` frontmatter `triggers:` block.
3. Is the skill in the `.claude/` (or `~/.claude/`) install scope you're using?
4. Did you invoke at the workflow level, or jump straight to a specialist? Sometimes the workflow's Decision Node hasn't routed yet.

Fix paths:

- Add a trigger phrase to the skill (run through `steward_promotion` if it's a permanent fix; ad-hoc edit for a one-off test).
- Use the skill-name explicit invocation: "Apply `<skill-name>` to this."

### "Two skills are giving conflicting guidance"

Read both SKILLs end-to-end. Often one is the right primary, the other is the consumer. The skill metadata's `consumers` field clarifies.

If genuinely conflicting (rare): both should be reconciled. Open a System Steward proposal for the next quarterly cycle. Meanwhile, pick one explicitly; document the choice as an ADR.

### "Architecture Challenger is over-blocking"

Per blueprint R3: the Challenger has 5 sub-personas (scale / security / cost / operations / reliability). If one sub-persona keeps blocking, it might be calibrated wrong for the project's actual NFRs.

Fix: re-check the NFR register. If the NFRs are realistic, the Challenger is doing its job — accept the finding or override via ADR. If the NFRs are aspirational, that's the root cause; address the NFRs.

### "Tech debt register is becoming a graveyard"

Symptom of skipping the quarterly walk. Triage:

- Close any items resolved.
- Reclassify wont-fix items past their re-review date.
- For genuinely-paid debt, mark paid + dated.
- For never-going-to-be-paid items, decide wont-fix (with rationale).

### "Production_go_live gate keeps failing first-submission"

Per factory-eval, this is a signal. Diagnose: which evidence item is missing each time? If consistent, the upstream skill or agent has a gap. System Steward proposal next quarter.

### "Slices are growing past 5 days"

Lead Dev should refuse oversized slices. If they're growing anyway:

- Acceptance criteria too broad? Re-decompose.
- Hidden complexity discovered mid-slice? Pause; impact-analysis; re-scope.
- Unclear dependencies? Surface in KUACQ at slice start.

### "I want to skip a gate this once"

You can, but record it. Every skip becomes an ADR. The library catches up later — the gate's evidence-required becomes a debt entry.

### "The library is starting to feel bloated"

Skill count > 90 = review zone; > 101 = mandatory consolidation. System Steward owns this in steady state. Manually: run a capability balance check; identify the largest area; look for consolidation candidates.

### "`deep`-tier usage exhausted mid-week"

Diagnose which tasks burned it. Read `.project/telemetry/model-routing.jsonl` and filter for `chosen_tier: deep` entries (or the harness's resolved model, e.g. `opus` / `high` reasoning effort, per `governance/model-routing.yaml`). For each, look at the 5-signal score — anything low that was still routed to `deep` is a habit-forming waste. The routing rubric would have selected `standard`.

Fix paths:
- **Short-term:** open new sessions at the `standard` tier only for the rest of the week; escalate individual tasks per `adaptive-model-routing`'s escalation protocol if you hit a genuinely hard problem.
- **Structural:** if the same task type keeps scoring low but you kept routing it to `deep`, add a fast-path `standard`-tier override for that task type in `.project/procedural/model-routing-overrides.md`.
- **Never:** downgrade threat-modeling, architecture sign-off, or P0 post-mortems to save quota. The routing rubric flags these as fast-path `deep` for a reason.

### "`standard` tier keeps failing a specific task class"

Escalation-worthy. Read `.project/episodic/model-escalations.md` — if the same class appears 3+ times, that class should be a project-local fast-path override to `deep`. Add it to `.project/procedural/model-routing-overrides.md` and stop wasting `standard`-tier cycles on the first attempt.

### "adaptive-model-routing suggestions look wrong"

The routing rubric is trained on general engineering patterns. Every project has quirks. If the SKILL keeps suggesting `standard` for a task that in your project always needs `deep` (or vice versa), the fix is a per-project override, not a SKILL edit. Add a project-local fast-path in `.project/procedural/model-routing-overrides.md`. The routing SKILL honors overrides before applying the rubric.

If the same override recurs across 3+ projects, propose a SKILL update via System Steward at quarterly review.

### "factory-usage-report.py shows no checkpoint records"

Two common causes:
1. **No closure boundary reached yet:** checkpoint records are written at gate/phase/slice/loop closures (`.project/episodic/checkpoint-*.md`), not on every tool use. If you haven't closed a slice, hit a gate, or finished a phase yet, there's nothing to write. This is expected early in a session.
2. **delivery-lead short-circuited the AOP:** the checkpoint write is a mandatory Document step, but a delivery-lead that skips the AOP can skip it. Check whether the closure actually happened per the workflow, and prompt: "Write the checkpoint record for that closure now."

`.project/telemetry/sessions.jsonl`, `agent-spawns.jsonl`, and `drive.jsonl` empty is a different problem — those are hook/runner-written and deterministic. If they're missing:
1. **Hooks not loaded:** run `/reload-plugins` in Claude Code (or restart the session).
2. **The tap.sh hook is failing silently:** run `bash hooks/tap.sh SessionStart < /dev/null` manually to check for syntax errors. Hook failures are swallowed by design (telemetry never blocks work), so silent errors are possible.

Fallback for either: use the `/praxis:factory-record` slash command to write observations manually. That path doesn't rely on the tap or the checkpoint discipline. `.project/operational/factory-metrics/` is now a legacy/supplementary layer (command stubs + `/factory-record` observations only) — an empty `skills/`/`agents/` subtree there is expected and not a bug; it stopped being the primary usage source.

### "Experimental SKILL flagged stale by factory-aging"

`scripts/factory-aging.sh` flags experimental SKILLs with zero telemetry in the last 30 days. Three responses:
1. **Promote:** if the SKILL earned its keep on the projects that DID use it, promote to `state: active` via `steward_promotion` gate.
2. **Refactor triggers:** if the SKILL should have fired but didn't, its trigger phrases are wrong. Tune them; re-run for another cycle.
3. **Kill:** if no project genuinely needed it, tombstone via `state: removed` and move the directory to `archive/skills/`.

Do not ignore the flag — that defeats the visibility the aging gate is designed to provide.

### "Usage report shows a SKILL named in far more checkpoints than expected"

Investigate. Two possibilities:
1. Genuine heavy use — the SKILL is in the load-bearing set for this project's phase. Fine.
2. Trigger phrase too broad — the SKILL is firing when it shouldn't. Read a few of the recent `.project/episodic/checkpoint-*.md` entries that name it (or, if the SKILL predates the checkpoint-record slimdown, any legacy entries under `.project/operational/factory-metrics/skills/<name>/`); if most of them are false-positive uses, tune the trigger phrases.

Note it in `.project/operational/library-evolution/` for the next quarterly review.

---

## 11. Appendix — what each Wave gives you

Quick reference if you're choosing how much to install.

| Wave | Gives you | Activates when |
|---|---|---|
| 1 | Planning capability (PM, SA, Lead Dev, Platform/SRE basic, BE Dev) | Always |
| 2 | Build + ship quality gates (UX, FE Dev, Code Review, Security Review, QA, Tech Writer) | Always |
| 3 | Deployment plane (CI/CD, containers, IaC, environments, K8s) | Always |
| 4 | Operational hardening (reliability, chaos, multi-tenancy, threat modeling, compliance, cost, perf, cloud packs) | Always (some skills conditional) |
| 5 | Data plane (pipelines, warehouse, quality, governance) + Data Engineer | `has_data_plane == true` |
| 6 | ML + agentic-AI plane (problem framing → drift; agentic architecture → cost) + ML/AI Engineer | `has_ml == true` OR `has_agentic_ai == true` |
| 7 | Maintenance + self-improvement (factory eval, tech debt, impact analysis, arch + tech docs, legacy modernization) + System Steward | Always (steward operates cross-project on quarterly cadence) |

**MVP for first test:** install all of praxis/ (everything ships together). Use only what each project triggers. The unused skills don't activate; they don't cost anything until they fire.

---

## 12. Living playbook

This playbook itself improves. When you hit a moment that wasn't covered, extend it. The playbook lives at `praxis/PLAYBOOK.md` and travels with the library install.

Quarterly cadence: System Steward reviews the playbook for stale guidance (alongside the library proposals). Updates flow through `steward_promotion`.

The platform doesn't help if the operating guide goes stale. Treat this playbook the same way the library treats its own artifacts: living, owned, reconciled.
