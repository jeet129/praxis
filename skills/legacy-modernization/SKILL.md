---
name: legacy-modernization
description: Replacing legacy systems without big-bang rewrites. Strangler fig pattern, anti-corruption layers, parallel-run validation, traffic-shift strategies, data-migration with cutover discipline, sunset planning. Distinct from `tech-debt-management` (incremental hygiene) — this is whole-subsystem replacement. Brownfield-only activation; never fires in greenfield.
---

# Legacy Modernization


<!-- praxis:description:full -->
## Full description

Replacing legacy systems without big-bang rewrites. Strangler fig pattern, anti-corruption layers, parallel-run validation, traffic-shift strategies, data-migration with cutover discipline, sunset planning. Distinct from `tech-debt-management` (incremental hygiene) — this is whole-subsystem replacement. Brownfield-only activation; never fires in greenfield. Solution Architect leads; PM owns the business case; principal approves the strategic decision. Use when proposing a legacy system replacement, when scoping a strangler-fig migration, when designing the anti-corruption layer, when planning parallel-run validation, or when sequencing the cutover.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: active
dependencies:
  - codebase-comprehension
  - architecture-pattern-selection
  - impact-analysis
  - tech-debt-management
  - data-warehouse-modeling
  - api-design
triggers:
  - "proposing legacy system replacement (the business case)"
  - "scoping a strangler-fig migration"
  - "designing the anti-corruption layer for the boundary"
  - "planning parallel-run validation"
  - "sequencing the migration cutover"
  - "deciding sunset criteria and timeline"
  - "investigating why a previous modernization stalled"
outputs:
  - modernization strategy doc (the whole plan; multi-phase)
  - business case (cost / risk / value of replacing vs maintaining)
  - strangler-fig boundary map (what gets replaced; in what order)
  - anti-corruption-layer design (the translation boundary)
  - parallel-run validation plan (what we compare; how long)
  - cutover plan (per slice of the legacy)
  - sunset plan (when legacy is decommissioned)
consumers:
  - solution-architect (primary author)
  - product-manager (business case; tradeoff prioritization)
  - principal (strategic decision)
  - lead-developer (execution per slice)
  - architecture-challenger (challenges the strategy)
  - platform-sre (cutover operations)
references: []
```
<!-- praxis:metadata:end -->

The discipline of replacing legacy systems without the catastrophic big-bang rewrite. Big-bang rewrites fail more often than they succeed — they consume years, accumulate scope, run parallel to the legacy whose feature set keeps growing, and frequently get cancelled. This skill is the alternative: replace incrementally, validate continuously, cutover surgically, sunset deliberately.

The principle: **legacy systems are replaced piece by piece, with the legacy still serving traffic, until there's nothing left to serve.**

## When this skill fires

- Proposing legacy system replacement — building the business case.
- Scoping a strangler-fig migration.
- Designing the anti-corruption layer at the boundary.
- Planning parallel-run validation.
- Sequencing the migration cutover.
- Deciding sunset criteria + timeline.
- Investigating why a previous modernization stalled.

**Brownfield-only.** This skill never fires in greenfield (no legacy to modernize).

## When NOT to modernize

Before committing, ask:

- Is the legacy actually failing the business, or just unfashionable?
- Could `tech-debt-management` handle it incrementally?
- Is the business case strong (cost to maintain >> cost to replace; risk of staying on legacy >> risk of replacing)?
- Do we have the will to follow through for 12-36 months?

Often the answer is "keep it; fix the worst debt." Modernization is expensive; the framing matters.

## The strangler fig pattern

Named for the strangler fig tree — grows around its host, eventually replaces it. Applied to software:

1. Identify a slice of legacy behavior that can be re-implemented.
2. Build the replacement, exposing the same interface (or a routed interface).
3. Route a fraction of traffic to the replacement (per `deploy-release` traffic-shift).
4. Validate (per `evaluation-engineering`-style outputs OR parallel-run-validation).
5. Increase traffic to the replacement; decrease to the legacy.
6. When the legacy slice carries 0 traffic for a sustained period, decommission.
7. Repeat for the next slice.

The legacy keeps running. The replacement grows. Eventually the legacy has nothing left to do.

## The anti-corruption layer

When old and new exchange data or calls, the boundary needs a translation layer that:

- **Speaks new on the new side** — modern types, modern protocols, clean semantics.
- **Speaks legacy on the legacy side** — adapts to whatever the legacy expects, including its bugs.
- **Owns the translation logic** — both sides remain clean.

Without the ACL, the new system gets "infected" with legacy concepts and the modernization stalls (because the new looks like the old).

ACL design considerations:

- Bidirectional (calls in both directions through it).
- Stateful when needed (e.g., session translation, identifier mapping).
- Versioned (legacy evolves slowly; ACL accommodates).
- Has a sunset — when the legacy is gone, the ACL is too.

Per `architecture-pattern-selection`, the ACL is a first-class subsystem in the modernization plan.

## Parallel-run validation

For correctness-critical replacements (financial calculations, fraud scoring, ranking, etc.):

1. Both legacy and new run on the same input.
2. Outputs compared.
3. Differences logged + analyzed (not necessarily blocking — the new might be correct; the legacy might be the bug).
4. When the new matches legacy (or matches reality where legacy was buggy) within tolerance, traffic shifts.

Parallel run is expensive — double the compute, more complex flows — but it's the only way to validate correctness-sensitive replacements pre-cutover.

Duration: weeks to months depending on the slice. Cutover when:

- Match rate within tolerance for the soak period.
- Diff analysis explains every meaningful difference.
- Operations confidence that the new can carry the load.

## Cutover planning per slice

Each strangler-fig slice has a cutover plan:

```markdown
# Cutover Plan — Order Lookup (legacy → new)

