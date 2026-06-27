# examples/

Extension point for **worked examples** demonstrating how SKILLs and workflows produce real artifacts on real projects.

## What goes here

- Sanitized excerpts from real projects (charter, NFR register, ADRs, threat model, debt register, fairness audit, etc.).
- End-to-end walkthroughs showing what each phase's outputs look like.
- "Good vs bad" pairs — a well-formed artifact next to a common-mistake version.

## Currently empty

This directory is intentionally a starting point. The first compelling examples emerge from real project use of the library. The System Steward (per quarterly cadence) is the right place to propose adding examples that recur across projects.

## Suggested layout

```
examples/
├── greenfield-api-service/
│   ├── charter.md                 sample project charter
│   ├── nfr-register.md            sample NFR register
│   ├── adr-001-stack-choice.md    sample ADR
│   └── slice-walkthrough.md       one slice end-to-end
├── brownfield-enhancement/
│   └── ...
└── responsible-ai/
    ├── fairness-audit-sample.md   sample fairness audit
    └── datasheet-sample.md        sample datasheet
```

Per the Knowledge Growth Policy in `README.md`, examples are one of the preferred ways the library grows — they accumulate without inflating the SKILL count.
