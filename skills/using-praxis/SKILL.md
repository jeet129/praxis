---
name: using-praxis
description: "The front-door SKILL AND the workflow execution engine. Two layers in one SKILL because they're inseparable in practice. LAYER 1 (routing) — maps incoming user intent to the right workflow → agent → skill sequence; THE FIRST SKILL TO READ on a session start. LAYER 2 (orchestration runtime) — loads a workflow from `workflows/`, evaluates entry criteria, sequences steps, evaluates Decision Nodes, routes to agents, enforces gates per `governance.yaml`, applies failure paths. The Delivery Lead persona runs this SKILL — the persona is the WHO, this SKILL is the HOW. Use when starting any session, when uncertain which workflow / agent / skill to invoke, when advancing a workflow, when evaluating a Decision Node, when enforcing a gate, or when handling a step failure."
---

# Using the Praxis

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - delivery-planner
  - project-memory
  - memory-management
  - skill-registry
  - adr-decision-records
  - adaptive-model-routing
triggers:
  - "session just started; what should I do first?"
  - "user gave a vague request; which workflow does it map to?"
  - "uncertain which skill to invoke for the current task"
  - "starting a project (initialize workflow)"
  - "advancing a workflow to the next step"
  - "evaluating a Decision Node"
  - "routing work to a phase lead or specialist"
  - "enforcing a gate (governance matrix)"
  - "handling a step failure (rollback, re-run, escalate)"
  - "ending a slice and opening the next"
outputs:
  - intent-to-workflow routing decision
  - which agent to spawn next
  - which skill the agent should consume
  - which slash command corresponds to the current phase
  - workflow run-state (in `.project/working/`)
  - gate evaluations (pass/fail + approver routing)
  - phase exit artifacts (handed to next agent or back to orchestrator)
