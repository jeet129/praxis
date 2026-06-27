---
name: nfr-definition
description: Make non-functional requirements explicit, measurable, and gated. Produces the NFR register — target numbers per quality attribute (performance, availability, scalability, security, compliance, accessibility, observability, RTO/RPO, cost) plus the verification method for each. Without this, NFRs get discovered in production.
---

# NFR Definition


<!-- praxis:description:full -->
## Full description

Make non-functional requirements explicit, measurable, and gated. Produces the NFR register — target numbers per quality attribute (performance, availability, scalability, security, compliance, accessibility, observability, RTO/RPO, cost) plus the verification method for each. Without this, NFRs get discovered in production. Use whenever a project enters the architecture phase or a slice introduces new quality targets. The NFR register is consumed by every Decision Node that checks "did we meet the bar?" — `nfr_satisfied()` predicates parameterize against this register.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: discovery
domain: cross-cutting
state: active
dependencies:
  - product-discovery
triggers:
  - "entering architecture phase"
  - "a slice introduces new performance/availability/security targets"
  - "calibrating Decision Node thresholds"
  - "scoping the production-go-live gate evidence"
outputs:
  - NFR register (`.project/semantic/nfr-register.md`)
  - verification plan (how each NFR will be measured)
  - target numbers per attribute (used to parameterize Decision Nodes)
