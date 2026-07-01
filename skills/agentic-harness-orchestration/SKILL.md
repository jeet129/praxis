---
name: agentic-harness-orchestration
description: "Design and run swappable agentic-harness workflows where roles such as creator, reviewer, enhancer, and arbiter are bound at runtime to Claude, Codex, Gemini, Cursor, OpenCode, or custom harnesses. Use for iterative artifact refinement, cross-harness critique loops, convergence checks, and harness adapter contracts."
---

# Agentic Harness Orchestration

<!-- praxis:metadata:begin -->
```yaml
capability: agentic-ai
domain: cross-cutting
state: active
dependencies:
  - agentic-architecture
  - evaluation-engineering
  - llm-safety
triggers:
  - "configuring creator and reviewer harnesses"
  - "swapping Claude, Codex, Gemini, Cursor, OpenCode, or custom harnesses"
  - "running iterative ideation refinement"
  - "checking convergence across agent feedback loops"
outputs:
  - harness role binding record
  - structured review packet
  - revision packet
  - convergence verdict
  - user approval summary
consumers:
  - product-manager
  - solution-architect
  - tech-writer
  - delivery-lead
references: []
```
<!-- praxis:metadata:end -->

This skill keeps an agentic workflow portable across harnesses. Treat harnesses
as adapters and roles as the stable contract. Claude, Codex, Gemini, Cursor,
OpenCode, and future tools can be bound to roles without rewriting the workflow.

## Core Principle

Do not encode product names into the reasoning protocol. Encode roles:

| Role | Responsibility |
|---|---|
| creator | produce or expand the artifact |
| reviewer | critique the artifact and produce severity-tagged findings |
| enhancer | evaluate findings, apply improvements, and explain rejected feedback |
| arbiter | decide convergence and prepare the user approval summary |

The same harness can serve multiple roles, but the run log must record that fact
and each role must use a separate prompt shape.

## Harness Contract

Every bound harness must be able to:

- accept a structured prompt with role, artifact, constraints, and expected output;
- return structured markdown or JSON;
- preserve artifact version labels;
- distinguish findings from rewrites;
- identify assumptions, open questions, and confidence;
- emit a verdict without claiming perfection.

If a harness cannot satisfy the contract, pause the workflow and ask the user for
a replacement harness or permission to degrade to manual copy/paste handoff.

## Runtime Binding Record

Record this at the start of each run:

```yaml
run_id: <stable id>
source_artifact_or_topic: <path or topic>
creator_harness: <name>
reviewer_harness: <name>
enhancer_harness: <name>
arbiter_harness: <name>
quality_bar: standard|high|rigorous
max_passes: <integer>
started_at: YYYY-MM-DDTHH:MM:SS
```

## Review Packet

Reviewer output must use this shape:

```markdown
# Review Packet

**Verdict:** pass | pass_with_fixes | needs_revision | blocked
**Confidence:** low | medium | high

## Findings

| id | severity | surface | finding | rationale | suggested fix |
|---|---|---|---|---|---|

## Missing Questions

## Assumptions To Validate

## Nice-To-Have Improvements
```

Severity levels:

| Severity | Meaning |
|---|---|
| blocker | artifact cannot be approved until resolved |
| major | material weakness; should be resolved before approval |
| minor | useful improvement; approval can proceed with rationale |
| nit | wording or polish only |

## Revision Packet

Enhancer output must use this shape:

```markdown
# Revision Packet

## Revised Artifact

<full revised artifact or exact patch>

## Change Log

| finding_id | disposition | change | rationale |
|---|---|---|---|

## Rejected Feedback

| finding_id | reason |
|---|---|

## New Assumptions Or Risks
```

## Convergence Check

The arbiter should stop the loop when:

- no blocker or major findings remain unresolved;
- the reviewer is repeating prior feedback without new evidence;
- the next pass is expected to produce only cosmetic or low-value changes;
- the artifact is decision-ready for the user's stated purpose.

Do not use "100% refined" as a literal standard. Use decision language:

- `ready_for_approval`
- `needs_another_pass`
- `blocked_on_user_decision`

## User Approval Summary

End every run by presenting:

- final artifact path;
- harness role bindings;
- number of passes completed;
- major changes made;
- unresolved findings and risks;
- accepted and rejected reviewer feedback;
- recommendation to approve or run another pass.

The user owns the final approval decision.
