# Proposal: requirements-intake

**Status:** Promoted directly to `state: experimental` on 2026-06-28 by principal (Jitesh). Skipping the normal backlog → review path because it fills a known operational gap that surfaces in every brownfield engagement. Will be reviewed by System Steward in the next quarterly cycle.

## The gap it fills

Praxis ships `/discover` (one-time discovery), `requirements-elicitation` (elaborate one validated ask into testable specs), and `product-discovery` (find the opportunity). But none of these address **steady-state intake** — the continuous arrival of new requirements after the initial discovery + architecture pass.

In every brownfield engagement, the team faces:
- New tickets, asks, change requests arriving daily
- A choice each time between "treat as a new project" (full ceremony, burns out) and "just do it" (skips impact-analysis, detonates load-bearing modules)
- No documented discipline for triage → sequence → group → route

Without a SKILL for this, teams default to one of two failure modes (FIFO churn or impulse coding). Both are common; both are documented as anti-patterns in this SKILL's anti-rationalization table.

## Four-condition Skill Creation Policy check

| Condition | Met? | Evidence |
|---|---|---|
| Repeated need across ≥3 projects | ✓ | Every brownfield engagement past month 3 needs it |
| No existing skill covers it | ✓ | `requirements-elicitation` handles one item in scope; `product-discovery` handles initial opportunity; neither handles intake of new items in an existing project |
| Discipline is non-obvious | ✓ | The triage/group/sequence pattern is rarely intuited; teams default to FIFO |
| Failure mode is high-stakes | ✓ | Both failure modes (burnout, blast-radius surprise) cost weeks of project time |

## Promotion path

- 2026-06-28: created at `state: experimental`, added to manifest
- After it runs on 2–3 real projects: System Steward reviews + collects telemetry
- If telemetry supports → promote to `state: active` via `steward_promotion` gate
- If unused or merged into another SKILL → tombstone or merge

## Related SKILLs and complements

- **`product-discovery`** — produces the original opportunity; doesn't recur
- **`requirements-elicitation`** — elaborates one in-scope item into testable specs (downstream of this skill)
- **`impact-analysis`** — referenced as mandatory per item; this skill makes the reference explicit
- **`codebase-comprehension`** — referenced for freshness check; partial re-comp pattern is named here
- **`project-memory`** — the `.project/working/inbox*.md` artifacts persist in working memory

## Open questions for next steward review

- Should sequencing use a different formula than `urgency × (6 - risk)`? Real telemetry will inform this.
- Is the 30/90 day `.repo-intel/` freshness threshold right?
- Should the triage step have an explicit "reject early" cutoff for asks that don't align with the project?
- Does the weekly cadence work, or does a per-arrival cadence reduce backlog rot more reliably?
