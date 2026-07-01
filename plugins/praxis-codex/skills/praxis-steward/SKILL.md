---
name: praxis-steward
description: Use when running Praxis library stewardship in Codex; performs factory evaluation, drift review, and steward_promotion proposal preparation.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [factory-evaluation, skill-registry, memory-management, adr-decision-records]
triggers: [praxis steward, library review, quarterly review, steward promotion]
outputs: [factory_evaluation_summary, steward_report, promotion_pack]
consumers: [system-steward]
references: [../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Steward

Run library stewardship.

1. Read `agents/system-steward.md`, `skills/factory-evaluation/SKILL.md`, and governance.
2. Review factory metrics, skill usage, workflow drift, command drift, and missing references.
3. Produce a steward report with evidence, proposed changes, expected impact, and rollback plan.
4. Route changes through the `steward_promotion` gate.

Do not edit library assets directly unless the promotion gate is approved.
