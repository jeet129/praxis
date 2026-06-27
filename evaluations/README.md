# evaluations/

Extension point for **evaluation harnesses, golden datasets, and benchmark suites** that the library uses to measure itself and the products it helps build.

## What goes here

- **Library evals**: golden datasets that measure SKILL invocation precision/recall, agent decision quality, workflow completion rates. Consumed by `factory-evaluation` (per `skills/factory-evaluation/`).
- **Product evals** (when projects are running): the per-project eval suites for ML/agentic-AI features. Consumed by `evaluation-engineering`.
- **Skill change verification**: A/B harnesses that the System Steward runs when proposing skill changes (per `skills/system-steward.md` agent's rigorous-mode).

## Currently empty

This directory is intentionally a starting point. Populate when:

- You have a real project using the library AND
- You've decided to wire telemetry (per `INSTALLATION.md §7`) for `factory-evaluation` to consume.

## Suggested layout

```
evaluations/
├── library/
│   ├── skill-trigger-precision.jsonl   golden: query → expected SKILL
│   ├── agent-decision-quality.jsonl    golden: scenario → expected verdict
│   └── workflow-completion-baseline.md baseline rates per workflow
└── per-project/
    └── <project-name>/                 product evals per project
        └── eval-suite.yaml
```

Until populated, the `factory-evaluation` SKILL operates from manual observations rather than scored golden datasets — see INSTALLATION.md §7.
