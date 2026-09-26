# Orchestration runtime detail

Supporting detail for `using-praxis`. Load this file when you need the full tables/sequences behind the SKILL.md pointers.

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

## Decision Node evaluation example

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

## Agent routing model

When a step says `agent: solution-architect`:

1. Load the agent definition (`agents/solution-architect.md`).
2. Spawn a subagent instance in the host (Claude Code subagent tool; Codex session-as-agent pattern).
3. Hand it the step's `inputs` (resolved from prior step outputs).
4. Await the agent's outputs (declared in the agent's frontmatter).
5. Validate outputs against the declared shape; failure triggers `on_failure`.

This SKILL never executes agent work itself. It is the routing and gate layer; the agents are the workers.

## Gate enforcement — full sequence

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

## Outputs — full table

| Output | Location |
|---|---|
| Routing decision | inline reasoning; logged to `.project/episodic/routing-decisions.md` if non-obvious |
| Active workflow marker | `.project/working/active-workflow.md` |
| Workflow state | `.project/working/workflow-state.yaml` |
| Gate evaluation records | `.project/operational/governance-events/` |
| Decision Node decisions | inline in workflow state |

## What this SKILL does NOT do — full list

- Execute the work — it routes to the SKILL / workflow / agent that does.
- Bootstrap the charter — that's `delivery-planner` via `/start`.
- Catalog the SKILLs — that's `skill-registry` (machine-readable index).
- Plan the project — that's `delivery-planner` + `project-phasing`.
- Make agent-level judgment — agents do that within their phase.
- Modify the library — System Steward does that; this SKILL consumes the library as-published.

## Workflow gate-topology signatures

| Workflow | Gate-topology signature |
|---|---|
| `ideation-refinement-loop` | 1 gate — bounded convergence loop |
| `greenfield-api-service` | 2 gates (`requirements_freeze`, `architecture_sign_off`) + slice sub-gates |
| `greenfield-saas` | same 2-gate shape, parallel BE/FE/Data slices |
| `brownfield-enhancement` | same 2-gate shape + comprehension precondition |
| `implementation-slice` | pre-merge review/QA gate; sub-workflow, no top-level gate of its own |
| `production-release` | 1 gate (`production_go_live`), 10-item evidence pack |
| `expedited-change` | 2 gates — compressed now + MANDATORY retro |
| `spike` | 1 gate (`spike_disposition`); no review gate; code never merges |
| `modernization` | 3 gates — strategy sign-off, per-increment parallel-run, decommission |

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
