---
name: reliability-dr
description: "Reliability engineering and disaster recovery discipline. SLO design from NFRs, error budgets and burn-rate alerts, backup/restore patterns, RTO/RPO targets and verification, multi-AZ/region topology, runbook/restore drill cadence, DR readiness attestation for production_go_live evidence. Platform/SRE owns this; consumes observability's SLI definitions and feeds the production_go_live gate. Use whenever a project defines reliability targets, when designing backup or failover, when running DR drills, or when reliability is being audited."
---

# Reliability & Disaster Recovery

<!-- praxis:metadata:begin -->
```yaml
capability: operations
domain: infra
state: active
dependencies:
  - nfr-definition
  - observability
  - deploy-release
  - iac
triggers:
  - "designing SLOs and error budgets from NFRs"
  - "planning backup and restore strategy"
  - "designing multi-AZ or multi-region topology"
  - "scheduling and running a DR drill"
  - "investigating an SLO breach"
  - "preparing DR-attestation for production_go_live"
outputs:
  - SLO documents per service (SLI definition + target + window + burn-rate alert)
  - DR plan (RTO/RPO targets, topology, runbook references)
  - backup policy (what, where, how often, how verified)
  - restore drill schedule + last-pass attestation
  - error budget policy (what slows feature work when budget burns)
consumers:
  - platform-sre (primary author)
  - observability (consumes SLI definitions for instrumentation)
  - deploy-release (consumes for production_go_live evidence)
  - incident-runbook (consumes for incident severity classification)
  - chaos-engineering (consumes DR plan for game day scenarios)
references:
  - references/examples.md
```
<!-- praxis:metadata:end -->

The discipline that turns NFR availability targets into operational reality. SLOs make availability *measurable*; error budgets make trade-offs *visible*; backup and restore patterns make failures *recoverable*; DR drills make all of this *rehearsed* rather than theoretical.

The principle: **untested reliability is a story you tell yourself, not a property of the system.** The first restore drill must not be a real incident.

## When this skill fires

- A project defines reliability targets — translate NFR availability + RTO + RPO into SLOs and the DR plan.
- A new service is being designed and its reliability properties need explicit articulation.
- A backup or failover topology is being designed.
- A DR drill is being scheduled or executed.
- An SLO has breached and the error-budget policy is being applied.
- The production_go_live gate needs DR attestation.

## SLO design from NFRs

The NFR register's availability targets (per `nfr-definition`) translate into SLOs. The translation is *deliberate*; don't just copy the NFR number into an SLO target.

### The SLI/SLO/error budget triple

For each user journey worth tracking:

**SLI** (Service Level Indicator) — the measurement, in user terms:

```
"The fraction of POST /orders requests that return 2xx within 500ms,
 measured over rolling 5-minute windows."
```

The SLI is a *ratio of good events over valid events*. "Good" and "valid" are both defined; "valid" excludes things outside the service's control (client errors, planned maintenance, auth failures from invalid credentials).

**SLO** (Service Level Objective) — the target for the SLI:

```
"99.9% over any rolling 30-day window."
```

The window matters: a single bad hour kills a 99.9% / 30-day SLO completely. A single bad hour barely dents a 99.0% / 30-day SLO. Window + target together set the *tolerance* the team commits to.

**Error budget** — the inverse of the SLO:

```
"99.9% allows 0.1% bad events = 43.2 minutes of breach per month."
```

The budget is *spendable* — the team explicitly accepts that some breach happens. When it burns fast, feature work slows; when intact, feature work proceeds. The policy is explicit (below).

### Target selection — be honest about cost

More nines is exponentially more expensive. The cost difference between 99.9% and 99.95% is order-of-magnitude in *some* dimension (engineering effort, infrastructure cost, operational vigilance, or all three).

Pick the target the team can actually deliver and the business actually values. A 99.99% SLO that the team can't hit produces continuous failure plus the cost of trying; a 99.5% SLO that the team beats easily provides no useful signal for operational decisions.

