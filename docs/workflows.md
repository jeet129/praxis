# Using the workflows

Praxis ships **9 workflows**. A workflow is a gated, multi-step orchestration — a rhythm of agent work punctuated by human approval gates. You don't run the YAML directly; you invoke a workflow by intent, and the Delivery Lead (the `using-praxis` front-door skill) routes to the right one, sequences its steps, evaluates decision nodes, and stops at gates.

There are three ways to invoke a workflow:

1. **Slash command** (Claude Code) / **`$praxis-*` command** (Codex) — the deterministic entry points for the common lifecycle steps.
2. **Plain intent** — describe what you want ("prove this is feasible", "production is down, patch it now") and the front door routes you. Used for the workflows without a dedicated command (spike, expedited-change, modernization).
3. **Autonomous drive** — `/drive` runs the loop between human touchpoints instead of you advancing each step. See "Running a workflow autonomously" at the end.

Every workflow bottoms out at **governance gates** that always stop for a human, regardless of autonomy. Gates are defined in `governance/governance.yaml`.

> **Always start with `/start`.** It runs `delivery-planner`, which interviews you and writes `.project/semantic/project-charter.md`. The charter's flags (greenfield/brownfield, data plane, ML, agentic AI, compliance, scale) are what let the front door pick and parameterize the right workflow. Without a charter, nothing routes.

## Command ↔ workflow map

| Command (Claude / Codex) | Workflow | Gate(s) |
|---|---|---|
| `/start` · `$praxis-start` | bootstrap (charter) | — |
| `/discover` · `$praxis-discover` | greenfield-* / brownfield Phase A | `requirements_freeze` |
| `/architect` · `$praxis-architect` | Phase B | `architecture_sign_off` |
| `/audit` · `$praxis-audit` | brownfield first-week kickoff | — (feeds brownfield-enhancement) |
| `/slice` · `$praxis-slice` | implementation-slice | `code_review`, `security_review`, `qa` (per slice) |
| `/release` · `$praxis-release` | production-release | `production_go_live` |
| `/refine-idea` · `$praxis-refine-idea` | ideation-refinement-loop | `ideation_refinement_approval` |
| `/review` · `$praxis-review` | on-demand review (not a full workflow) | — |
| `/drive` · `$praxis-drive` | autonomous iteration of any active workflow/slice | (all gates still stop) |
| *(describe intent)* | spike | `spike_disposition` |
| *(describe intent)* | expedited-change | `expedited_change_approval`, `expedited_change_retro` |
| *(describe intent)* | modernization | `modernization_strategy_sign_off`, `parallel_run_verification`, `legacy_decommission_approval` |

---

## The lifecycle workflows

These carry a project from idea to production. You normally walk them in order via the phase commands.

### greenfield-saas — build a new SaaS product

A new web product from scratch: discovery → requirements (incl. UX journey mapping) → **parallel** architecture + UX design (with adversarial Challenger review) → slice-by-slice implementation with Backend + Frontend in parallel → code/security/QA review → CI/CD → deploy. Activates the UX Designer and Frontend Developer agents.

**Use when:** the charter is greenfield and the product has a user-facing web surface.
**How:** `/start` → `/discover` → `/architect` → `/slice` (repeat per slice) → `/release`.

### greenfield-api-service — build a new backend API

Same greenfield spine, no UX phase: discovery → requirements → architecture (adversarial review) → slice-by-slice implementation → code review → (Wave 2+) CI/CD + deploy.

**Use when:** the charter is greenfield and the deliverable is a service/API with no first-party UI.
**How:** `/start` → `/discover` → `/architect` → `/slice` → `/release`.

### brownfield-enhancement — change an existing system

Add or change behavior in a system that already exists. **Comprehension runs first** (grounds the team in `.repo-intel/`), then **impact analysis before any modification** (names the blast radius), then implementation that matches existing conventions.

**Use when:** the charter is brownfield and you're modifying a real codebase.
**How:** `/start` (mode: brownfield) → `/audit` (comprehension → arch reconciliation → debt → impact) → `/slice` per change → `/release`.

---

## The unit-of-work workflows

Called repeatedly inside the lifecycle, or on their own.

### implementation-slice — build one slice

