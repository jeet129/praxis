---
name: impact-analysis
description: Predict the ripple effects of a proposed change BEFORE making it. Combines static analysis (dependency graph, reverse callers, schema references), runtime telemetry (which services / consumers actually hit this surface), contract knowledge (API consumers, event subscribers, downstream batch jobs), data lineage (warehouse models depending on a...
---

# Impact Analysis


<!-- praxis:description:full -->
## Full description

Predict the ripple effects of a proposed change BEFORE making it. Combines static analysis (dependency graph, reverse callers, schema references), runtime telemetry (which services / consumers actually hit this surface), contract knowledge (API consumers, event subscribers, downstream batch jobs), data lineage (warehouse models depending on a source), and historical incident data (what broke last time we touched this). Read at slice planning time on brownfield, at refactor proposal time, before schema migrations, before API contract changes, and before deprecations. Lead Developer runs it; Architecture Challenger consumes for the scale / operations sub-personas. Distinct from `codebase-comprehension` (which maps the system) — this skill asks "if I change THIS, what is affected?".

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: active
dependencies:
  - codebase-comprehension
  - data-warehouse-modeling
  - api-design
  - observability
  - tech-debt-management
triggers:
  - "planning a brownfield slice that touches existing code"
  - "proposing a refactor; need to scope its blast radius"
  - "before any schema migration"
  - "before any API contract change (even backward-compatible)"
  - "before deprecating an endpoint, event, or table"
  - "challenger reviewing a change with cross-cutting effects"
  - "investigating where else a similar bug might exist"
outputs:
  - blast-radius map (what's affected; how)
  - consumer inventory (per change: who depends on the changed surface)
  - test scope (which tests must pass; which suites must run)
  - rollout plan (sequencing across consumers if breaking)
  - go/no-go recommendation (proceed / proceed with conditions / scope-blocker)
consumers:
  - lead-developer (primary author at slice planning)
  - architecture-challenger (scale + ops sub-personas)
  - solution-architect (architecture-affecting changes)
  - data-engineer (schema / lineage impact)
  - platform-sre (operational impact)
  - product-manager (consumer-breaking changes; coordination scope)
references: []
```
<!-- praxis:metadata:end -->

The discipline that asks the cheap question before paying the expensive cost. Most production incidents trace to a change whose blast radius was misunderstood. Impact analysis is the discipline of mapping that blast radius BEFORE the change ships.

The principle: **the cost of impact analysis is bounded and small; the cost of misjudged impact is unbounded. Trade the small cost reliably.**

## When this skill fires

- Planning a brownfield slice that touches existing code.
- Proposing a refactor; need to scope its blast radius.
- Before any schema migration — what reads the columns being changed?
- Before any API contract change — even backward-compatible changes need consumer awareness.
- Before deprecating an endpoint, event, or table.
- Architecture Challenger reviewing a cross-cutting change.
- Investigating where else a similar bug might exist (lateral impact).

## The four lenses

A complete impact analysis combines four lenses. Any single lens is insufficient.

### Lens 1: Static (the code)

What does the code itself say is connected?

- **Reverse-call graph** — who calls the function/method/endpoint being changed?
- **Import / reference graph** — which modules import this type / class?
- **Schema references** — which queries read/write the affected columns? (`pg_stat_statements` for Postgres; `INFORMATION_SCHEMA` queries; LSP / language tools.)
- **Configuration references** — which configs key off this value?
- **String references** — endpoint paths, event names, queue names typically reach via strings; grep is essential.

Tools: language LSP, IDE "find usages", `grep` for strings, dependency-graph tools per language.

Limitation: static analysis misses dynamic dispatch, reflection, configuration-driven wiring, and cross-system links (HTTP calls, events on a bus).

### Lens 2: Runtime (the actual traffic)

What actually happens in production?

- **Endpoint callers** — from access logs / API gateway, who's calling the endpoint and at what rate?
- **Event subscribers** — from message bus topics + consumer group registry.
- **Query patterns** — `pg_stat_statements` or equivalent: what queries hit the affected tables / columns.
- **Service-to-service edges** — distributed-trace data (per `observability`): the actual call graph.

Tools: APM / tracing (OpenTelemetry, Datadog, Honeycomb); access logs; database query stats.

This lens catches what static misses. Critical for systems where the deployed reality has drifted from the codebase's apparent structure.

### Lens 3: Contract (the agreements)

Who depends on the contract, regardless of code?

- **API consumers** — internal services + external customers + their SLA expectations.
- **Event subscribers** — including downstream batch jobs that consume an event log.
- **Data consumers** — analytical models, dashboards, ML feature pipelines depending on the data source.
- **Documentation references** — public docs, SDKs, partner integrations.

Tools: API gateway consumer registry; event-bus subscriber registry; data lineage tool (per `data-warehouse-modeling`); documentation site analytics.

Some consumers don't show up in runtime data because their cadence is monthly; some don't show up in code because they live in a partner's system. Contract lens catches them.

### Lens 4: Historical (the past)

What broke last time someone touched this?

- **Incident history** — per `incident-runbook`, which incidents involved this surface?
- **Bug-fix history** — git blame on the affected code; surface that's been touched 50 times has different risk than one touched once.
- **Reverts** — when this was changed before, was the change reverted? Why?
- **Recent ADRs** — was there a recent decision that constrains this?

Tools: incident registry; git log + blame; ADR archive.

This lens catches knowledge that lives in incident reports, not the code.

## The analysis output

Combined output of the four lenses:

```markdown
# Impact Analysis — Add `currency` column to `payments.transactions` table

## Surface
- Schema: `payments.transactions` (production DB).
- Field type: VARCHAR(3); NOT NULL; default 'USD' (backfill).

## Static lens
- 14 source files reference `payments.transactions`.
- 7 are read-only queries; 4 write inserts; 3 update.
- 2 of the 14 use SELECT * (would auto-pick up new column — flag).
- 3 use explicit column lists (will need explicit add).

## Runtime lens
- Average 4,200 reads/sec; 180 writes/sec in production.
- Top 3 consuming services: payment-orchestrator, fraud-detector, reporting-aggregator.
- 2 batch jobs hit the table nightly: warehouse-sync, monthly-recon.

## Contract lens
- API `GET /v1/transactions/{id}` returns transaction object — currency will surface in response (additive; safe).
- Event `TransactionCompleted` includes transaction payload — currency will be added.
- Analytical model `fct_transactions` reads this table — needs lineage update.
- Two external partners poll an export feed; currency will appear in export.

## Historical lens
- 4 incidents in 2025-2026 involving this table; 2 were schema migrations.
- Last schema migration (2026-04) caused 18m of degradation due to lock contention.
- ADR-038 (2025-11) constrains: no destructive changes to this table without 2-week notice to external partners.

## Blast radius summary
- Internal: 14 code locations + 3 services + 2 batch jobs.
- External: 2 partners + 1 analytical surface.
- Risk: medium (additive change; locking risk during migration on a hot table).

## Recommended plan
1. Backfill default 'USD' deployed first (online ALTER + backfill, batched).
2. Producer services updated to write currency (no consumer breakage; default still applied).
3. Consumer services updated to read currency (with USD fallback).
4. External partners notified (per ADR-038's 2-week rule).
5. Warehouse lineage updated; downstream fct_transactions adds column.
6. Reporting backfilled (90 days history).

## Tests required
- Migration tested in staging including production-data-sized backfill (load test under representative write traffic).
- Consumer-contract tests for both internal services and external feed.
- Locking behavior verified under production-like write load.

## Recommendation: PROCEED WITH CONDITIONS
- Use Wave-3 online-migration pattern (per `data-warehouse-modeling`).
- Migration runs in a maintenance window even though "online" — concurrent index discipline.
- Partner notification 2-week-out enforced.
```

## Going / no-going

Three outcomes:

- **Proceed** — blast radius small + well-tested + low-risk surface.
- **Proceed with conditions** — proceed, but observe specific guardrails (rollout phasing, soak times, monitoring focus).
- **Scope blocker** — blast radius too large for the slice; needs decomposition into multiple slices, or strategic debt escalation.

The recommendation is Lead Dev's; Solution Architect signs off on "scope blocker" calls.

## Special cases

### Schema migrations

Always run impact analysis. The four-lens treatment is non-negotiable for production-table changes. Add explicit:

- **Lock behavior** — ALTER TABLE locking model on the database engine; concurrent index discipline.
- **Backfill plan** — for NOT NULL with default; in batches.
- **Rollback plan** — if migration fails mid-way, how to revert.

### API contract changes

Even "backward-compatible" changes need analysis:

- New field added — consumers using `SELECT *` or `?` operator may unexpectedly receive it.
- New optional parameter — consumers may stop passing it; if you later require it, you've broken them.
- Response field type widened — some consumers may have narrow client-side parsing.

Strict contract testing (per `api-design`) catches most of this; impact analysis catches what tests can't (partner integrations).

### Deprecations

Highest-risk class. Impact analysis required + announcement timeline + monitoring of pre-deprecation usage + sunset date with extensions process.

### Refactors

Even "no behavior change" refactors need analysis. The blast radius is the code surface area touched; the test surface is everything that depends on the touched code.

## Outputs

| Output | Location |
|---|---|
| Impact analysis report | `.project/operational/impact-analyses/{change}-{date}.md` |
| Blast-radius map | inline in report |
| Consumer inventory | inline in report |
| Test scope addition to slice plan | passed to QA Engineer |
| Rollout plan | passed to Platform/SRE for sequencing |
| ADR (if architecture-affecting) | `.project/decision/` |

## Mode handling (G/B)

**Greenfield.** Lighter weight — the four lenses are mostly empty (no runtime, no historical, limited contract). Use the static + contract lenses to think about future consumers.

**Brownfield.** Mandatory before any non-trivial change. The four lenses are where the value is. Without impact analysis, brownfield engagements ship incidents.

## Critical disciplines

**Run before deciding scope.** Impact analysis informs whether a slice's scope is correct. Doing the analysis after the slice is sized misses its main value.

**All four lenses.** Skipping one is how you miss the consumer that breaks.

**Document the report.** It's evidence in the slice's review and in any post-incident analysis.

**Update with new findings.** If during implementation a new consumer is discovered, update the report; it becomes the trail of what was considered.

**Don't analyze every change.** Analysis cost should be proportional to change risk. Tiny isolated changes don't need a four-lens treatment.

## Verification

You are done when:

- [ ] Four lenses applied (Static / Runtime / Contract / Historical) — none skipped or marked "not applicable" without rationale.
- [ ] Blast-radius map identifies: code surfaces touched, services consuming, contracts affected, partner integrations, historical incidents.
- [ ] Per-finding: severity classified (low / medium / high blast).
- [ ] Rollout plan sequenced if breaking (consumers updated before producers if breaking; backward-compat shim if not).
- [ ] Test scope expanded based on analysis (which suites must pass; which migrations need staged tests).
- [ ] Recommendation: proceed / proceed-with-conditions / scope-blocker — with rationale.
- [ ] Report saved to `.project/operational/impact-analyses/<change>-<date>.md`.

Evidence to check:
- Runtime data was actually consulted (logs / metrics / traces / DB stats), not assumed.
- Contract lens consulted: external partners, downstream batch jobs, analytics models.
- Historical lens consulted: prior incidents involving this surface.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "The change is small; skip the analysis." | Small changes break large systems via consumers the agent didn't see. Right-size the analysis to the surface, not the change. |
| "Find Usages tells me who's affected." | That's the Static lens — 1 of 4. Runtime, Contract, and Historical lenses see what the IDE can't. |
| "We have good tests; tests will catch it." | Tests catch what they're written for. Consumers in other repos / partner systems / batch jobs don't ship their tests with yours. |
| "We've changed this before; we know what happens." | Past changes are the Historical lens. They're inputs, not substitutes for the other three. |
| "Schema migration is just ALTER TABLE." | Locks, replication lag, downstream readers, analytical models, partner exports. Nine items on average. Analyze. |
| "I'll do impact analysis after the slice ships." | Hindsight blast radius isn't impact analysis. The whole point is to inform sizing BEFORE the change. |

## Anti-patterns

- Static lens only ("the IDE says these files use it").
- Runtime lens skipped ("but we don't have production telemetry for this").
- Contract lens skipped — partners discovered post-incident.
- Historical lens skipped — repeat the past mistake.
- Impact analysis after the slice ships ("hindsight blast radius").
- Treating "the migration tool is online" as proof of safety (locks still matter).
- Schema change without consumer inventory.
- Refactor declared "behavior-preserving" without test scope analysis.
- Single tool used; analysis depth missed across lenses.
- Recommendation skipped — analysis with no actionable output is wasted.
