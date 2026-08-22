# patterns/

Extension point for **reusable solution shapes** the library doesn't promote to full SKILLs but does treat as named patterns referenceable by SKILLs and ADRs.

## Patterns vs SKILLs

| Patterns | SKILLs |
|---|---|
| Reusable solution shapes | Active workflows the agent follows |
| Referenced when relevant | Triggered by intent/context |
| No frontmatter required | Eight-field frontmatter required |
| Don't count toward library health band | Count toward the 70-90 SKILL target |

## What goes here

- **Strangler fig migration pattern** (referenced by `legacy-modernization`)
- **Anti-corruption layer pattern** (referenced by `legacy-modernization`, `architecture-pattern-selection`)
- **Outbox pattern** (referenced by `distributed-systems-patterns`)
- **Saga pattern** (referenced by `distributed-systems-patterns`)
- **Circuit breaker pattern** (referenced by `resilience-patterns`)
- **Bulkhead pattern** (referenced by `resilience-patterns`)
- **Idempotency key pattern** (referenced by `api-design`, `distributed-systems-patterns`)
- **Hexagonal architecture / Ports & Adapters** (referenced by `engineering-standards`)

## Currently empty

This directory is intentionally a starting point. Patterns currently live as inline content within the SKILLs that reference them; extracting them here is one of the lower-risk growth paths per the Knowledge Growth Policy.

The System Steward (per quarterly cadence) is the right place to propose extracting an inline pattern into its own file when it recurs across multiple SKILLs.

## Suggested format

Each pattern is a single Markdown file with:

```markdown
# Pattern: Strangler Fig

## When to apply
...

## Structure
...

## Trade-offs
...

## Referenced by
- skills/legacy-modernization/SKILL.md
- skills/architecture-pattern-selection/SKILL.md
```

Per the Knowledge Growth Policy in `README.md`, patterns are one of the preferred growth paths — they accumulate without inflating the SKILL count.
