# library-backlog/

Extension point for **proposed but not-yet-promoted** library content: candidate skills, candidate patterns, candidate references. Items here are documented possibilities, not active library content.

## What goes here

- `proposed-skills/` — SKILL proposals being evaluated against the four-condition Skill Creation Policy (distinct trigger / cross-project / substantive / clear consumers).
- `proposed-patterns/` — patterns that have appeared in 1-2 projects; tracking whether they recur into 3+ (the promotion threshold).
- `proposed-references/` — reference docs being drafted.

## Currently empty

This directory is intentionally a starting point. The System Steward (per `skills/system-steward.md`) populates it as quarterly factory-evaluation surfaces candidate additions.

## Suggested layout

```
library-backlog/
├── proposed-skills/
│   └── <skill-name>/
│       ├── proposal.md            why this skill; four-condition assessment
│       └── draft-SKILL.md         work-in-progress content
├── proposed-patterns/
│   └── <pattern-name>/
│       ├── observed-in.md         which projects used this pattern
│       └── draft-pattern.md       work-in-progress write-up
└── proposed-references/
    └── <reference-name>.md
```

## Workflow

Promotion from backlog → active library routes through the `steward_promotion` governance gate (per `governance/governance.yaml`). Rejected proposals stay as ADRs explaining why; this prevents the same idea from being repeatedly re-proposed.
