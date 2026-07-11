---
description: "Brownfield kickoff: comprehension + architecture reconciliation + debt audit + impact analysis."
---

Brownfield engagement first-week sequence. Run in order:

Day 0 — Setup. Initialize the `.project/` memory tree if absent (semantic / decision / episodic / operational / procedural / working / telemetry). Seed the per-project governance overrides: copy the plugin's `governance/model-routing.yaml` and `governance/autonomy.yaml` to `.project/governance/` if not present. Then ask me ONE concise question set: keep default adaptive routing and autonomy, or tune for this engagement — `force_tier`, `cost_weights`, drive `stop_after` + `run_budget`. Apply answers to the PROJECT copies only. (Brownfield default worth suggesting: `stop_after: slice` until characterization-test coverage is trusted.)

Day 1 — `codebase-comprehension` SKILL.
Activate Tech Writer (narrate) + Lead Developer (structure). Produce `.repo-intel/` outputs:
- System map (Level 1 + 2 of C4 derived from actual deployed system, not aspirational diagrams).
- Data flows (sync + async; cross-boundary).
- Build + deploy story (what runs where; how it gets there).
- Runtime model (what processes / containers / functions live).
- Hot paths (highest-traffic surfaces).
Save to `.project/semantic/codebase-overview.md` plus per-service notes.

Day 2 — `architecture-documentation` reconciliation.
Compare deployed reality vs any existing C4 diagrams + ADRs. Surface discrepancies. Per item, decide:
- Fix the docs (default).
- OR open a `tech-debt-management` entry if docs reflect intended target.
Update `.project/working/architecture/overview.md`.

Day 3 — `tech-debt-management` brownfield audit.
Interview me about what feels hard. Run static analysis (complexity / duplication / coverage). Produce triaged register at `.project/operational/debt-register.md`. Limit to 20-50 items. Classify each per Fowler's quadrants (prudent/reckless x intentional/inadvertent). Prioritize by payoff x risk x cost.

Day 4 — `impact-analysis` for the proposed enhancement.
All four lenses (Static + Runtime + Contract + Historical). Surface the blast radius. Recommend: proceed / proceed-with-conditions / scope-blocker. Save to `.project/operational/impact-analyses/`.

Day 5+ — Phase A starts via `/discover`.

Common rationalizations to ignore:
- "I'll skim the code; I don't need comprehension." -> brownfield without comprehension ships incidents. Always run.
- "200-item register is fine." -> no. Triage to 20-50. The register is a queue, not a graveyard.
- "Static analysis is the same as impact-analysis." -> no. Four lenses. The IDE doesn't see contracts or history.