For most SaaS: **99.9%** is the right baseline for customer-facing critical paths. Reserve 99.95% / 99.99% for revenue-critical or contractually-required surface.

### Burn-rate alerts

Static error-budget thresholds (alert at 50% consumed) are dangerous — by the time they fire, the budget is mostly gone. Use **burn-rate alerts** based on Google's multi-window multi-burn-rate pattern:

```
Fast burn (page immediately):
  - Last 1h: burning at >14.4x normal rate
  - Last 5m: burning at >14.4x normal rate
  → would exhaust monthly budget in 2 days at this pace

Slow burn (ticket, not page):
  - Last 6h: burning at >6x normal rate
  - Last 30m: burning at >6x normal rate

Moderate burn (ticket):
  - Last 3d: burning at >3x normal rate
  - Last 6h: burning at >3x normal rate
```

The dual-window pattern prevents false positives from short noise; the multi-burn-rate pattern catches both fast and slow problems. Implement via Prometheus / observability stack per the cloud / runtime.

### Error budget policy

The policy is explicit and pre-agreed — *what slows feature work when budget burns?*

```markdown
# Error Budget Policy — order-service

## When budget is intact (>50% of monthly remaining)
- Normal feature velocity.
- Risky changes allowed if rollback plan armed.

## When budget is 25–50% remaining
- Feature work continues but new risky changes need explicit ADR.
- Reliability work prioritized in next slice.

## When budget is <25% remaining
- Feature work paused; only reliability fixes ship.
- Daily reliability standup until budget recovers.
- Postmortem completed for the budget-consuming incident(s).

## When budget is exhausted (>100% consumed for 30-day window)
- Production deploys frozen except for fixes to root cause.
- Emergency reliability review by SA + Platform/SRE + PM.
- Trade-off conversation: lower the SLO, invest in reliability, or both.
```

The policy is *agreed in advance*, not negotiated mid-incident. It's a contract that protects users (by forcing reliability investment) and the team (by giving permission to slow feature work without explaining).

## Backup and restore

### What gets backed up

Per data store + per critical state:

- **Databases** — point-in-time recovery enabled; retention per compliance regime (typically 7-35 days for operational, longer for compliance).
- **Object storage** — versioning enabled; lifecycle policy; cross-region replication for production.
- **Stateful services** (Kafka topics, Redis snapshots) — per service's persistence model.
- **Configuration** — IaC (versioned in Git is the backup); secret-store contents (managed-service backups + cross-region replication).
- **Application state** — anything that can't be regenerated from upstream sources.

### Backup verification

Backups that haven't been tested are *hopes*. Restore-test cadence:

- **Database restore drill** — quarterly: restore production backup into a sandbox, verify integrity, measure time-to-restore (validates RTO claim).
- **Application restore from scratch** — semi-annually: rebuild the application stack in a fresh environment from IaC + backups.
- **Cross-region failover** — semi-annually for multi-region projects: cut over to the secondary region and run for an hour; verify correctness.

Each drill produces an attestation in `.project/operational/drills/` — template + worked example: `references/examples.md#drill-attestation-example`.

## RTO and RPO

From the NFR register:

- **RTO** (Recovery Time Objective) — how long can the system be down before business impact is unacceptable? Drives standby capacity, restore automation, failover tooling.
- **RPO** (Recovery Point Objective) — how much data loss is acceptable? Drives backup frequency, replication topology.

Common targets:

| Service criticality | RTO | RPO |
|---|---|---|
| Internal tool | 4 hours | 24 hours |
| Customer-facing SaaS | 30 min – 1 hour | 5–15 min |
| Revenue-critical | 5–15 min | <1 min (often via streaming replication) |
| Mission-critical | <1 min | 0 (synchronous replication) |

Aggressive RTO/RPO costs more (always-on standby, sync replication, cross-region active-active). Pick honestly.

## Topology choices

