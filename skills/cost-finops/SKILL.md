---
name: cost-finops
description: Cost-aware design and continuous optimization. Right-sizing, spot / reserved / committed-use, storage tiering, tagging + showback, budget alerts, FinOps culture. Distinct from `capacity-resource-estimation` (which sets initial sizing); this skill ensures cost stays optimal as the system runs. Platform/SRE owns this; PM consults on cost vs. feature trade-offs; principal approves overruns. Use whenever provisioning happens, when cost trends concern, when running quarterly cost reviews, or when budgets need adjustment.
---

# Cost / FinOps


<!-- praxis:metadata:begin -->
```yaml
capability: operations
domain: infra
state: active
dependencies:
  - capacity-resource-estimation
  - iac
  - nfr-definition
triggers:
  - "designing initial cost model for a new project"
  - "investigating cost trend (above plan; rising faster than usage)"
  - "running quarterly cost review"
  - "evaluating spot / reserved / committed-use options"
  - "setting up cost-attribution showback"
  - "designing budget alerts"
outputs:
  - cost model per environment (monthly $)
  - cost-attribution policy (tagging + showback)
  - budget + alert thresholds (per environment, per service)
  - optimization backlog (right-sizing / spot / reserved / tiering opportunities)
  - quarterly cost review (variance vs plan, action items)
consumers:
  - platform-sre (primary author + executor)
  - product-manager (consulted on feature-cost trade-offs)
  - solution-architect (consumes for architecture cost implications)
  - capacity-resource-estimation (paired skill — capacity sets target; this optimizes against it)
  - tech-debt-management (consumes optimization backlog)
references: []
```
<!-- praxis:metadata:end -->

The discipline that keeps run-cost in line with business value as the system scales. Capacity sizing (`capacity-resource-estimation`) sets the *initial* envelope; this skill ensures that as load actually arrives, growth happens, and architecture evolves, the cost stays optimal — not minimal, optimal (the lowest cost that meets the NFRs).

The principle: **cost is a deliberate engineering choice, made continuously and visibly, not a surprise discovered in the monthly bill.**

## When this skill fires

- A new project's cost model is being designed.
- A cost trend concerns the team (rising faster than usage; above plan).
- Quarterly cost review (default cadence).
- A specific optimization is being evaluated (move to spot; commit to reserved).
- Cost-attribution showback is being set up.
- Budget alerts need configuration.

## The FinOps mindset

Three principles:

1. **Inform** — make costs visible to the people making decisions. Engineers who can see their service's cost optimize it.
2. **Optimize** — continuous right-sizing, tier selection, commitment strategy.
3. **Operate** — budget management, alerts, reviews, accountability.

These compound. Showback (Inform) drives engineer-led optimization (Optimize); optimization wins flow into the budget (Operate); the budget guides decisions (Inform → again).

## The cost categories

Per environment (dev / test / staging / production) and per service:

| Category | What drives it |
|---|---|
| **Compute** | Instance types × hours × replica counts × environment. |
| **Storage** | Volume × $/GB × tier (hot / warm / cold). |
| **IOPS** | Provisioned IOPS × $/IOPS × storage type. |
| **Network** | Egress (most expensive); cross-AZ; cross-region; internet. |
| **Managed services** | Per-service: RDS, Kafka, Elasticsearch, etc. — usually instance × hours. |
| **Data transfer** | Replication; backup snapshots cross-region. |
| **Logging / metrics / traces** | High-volume observability is expensive (ingest + retention). |
| **External services** | SaaS APIs (Stripe, Auth0, etc.). |

The largest cost line per project is usually compute or managed services; observability cost can surprise.

## Right-sizing

The continuous practice of matching provisioned capacity to actual usage:

- **Compute**: instance types matched to actual CPU/memory utilization. Common waste: 4xLarge instances at 15% utilization → downsize to 2xLarge with autoscaler headroom.
- **Databases**: instance class matched to actual workload. Aurora I/O-optimized vs standard depending on I/O profile.
- **Storage volumes**: gp3 vs io2 vs io1 per actual IOPS need. gp3's $/IOPS is usually best when properly tuned.
- **K8s**: pod requests / limits matched to observed working set (VPA in recommendation mode).
- **Replica counts**: HPA bounds calibrated to actual peak; over-provisioning the floor wastes money.