consumers:
  - solution-architect (designs against the register)
  - architecture-challenger (attacks designs that don't meet the register)
  - delivery-planner (uses register to calibrate workflow)
  - capacity-resource-estimation (sizes against performance + scale)
  - performance-testing (verifies against targets)
  - reliability-dr (designs to RTO/RPO)
references: []
```
<!-- praxis:metadata:end -->

Non-functional requirements are the silent killers of projects. Functional requirements describe *what* the system does; NFRs describe *how well*. Most architectural mistakes are NFR-blind — the design works at scale 10 but breaks at scale 1000 because nobody pinned the target.

This skill makes NFRs explicit, measurable, and gated. The output — the NFR register — is the document every architectural decision is justified against.

## When this skill fires

- The project is transitioning from discovery to architecture. PM (sometimes SA) runs this skill to lock the targets before design begins.
- A new slice introduces quality targets the existing register doesn't cover (e.g., a real-time feature in a previously batch-only system).
- Mid-project, when factory-evaluation surfaces that an NFR was missed or under-specified.

## The NFR categories

The register covers nine attribute classes. Not every category applies to every project; mark `n/a` explicitly rather than omit.

### 1. Performance

- **Latency targets per critical operation** — p50, p95, p99. Specify the operation: `p99 GET /orders < 200ms; p99 POST /orders < 500ms; p99 search < 1s`.
- **Throughput targets** — peak QPS, sustained QPS. `peak 5000 QPS, sustained 1500 QPS`.
- **Time-to-first-byte and time-to-interactive** for user-facing flows (esp. frontend).

### 2. Availability

- **Uptime target** — `99.9% (8.77 hours downtime/year)` or `99.95%` or `99.99%`. Numbers matter; more nines is exponentially more expensive.
- **Maintenance windows** — allowed/disallowed; if allowed, frequency and duration.
- **Degraded-mode behavior** — what the system can keep doing when some dependency is down.

### 3. Scalability

- **Growth model** — expected user/data/load growth over 12 months and 24 months. Cite the discovery sizing.
- **Scaling axes** — vertical (bigger boxes) vs. horizontal (more boxes); which way the architecture scales.
- **Tenant scaling (if SaaS)** — number of tenants supported; per-tenant scaling characteristics.

### 4. Security

- **Authentication model** — pointers to `authn-authz` decisions.
- **Data classification** — what counts as PII, PHI, or otherwise sensitive; pointers to `compliance-privacy`.
- **Encryption requirements** — at rest, in transit, in use (if applicable); key management approach.
- **Audit logging** — what gets logged, retention, who can read.

### 5. Compliance

- **Applicable regimes** — SOC2, GDPR, HIPAA, PCI-DSS, ISO 27001, CCPA, NIST CSF, FedRAMP, others. From `compliance-privacy` resolved decisions.
- **Per-regime constraints** — specifics that affect architecture (data residency, retention, access controls).

### 6. Accessibility

- **WCAG conformance level** — AA is the typical bar for SaaS; AAA for specific regulated contexts.
- **Specific requirements** — keyboard navigation, screen reader compatibility, contrast ratios.

### 7. Observability

- **SLOs** — service-level objectives derived from performance + availability targets.
- **Coverage targets** — % of critical paths instrumented; key metrics, traces, logs.
- **Alerting thresholds** — what pages a human; what just notifies.

### 8. Disaster recovery

- **RTO (recovery time objective)** — how fast must the system be back after a disaster.
- **RPO (recovery point objective)** — how much data loss is tolerable.
- **DR topology** — multi-AZ, multi-region, cross-cloud; matches the budget.

### 9. Cost

- **Run-cost ceiling** — monthly cost target at MVP scale and at projected 12-month scale.
- **Unit economics** — cost per user, per transaction, per request, depending on the product shape.
- **Cost-attribution model** — tagging strategy; who pays for what (multi-tenant or multi-team).

## The register format

```yaml
# .project/semantic/nfr-register.md frontmatter + body

---
type: semantic
title: NFR Register
date: YYYY-MM-DD
author: product-manager
tags: [nfr, quality]
confidence: medium    # NFRs often start medium; refine as evidence arrives
---

# NFR Register

## Performance

| Attribute | Target | Operation/Scope | Verification |
|---|---|---|---|
| p99 latency | < 200ms | GET /orders | k6 load test at sustained QPS |
| p99 latency | < 500ms | POST /orders | k6 load test |
| Sustained throughput | 1500 QPS | API tier | k6 |
| Peak throughput | 5000 QPS | API tier (15-min sustained) | k6 |

## Availability

| Attribute | Target | Scope | Verification |
|---|---|---|---|
| Uptime | 99.95% | Customer-facing API | RUM + synthetic probes |
| Degraded behavior | Read-only mode | When write DB is down | Chaos experiment |

## Scalability

(... per the categories above)

## Security

(...)

## Compliance

(...)

## Accessibility

(...)

## Observability

(...)

## Disaster recovery

| Attribute | Target | Scope | Verification |
|---|---|---|---|
| RTO | 15 minutes | Production | Quarterly restore drill |
| RPO | 5 minutes | Customer data | Continuous backup verification |

## Cost

(...)
```

## Verification methods

Each NFR has a verification method — not a target without verification. Common methods:

- **Load test** (k6 / Gatling / Locust) — for performance and throughput.
- **Chaos experiment** — for availability and resilience.
- **Synthetic probes** — for availability and latency under real conditions.
- **Audit review** — for compliance and security controls.
- **Manual a11y testing** + **axe automated checks** — for accessibility.
- **Restore drill** — for RTO/RPO.
- **Cost dashboard** — for cost targets.

If an NFR can't be verified, it's either not a real target or it's a leading indicator (revisit at the verification skill).

## Decision Node parameterization

The NFR register's target numbers become the inputs to `nfr_satisfied()` predicate evaluations in workflows (see `using-praxis`). Example:

```yaml
predicate: nfr_satisfied
inputs:
  thresholds:
    p99_latency_ms: 200
    availability_target: 99.95
    rto_minutes: 15
    rpo_minutes: 5
  measured: <step output>
branches:
  true: continue
  false: revise_architecture
```

The planner reads the register and instantiates these thresholds per project.

## Mode handling (G/B)

**Greenfield.** Build the register from scratch from discovery + business context.

**Brownfield.** Read existing SLOs, runbooks, and operational history first (from `.project/operational/` and `.repo-intel/`). Many NFRs in brownfield are *measured current behavior* + a target delta ("currently p99 at 800ms; target 200ms"). Calling out the delta is essential — the SA designs around the gap, not the target alone.

## Verification

You are done when:

- [ ] NFR register at `.project/semantic/nfr-register.md` exists with all 9 attribute classes addressed (or marked `n/a` with rationale).
- [ ] Each NFR has a numeric target (or explicit "not applicable").
- [ ] Each NFR has a verification method (load test, chaos, SLO, drill, audit, etc.).
- [ ] Targets are measurable, not aspirational ("99.9% uptime" not "highly available").
- [ ] Cost-of-target documented when targets are stretch (each "9" of availability has a known cost).
- [ ] Decision Node predicates can be parameterized from the register (no soft thresholds).
- [ ] Trade-offs between attributes documented (e.g., chose 99.9% over 99.99% because of cost).

Evidence to check:
- A designer can take the register and produce an architecture justified against it.
- Architecture Challenger can attack the design using the register as the bar.
- production_go_live evidence can be assembled from register entries.

## What this skill does not do

- Functional requirements — those are `requirements-elicitation`.
- Architectural decisions to meet NFRs — those are `architecture-pattern-selection`.
- Verification execution — those are `performance-testing`, `chaos-engineering`, `compliance` audits.
- SLO/SLI implementation — that's `observability`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We'll define NFRs later when we have time." | NFRs drive architecture; defining them after architecture means redoing architecture. Now. |
| "The functional requirements are clear; that's enough." | Functional says *what*; non-functional says *how well*. A system that does the right thing too slowly fails. |
| "We'll know it when we see it." | No. NFRs are measurable targets with verification methods, or they don't exist. |
| "All NFRs at 99.99% / sub-100ms / unlimited scale." | Over-spec = over-engineer = over-cost. NFRs are deliberate trade-offs informed by business value. |
| "The principal will reject overly conservative NFRs." | Bring evidence (load model, growth curve, cost model). Conservative-with-evidence beats optimistic-without. |

## Sign-off

The NFR register is part of the **requirements_freeze** gate evidence. Targets can be revised mid-project but each revision is an ADR — silent NFR drift is one of the most expensive failure modes.