| Topology | Use when |
|---|---|
| **Single-AZ** | Internal tool; can tolerate AZ-level outage. Cheapest. |
| **Multi-AZ** | Most SaaS production. Survives single-AZ failure. Modest cost premium. |
| **Multi-region (active-passive)** | High RTO/RPO; regulatory-required geographic distribution. Significant cost. |
| **Multi-region (active-active)** | Lowest possible RTO; geographically distributed user base. Highest cost; consistency complexity. |
| **Multi-cloud** | Vendor-independence requirement; very rare and expensive. |

Multi-AZ is the default for production SaaS. Multi-region is the exception, justified explicitly per project.

## DR plan document

Per service or per logical system: targets (RTO/RPO/SLO), topology, per-failure-mode behavior, backup policy, runbook links, drill schedule, latest attestations. Full worked example (order-service): `references/examples.md#dr-plan-document--worked-example`.

## Outputs

| Output | Location |
|---|---|
| SLO documents | `.project/operational/slo-{service}.md` |
| DR plan | `.project/operational/dr-plan-{service}.md` |
| Backup policy | `.project/procedural/backup-policy.md` |
| Drill schedule + attestations | `.project/operational/drills/` |
| Error budget policy | `.project/procedural/error-budget-policy.md` |
| Burn-rate alert config | implemented in `observability` instrumentation |

## Mode handling (G/B)

**Greenfield.** Build SLOs from NFRs; design DR plan into the architecture; first drill within 30 days of production go-live.

**Brownfield.** Audit existing reliability. Common findings: SLOs not defined; backups exist but never restored; DR plan documented but never drilled. Prioritize *one good drill* over comprehensive paperwork — a single quarterly drill that actually validates restore beats a 50-page DR plan that's never tested.

## What this skill does not do

- Implement the observability stack — that's `observability` (the instrumentation side).
- Run the on-call rotation — that's `incident-runbook`.
- Inject failures — that's `chaos-engineering`.
- In-process / single-dependency fault handling (timeouts, retries, circuit breakers, bulkheads) — that's `resilience-patterns`; also `performance-testing` for throughput tuning.
- Cross-service coordination and correctness (saga, outbox, consensus, consistency models) — that's `distributed-systems-patterns`.
- Define security recovery (ransomware, breach) — that's part of `compliance-privacy` and `incident-runbook`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "RTO/RPO are aspirational." | RTO/RPO are commitments — to customers, to regulators, sometimes to contracts. Treat as binding. |
| "Backups are sufficient." | Untested backups are unverified backups. Restore drills are the only proof. |
| "Multi-AZ = disaster recovery." | Multi-AZ handles infrastructure failure within a region. Cross-region is for regional disaster. Different tier. |
| "DR runbook is enough." | A runbook never run is fiction. Drill quarterly minimum. |
| "Database backups = DR." | DR includes code, config, secrets, network state, third-party reconnections. Not just data. |
| "We'll figure it out when it happens." | "When it happens" you have minutes, not hours, of clear thinking. The runbook is what gets you through. |

## Verification

You are done when:

- [ ] SLOs defined per critical service (from `nfr-definition`).
- [ ] SLIs instrumented and visible.
- [ ] Error budgets defined; policy when burned through.
- [ ] RTO + RPO documented per data class.
- [ ] Backup strategy: frequency, retention, geographic distribution, integrity verification.
- [ ] Restore procedure documented + last-tested date.
- [ ] DR runbook covers: detection, decision authority, switchover, validation, communication.
- [ ] DR drill scheduled quarterly minimum; results documented.
- [ ] Multi-region / multi-cloud topology documented per architecture.

Evidence to check:
- Last restore drill passed within SLO.
- Error-budget dashboard surfaces current burn rate.

## Anti-patterns

- SLOs copied from NFR numbers without window selection.
- Static error-budget alerts (50% consumed) instead of burn-rate.
- Backups never restore-tested.
- DR plan documented but never drilled.
- "We have multi-AZ" stated without verifying through AZ-failure injection (`chaos-engineering`).
- Error budget policy negotiated mid-incident.
- Multi-region active-active because "it's enterprise" without the cost-justifying NFR.
- DR drills run on the same staging environment that's never been touched — drills should hit real backups.
