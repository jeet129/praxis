---
name: praxis-architect
description: Use when running Praxis architecture in Codex; drives Phase B design, ADRs, challenger review, and architecture_sign_off evidence.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [architecture-pattern-selection, project-phasing, adr-decision-records, threat-modeling]
triggers: [praxis architect, architecture, phase b, design]
outputs: [architecture_decision, c4_diagrams, architecture_adrs, challenge_report, phased_roadmap, architecture_sign_off_pack]
consumers: [praxis-slice]
references: [../../workflows/greenfield-api-service.yaml, ../../workflows/greenfield-saas.yaml, ../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Architect

Run Phase B: architecture and sign-off preparation.

1. Verify `requirements_freeze` has cleared or ask the user to approve the evidence pack.
2. Select the applicable workflow from `workflows/` based on the charter.
3. Create architecture decisions, ADRs, C4 diagrams, threat model, implementation constraints, and phased roadmap.
4. Spawn or use the `architecture-challenger` subagent if installed; otherwise run the Challenger role from `agents/architecture-challenger.md`.
5. Resolve Challenger findings by revising the design or recording override rationale.
6. Assemble the `architecture_sign_off` evidence pack from governance.
7. Stop for user approval before implementation.

Do not begin implementation slices before architecture sign-off.
