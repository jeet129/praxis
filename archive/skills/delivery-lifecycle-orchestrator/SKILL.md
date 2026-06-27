---
name: delivery-lifecycle-orchestrator
description: TOMBSTONE — This SKILL was consolidated into `using-praxis` in the Polish-1 pass. Its content (workflow execution model, step types, Decision Node evaluation, gate enforcement runtime, workflow lifecycle state machine) lives there under "LAYER 2 — Orchestration Runtime". Do not load this SKILL; do not depend on it; do not reference it. It exists only as a tombstone because the session that performed the consolidation could not delete files.
---

# Delivery Lifecycle Orchestrator — REMOVED


<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: removed
dependencies: []
triggers: []
outputs: []
consumers: []
references: []
```
<!-- praxis:metadata:end -->

This SKILL has been **consolidated into [`using-praxis`](../using-praxis/SKILL.md)** as part of the Polish-1 pass.

## Why it was removed

The boundary between this SKILL and `using-praxis` was fuzzy:

- `using-praxis` covered the front-door routing (intent → workflow → agent → skill).
- This SKILL covered the runtime that *walks* that workflow (step types, Decision Nodes, gates, failure paths).

In practice they are two layers of the same job. The merged SKILL covers both under explicit headings:

- **LAYER 1 — ROUTING** (the front-door content).
- **LAYER 2 — ORCHESTRATION RUNTIME** (this SKILL's content: workflow file shape, step types, Decision Node evaluation, agent routing model, gate enforcement, parallelism, failure paths, workflow lifecycle state machine).

## What to do

- **If you were going to load this SKILL** → load [`using-praxis`](../using-praxis/SKILL.md) instead.
- **If you were going to depend on this SKILL** → depend on `using-praxis`.
- **If you were going to reference workflow execution semantics** → see Layer 2 of `using-praxis`.

## Tombstone discipline

Per `skill-registry`, SKILLs with `state: removed`:
- Are NOT counted in the active library skill count.
- Are skipped by `install.sh` during install (won't land in user installs).
- Are skipped by `scripts/validate-skills.sh` totals (don't count toward 70-90 health band).
- Their names cannot be reused for at least 12 months.

## Cleanup

When you `cp -R` the library to your own writeable directory, you can safely:

```bash
rm -rf skills/delivery-lifecycle-orchestrator/
```

This tombstone exists only because the session that performed the consolidation hit a permission wall and could not delete the directory. The semantic outcome is identical: this SKILL is gone; its content moved.
