---
name: praxis-refine-idea
description: Use when refining an ideation artifact (concept note, PRD draft, proposal, roadmap sketch) in Codex through the bounded creator/reviewer/enhancer/arbiter loop before it enters formal discovery.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [agentic-harness-orchestration, requirements-interrogation, doubt-driven-decisions]
triggers: [praxis refine idea, refine idea, refine this concept, iterate on this proposal, ideation refinement]
outputs: [refined_artifact, refinement_log, convergence_summary, role_binding_record]
consumers: [praxis-discover, praxis-start]
references: [../../workflows/ideation-refinement-loop.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Refine Idea

Run the `ideation-refinement-loop` workflow against an ideation artifact.

1. Resolve the artifact or topic from the user prompt; confirm harness bindings for creator, reviewer, enhancer, and arbiter roles (defaults per the workflow's `runtime_bindings`).
2. Initialize the run: record role bindings and create the refinement log so the run is reproducible.
3. Creator pass produces the draft (or ingests the supplied artifact) with assumptions and open questions.
4. Loop, bounded by `max_passes`: reviewer produces severity-tagged findings against the review lenses; enhancer revises with a change log and rejected-feedback rationale; arbiter scores convergence against the pre-enhancer version.
5. Exit the loop when no findings at or above major remain and the next pass's expected value is cosmetic/low — or when `max_passes` is exhausted.
6. Present the convergence summary and remaining risks to the user; the `ideation_refinement_approval` gate requires their explicit approval or a request for another pass.
7. Record the final artifact path and refinement log under `.project/working/`.

Do not silently accept the enhancer's revision — every pass is scored by the arbiter before it becomes the current artifact.