VPA (in recommendation mode) and observability data drive this. Quarterly review of every service's right-sizing.

## Commitment strategies

Pay less by committing to longer-term usage:

- **On-demand** — pay-as-you-go; flexible; most expensive.
- **Spot / preemptible** — 60-90% discount; can be reclaimed; for fault-tolerant workloads.
- **Reserved instances** — 1-year or 3-year commitment; 30-60% discount; locks you in.
- **Committed-use discounts** — predictable spend commitment; flexible across instance families (cloud-specific).
- **Savings plans** — similar to reserved but more flexible (cloud-specific).

The strategy mix per project:

```
Production:
  - Baseline (steady-state replicas) → committed-use or reserved (1-year)
  - Burst (HPA-scaled replicas above baseline) → on-demand or spot (with autoscaler fallback)
Staging / Test:
  - Mostly spot; on-demand for stable parts
Dev:
  - On-demand with aggressive scale-down off-hours
```

Spot is suitable when:
- Workload is fault-tolerant (per `resilience-patterns`; HPA + Cluster Autoscaler recover).
- Application handles graceful shutdown (30-60s warning typical).
- Multiple instance families requested (less likely all are reclaimed simultaneously).

Spot is unsuitable for:
- Single-replica stateful services.
- Bin-packing critical workloads onto small node pools.

## Storage tiering

Object storage is the easiest cost-optimization target after compute:

| Tier | Use when |
|---|---|
| **Hot** (S3 Standard, GCS Standard) | Frequently accessed. |
| **Infrequent-access** (S3 IA, GCS Nearline) | < 1 access / month. Cheaper storage; per-access charge. |
| **Cold** (S3 Glacier, GCS Coldline) | < 1 access / quarter. Much cheaper; retrieval cost + latency. |
| **Archive** (S3 Deep Archive, GCS Archive) | Compliance retention; very rare access. Cheapest; long retrieval time. |

Lifecycle policies move data automatically: hot for 30 days → IA for 90 days → cold for 365 days → archive (or delete) per retention.

Database storage tiers similarly: standard SSD → magnetic for old / cold partitions.

## Tagging + showback

Per `iac`, every resource carries tags (project, environment, owner, cost-center, criticality). Showback uses these:

- **Cost reports per cost-center** — engineering teams see their slice.
- **Cost reports per service** — service owners see their service's cost.
- **Cost reports per tenant** (in multi-tenant systems) — informs per-tenant pricing.
- **Cost trend per service** — week-over-week; alerts on anomalies.

Tools: AWS Cost Explorer + Cost & Usage Reports; Azure Cost Management; GCP Cost Tools; Infracost; Vantage; Cloudability.

Showback drives accountability: when engineers see their cost, they optimize.

## Budget + alerts

Per environment + per service:

```
Production order-service:
  Monthly budget: $5,000
  Alert at 80% ($4,000): warning to platform-sre
  Alert at 100% ($5,000): page to platform-sre + notify PM
  Alert at 120% ($6,000): incident-level; engage SA + PM

Staging order-service:
  Monthly budget: $500
  Alert at 100%: warning

Dev:
  Monthly budget: $200 (combined all services)
  Alert at 100%: warning
```

Budget alerts use cloud-native tooling (Budgets API). Anomaly detection (sudden spike) often surfaces issues hours before budget breach.

## Cost vs. NFR trade-off

Some NFRs cost more (99.99% availability > 99.9%; multi-region > multi-AZ; sync replication > async). The trade-offs are explicit:

```
NFR: 99.99% availability
Required: multi-region active-active; sync DB replication; 24/7 on-call across 2 regions.
Estimated monthly cost (production): $80K
Estimated monthly cost (99.9% / multi-AZ alternative): $25K
Cost delta: $55K/month for the additional 9.

Trade-off accepted: $55K/month buys ~52 minutes of additional uptime per year.
ADR: yes / no?
```

Forced explicit. The PM and principal make the trade-off; the trade-off is documented.

## Quarterly cost review

Cadence: quarterly.

Format:

