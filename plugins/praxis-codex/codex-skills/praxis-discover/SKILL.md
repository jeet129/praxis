---
name: praxis-discover
description: Use when running Praxis discovery and requirements in Codex; drives Phase A through the requirements_freeze gate.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [product-discovery, requirements-elicitation, requirements-interrogation, nfr-definition]
triggers: [praxis discover, discovery, requirements, phase a]
outputs: [opportunity_brief, requirements_brief, user_stories, nfr_register, assumptions_register, requirements_freeze_pack]
consumers: [praxis-architect]
references: [../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Discover

Run Phase A: discovery, requirements, and NFR definition.

1. Read `.project/semantic/project-charter.md`.
2. Use `product-discovery`, `requirements-elicitation`, `requirements-interrogation`, and `nfr-definition`.
3. Produce or update `.project/semantic/opportunity.md`, `.project/semantic/requirements.md`, `.project/semantic/nfr-register.md`, `.project/working/assumptions.md`, and `.project/working/open-questions.md`.
4. Assemble the `requirements_freeze` evidence pack from `governance/governance.yaml`.
5. Stop for user approval before Phase B.

Do not skip open questions that block architecture.
