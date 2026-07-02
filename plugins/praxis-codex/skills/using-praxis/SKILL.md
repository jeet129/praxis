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
references: []
```
<!-- praxis:metadata:end -->

The single SKILL that takes you from "what just happened" to "what runs next." Two layers, deliberately combined:

- **Layer 1 — Routing (front door):** map user intent to the right workflow + agent + skill sequence. Cheap; always runs.
- **Layer 2 — Orchestration runtime:** execute the workflow as a state machine — sequence steps, evaluate Decision Nodes, route to agents, enforce gates, handle failure paths. Substantive; runs when a workflow is active.

The principle: **the platform's surface area is large; the path through it is small per request. This SKILL is the path AND the engine that walks it.**

The Delivery Lead persona is the **WHO**; this SKILL is the **HOW**. Persona and SKILL are not the same thing.

## When this SKILL fires

Layer 1 (routing):

- A session just started — what do I do first?
- The user gave a vague request — which workflow does it map to?
- I'm uncertain which SKILL to invoke for the current task.
- I'm handing off work to a sub-agent and need to brief them.
- A slash command was used and I need to know what it means.

Layer 2 (orchestration runtime):

- A new project begins → load the project's workflow, evaluate entry criteria.
- A workflow step completes → advance to next step or Decision Node.
- A Decision Node is reached → evaluate predicate, route to chosen branch.
- A gate is reached → pause, route approval, resume on approval.
- A step fails → apply the failure path (rollback / retry / escalate).
- A slice ends → close `working/` memory, open the next slice.

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
  │
  ├─ "Start a new project" / "Build me a new ..." 
  │     → /start (bootstraps; runs delivery-planner)
  │     → THEN: greenfield-api-service.yaml OR greenfield-saas.yaml
  │
  ├─ "Pick up this existing codebase" / "Add ... to our existing system"
  │     → /audit (brownfield first-week: comprehension → arch reconciliation → debt audit → impact analysis)
  │     → THEN: brownfield-enhancement.yaml
  │
  ├─ "Define what we're building" / "What are the requirements?"
  │     → /discover → Phase A (Product Manager)
  │     → Skills: product-discovery → requirements-elicitation → requirements-interrogation → nfr-definition
  │     → Gate: requirements_freeze
  │
  ├─ "Design the architecture" / "How will this be built?"
  │     → /architect → Phase B (Solution Architect)
  │     → Skills: architecture-pattern-selection → api-design → data-modeling → resilience-patterns → threat-modeling → project-phasing
  │     → Plus: Architecture Challenger (5 sub-personas)
  │     → Gate: architecture_sign_off
  │
  ├─ "Build slice N" / "Implement feature X"
  │     → /slice → implementation-slice.yaml workflow (per Lead Dev decomposition)
  │     → Activates the right specialist: backend-developer | frontend-developer | data-engineer | ml-ai-engineer
  │     → Skills: stack-X → secure-coding → testing-strategy → observability → code-review → security-review → QA
  │
  ├─ "Ship to production" / "Release v..."
  │     → /release → production-release.yaml workflow
  │     → Assembles 10-item evidence pack
  │     → Gate: production_go_live
  │
  ├─ "Run the quarterly library review"
  │     → /steward → System Steward agent
  │     → Consumes factory-evaluation report
  │     → Produces steward report
  │     → Gate: steward_promotion (per-proposal approval)
  │
  ├─ "Something broke" / "We have an incident"
  │     → incident-runbook SKILL
  │     → Severity routing per the matrix in incident-runbook
  │
  ├─ "Add a new ML feature" / "Build an LLM-powered ..."
  │     → ml-ai-engineer agent activates (has_ml or has_agentic_ai must be true)
  │     → Skills: ml-problem-framing (always start here for ML) OR agentic-architecture (for LLM)
  │
  └─ Unclear intent → ASK CLARIFYING QUESTION
        Don't guess. Per the requirements-interrogation discipline, surface ambiguity early.
```

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

Each slash command is a TOML file under `.claude/commands/` that activates the right sequence. Read the TOML if you want to see exactly which SKILLs it invokes.

## Agent → role mapping

When you decide which agent should do the work:

| User intent | Lead agent |
|---|---|
| Vague request, mode unclear | Delivery Lead |
| "Define what we're building" | Product Manager |
| "Design the architecture" | Solution Architect |
| "Review the architecture adversarially" | Architecture Challenger |
| "Decompose into slices" | Lead Developer |
| "Implement backend slice" | Backend Developer |
| "Implement frontend slice" | Frontend Developer |
| "Design the UX" | UX Designer |
| "Review this PR" | Code Reviewer |
| "Audit security" | Security Reviewer |
| "Write the test plan" | QA Engineer |
| "Write the docs" | Tech Writer |
| "Set up infra / CI / deploy" | Platform/SRE |
| "Build data pipeline / model the warehouse" | Data Engineer (has_data_plane required) |
| "Build ML feature / LLM agent / RAG / safety" | ML/AI Engineer (has_ml or has_agentic_ai required) |
| "Evolve the library itself" | System Steward (cross-project; quarterly) |