```markdown
# Cost Review — Q3 2026

## Summary
- Total spend Q3: $X (Y% above Q2; Z% above plan)
- Largest service: <service> at $X/month
- Largest growth area: <area> grew $X / Y%
- Largest waste candidate: <item>

## Right-sizing opportunities
| Service | Current | Recommended | Saving/month |
|---|---|---|---|
| order-service prod nodes | m5.2xlarge × 12 | m5.xlarge × 12 | $1,800 |
| analytics DB | db.r5.4xlarge | db.r5.2xlarge | $1,200 |

## Commitment opportunities
- Order-service baseline (6 instances × 24/7) → eligible for 1-year RI (~40% discount).
- Estimated saving: $3,600 / month.

## Storage tiering opportunities
- Order-history bucket: 5TB hot, ~99% < 30 days old → enable IA lifecycle.
- Estimated saving: $400 / month.

## Concerns
- Observability ingest (Datadog) grew 60% with no corresponding load increase. Investigate log volume.

## Actions
| Action | Owner | Due |
|---|---|---|
| Right-size order-service nodes | platform-sre | 2 weeks |
| Purchase order-service RI (1-year) | platform-sre + finance | 1 month |
| Enable order-history IA lifecycle | platform-sre | 1 week |
| Investigate Datadog ingest growth | platform-sre | 2 weeks |
```

Actions become tracked work — backlog items or sprint commitments.

## Outputs

| Output | Location |
|---|---|
| Cost model (per environment) | `.project/operational/cost-model.md` |
| Cost-attribution policy (tagging) | `.project/procedural/tagging-policy.md` (paired with `iac` policy-as-code) |
| Budgets + alert thresholds | configured in cloud-native tooling; documented in `.project/operational/budgets.md` |
| Optimization backlog | `.project/working/cost-optimization-backlog.md` |
| Quarterly cost review | `.project/operational/cost-reviews/cost-review-{quarter}.md` |

## Mode handling (G/B)

**Greenfield.** Design cost model from `capacity-resource-estimation`'s initial sizing; instrument showback from day one.

**Brownfield.** Audit existing spend; common findings: untagged resources; oversized instances; on-demand for steady-state; no lifecycle policies on storage; observability cost runaway. Prioritize by largest waste first.

## What this skill does not do

- Initial capacity sizing — that's `capacity-resource-estimation`.
- Negotiate vendor contracts — finance / procurement.
- Implement the optimizations themselves — done via `iac` PRs.
- Forecast revenue or product profitability — finance / business teams.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Cloud bill is one big number." | Without attribution, optimization is shooting in the dark. Tag + attribute first. |
| "Reserved instances cover everything." | They cover steady-state. Spot / on-demand mix for variable load is also a lever. |
| "Storage is cheap." | At small scale yes; at scale storage cost compounds. Lifecycle policies matter. |
| "Egress is unavoidable." | Architecture decisions (CDN, regional placement, batching) reduce egress meaningfully. |
| "Per-tenant cost is too hard to compute." | If you can't compute it, pricing is a guess. Tag aggressively. |
| "We'll optimize after launch." | Cost embeds in architecture. Some choices are 10x cheaper than others; decide deliberately. |
| "FinOps is finance's job." | Engineering owns the levers. Finance owns the report. Collaborate. |

## Verification

You are done when:

- [ ] Cost attribution working: resources tagged by team / service / environment / tenant where applicable.
- [ ] Cost dashboard with: current burn, projected month, anomaly detection.
- [ ] Per-feature cost computable for top-3 features.
- [ ] Reserved / committed-use contracts evaluated annually.
- [ ] Storage lifecycle policies set (tier transitions, retention, deletion).
- [ ] Egress audit performed; top sources identified.
- [ ] Idle resource scan scheduled.
- [ ] Budget alerts configured per project / per category.
- [ ] LLM cost (if applicable) tracked per `llm-cost-optimization`.

Evidence to check:
- The cost dashboard surfaced at least one optimization opportunity in the past quarter.
- Budget alerts have triggered + been acted on.

## Anti-patterns

- Cost visible only to finance, not engineering (no engineer-led optimization).
- Tagging absent or inconsistent (no attribution possible).
- Reserved instances bought for elastic workloads (commits to overprovisioning).
- Spot used for stateful single-replica services.
- Storage lifecycle policies never set (hot tier for years).
- Budget alerts without action plan (alerts fire; nothing changes).
- Cost reviews skipped or rushed (waste accumulates).
- Showback metrics without context (engineers see numbers, not trends).
- Observability cost growing 50%+/year without scrutiny.
- "Just throw more instances at it" as the default response to latency issues (often a code fix is cheaper than scale).
