---
name: delivery-planner
description: |-
  Adaptive planning — instantiate a workflow template for *this* project using its characteristics. Consumes a workflow template (from `workflows/`), the PM's product-discovery output, the SA's architecture, the NFR register, scale targets, regulatory exposure, team composition, distributed-systems complexity, and ML/agentic content. Produces an *executable workflow instance* with the right phases activated, Decision Node thresholds calibrated, gate intensity scaled to risk, parallelism strategy selected, and optional skills toggled. Without this, "build Uber" and "build internal CRUD tool" would run the same workflow — different problems demand different execution graphs. Use whenever a project transitions from discovery to architecture-and-planning, or whenever the project's characterization changes materially.
---

# Delivery Planner

<!-- praxis:metadata:begin -->
```yaml
capability: lifecycle
domain: cross-cutting
state: active
dependencies:
  - skill-registry
  - project-memory
triggers:
  - "starting workflow execution for a project"
  - "project characteristics change materially"
  - "instantiating greenfield-saas / brownfield-enhancement / ml-feature-launch / etc. for a real engagement"
  - "scale targets or regulatory exposure change mid-project"
outputs:
  - executable workflow instance (workflow file + project-specific parameterization)
  - activation manifest (which optional skills, sub-personas, gates are on)
  - parallelism plan (which steps run concurrently)
consumers:
  - using-praxis
  - delivery-lead
references: []
```
<!-- praxis:metadata:end -->

Workflow templates in `workflows/` are *patterns*, not plans. `greenfield-saas` is the same shape regardless of whether you're building Uber or a small internal CRUD tool, but the execution graph these two should run is wildly different. The planner is what turns templates into project-specific executables.

## When this skill fires

- At project start, once enough discovery + architecture data exists to characterize the project (typically right after `nfr-definition` and before the first slice begins).
- When project characteristics change materially during execution — scale targets revised upward, new regulatory regime added, ML component introduced, distributed-systems complexity reassessed.
- When a workflow template itself is updated and the active project needs to re-plan against the new template.

## Inputs

The planner consumes:

| Input | Source | What it tells the planner |
|---|---|---|
| Workflow template | `workflows/<name>.yaml` | The shape of the execution graph |
| `product-discovery` output | `.project/working/` | Vision, JTBD, opportunity sizing, MVP scope |
| `nfr-definition` output | `.project/working/` | Scale targets, RTO/RPO, performance targets, regulatory bindings |
| `architecture-pattern-selection` (if run) | `.project/working/` | Macro architecture (monolith / microservices / event-driven / serverless), distributed-systems decisions |
| Project characteristics (extracted) | discovery + architecture | Canonical flags (all agents read): `mode` (G/B), `has_data_plane`, `has_ml`, `has_agentic_ai`, `is_multi_tenant`, `compliance_regimes`, `scale_target_qps`, `availability_target`. Planner-extended flags (planner uses; not propagated): `has_ui`, `team_size`, `budget_constrained`. |

The planner can be invoked with partial inputs — it produces the *most-instantiated* workflow possible given what's available, and the orchestrator re-plans when more inputs arrive.

## Workflow-selection table

Which template to instantiate, keyed off the scenario signal:

| Scenario signal | Template |
|---|---|
| Vague idea, nothing scoped yet | `ideation-refinement-loop` |
| New API service, requirements clear | `greenfield-api-service` |
| New product / SaaS | `greenfield-saas` |
| Feature on an existing system | `brownfield-enhancement` |
| P0/P1 emergency (or critical security patch) | `expedited-change` |
| Feasibility / "can we even do X" question | `spike` |
| Legacy system replacement | `modernization` |
| Per-slice execution (any template above) | `implementation-slice` (sub-workflow) |
| Ready to ship | `production-release` |

