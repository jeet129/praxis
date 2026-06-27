# GitHub Copilot — Praxis Integration

This repository ships the Praxis — a structured library of skills, agents, and workflows for end-to-end software delivery.

## Discovering the right skill
For any non-trivial task, consult `skills/using-praxis/SKILL.md` — the front-door SKILL with the full intent → workflow → agent → skill decision tree.

## Activation flags
Read `.project/semantic/project-charter.md` to know the project's mode (G/B), data/ML/agentic-AI flags, compliance regimes, scale targets, and stack preferences. Skills activate per these flags.

## Where things live
- Skills: `skills/<name>/SKILL.md` (80 SKILLs)
- Agent personas: `agents/*.md` (16 role agents)
- Workflows: `workflows/*.yaml`
- Governance gates: `governance/governance.yaml` (7 active + 4 conditional)
- Cross-cutting references: `references/`
- Project memory: `.project/` (six-type taxonomy)

## Key disciplines (always apply)
1. **Source-grounded coding** — `skills/source-grounded-coding/SKILL.md`. Verify framework decisions against official docs; cite sources; flag unverified.
2. **Doubt-driven decisions** — `skills/doubt-driven-decisions/SKILL.md`. CLAIM → EXTRACT → DOUBT → RECONCILE → STOP for non-trivial decisions.
3. **Engineering standards** — `skills/engineering-standards/SKILL.md` + `references/git-workflow-checklist.md` + `references/code-simplification-heuristics.md`.

## What NOT to do
- Don't write code citing no source for non-trivial framework decisions (hallucination risk).
- Don't skip the discovery phase on greenfield projects.
- Don't merge changes that haven't gone through the appropriate review SKILL.
