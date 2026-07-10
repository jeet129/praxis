# Worked examples

Worked templates supporting `factory-evaluation`. Load this file when you need the full artifact behind a SKILL.md pointer.

## Quarterly factory report — full template

```markdown
# Factory Report — 2026 Q4

## Library counts
- SKILLs: 84 (target 70-90) — healthy.
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

## Skill efficacy report — full template

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