Two-tier orchestration: **Delivery Lead routes phases → Phase Leads run their phase → Specialists execute slices.** Don't have agents invoke other agents directly outside this pattern.

## Cadences

| Cadence | What runs |
|---|---|
| **Per slice** (2-5 days) | `implementation-slice.yaml` + Code Review + Security Review + QA gates + slice DoD |
| **Per cycle** (2-4 weeks) | Cycle planning; debt allocation (15-25%); cycle retro |
| **Per release** | `production-release.yaml` + `production_go_live` gate + release notes |
| **Monthly** | Architecture documentation reconciliation; runbook freshness; ADR walk |
| **Quarterly** | `factory-evaluation` → System Steward → `steward_promotion` |

## Project memory map

When writing artifacts, place them per the six-type taxonomy (per `memory-management`):

| Type | Where | What |
|---|---|---|
| **Semantic** | `.project/semantic/` | What we know (charter, glossaries, product discovery, NFR register, datasheets) |
| **Episodic** | `.project/episodic/` | What happened (retros, incidents, postmortems, decision-event logs) |
| **Procedural** | `.project/procedural/` | How we do things (procedures, policies, runbook templates) |
| **Decision** | `.project/decision/` | ADRs; immutable; INDEX.md catalogs |
| **Operational** | `.project/operational/` | What's live (runbooks, releases, ml-models, factory-metrics, debt-register) |
| **Working** | `.project/working/` | In-flight artifacts (architecture overview, in-flight diagrams, workflow-state.yaml) |

Every artifact carries the seven-field memory frontmatter so `memory-management` can index it.

---

# LAYER 2 — ORCHESTRATION RUNTIME

A workflow file (in `workflows/`) is the declarative state machine; this SKILL's Layer 2 is the interpreter.

## Workflow file shape

```yaml
name: greenfield-api-service
version: 1
entry_criteria:
  - requirements_brief_exists
  - target_repo_identified
  - mode_known
steps:
  - id: discovery
    type: agent_invocation
    agent: product-manager
    skill: requirements-elicitation
    inputs:
      from: initial_brief
    outputs: [requirements_brief, scope_boundary]
    on_failure: escalate

  - id: nfr_definition
    type: agent_invocation
    agent: product-manager
    skill: nfr-definition
    inputs:
      from: requirements_brief
    outputs: [nfr_register]

  - id: requirements_gate
    type: gate
    name: requirements_freeze
    approver: governance.requirements_freeze.approver

  - id: architecture
    type: parallel
    branches:
      - agent: solution-architect
        skill: architecture-pattern-selection
        outputs: [architecture_decision, c4_diagrams]
      - agent: ml-ai-engineer
        skill: ml-problem-framing
        condition: project.has_ml == true

  - id: challenger_review
    type: agent_invocation
    agent: architecture-challenger
    skill: architecture-pattern-selection
    sub_personas: [scale, security, cost, operations, reliability]
    inputs:
      from: architecture
    outputs: [challenge_report]

  - id: nfr_check
    type: decision_node
    predicate: nfr_satisfied(architecture_decision, nfr_register)
    branches:
      true: [architecture_gate]
      false: [architecture, with_violations_as_input]

  - id: architecture_gate
    type: gate
    name: architecture_sign_off
    approver: governance.architecture_sign_off.approver

  - id: implementation_loop
    type: per_slice
    workflow: implementation-slice
    until: project_phasing.complete == true

exit_criteria:
  - all_phases_complete
  - production_go_live_approved
failure_paths:
  rollback:
    - revert_repo_changes
    - close_slice
    - notify_human
```

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

Decision Nodes are first-class — this SKILL owns the logic, not the agent.

```yaml
- id: nfr_check
  type: decision_node
  predicate: nfr_satisfied(architecture_decision, nfr_register)
  branches:
    true: [architecture_gate]
    false: [architecture, with_violations_as_input]
```

The `predicate` is named — dispatch to a small library of evaluators (in `predicates/`). Each predicate is a pure function that reads step outputs and returns a branch key. New predicates are added per workflow as needed; they live in the workflow's namespace.

## Model selection before agent spawn

Before every `agent_invocation` step, the Delivery Lead MUST run `adaptive-model-routing` to select the correct model. Pass the result as the `model:` field in the Agent tool call. Do not default to Opus without scoring — Opus quota is finite and the rubric exists to prevent waste.

Fast reference:
- Architecture Challenger, threat-modeling, novel cross-cutting ADR → `claude-opus-4-8`
- Everything else → score the rubric; default is `claude-sonnet-4-6`
- Classification, intent detection, pre-flight → `claude-haiku-4-5-20251001`

Log every routing decision to `.project/working/model-routing-log.yaml`.

