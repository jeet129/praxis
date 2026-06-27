# Praxis — Operating Playbook

How to actually use this library in real projects. Greenfield and brownfield, on Claude Code first, with a Codex addendum at the end. Practical: real prompts, real directory layout, real cadences.

This playbook assumes you've read the `README.md` at least once.

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
| `--both` | Install both Claude Code and Codex layouts side by side. |
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

### 2.3 The polished path — Claude Code plugin (future)

Once you've tested the library and it's stable, the cleanest distribution is a **Claude Code plugin**. The library is well-structured for it — skills + agents + workflows in the standard layout, governance under its own directory. Packaging it as a `.plugin` file means:

- One-click install in Claude Code.
- Versioned releases (v1.0, v1.1, etc.).
- Shareable across teams without copying directories.
- Marketplace-ready if you ever want to distribute beyond your own use.

The `create-cowork-plugin` skill (bundled with Cowork mode) walks through plugin authoring. After your first round of real-project testing, ask for the plugin packaging. The install script will still work for development iteration; the plugin is the production distribution.

### 2.4 Sanity check

After install, open the project in your tool and paste:

```
You: I just installed the Praxis. Confirm you can see the agents
and skills, and tell me which roles and which skills are available. Then read
the governance.yaml and summarize the active gates.
```

You should see Claude Code list **16 agents**, **77 skills**, and the **7 active governance gates** (plus 4 conditional project-specific gates). If it can't see them, the install scope is wrong — re-run `install.sh --dry-run` to confirm the destination.

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
│ SKILLS — the 77 SKILL.md bundles                        │
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

### When to invoke which layer

- **Workflow** when starting a new project, new slice, or release.
- **Agent (by name)** when you want a specific role's perspective: "Architecture Challenger, review this." "Security Reviewer, audit this PR." For most work, the Delivery Lead picks the agent.
- **Skill (by name)** when you want a specific discipline applied: "Apply `threat-modeling` to this design." For most work, the agent picks the skill.
- **Governance gate** never invoked directly — gates fire from workflow steps; you approve when they reach you.

Default: invoke the workflow. Let it orchestrate. Specialize only when needed.

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

### 7.1 Per slice (every 2-5 days)

- `implementation-slice.yaml` runs end to end.
- Code Review + Security Review + QA gates fire.
- Slice DoD checked.
- Boy-scout fixes go in the slice; bigger items go in `debt-register.md`.
- Memory artifacts updated per `memory-management`.

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

### 7.5 Quarterly — the library's own rhythm

This is what makes the platform self-improving.

- `factory-evaluation` runs against the telemetry from the past quarter.
- Output: factory report covering library health, skill efficacy, agent performance, workflow completion.
- `system-steward` reads the factory report; drafts the quarterly steward report.
- Proposals route through `steward_promotion` gate.
- Principal approves per-proposal.
- Documentation audit (per `technical-documentation`).
- Debt-rate-of-change report.

Run quarterly cadence as a single block of work — 1-2 days every 3 months. Don't run more often (over-tweaking); don't run less (drift).

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
You: System Steward, run quarterly cadence. Read the latest
factory-evaluation report at .project/operational/factory-metrics/<quarter>.md.
Draft the quarterly steward report. Identify lifecycle changes, trigger
tunings, reference / pattern additions, consolidations. Route through
steward_promotion gate evidence pack.
```

### 8.4 Skill-specific prompts

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
.team/skills/. Then list the 16 agents and the 77 skills you can see.
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
