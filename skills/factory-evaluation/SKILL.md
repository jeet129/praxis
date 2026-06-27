---
name: factory-evaluation
description: How the Praxis measures and evaluates ITSELF. The library's evals — skill efficacy, agent performance, workflow completion rate, gate clearance discipline, time-to-evidence per gate, defect leakage, slice cycle time, knowledge growth health. Distinct from `evaluation-engineering` (which evaluates the products you ship) — this skill evaluates the *factory that builds them*. Read by System Steward as the input for library-evolution proposals. Use when establishing baseline factory metrics, when investigating systematic regressions across projects, when proposing a skill change with evidence, when reviewing the library quarterly, or when the team feels something is degrading without knowing why.
capability: factory
domain: cross-cutting
state: active
dependencies:
  - skill-registry
  - memory-management
  - project-memory
  - engineering-standards
triggers:
  - "establishing baseline factory metrics for a new library install"
  - "quarterly library review"
  - "System Steward proposing a library change; evidence required"
  - "investigating cross-project regression (multiple projects degrading similarly)"
  - "evaluating whether a recent skill change improved or regressed outcomes"
  - "reporting library health to leadership"
outputs:
  - factory metric catalog (what we measure)
  - eval harness for the library (the harness itself)
  - quarterly factory report (the analysis)
  - skill efficacy report per skill
  - agent performance report per agent
  - knowledge-growth health report
consumers:
  - system-steward (primary consumer; proposes changes from evidence)
  - delivery-lead (consumes for orchestration retros)
  - principal (consumes for ROI conversations)
  - skill-registry (catalogs eval results per skill)
  - memory-management (memory health metrics)
references: []
---

# Factory Evaluation

The discipline of evaluating the Praxis itself. Teams that don't measure their factory cannot improve it — they iterate on hunches, ship "improvements" that may regress, and accumulate skill bloat. This skill makes the factory measurable: skills measured for efficacy, agents measured for performance, workflows measured for completion + cycle time, governance gates measured for evidence-completeness + time-to-clear.

The principle: **what we measure improves. The library is no exception. Measure the library; improve the library.**

## When this skill fires

- Establishing baseline factory metrics for a new library install.
- Quarterly library review.
- System Steward proposing a library change with evidence.
- Investigating cross-project regression (multiple projects show similar degradation).
- Evaluating whether a recent skill change improved or regressed outcomes.
- Reporting library health to leadership / principal.

## What this skill is NOT