Selection signals come from `requirements-intake`, incident severity, or characterization flags (e.g. brownfield comprehension's characterization output); when two templates fit, gate topology decides — see `skills/using-praxis/SKILL.md`'s Workflow composition policy.

## Outputs

The output is a workflow *instance* — same shape as a template but with:

- **Phase activation** — optional phases enabled or disabled per project characteristics. A project with `has_ml=false` skips the ML training/evaluation/serving phases entirely.
- **Decision Node thresholds calibrated** — generic predicates like `nfr_satisfied?` parameterize against the actual NFR register. The `cost_under_budget?` predicate gets the actual budget number from `nfr-definition`.
- **Gate intensity scaled to risk** — a high-regulation project (HIPAA + PCI) gets extra security and compliance gates; an internal CRUD tool gets the minimum.
- **Parallelism strategy** — which steps run concurrently for this project. A simple service with one slice runs sequentially; a multi-team SaaS runs BE/FE/Data slices in parallel.
- **Optional skills toggled** — only the skills the project needs are loaded into the orchestrator's plan. `multi-tenancy` activates only if `is_multi_tenant=true`; `responsible-ai` activates only if `has_ml=true`.
- **Sub-persona selection** — Architecture Challenger's sub-personas (scale/security/cost/operations/reliability) are selected per project. Internal CRUD might get only `operations` + `security`; multi-tenant SaaS gets all five.

The output file lives in `.project/working/workflow-instance.yaml` and is what the orchestrator actually executes.

## Planning logic

The planner runs a small set of rules over the inputs:

### Phase activation rules

```
if project.has_ui:
    activate phases: ux_design, frontend_implementation
if project.has_data_plane:
    activate phases: data_engineering
if project.has_ml or project.has_agentic_ai:
    activate phases: ml_problem_framing, ml_training_evaluation, ml_serving, ml_monitoring
if project.has_agentic_ai:
    activate skills: agentic-architecture, rag-design, evaluation-engineering, llm-safety
if project.is_multi_tenant:
    activate skills: multi-tenancy
    add gate: tenant-isolation-review
if project.mode == 'brownfield':
    activate skills: codebase-comprehension, impact-analysis
    prepend phase: comprehension before any modification step
```

### Decision Node calibration

Generic predicates carry parameter slots filled at planning time:

```
predicate template:    nfr_satisfied(architecture, nfr_register)
parameterized:         nfr_satisfied(architecture, nfr_register, thresholds={
                          'p99_latency_ms': 200,
                          'availability_target': 99.95,
                          'rto_minutes': 15,
                          'rpo_minutes': 5
                       })
```

The thresholds come from `nfr-definition`'s output. If thresholds are absent, the planner flags this back to the orchestrator (insufficient inputs).

### Gate intensity rules

```
base gates (always on):
  - requirements_freeze
  - architecture_sign_off
  - production_go_live

added gates by regime:
  if 'HIPAA' in compliance_regimes:
    add: hipaa-control-review (after security review)
  if 'PCI' in compliance_regimes:
    add: pci-scope-review (before deploy)
  if 'SOC2' in compliance_regimes:
    add: soc2-evidence-capture (continuous; at each phase exit)
  if 'FedRAMP' in compliance_regimes:
    add: fedramp-boundary-review (architecture phase)

added gates by characteristic:
  if project.is_multi_tenant:
    add: tenant-isolation-review (after architecture)
  if project.has_ml:
    add: responsible-ai-review (before model deploy)
  if project.scale_target_qps > 10000:
    add: capacity-stress-test (before production go-live)
```

### Sub-persona selection (Architecture Challenger)

```
default sub-personas: [security, operations]    # always on
add 'scale' if: scale_target_qps > 1000 or is_multi_tenant
add 'cost' if: scale_target_qps > 5000 or budget_constrained
add 'reliability' if: availability_target >= 99.95 or (scale_target_qps > 10000 and is_multi_tenant)
```

### Parallelism strategy

```
default: sequential within phase, parallel across phases where dependencies allow
upgrade to phase-internal parallelism if:
  - team_size >= 3 (enough agent capacity)
  - phase has independent sub-tasks (BE + FE + Data on the same slice)
downgrade to fully sequential if:
  - solo_dev_mode (single principal driving everything)
  - first_slice (walking skeleton — keep it serial to expose plumbing issues early)
```

## The "build Uber vs. build CRUD tool" example

Two projects starting from `greenfield-saas`:

**"Internal CRUD tool" project characterization:**
- `has_ui=true, has_data_plane=false, has_ml=false, is_multi_tenant=false`
- `scale_target_qps=10, availability_target=99.0, RTO=4 hours, RPO=24 hours`
- `compliance_regimes=[SOC2 (light)]`
- `team_size=1 (solo dev)`

Instance produced: minimal phases (discovery → architecture → BE+FE in parallel → light testing → deploy); Challenger sub-personas `[security, operations]` only; gates `[requirements_freeze, architecture_sign_off, production_go_live]`; no chaos engineering, no multi-tenancy skills loaded; sequential execution within phases.

**"Build Uber" project characterization:**
- `has_ui=true, has_data_plane=true, has_ml=true, has_agentic_ai=false, is_multi_tenant=true (geographic)`
- `scale_target_qps=50000, availability_target=99.99, RTO=5 minutes, RPO=30 seconds`
- `compliance_regimes=[SOC2, GDPR, PCI-DSS, regional regulations]`
- (distributed-systems characteristics are derived from `scale_target_qps + is_multi_tenant + availability_target` — no separate flag)
- `team_size=many`

Instance produced: full phase tree; Challenger sub-personas `[scale, security, cost, operations, reliability]` all on; gates include `tenant-isolation-review, capacity-stress-test, pci-scope-review, gdpr-data-residency-review`; chaos engineering required pre-prod; multi-tenancy + distributed-systems-patterns + capacity-resource-estimation skills loaded; parallel BE/FE/Data execution within phases; chaos-engineering experiments scheduled at each major milestone.

Same template, radically different executable workflows. That's the planner's value.

## Re-planning

The planner can be re-invoked mid-project if characteristics change. The new instance is diffed against the running one; the diff identifies steps to add, remove, or modify. The orchestrator applies the diff at the next safe transition point (typically next phase boundary). Material changes trigger an ADR documenting the re-plan.

## Mode handling (G/B)

**Greenfield.** Standard planning from template + characteristics.

**Brownfield.** The planner's first action is to read `.repo-intel/` for the existing system characterization. Many characteristics are inferred from the existing system (stack, scale, integration points, compliance regime evidence). The PM still validates these characterizations with the human before the planner finalizes.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "The project is obvious; I don't need a charter." | Multiple agents read the charter. Inference fragments their view. Write it once. |
| "I'll set all flags conservatively to be safe." | Over-flagging activates skills that don't apply; cost without benefit. Flag what's true. |
| "Compliance regime can be 'we'll figure it out later'." | Compliance shapes architecture. Decide now; revise via ADR if needed. |
| "Scale target = whatever the user asked for." | The user often asks for what they think they want, not what's defensible. Validate the QPS assumption. |
| "Greenfield by default if mode is unclear." | Brownfield has different first moves (codebase-comprehension, debt audit). Mis-classification means weeks of wrong-shaped work. |
| "Charter is just paperwork." | Charter is the runtime config for every other agent. Get it wrong and every agent makes consistent wrong decisions. |

## Verification

You are done when:

- [ ] `.project/semantic/project-charter.md` exists with all required flags populated.
- [ ] Mode (G/B) is set with a clear rationale.
- [ ] Activation flags are evaluated against the project's actual scope: `has_data_plane`, `has_ml`, `has_agentic_ai`, `is_multi_tenant`.
- [ ] `compliance_regimes` lists every applicable regime (or `none` with rationale).
- [ ] NFR targets are numeric where possible (`scale_target_qps`, `availability_target`).
- [ ] Stack + cloud preferences captured.
- [ ] Brownfield only: `.repo-intel/` has been generated and informs the charter.

Evidence to check:
- The charter file passes `memory-management`'s seven-field frontmatter validation.
- Workflows selected for this project match the charter's mode + flags (e.g., `has_ml=true` activates `ml-ai-engineer`).
- Conditional governance gates from `governance.yaml` (responsible_ai_review, hipaa_control_review, etc.) match the charter's flags.

If any item is missing, the charter is incomplete; do not advance to Phase A.

## What this skill does not do

- Execute the workflow — that's `using-praxis`.
- Decide whether to start a project — that's a human decision.
- Modify workflow templates — those are managed by the Curator + Steward.
