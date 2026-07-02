---
name: praxis-start
description: Use when starting or bootstrapping a Praxis project in Codex; creates the charter, memory tree, routing context, and next-step recommendation.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [delivery-planner, architecture-documentation, project-memory]
triggers: [praxis start, bootstrap project, start project, initialize praxis]
outputs: [project_charter, memory_tree, active_gate_summary, next_command]
consumers: [praxis-discover, praxis-audit, praxis-slice]
references: [../../workflows/greenfield-api-service.yaml, ../../workflows/brownfield-enhancement.yaml, ../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Start

Run the Praxis bootstrap flow for Codex.

1. Locate the installed plugin root by walking up from this skill until `workflows/` and `governance/` are present.
2. Read `skills/delivery-planner/SKILL.md`, `skills/project-memory/SKILL.md`, and `governance/governance.yaml`.
3. Create or update `.project/semantic/project-charter.md` with project mode, data/ML/AI flags, compliance regimes, scale, availability, tenancy, stack, and cloud.
4. Create the `.project/` memory tree if missing.
5. Summarize active governance gates from `governance/governance.yaml`.
6. Recommend `$praxis-discover` for greenfield or `$praxis-audit` for brownfield.

Do not modify Claude Code plugin files.