The per-slice loop: open the slice, build the implementation packet, decompose via Lead Developer, dispatch specialists (Backend / Frontend / Data / ML as the charter activates), run Code Review + Security Review + QA acceptance, validate integration, close. This is the workhorse and the home of the autonomous **slice-drive** loop.

**Use when:** you have a defined, bounded piece of work to implement.
**How:** `/slice`. Runs its own review gates before closing.

### production-release — ship to production

Assemble the `production_go_live` evidence pack, gate on approval, execute the deployment strategy with **rollback armed**, run post-deploy verification, record the release.

**Use when:** a slice (or set) is ready to go live.
**How:** `/release`. The go-live gate is a hard human stop.

---

## The situational workflows

Invoked by describing intent — they have distinct gate topologies, not just different content, which is why they're separate workflows.

### spike — time-boxed feasibility

A declared time box (default 3 days) to answer a question or test a bet. The build-to-learn loop produces **evidence, not production code** — spike code never merges. The spike report is the only artifact allowed to outlive the spike; whether to archive it or promote it into discovery is an explicit principal call at the `spike_disposition` gate.

**Use when:** "Can we even do X?" / "prove feasibility first."
**How:** say exactly that. Set the time box when asked.

### expedited-change — P0/P1 fast path

Fast path for a P0/P1 incident fix or critical security patch. Gates are compressed to what a 2 a.m. responder can clear — blocker-only review, single-approver gate, rollback armed before deploy — but the compression is **repaid within a declared retroactive window**: a normal-bar review pass, a postmortem, and a tech-debt entry for every shortcut. The retro half (`expedited_change_retro`) is mandatory, not optional.

**Use when:** "Production is broken and needs a fix NOW" — and severity is genuinely P0/P1 (the front door checks `incident-runbook` severity first; anything less reroutes to brownfield-enhancement).
**How:** describe the incident and its severity.

### modernization — replace a legacy system incrementally

Strangler-fig, not big-bang. Deep comprehension and seam identification first; the target architecture and migration strategy are sign-off gated *before any seam is touched*; each increment carves one seam, builds its replacement as an `implementation-slice` sub-workflow, runs old and new in parallel with comparison telemetry, then shifts traffic. Legacy decommission is its own gated phase after cutover is clean.

**Use when:** "Replace / modernize this legacy system."
**How:** describe the system and the goal. Expect three gate families: strategy sign-off, per-increment parallel-run verification, and decommission approval.

### ideation-refinement-loop — sharpen an idea

A bounded creator/reviewer/enhancer loop over an ideation artifact, with an arbiter scoring convergence. Harnesses are runtime bindings — Claude, Codex, etc. can each be bound to the creator/reviewer/enhancer/arbiter roles. Convergence is machine-checked (the arbiter writes a verdict; no findings ≥ major and next-pass value cosmetic/low ⇒ converged), then a human signs off at `ideation_refinement_approval`.

**Use when:** you have a raw idea/brief to refine before it enters discovery.
**How:** `/refine-idea`.

---

## Running a workflow autonomously

Instead of advancing each step yourself, let the drive loop run between human touchpoints. Two altitudes:

- **`/drive` (slice-drive)** — iterates the active slice's task ledger: takes the next ready task, runs it on the task tier's model + reasoning effort, verifies, updates status, and stops at any gate, decision point, or budget/stall limit.
- **workflow-drive** — `scripts/praxis-drive.sh --workflow` loops a workflow's *steps* (reading `.project/working/workflow-state.yaml`), each step on its phase-tier model. Its autonomous span is implementation → release (phases C→D); discovery and architecture (A/B) stay human-gated by design.

Both honor the autonomy dial in `governance/autonomy.yaml` (`stop_after: task | slice | phase | gate`) and three non-negotiable stops: governance gates, decision points, and budget/stall/exhaustion. Governance gates are never machine-cleared. See `docs/autonomous-drive.md` for the full protocol and `references/phase-gates.md` for the step/predicate schema.

## When to add a new workflow (vs. reuse one)

A scenario earns a **new** workflow file only when its **gate topology** differs — a different rhythm of human approvals — not merely because its content differs. Otherwise it's `delivery-planner` parameterizing an existing template via charter flags. This is the anti-sprawl rule; `factory-evaluation` treats workflow-count creep as a decay signal. The per-workflow gate-topology signatures live in `references/orchestration-runtime-detail.md`.