consumers:
  - delivery-lead (the agent persona that runs this SKILL)
  - every agent at session start
  - all role agents (receive routed work)
  - delivery-planner (this SKILL runs against the planner's output)
references:
  - workflow-file-shape.md
  - orchestration-runtime-detail.md
```
<!-- praxis:metadata:end -->

The single SKILL that takes you from "what just happened" to "what runs next." Two layers, deliberately combined:

- **Layer 1 — Routing (front door):** map user intent to the right workflow + agent + skill sequence. Cheap; always runs.
- **Layer 2 — Orchestration runtime:** execute the workflow as a state machine — sequence steps, evaluate Decision Nodes, route to agents, enforce gates, handle failure paths. Substantive; runs when a workflow is active.

The principle: **the platform's surface area is large; the path through it is small per request. This SKILL is the path AND the engine that walks it.**

The Delivery Lead persona is the **WHO**; this SKILL is the **HOW**. Persona and SKILL are not the same thing.

## When this SKILL fires

Layer 1 (routing): session just started; a vague user request needs mapping to a workflow; uncertain which SKILL to invoke; handing off work to a sub-agent; a slash command needs interpreting.

Layer 2 (orchestration runtime): a new project begins (load workflow, evaluate entry criteria); a workflow step completes (advance to next step or Decision Node); a Decision Node is reached (evaluate predicate, route to branch); a gate is reached (pause, route approval, resume); a step fails (apply the failure path); a slice ends (close `working/` memory, open the next).

---

# LAYER 1 — ROUTING

## First moves on session start

In order:

1. **Read `.project/semantic/project-charter.md`** — set by `delivery-planner` at project bootstrap. Tells you the activation flags (mode = G/B, has_data_plane, has_ml, has_agentic_ai, compliance regimes, scale, availability). **If the charter doesn't exist, the project hasn't been bootstrapped** — run `delivery-planner` first via the `/start` command.
2. **Read `.project/decision/INDEX.md`** — recent ADRs orient you to in-flight decisions.
3. **Check active workflow** at `.project/working/active-workflow.md` if it exists.
4. **Scan recent `.project/operational/factory-metrics/`** if quarterly cadence is due (per `system-steward`).

Now you know where you are.

## Intent → workflow routing

Match the user's intent against this decision tree:

```
USER INTENT
  ├─ "Start a new project" / "Build me a new ..."
  │     → /start (bootstraps; runs delivery-planner)
  │     → THEN: greenfield-api-service.yaml OR greenfield-saas.yaml
  ├─ "Pick up this existing codebase" / "Add ... to our existing system"
  │     → /audit (brownfield first-week: comprehension → arch reconciliation → debt audit → impact analysis)
  │     → THEN: brownfield-enhancement.yaml
  ├─ "Define what we're building" / "What are the requirements?"
  │     → /discover → Phase A (Product Manager)
  │     → Skills: product-discovery → requirements-elicitation → requirements-interrogation → nfr-definition
  │     → Gate: requirements_freeze
  ├─ "Design the architecture" / "How will this be built?"
  │     → /architect → Phase B (Solution Architect)
  │     → Skills: architecture-pattern-selection → api-design → data-modeling → resilience-patterns → threat-modeling → project-phasing
  │     → Plus: Architecture Challenger (5 sub-personas)
  │     → Gate: architecture_sign_off
  ├─ "Build slice N" / "Implement feature X"
  │     → /slice → implementation-slice.yaml workflow (per Lead Dev decomposition)
  │     → Activates the right specialist: backend-developer | frontend-developer | data-engineer | ml-ai-engineer
  │     → Skills: stack-X → frontend-design (UI tasks) → secure-coding → testing-strategy → observability → code-review → visual review (UI) → security-review → QA
  ├─ "Ship to production" / "Release v..."
  │     → /release → production-release.yaml workflow
  │     → Assembles 10-item evidence pack
  │     → Gate: production_go_live
  ├─ "Run the quarterly library review"
  │     → /steward → System Steward agent
  │     → Consumes factory-evaluation report → produces steward report
  │     → Gate: steward_promotion (per-proposal approval)
  ├─ "I have a rough idea" / "Help me refine this concept before we build"
  │     → /refine-idea → ideation-refinement-loop.yaml workflow
  │     → Bounded creator/reviewer/enhancer/arbiter loop; harnesses are swappable bindings
  │     → Gate: ideation_refinement_approval
  ├─ "Review this contract / ADR / roadmap" (outside a normal gate)
  │     → /review → on-demand closed-loop review
  │     → Skills: code-review + secure-coding + threat-modeling + api-design as scoped
  ├─ "Record what we learned using skill X" / "capture an observation"
  │     → /factory-record → rich factory-metrics observation for steward review
  ├─ "Something broke" / "We have an incident"
  │     → incident-runbook SKILL; severity routing per its matrix
  ├─ "Production is broken and needs a fix NOW" (P0/P1)
  │     → incident-runbook severity check first — only P0/P1 (or a critical
  │       security patch) is expedited-path eligible; else reroute to brownfield-enhancement.yaml
  │     → THEN: expedited-change.yaml — compressed gates now, MANDATORY retro
  │     → Gates: expedited_change_approval, expedited_change_retro
  ├─ "Can we even do X?" / "prove feasibility first"
  │     → spike.yaml — time-boxed build-to-learn loop; spike code NEVER merges
  │     → Gate: spike_disposition (archive | promote report into discovery)
  ├─ "Replace/modernize this legacy system"
  │     → modernization.yaml — strangler-fig; comprehension → target
  │       architecture/migration strategy → per-seam increment loop → cutover
  │     → Gates: modernization_strategy_sign_off, parallel_run_verification (per increment), legacy_decommission_approval
  ├─ "Add a new ML feature" / "Build an LLM-powered ..."
  │     → ml-ai-engineer agent activates (has_ml or has_agentic_ai must be true)
  │     → Skills: ml-problem-framing (always start here for ML) OR agentic-architecture (for LLM)
  ├─ "Run it autonomously" / "Keep going without me"
  │     → /drive → `autonomous-drive` protocol iterates the active task ledger
  └─ Unclear intent → ASK CLARIFYING QUESTION. Don't guess — per
        requirements-interrogation, surface ambiguity early.
```

## Workflow composition policy

Workflow templates in `workflows/` are patterns, instantiated per-project by
`delivery-planner` (flags activate/deactivate branches, phases, sub-personas).
A scenario earns a **new** workflow file only when its **gate topology**
differs — a different rhythm of human approvals — not merely because its
content differs; otherwise it's planner parameterization of an existing
template. This is the anti-sprawl rule: `factory-evaluation` treats
workflow-count creep as a decay signal, same as skill-count creep.

The per-workflow gate-topology signatures (all 9, one line each) live in
`references/orchestration-runtime-detail.md` — load when deciding whether a
scenario needs a new workflow or a planner flag.

## Slash commands

| Command | What it does | Maps to |
|---|---|---|
| `/start` | Bootstrap a new project | `delivery-planner` + architecture-doc skeleton |
| `/discover` | Phase A — requirements + NFRs | PM + 4 skills + `requirements_freeze` |
| `/architect` | Phase B — architecture + threat model + Challenger | SA + 7 skills + `architecture_sign_off` |
| `/slice` | One implementation slice | `implementation-slice.yaml` workflow |
| `/release` | Production release | `production-release.yaml` + `production_go_live` |
| `/audit` | Brownfield first-week kickoff | comprehension → reconciliation → debt → impact analysis |
| `/steward` | Quarterly library review | System Steward + `steward_promotion` |
| `/refine-idea` | Bounded ideation refinement loop | `ideation-refinement-loop.yaml` + `ideation_refinement_approval` |
| `/drive` | Autonomous drive iteration over the active task ledger | `autonomous-drive` SKILL |
| `/review` | On-demand closed-loop artifact review | reviewer roles + `.project/operational/reviews/` |
| `/factory-record` | Capture a rich telemetry observation | `scripts/factory-record.sh` |

Each slash command is a Markdown file (YAML frontmatter + prompt) under `.claude/commands/` for Claude Code; Gemini CLI uses the TOML variants under `.gemini/commands/`. Read the command file if you want to see exactly which SKILLs it invokes.

## Agent → role mapping

Two-tier orchestration: **Delivery Lead routes phases → Phase Leads (PM, Solution Architect, Lead Developer, Platform/SRE) run their phase → Specialists execute slices.** Don't have agents invoke other agents outside this pattern. Each agent's frontmatter description states its trigger; the full intent → lead-agent table lives in `references/orchestration-runtime-detail.md`. Conditional specialists: Data Engineer (`has_data_plane`), ML/AI Engineer (`has_ml` or `has_agentic_ai`), Mobile Developer (mobile in scope).

## Cadences

Load `references/orchestration-runtime-detail.md` for the full per-slice / per-cycle / per-release / monthly / quarterly cadence table.

## Project memory map

Artifacts are placed per the six-type taxonomy (semantic, episodic, procedural, decision, operational, working) defined in `memory-management`. Load `references/orchestration-runtime-detail.md` for the full location table. Every artifact carries the seven-field memory frontmatter so `memory-management` can index it.

---

# LAYER 2 — ORCHESTRATION RUNTIME

A workflow file (in `workflows/`) is the declarative state machine; this SKILL's Layer 2 is the interpreter. Drive-mode sessions run this same interpreter one task at a time — see `autonomous-drive` for the per-iteration protocol.

## Workflow file shape

Workflow YAMLs follow a canonical shape (metadata, phases, steps with agent/skills/inputs/outputs, decision nodes, gates, failure paths). Load `references/workflow-file-shape.md` for the annotated structure before executing an unfamiliar workflow.

## Step types

The orchestrator understands a small set of step types:

| Type | Behavior |
|---|---|
| `agent_invocation` | Spawn the named agent; hand it the inputs; wait for outputs. |
| `skill_invocation` | Direct SKILL invocation without an agent persona (rare; foundation SKILLs). |
| `parallel` | Run multiple branches concurrently; wait for all. |
| `decision_node` | Evaluate the named predicate; route to the matching branch. |
| `gate` | Pause; route approval request per `governance.yaml`; resume on approval. |
| `per_slice` | Iterate a sub-workflow per slice from `project-phasing`'s output. |
| `parallel_until` | Run repeatedly in parallel until a condition (e.g., model training rounds). |

## Decision Node evaluation

Decision Nodes are first-class — this SKILL owns the logic, not the agent. The `predicate` is named — dispatch to a small library of evaluators (in `predicates/`). Each predicate is a pure function that reads step outputs and returns a branch key. New predicates are added per workflow as needed; they live in the workflow's namespace. Load `references/orchestration-runtime-detail.md` for a worked `decision_node` YAML example.

## Model selection before agent spawn

Before every `agent_invocation` step, the Delivery Lead MUST run `adaptive-model-routing` to select the correct capability tier (deep | standard | light) and pass it as the `model:` field in the Agent tool call, per `governance/model-routing.yaml`. Do not default to the deep tier without scoring — deep-tier budget is finite. Fast reference: Architecture Challenger / threat-modeling / novel cross-cutting ADR → `deep`; everything else → score the rubric, default `standard`; classification / intent detection / pre-flight → `light`. Log every decision to `.project/telemetry/model-routing.jsonl`. Each agent's frontmatter `model:` field is the fallback default when spawned without an explicit routing decision; `adaptive-model-routing` overrides it when the task profile warrants.

## Agent routing model

When a step names an agent: load its definition, spawn it with the step's resolved inputs, await its declared outputs, and validate the shape (failure triggers `on_failure`). Load `references/orchestration-runtime-detail.md` for the full five-step sequence. This SKILL never executes agent work itself — it is the routing and gate layer; the agents are the workers.

## Agent Operating Protocol (AOP)

Every role agent (specialist, phase lead, or gate reviewer) executes its work as the same seven-phase loop. Agents don't restate this generically — each agent's "Working pattern (AOP)" section names only what's *specific* to that role at each phase; this is the canonical definition of what each phase means:

1. **Understand.** Read the task's inputs — scoped to what this task needs (the slice packet, the named ADRs, the agent's own portion of `.project/working/`), not a whole-directory read. Ground yourself in the current state before acting.
2. **Clarify.** Run `requirements-interrogation` to produce a KUACQ block (Known / Unknown / Assumed / Constraints / Questions) for anything ambiguous in the task. Route Questions to the responder who owns the answer.
3. **Plan.** Decompose the task into an ordered sequence of concrete steps before starting work.
4. **Execute.** Do the work, following the plan and the role's governing SKILLs/standards.
5. **Validate.** Self-check the output against the task's acceptance bar (tests, linters, gate criteria, or equivalent) before calling it done.
6. **Document.** Record what was done and why — implementation notes, ADRs for non-trivial choices, updates to `.project/working/` state.
7. **Hand-off.** Deliver the output to whoever consumes it next (reviewer, orchestrator, downstream agent) with enough context that they don't have to reconstruct scope.

Agents reference this list as "the seven-phase AOP" and add only their role-specific detail per phase.

## Gate enforcement

When a `gate` step is reached: read `governance/governance.yaml` for the approver, construct the approval request (what's being approved, evidence package, recommended action), route to the approver (solo dev: the principal; team: per the matrix), pause the workflow, then resume on `approved`/`rejected` — on rejection, loop back to the prior step with the rejection rationale or escalate per the workflow's rejection-path declaration. Load `references/orchestration-runtime-detail.md` for the full six-step sequence. Gates are non-skippable. A `challenger_objection_override` is itself a gated decision that produces an ADR.

## Parallelism, failure paths, and lifecycle

`parallel`/`parallel_until` steps run concurrently, coordinated via the agent host; writes to `.project/` are serialized regardless. Every step that can fail declares an `on_failure` action (`escalate` default, `rollback`, `retry_n`, or `route_to:`). Workflow state persists in `.project/working/workflow-state.yaml` and archives to `.project/episodic/` on completion. Load `references/orchestration-runtime-detail.md` for the full failure-path detail and the workflow lifecycle state diagram.

---

## Common rationalizations

Load `references/orchestration-runtime-detail.md` for the full rationalization-vs-counter table (charter-skipping, front-door-skipping, peer-spawning, discovery-skipping, gate-bypassing, Decision Node inlining, unpersisted steps).

## Mode handling (G/B)

**Greenfield.** Standard workflow execution. Entry criteria minimal (requirements brief exists, target repo identified).

**Brownfield.** Add a precondition: `codebase-comprehension` runs first; its `.repo-intel/` output is added to the workflow's input pool. Many subsequent steps consume `.repo-intel/` to ground decisions in the existing system. The `nfr_check` predicate is stricter on brownfield — NFR violations against existing infrastructure require explicit ADR.

## Verification

You are done routing (Layer 1) when:

- [ ] The user's intent has been classified against the routing tree.
- [ ] The next workflow / agent / SKILL / slash command is named explicitly.
- [ ] Activation flags from the charter have been evaluated (right specialists activated; conditional gates flagged).
- [ ] An `.project/working/active-workflow.md` exists (or the routing is for a one-off task that doesn't need workflow state).

You are done orchestrating (Layer 2) a workflow step when:

- [ ] Step inputs were resolved from prior outputs (or workflow inputs).
- [ ] The right agent was spawned with the declared inputs.
- [ ] Agent outputs were validated against the declared shape.
- [ ] Workflow state persisted to `.project/working/workflow-state.yaml`.
- [ ] If a gate fired: the approver routed, evidence packaged, decision recorded.
- [ ] If a Decision Node fired: the predicate evaluated, branch selected, branch entered.
- [ ] On failure: the declared `on_failure` action was taken (not silent retry).

If any item is missing, the step is not complete; do not advance.

## Outputs

Routing decisions (inline; logged to `.project/episodic/routing-decisions.md` if non-obvious), the active workflow marker (`.project/working/active-workflow.md`), workflow state (`.project/working/workflow-state.yaml`), gate evaluation records (`.project/operational/governance-events/`), and Decision Node decisions (inline in workflow state). Load `references/orchestration-runtime-detail.md` for the full output-location table.

## What this SKILL does NOT do

Execute the work (it routes only), bootstrap the charter (`delivery-planner` via `/start`), catalog the SKILLs (`skill-registry`), plan the project (`delivery-planner` + `project-phasing`), make agent-level judgment (agents do that within their phase), or modify the library (System Steward's job). Load `references/orchestration-runtime-detail.md` for the full list.

## Anti-patterns

- Charter never read (agents guess) / routing skipped (jumps straight to implementation) / wrong agent invoked (intent unparsed).
- Slash commands bypassed (200-word prompts each time) / specialist spawns peers (two-tier rule violated).
- Cadences ignored — quarterly steward review never happens; library decays.
- Workflow steps "remembered" instead of persisted — execution can't resume; gates skipped programmatically — no evidence trail.
- Decision Node logic inlined as if-statements (can't be versioned) / predicates re-implemented per workflow (drift between evaluators).
- `on_failure` not declared — failures silently swallowed; no rollback.

## Implementation notes

This SKILL runs in the Delivery Lead's context; subagents run in their own, with cross-context state passing through `.project/working/`. Predicate evaluators are versioned alongside workflows — changing one used in production requires an ADR. This SKILL never *writes* to skills, agents, workflows, or governance (read-only at runtime); modifications go through System Steward + `steward_promotion`.
