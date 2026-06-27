---
name: tech-debt-management
description: Identify, classify, log, prioritize, and pay down technical debt deliberately. Distinguishes prudent vs reckless debt (Fowler's quadrants), enforces a debt register, applies the "boy-scout rule" inside slices, allocates explicit debt-payoff capacity each cycle, escalates strategic debt to PM for prioritization. Brownfield-default activation (B-mode); greenfield optional but recommended once a project is six months old. Distinct from `legacy-modernization` (whole-system replacement) — this is incremental hygiene. Lead Developer owns the register; PM owns prioritization; Solution Architect adjudicates classification on disputes. Use when starting a brownfield engagement, when shipping a quick fix that creates debt, when planning a sprint / cycle, when investigating "everything is hard now", or when proposing debt-payoff as scope.
---

# Technical Debt Management


<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: active
dependencies:
  - codebase-comprehension
  - architecture-pattern-selection
  - project-phasing
  - adr-decision-records
triggers:
  - "starting a brownfield engagement (audit existing debt)"
  - "shipping a quick fix that creates known debt"
  - "planning a sprint / cycle (allocate debt-payoff capacity)"
  - "investigating sustained velocity decline"
  - "deciding whether a refactor warrants its own slice"
  - "proposing debt-payoff slices to PM"
outputs:
  - debt register (per project; living document)
  - debt classifications (prudent / reckless × intentional / inadvertent)
  - debt-payoff plan per cycle (which items, why, expected payoff)
  - debt-rate-of-change report
  - escalation pack for strategic debt (to PM)
consumers:
  - lead-developer (register owner)
  - product-manager (debt-payoff prioritization)
  - solution-architect (classification disputes; strategic debt)
  - delivery-lead (cycle planning includes debt allocation)
  - architecture-challenger (challenges debt-accumulating decisions)
references: []
```
<!-- praxis:metadata:end -->

The discipline that prevents codebases from becoming the slow nightmares teams complain about. Debt accumulates whether you track it or not — tracking is what gives you the option to pay it down deliberately. Without a register, "we'll fix it later" means "never"; with one, the register itself becomes the queue PM prioritizes against.

The principle: **debt is unavoidable; debt accumulation is. The register is the difference between a codebase that ages well and one that decays.**

## When this skill fires

- Starting a brownfield engagement — audit existing debt.
- Shipping a quick fix that creates debt — log it before merging.
- Planning a sprint / cycle — allocate debt-payoff capacity.
- Investigating sustained velocity decline — debt is often the cause.
- Deciding whether a refactor warrants its own slice.
- Proposing strategic debt-payoff to PM.

## Fowler's quadrants

Classify each debt item:

| | Intentional | Inadvertent |
|---|---|---|
| **Prudent** | "We know it's not perfect; we shipped to learn; we'll refactor." | "Now we know what we should have done." |
| **Reckless** | "We don't have time to do it right." | "What's TDD?" |

The classification determines response:

- **Prudent intentional**: payoff scheduled; documented as ADR; track until paid.
- **Prudent inadvertent**: capture the learning; payoff scheduled.
- **Reckless intentional**: STOP. This is the debt that compounds catastrophically. Address before next slice.
- **Reckless inadvertent**: training / process gap; the debt itself is paid normally, but the systemic cause must be addressed.

Lead Developer applies the classification; Solution Architect adjudicates disputes.

## The debt register

The living artifact. Stored in `.project/operational/debt-register.md` — a Markdown file under version control.

Entry template:

```markdown
## DEBT-2026-074: Synchronous external call in OrderService.create

- **Recorded**: 2026-10-22 by Lead Dev during slice 47 review.
- **Class**: Prudent / Intentional (shipped to meet beta deadline; ADR-053 documented choice).
- **Surface**: `services/order/OrderService.java`, lines 142-167.
- **Symptom**: External payment-gateway call is sync; blocks request thread; couples Order availability to payment-gateway availability.
- **Expected payoff**: Move to async pattern with outbox + event handler. Estimated 3-5 day slice. Unblocks SLO target 99.95% (currently can't meet because tied to gateway uptime).
- **Risk if unpaid**: Will surface as availability incident under gateway degradation. Probability rising as we add more payment methods.
- **Owner**: Lead Dev.
- **Status**: pending.
- **Last reviewed**: 2026-10-22.
```

Required fields:

- Identifier (project-prefixed, year-prefixed, sequential).
- Recorded date + by whom.
- Fowler classification.
- Surface (where the debt lives).
- Symptom (what's wrong).
- Expected payoff (cost + value).
- Risk if unpaid.
- Owner (who's accountable for tracking, not necessarily payment).
- Status (pending / scheduled / in-flight / paid / wont-fix).
- Last-reviewed (every quarter at minimum).

Status transitions: pending → scheduled → in-flight → paid (or wont-fix with rationale).

## The Boy Scout rule (within slices)

While in a file for slice work, fix the small things you see — tests added, names improved, dead code removed. The boy-scout payoff doesn't go in the register; it just happens. Reserve the register for items that warrant explicit attention.

Discipline: boy-scout fixes don't expand slice scope. If a fix needs more than 30 minutes or touches code outside the slice's boundary, it goes in the register instead of getting bundled.

## Cycle-level debt allocation

Each cycle allocates explicit debt-payoff capacity:

```markdown
# Cycle 23 plan

- Feature slices: 7 (planned 80% capacity).
- Debt-payoff slices: 1 (planned 20% capacity).
  - DEBT-2026-074 (sync external call — see above).
- Spike / research: 0.
```

Default allocation: **15-25% per cycle** dedicated to debt. Varies:

- New product, pre-PMF: 5-10% (correctly prioritize features).
- Mature product, sustained: 20-30%.
- Crisis mode (everything slow + buggy): 40-60% until breathing room recovered.

Allocation is a PM decision informed by debt register + velocity trend + business stage.

## Strategic debt

Some debt is too big for cycle-level payoff. Examples:

- "Wrong database technology for our access pattern."
- "Monolith needs split into 3 services."
- "Auth system pre-dates our compliance regime; full re-design needed."

These get their own ADR and project phase (per `project-phasing`). Lead Dev escalates; SA + PM + principal scope it as a project, not a slice. Often consumes a full quarter or more.

Strategic debt is rare. Most debt is cycle-payable. Escalating something to strategic when it's actually 5-10 cycle-payable items hides the real plan.

## Debt-rate-of-change

Quarterly report (consumed by `factory-evaluation` for library health context):

| Quarter | New debt logged | Debt paid | Net | Strategic items | Wont-fix items |
|---|---|---|---|---|---|
| 2026 Q1 | 22 | 14 | +8 | 0 | 2 |
| 2026 Q2 | 18 | 19 | -1 | 0 | 1 |
| 2026 Q3 | 24 | 17 | +7 | 1 | 0 |
| 2026 Q4 | 19 | 21 | -2 | 0 | 3 |

Trend interpretation:

- Sustained positive net → accumulating; allocation too low or new debt rate too high.
- Sustained negative net → either healthy payoff OR over-allocation to debt vs features.
- Spike in wont-fix → review the rationales; some "wont-fix" is just abandonment.

## What does NOT belong in the register

- Bug reports (separate tracker).
- Feature requests (separate backlog).
- "Nice to have" refactors with no concrete payoff (ideas, not debt).
- Performance optimizations not tied to NFR breach (premature optimization).
- Style preferences that aren't engineering standards.

The register is reserved for items that genuinely impede future work or carry risk.

## Brownfield audit

When activating this skill on an existing codebase:

1. **Comprehension first** — per `codebase-comprehension`. Map the system before judging it.
2. **Surface candidates** — interview owners; static analysis (complexity metrics, duplication, test coverage gaps); run a "what's hard about this codebase?" workshop.
3. **Triage** — many "debt" items are actually fine for the project's current needs. Don't log items the project doesn't need to fix.
4. **Classify** — Fowler quadrants.
5. **Prioritize** — by payoff × risk × cost.
6. **Schedule** — top 5-10 items into upcoming cycles; rest in register for visibility.

A brownfield audit's first register typically has 20-50 entries. Don't try to fix all at once; the register makes them visible.

## Outputs

| Output | Location |
|---|---|
| Debt register | `.project/operational/debt-register.md` |
| Strategic debt ADRs | `.project/decision/` |
| Cycle-level debt allocation | included in cycle plan |
| Debt-rate-of-change report | quarterly in `.project/operational/factory-metrics/{quarter}.md` |
| Escalation pack | `.project/operational/debt-escalations/` |

## Critical disciplines

**Log it before merging.** If a PR ships debt, the register entry is part of the PR. Otherwise the debt is invisible by PR merge.

**Quarterly review.** Walk the register; close paid items; re-classify if needed; identify stale wont-fixes.

**ADR for strategic debt.** "We're going to live with this for the year because X" is an ADR, not a one-liner in the register.

**Don't allow infinite wont-fix.** Wont-fix items still need periodic re-review; circumstances change.

**Pay before you grow.** Strategic debt left unpaid while features accumulate makes the eventual fix worse.

## Mode handling (G/B)

**Greenfield.** Optional in early months; recommended once project is 6 months old or has shipped to production. Register may be empty initially.

**Brownfield.** Mandatory. The register is the artifact that turns "this codebase is hard" into a queue of solvable items.

## Verification

You are done when:

- [ ] Debt register exists at `.project/operational/debt-register.md`.
- [ ] Each item has: ID, recorded date + by whom, Fowler classification, surface, symptom, payoff, risk-if-unpaid, owner, status, last-reviewed.
- [ ] Status transitions tracked: pending → scheduled → in-flight → paid (or wont-fix with rationale).
- [ ] Cycle allocation explicit (15-25% default).
- [ ] Quarterly review walked the register; resolved items closed.
- [ ] Strategic debt items have ADRs.
- [ ] Boy-scout fixes captured in slice PRs without expanding slice scope.

Evidence to check:
- Debt-rate-of-change graph trends meaningfully (paid items match new items over a quarter).
- Wont-fix items have re-review dates set; no stale wont-fixes > 12 months.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We'll fix it later — no need to log it." | "Later" doesn't happen without an entry. The entry is the difference between "we'll fix it" and "it stays broken." |
| "It's just a quick fix; not really debt." | If you noticed it's not the right shape, it's debt. The register exists so noticed-but-not-fixed has a home. |
| "We can ship reckless debt because we're moving fast." | Reckless-intentional debt is the kind that compounds catastrophically. Stop. Reclassify or address. |
| "The register is overwhelming; we'll skip the audit." | The register isn't overwhelming if you triage. 20-50 items is the ceiling; the rest weren't truly debt. |
| "100% to features this cycle." | Sustained 100% to features = built-in decay. 15-25% to debt is the default for sustained throughput. |
| "We'll do a big refactor in Q3." | Big refactors get cancelled. Pay debt incrementally per cycle; reserve "big refactor" only for genuinely strategic items. |

## Anti-patterns

- "We'll just fix it later" without a register entry (it doesn't happen).
- Register exists but isn't reviewed (becomes a graveyard).
- Bug tracker + feature backlog + debt register all conflated.
- Reckless intentional debt allowed to ship without remediation plan.
- 100% capacity to features, 0% to debt (decay built in).
- 80% to debt, 20% to features (paying off too much; symptom of over-correction).
- Debt items vague ("clean up the codebase"); not actionable.
- ADR-skipped strategic debt; team forgets the rationale.
- Boy-scout fixes that expand slice scope (don't ship; log instead).
- Wont-fix marked, never re-reviewed.
- Audit produces a 200-item register that nobody touches (no triage discipline).