Each agent also ships a default model in its own frontmatter (`model:` field). That default applies when the agent is spawned without an explicit routing decision. `adaptive-model-routing` overrides the default when the task profile warrants.

## Agent routing model

When a step says `agent: solution-architect`:

1. Load the agent definition (`agents/solution-architect.md`).
2. Spawn a subagent instance in the host (Claude Code subagent tool; Codex session-as-agent pattern).
3. Hand it the step's `inputs` (resolved from prior step outputs).
4. Await the agent's outputs (declared in the agent's frontmatter).
5. Validate outputs against the declared shape; failure triggers `on_failure`.

This SKILL never executes agent work itself. It is the routing and gate layer; the agents are the workers.

## Gate enforcement

When a `gate` step is reached:

1. Read `governance/governance.yaml` for the gate's approver.
2. Construct the approval request (what's being approved, evidence package, recommended action).
3. Route to the approver (solo dev: the principal; team: per the matrix).
4. Pause the workflow.
5. Resume on `approved` or `rejected` response.
6. On `rejected`: loop back to the prior step with rejection rationale as input, or escalate per the workflow's rejection-path declaration.

Gates are non-skippable. A `challenger_objection_override` is itself a gated decision that produces an ADR.

## Parallelism

`parallel` and `parallel_until` steps run concurrently. Coordinate via the agent host (Claude Code spawns subagents; Codex spawns serial sessions with shared `.project/`). Writes to `.project/` are serialized regardless of parallel agent execution.

## Failure paths

Every step that can fail declares an `on_failure` action:

- `escalate` — route to human (default).
- `rollback` — apply the workflow's rollback steps.
- `retry_n` — retry with backoff up to N times.
- `route_to: <step_id>` — jump to a remediation step.

## Workflow lifecycle

```
loaded → entry_criteria_met → running → (each step: pending → in_progress → complete) → exit_criteria_met → complete
                                  ↓
                              failed (if exit_criteria_not_met + no recovery)
```

Workflow state persists in `.project/working/workflow-state.yaml` so execution can resume across sessions. On project completion, the state archives to `.project/episodic/`.

---

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll skip the charter; I can infer the flags." | The charter exists for a reason — multiple agents read it. Inferring fragments the team's view. Read it. |
| "I know which SKILL to use; I don't need the front door." | The front door is 60 seconds. Choosing the wrong starting SKILL is 60 minutes of rework. |
| "I'll spawn another agent from inside this one." | Two-tier rule: only the Delivery Lead routes. Specialists do work; they don't spawn peers. |
| "The user said 'just build it'; I'll skip discovery." | Vague-request-into-implementation is the #1 failure mode. Always at least run requirements-interrogation's KUACQ block. |
| "Gates are bureaucracy; I'll bypass." | Gates are how approvals leave evidence trails. Bypass = no trail = no audit answer. |
| "Decision Nodes are just if-statements; I'll inline." | Named predicates exist to be versioned, evaluated identically every time, and overridden by ADR when needed. Inlining defeats all three. |
| "The workflow file is verbose; I'll just remember the steps." | Workflows are how the system survives sessions. Steps in your head die at session end. |

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

| Output | Location |
|---|---|
| Routing decision | inline reasoning; logged to `.project/episodic/routing-decisions.md` if non-obvious |
| Active workflow marker | `.project/working/active-workflow.md` |
| Workflow state | `.project/working/workflow-state.yaml` |
| Gate evaluation records | `.project/operational/governance-events/` |
| Decision Node decisions | inline in workflow state |

## What this SKILL does NOT do

- Execute the work — it routes to the SKILL / workflow / agent that does.
- Bootstrap the charter — that's `delivery-planner` via `/start`.
- Catalog the SKILLs — that's `skill-registry` (machine-readable index).
- Plan the project — that's `delivery-planner` + `project-phasing`.
- Make agent-level judgment — agents do that within their phase.
- Modify the library — System Steward does that; this SKILL consumes the library as-published.

## Anti-patterns

- Charter never read; agents operate on guesses.
- Routing decision skipped; agent jumps straight to implementation.
- Wrong agent invoked because the intent wasn't parsed.
- Slash commands bypassed; the user types out 200-word prompts each time.
- Specialist agent spawns peers (two-tier rule violated).
- Cadences ignored — quarterly steward review never happens; library decays.
- Workflow steps "remembered" instead of persisted to state — execution can't resume.
- Gates skipped programmatically — no evidence trail.
- Decision Node logic inlined as if-statements — can't be versioned or overridden.
- Predicates re-implemented per workflow — duplication; drift between evaluators.
- `on_failure` not declared — failures silently swallowed; no rollback.

## Implementation notes

- This SKILL runs in the Delivery Lead's context; subagents run in their own contexts. Cross-context state passes through `.project/working/`.
- Predicate evaluators are versioned alongside workflows. Changing a predicate used in production workflows requires an ADR.
- This SKILL never *writes* to skills, agents, workflows, or governance — those are read-only at runtime. Modifications go through System Steward + `steward_promotion`.
