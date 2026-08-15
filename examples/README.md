# examples/

Extension point for **worked examples** demonstrating how SKILLs and workflows produce real artifacts on real projects.

## What goes here

- Sanitized excerpts from real projects (charter, NFR register, ADRs, threat model, debt register, fairness audit, etc.).
- End-to-end walkthroughs showing what each phase's outputs look like.
- "Good vs bad" pairs — a well-formed artifact next to a common-mistake version.

## Where the worked examples live today

This directory will eventually hold **sanitized real-project artifacts**, but those
only emerge from real project use — so for now it is an intentional starting point.
Until it fills in, the worked *usage* examples already exist in the docs:

- [`docs/scenarios.md`](../docs/scenarios.md) — 15 common situations, each with its entry point, what runs, where you approve, and what lands where.
- [`docs/drive-first-playbook.md`](../docs/drive-first-playbook.md) — one product's life through every workflow end to end, including the ongoing-sprint steady state.
- [`PLAYBOOK.md`](../PLAYBOOK.md) — greenfield + brownfield walkthroughs, the prompt library, and cadences.
- [`docs/lifecycle.md`](../docs/lifecycle.md) — the six-phase lifecycle, gate by gate.

What still belongs **here** — and does not exist yet — is concrete *artifact* samples
(a real charter, NFR register, ADR, threat model, slice walkthrough) captured from an
actual engagement. The System Steward (per quarterly cadence) is the right place to
propose adding examples that recur across projects.

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