## Pre-cutover
- New service deployed; passes synthetic + canary traffic.
- Anti-corruption layer routes legacy callers to new.
- Parallel run live for 6 weeks; match rate 99.97% (acceptable per ADR-105).

## Cutover phases
1. T+0: route 1% of traffic to new (24h soak; monitor matched against legacy via parallel run).
2. T+1d: route 10% (48h soak).
3. T+3d: route 50% (72h soak).
4. T+6d: route 100% (legacy serving 0% production traffic).
5. T+13d: legacy still receiving shadow traffic for monitoring; new is the source of truth.
6. T+27d: legacy shadow traffic stopped; legacy in cold-standby.
7. T+90d: legacy fully decommissioned; data archived; infra reclaimed.

## Rollback triggers
- Match rate drops below 99.9% during cutover.
- SLO breach attributable to new system.
- Discovery of correctness regression.

## Rollback procedure
- Within 90 days: traffic shifted back to legacy; new in shadow; investigation continues.
- After 90 days: rollback option lost; only forward (per `deploy-release` discipline).
```

## Data migration

The hardest part of most modernizations. Categories:

- **Reference data** (small; static-ish) — copy + verify.
- **Operational data** (current state) — live replication during parallel run; cutover seizes the new system as the source of truth at a precise moment.
- **Historical data** (long-tail; less critical) — bulk-migrated post-cutover or kept in legacy read-only.

Strategies:

- **Dual-write** — both systems written simultaneously; verification compares. Risky if writes can diverge.
- **CDC (change data capture)** — legacy DB streams changes to new; new is read-only consumer during parallel run; cutover flips write direction.
- **Bulk + delta** — bulk copy at point T; delta from T to cutover applied at cutover.

Per `data-warehouse-modeling` for analytical data; per `data-pipeline` for the migration pipeline itself.

## Sunset plan

The end of the modernization. Required content:

- **Sunset date** — when the legacy is decommissioned.
- **Pre-sunset checklist** — all consumers migrated; all data extracted; runbooks updated.
- **Sunset event** — the actual decommissioning; runs as a planned change with rollback (rollback = restore from backup if needed).
- **Post-sunset retention** — backups retained for X years per compliance regime.
- **ACL removal** — the anti-corruption layer is removed (its purpose is fulfilled).

Without a sunset, modernizations linger forever — legacy runs forever in "we'll get to it" mode, expensively.

## Why modernizations stall

Common causes; designed-in mitigations:

| Cause | Mitigation |
|---|---|
| Legacy adds features faster than new replaces | Freeze legacy feature additions; new feature work goes to new. |
| Parallel run mismatches accumulate; team loses confidence | Investigate every mismatch; document tolerance criteria explicitly. |
| ACL bloats; carries old assumptions into new | Periodic ACL review; refactor when stable. |
| Sunset perpetually deferred | Hard sunset date in plan; treat as immovable. |
| Strategic debt reclassified as feature work | PM discipline; modernization slices ARE feature work for the business. |
| Team rotates; institutional memory lost | Documentation per `technical-documentation` + `architecture-documentation`. |

## Outputs

| Output | Location |
|---|---|
| Modernization strategy doc | `.project/decision/adr-NNN-{system}-modernization.md` |
| Business case | `.project/operational/modernization/{system}-business-case.md` |
| Strangler-fig boundary map | `.project/working/architecture/strangler-{system}.md` |
| ACL design | `.project/decision/adr-NNN-{system}-acl.md` |
| Parallel-run validation plan | `.project/operational/modernization/{system}-parallel-run.md` |
| Cutover plans (per slice) | `.project/operational/modernization/{system}-cutover-{slice}.md` |
| Sunset plan | `.project/operational/modernization/{system}-sunset.md` |

## Critical disciplines

**Reject big-bang.** Always.

**Slice it small.** Strangler-fig slices should be 2-8 weeks each. Larger = the legacy outruns you.

**Validate continuously.** Parallel run for correctness-critical; canary for behavior.

**ACL ownership.** Someone owns the boundary layer; it's not "code that emerges."

**Sunset is a date.** Not "eventually."

**ADR the strategy.** Future team will ask "why did we modernize this?" — the ADR is the answer.

## Mode handling

**Greenfield**: doesn't apply.

**Brownfield**: this is the planning skill for replacement-class projects. Often spawned alongside `project-phasing` (the modernization itself is phased).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Rewrite is faster." | It almost never is. The legacy keeps adding features; the rewrite runs in parallel. Strangler is the boring answer. |
| "ACL is over-engineering." | Without it, new code adopts legacy idioms; the rewrite stalls. ACL keeps the boundary clean. |
| "Sunset will happen eventually." | Without a hard date, it doesn't. Set the date; treat it as immovable. |
| "We can deprecate legacy gradually." | Then it lives forever. Deprecation has a removal date AND consumers migrated AND data extracted. |
| "Parallel run is unnecessary; tests are enough." | Tests verify what's written. Parallel run verifies what's reality. Both. |
| "Modernization should match team headcount." | Modernization matches the strangler-fig graph; team capacity informs pace, not scope. |

## Verification

You are done when:

- [ ] Modernization strategy ADR exists.
- [ ] Business case quantified (cost / risk / value).
- [ ] Strangler-fig boundary map: which slices, in what order.
- [ ] ACL designed with sunset criteria.
- [ ] Parallel-run plan: duration, tolerance, divergence response.
- [ ] Cutover plan per slice: phases, abort criteria, rollback.
- [ ] Data migration: bulk + delta or CDC, with cutover discipline.
- [ ] Sunset plan: hard date + pre-sunset checklist + retention policy.

Evidence to check:
- Last cutover was within plan.
- ACL is being removed as expected.

## Anti-patterns

- Big-bang rewrite ("it'll only take 6 months").
- No ACL ("we'll just call the legacy directly").
- Sunset deferred indefinitely.
- Parallel run skipped on correctness-critical replacements.
- New system grows feature-parity scope without business case for the features.
- Legacy continues to receive feature work during modernization.
- Cutover without rollback plan.
- Data migration assumed to be "just copy"; reality more complex.
- ACL never decommissioned (lingers as legacy-of-legacy).
- "It's mostly there" claimed for 18+ months; never finishes.
- Strangler fig slices too big; legacy outpaces them.
- Stakeholder buy-in absent; modernization defunded mid-flight.
