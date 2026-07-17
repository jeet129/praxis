---
name: skill-registry
description: "The library's orchestration backbone. Aggregates every SKILL.md's frontmatter metadata (dependencies, triggers, outputs, consumers, capability, domain, state) into a single `skill-registry.yaml` that the orchestrator consults to resolve which skills to load for a given task, what their dependencies are, and which agents consume their outputs. Validation runs at promotion — broken dependencies, orphaned consumers, duplicate outputs, cycle detection, and state-transition rules all fail the build. Use whenever a new skill is added or modified, when the orchestrator needs to plan a workflow run, or when the library is being audited for overlap and health."
---

# Skill Registry

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies: []
triggers:
 - "adding a new skill to the library"
 - "modifying SKILL.md frontmatter"
 - "promoting a skill from experimental to active"
 - "deprecating or removing a skill"
 - "orchestrator resolving skills for a task"
 - "library audit or health check"
 - "Curator review of skill overlap"
outputs:
 - skill-registry.yaml
 - validation report
 - dependency-graph visualization (DOT or Mermaid)
consumers:
 - using-praxis
 - delivery-planner
 - system-steward
 - library-curator (human)
 - factory-evaluation (reads skill list for usage metrics)
references: []
```
<!-- praxis:metadata:end -->

At ~91 skills (with the library targeting 70–90 — see blueprint Section 7), naïve orchestration becomes fragile. The skill-registry is the structured representation of *what the library contains*, *what depends on what*, *who consumes what*, and *what state each skill is in*. The orchestrator never scans `skills/*/SKILL.md` directly at runtime; it consults the registry.

## When this skill fires

- A new skill is being authored — its frontmatter is validated against the schema before promotion.
- An existing skill is modified — the registry is regenerated; dependents are re-validated.
- The orchestrator plans a workflow run — it queries the registry to resolve dependencies and load order.
- The `delivery-planner` instantiates a workflow for a project — it filters the registry by capability and domain to find applicable skills.
- The Curator runs a monthly audit — the registry surfaces overlap (multiple skills with the same outputs), orphaned skills (no consumers), and lifecycle candidates (low usage + age = deprecation candidates).
- `factory-evaluation` reports per-skill usage — it joins the registry to attribute usage to capabilities and domains.

## The registry schema

```yaml
# skill-registry.yaml (generated)
version: 1
generated_at: 2026-06-15T10:30:00Z
library_target: 70-90
current_count: 91
capabilities:
 foundation:
 skills: [engineering-standards, project-memory, memory-management, skill-registry, adr-decision-records]
 domain: cross-cutting
 lifecycle:
 skills: [using-praxis, delivery-planner]
 domain: cross-cutting
 discovery:
 skills: [product-discovery, requirements-elicitation, requirements-interrogation, nfr-definition]
 domain: cross-cutting
 ...
skills:
 - name: engineering-standards
 capability: foundation
 domain: cross-cutting
 state: active
 dependencies: []
 triggers: [...]
 outputs: [standards-reference, violation-findings]
 consumers:
 agents: [backend-developer, frontend-developer, ...]
 skills: [code-review, all-stack-packs]
 references: [java-spring.md, node-ts.md, python.md]
 version: 1.0.0
 last_modified: 2026-06-15
 - name: project-memory
 ...
```

The registry is *generated*, not hand-edited. The source of truth is the SKILL.md frontmatter in each skill directory; the registry is a built artifact.

## The frontmatter contract

Every SKILL.md must declare, in YAML frontmatter, these eight fields beyond `name` and `description`:

| Field | Type | Purpose |
|---|---|---|
| `capability` | string | The larger unit this skill participates in (e.g., `discovery`, `architecture`, `data-engineering`). Multiple skills can share a capability. |
| `domain` | enum | One of: `frontend`, `backend`, `data`, `ml`, `agentic-ai`, `infra`, `cross-cutting`. |
| `state` | enum | `experimental` / `active` / `deprecated` / `merged` / `removed` (lifecycle, blueprint Section 7). |
| `dependencies` | list | Other skills whose outputs this skill reads, or that must be loaded before this one. |
| `triggers` | list | Structured invocation contexts (also informs the `description` for triggering). |
| `outputs` | list | Artifact types this skill produces. |
| `consumers` | object | `{agents: [...], skills: [...]}` — who reads this skill's outputs. |
| `references` | list | Variant references inside `references/` directory (e.g., `[aws.md, azure.md, gcp.md]`). |

Missing any of these is a promotion-blocking validation failure.

## Validation rules

Run at promotion (skill is being moved from `experimental` to `active`, or modified while `active`) and at library audit (Curator review).

### Structural validation

1. **All required frontmatter fields present.**
2. **`capability` must be declared** in the registry's `capabilities:` map (you can add a new capability, but it must be explicit).
3. **`domain` must be one of the seven enum values.**
4. **`state` lifecycle is monotonic** except `experimental → active → deprecated` (allowed) or `deprecated → active` (re-promotion; allowed with ADR).

### Dependency validation

5. **No broken dependencies.** Every skill named in `dependencies` must exist in the registry.
6. **No cycles.** Tarjan's strongly-connected-components run over the dependency graph; any SCC of size > 1 fails the build.
7. **Dependencies respect the layer order.** A Layer-0 skill cannot depend on a Layer-2 skill; layer hierarchy is enforced.

### Consumer validation

8. **Every `outputs` value is consumed by something.** Orphaned outputs (no consumer reads them) are warnings, not blockers — but the Curator must justify them at audit.
9. **Every `consumers.skills` entry must exist** in the registry and must actually have this skill in *its* `dependencies` (bidirectional consistency).

### Output validation

10. **No duplicate outputs across active skills.** Two skills producing the same output type without a clear separation is a duplication warning — the Curator decides merge or differentiate.

### State validation

11. **A `deprecated` skill cannot be a dependency of an `active` skill.** Migrate first, then deprecate.
12. **A `merged` or `removed` skill's name cannot be reused** for at least 12 months (avoids confusion with the prior incarnation).

Validation results go to a report consumed by the System Steward and the human Curator.

## Building the registry

The skill exposes a build command (a script in `scripts/build-registry.sh` or equivalent per the implementation). It walks `skills/*/SKILL.md`, parses frontmatter, runs all validations, and emits `skill-registry.yaml` plus a validation report. CI integration: every PR that touches `skills/` runs the build; failure blocks merge.

## The dependency-graph visualization

A side artifact useful for the Curator. The build also emits `skill-registry.dot` (Graphviz) or `skill-registry.mermaid` showing the dependency DAG, colored by capability and domain. Helps spot tight clusters, hub skills, and isolated branches.

## Mode handling (G/B)

**Greenfield.** Start with an empty `skill-registry.yaml`. As skills are added, the registry grows.

**Brownfield.** If a project is adopting the library onto an existing repo, the registry is regenerated from the library's `skills/` directory on first install. No special handling.

## What this skill does not do

- Discover skills from outside the `skills/` directory.
- Resolve runtime invocation — that's the orchestrator. This skill provides the *map*; the orchestrator does the *driving*.
- Enforce the four-condition Skill Creation Policy (blueprint Section 7). That's a Curator responsibility; the registry surfaces the data but doesn't gatekeep on policy.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Registry will regenerate later; skip frontmatter validation." | The registry IS the validation gate. Skipping it means broken dependencies surface at runtime. |
| "Two-field frontmatter is enough." | Two fields don't carry triggers, consumers, dependencies, lifecycle. The other six fields are what makes the registry useful. |
| "Duplicate outputs across SKILLs are fine; they cover different cases." | Then their outputs aren't actually duplicate — sharpen the output schemas. Real duplicates are real warning signs. |
| "Cycles in dependencies might be OK in our case." | Cycles in skill dependencies mean unresolvable load order; failed validation is a hard stop, not a soft warning. |
| "I'll skip the registry build; I know which skills I need." | The orchestrator consults the registry; bypassing means the orchestrator can't route. Your local knowledge doesn't replace the index. |
| "Deprecated skills can still be depended on; we'll migrate someday." | Deprecated → active dependency is a hard validation failure. Migrate first; then deprecate. |

## Verification

You are done when:

- [ ] `skill-registry.yaml` regenerated successfully.
- [ ] All 91 active SKILLs validated; zero failures.
- [ ] No broken dependencies (every dependency name exists).
- [ ] No cycles in the dependency graph.
- [ ] No `active` skill depends on a `deprecated` or `removed` skill.
- [ ] Bidirectional consumer consistency holds (if A is in B's `consumers.skills`, B must be in A's `dependencies`).
- [ ] Duplicate-output warnings reviewed by the Curator.
- [ ] Dependency-graph visualization emitted (DOT or Mermaid).

Evidence to check:
- The `current_count` in the registry matches the active skill count.
- Capability balance computed; no capability area exceeds the planned share.
- Orphan outputs (no consumer) are explicitly justified or removed.

## Versioning

The registry itself has a schema version (`version: 1` at the top). Schema-breaking changes carry an ADR. Every regeneration replaces the file atomically; no incremental edits.