- Evaluating products / AI features you ship (that's `evaluation-engineering` for agentic; `ml-training-evaluation` for ML; `testing-strategy` for application code).
- Measuring individual contributor performance (this is about the factory, not the worker).
- A replacement for retros (it informs retros).

## The factory metric catalog

Five metric families.

### 1. Skill metrics (per SKILL)

| Metric | What it measures | Signal |
|---|---|---|
| **Invocation rate** | How often the skill fires across projects | Discoverability problem if invocation < expected. |
| **Trigger precision** | When the skill fires, was it the right skill? | Trigger description quality. |
| **Trigger recall** | When the skill SHOULD have fired, did it? | Missing trigger phrases. |
| **Time-to-output** | How long from invocation to producing the output | Skill bloat / clarity issue if growing. |
| **Output acceptance rate** | Reviewers accept the skill's output without major rework | Skill quality. |
| **Downstream rework rate** | Outputs that downstream skills had to rework | Skill incompleteness or boundary leak. |
| **Reference drift** | How often references go stale | Maintenance load. |
| **Lifecycle state** | experimental / active / deprecated / merged | Health snapshot. |

### 2. Agent metrics (per ROLE AGENT)

| Metric | What it measures | Signal |
|---|---|---|
| **Hand-off latency** | Time agent waits between getting a packet and acting | Coordination overhead. |
| **Decision quality** | Sample-reviewed decisions vs principal's would-be-decision | Agent calibration. |
| **Escalation rate** | How often the agent escalates to principal | Either correctly escalating (good) or under-confident (bad). |
| **Per-AOP-step time distribution** | Where in the AOP the agent spends most time | Bottleneck identification. |
| **Tool-call efficiency** | Number of tool calls per outcome | Agent verbosity / loop discipline. |
| **Cross-agent contention** | Tasks waiting on this agent | Bottleneck. |

### 3. Workflow metrics (per WORKFLOW)

| Metric | What it measures | Signal |
|---|---|---|
| **Completion rate** | Workflows that reach exit_criteria | Process health. |
| **Phase cycle time** | Time per phase (PM, SA, Implementation, Release) | Bottleneck. |
| **Decision Node distribution** | Branches taken at each Decision Node | Workflow fit; rare-branch over-engineering. |
| **Gate clearance time** | Time from gate-reached to gate-cleared | Governance overhead vs evidence depth. |
| **Defect leakage** | Defects found in slice N that originated in slice N-K | Quality gates regressing. |
| **Rework rate** | Slices reopened after closure | DoD discipline. |

### 4. Governance metrics (per GATE)

| Metric | What it measures | Signal |
|---|---|---|
| **Evidence completeness on first submission** | Was the evidence pack right the first time? | Skill / agent training quality. |
| **Time-to-clear** | From gate-reached to approver decision | Governance load; principal bandwidth. |
| **Reject + iterate rate** | Gates that needed multiple rounds | Quality of upstream work. |
| **Conditional gate fire rate** | Conditional gates that actually triggered | Activation rule calibration. |
| **Override usage** | Challenger objections overridden / security findings accepted | Risk posture trend. |

### 5. Library health metrics

| Metric | What it measures | Signal |
|---|---|---|
| **Skill count** | Total SKILLs | Approaching 101+ → consolidation. |
| **Capability balance** | Skill count per capability area | Imbalance — one area expanding unmanaged. |
| **Skill lifecycle distribution** | % active / experimental / deprecated | Pruning discipline. |
| **Memory volume per type** | Lines per memory class (semantic / episodic / etc.) | Memory bloat per `memory-management`. |
| **Memory stale rate** | Memory entries unrefreshed beyond SLO | Reconciliation discipline. |
| **Reference count per skill** | References attached to each skill | Knowledge growth in references not skills. |
| **Pattern catalog size** | Pattern count and adoption | Pattern reuse discipline. |

## The factory eval harness

Implementation:

- **Telemetry from agents** — every skill invocation, agent action, gate event logged with structured metadata.
- **Periodic batch eval** — scripts that compute the catalog metrics from the telemetry.
- **Sampling** — for quality metrics (decision quality, output acceptance), sample N items and have principal review.

Storage:

- Telemetry in append-only event log (file-based or DB depending on scale).
- Metrics in `.project/operational/factory-metrics/{quarter}.md`.
- Sampled review items in `.project/operational/factory-samples/`.

## The quarterly factory report

Template:

```markdown
# Factory Report — 2026 Q4

## Library counts
- SKILLs: 71 (target 70-90) — healthy.
- Agents: 15.
- Workflows: 5.
- References: 14.

## Top-5 skills by invocation
1. requirements-interrogation — 142 invocations.
2. code-review — 98.
3. observability — 87.
4. resilience-patterns — 64.
5. testing-strategy — 59.

## Bottom-5 skills by invocation (candidates for review)
- ml-monitoring-drift — 3 invocations (expected; gated on has_ml).
- chaos-engineering — 4 (low for projects with availability >= 99.95; investigate).
- ...

## Agent performance
- delivery-lead: 24 workflows orchestrated; avg phase-cycle 4.2 days (Q3: 4.7); ↗ improved.
- ...

## Workflow completion
- greenfield-api-service: 8 runs; 6 reached production_go_live; 2 paused at requirements_freeze.

## Gate clearance
- production_go_live: avg time-to-clear 1.8 days; evidence-complete first-submission 78%.
- responsible_ai_review: 3 invocations; all cleared first-submission (small sample).

## Findings
- chaos-engineering under-invoked → investigate delivery-planner activation rule.
- Two skills haven't been invoked this quarter: experimental → deprecation candidates.
- Memory volume grew 18% — pattern of episodic accumulation; trigger memory-management reconciliation.

## Recommendations (handed to System Steward)
- Promote pattern X to skill (used in 4 projects; warrants own SKILL.md).
- Deprecate skill Y (zero invocations across 3 quarters).
- Update trigger phrases on skill Z (recall problem identified).
```

## The skill efficacy report

Per skill, periodic deep-dive:

```markdown
# Skill Efficacy — `code-review`

## Period: 2026 Q4

## Invocation
- 98 invocations; 87 in active workflows + 11 ad-hoc.

## Trigger precision
- Sampled 20; 19 correct invocations. Precision 0.95.

## Trigger recall
- Cross-referenced 20 PRs without code-review skill — 2 should have invoked but didn't. Recall ~0.91.

## Output acceptance
- 92% of code-review outputs accepted without major rework. Healthy.

## Downstream rework
- 4 PRs where code-review missed an issue caught by security-review. Boundary leak — investigate.

## Recommendations
- Add explicit trigger phrase for PR labels matching `security:` prefix.
- Strengthen the boundary table in code-review's SKILL.md (what does and doesn't fire security-review).
```

System Steward consumes these to propose changes.

## Knowledge growth health

Per the Knowledge Growth Policy (blueprint Section 14): new knowledge grows in references / patterns / examples / evaluations — NOT skills.

Metric:

- Skill additions this quarter: 0 expected at steady state; reviewed if > 2.
- Reference additions: typical 3-8 per quarter at steady state.
- Pattern additions: typical 1-3.
- Example additions: typical 2-6.

Skill count creep (skills added that should have been references) is the leading indicator of library decay.

## Outputs

| Output | Location |
|---|---|
| Factory metric catalog | this SKILL + `references/factory-metrics-catalog.md` |
| Eval harness scripts | `factory-eval/` |
| Quarterly factory report | `.project/operational/factory-metrics/{quarter}.md` |
| Skill efficacy reports | `.project/operational/factory-metrics/skills/{skill}/{quarter}.md` |
| Agent performance reports | `.project/operational/factory-metrics/agents/{agent}/{quarter}.md` |
| Knowledge-growth health | included in quarterly report |

## Mode handling

Same in greenfield and brownfield — the factory eval applies regardless of project mode. The library installation date is the start of telemetry.

## Critical disciplines

**Telemetry from day one.** Without telemetry there's no eval; without eval there's no improvement.

**Sample-based quality eval.** Some metrics (decision quality, output acceptance) require human review — sample N items, don't try to instrument everything.

**Evidence-driven proposals only.** System Steward proposals reference factory-eval evidence. "It feels like X is slow" is not evidence.

**Quarterly cadence default.** More frequent reviews tend toward over-tweaking; less frequent let problems compound. Quarterly is the default sweet spot.

**Don't optimize the metric.** Goodhart's law applies — once a metric becomes a target it stops being a good measure. Watch for measure-gaming.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We feel like the library is healthy." | Feel isn't measurement. Metrics are the calibration. |
| "Telemetry is over-engineering." | Without telemetry, the System Steward operates on hunches. Evidence-based proposals require data. |
| "Quarterly is too often." | Annual misses 4 quarters of compounding issues. Quarterly is the sweet spot. |
| "Single skill metric is enough." | One metric ignores precision-vs-recall, output-vs-cost, etc. Five families exist for reasons. |
| "Goodhart's law is theoretical." | It isn't. Once a metric is a target, the metric games itself. Watch the indirect signals. |
| "Improvements are obvious from inspection." | Hunches are wrong half the time. Evidence-based proposals avoid wasted churn. |

## Verification

You are done when:

- [ ] Telemetry collection in place across skills/agents/workflows/governance.
- [ ] All five metric families computed: skill / agent / workflow / governance / library health.
- [ ] Quarterly report at `.project/operational/factory-metrics/<quarter>.md`.
- [ ] Per-skill efficacy reports for the top-10 most-invoked + bottom-10 least-invoked.
- [ ] Knowledge-growth metric tracked (skills vs references vs patterns vs examples).
- [ ] Goodhart-watch: indirect signals reviewed for measure-gaming.
- [ ] Recommendations grouped into `steward-promotion` proposals.
- [ ] Items NOT proposed explicitly listed (discipline against over-reacting).

Evidence to check:
- A proposed change cites specific metric movement.
- Past quarterly recommendations have measurable follow-through.

## Anti-patterns

- No telemetry; "improvements" proposed from feel.
- Single metric used to judge everything ("invocation count").
- Quality metrics computed without sampling (LLM-judge of skill outputs is tempting but biased the same way as in `evaluation-engineering`).
- Quarterly report becomes performative; recommendations don't drive action.
- Over-tweaking — change something every week based on noise.
- Measuring everything; analyzing nothing.
- No baseline — "is this good?" can't be answered without prior data.
- Goodhart on a single skill metric (boosting invocation counts to look healthy).
- Factory-eval skipped in busy quarters; library decays unobserved.
- Skill changes without before-after evidence (System Steward can't operate without this).
