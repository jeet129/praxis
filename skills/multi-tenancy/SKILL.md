---
name: multi-tenancy
description: SaaS tenancy model design — silo / pool / bridge — with tenant isolation, per-tenant data, noisy-neighbor controls, tenant-aware observability, tenant-context propagation, and tenant-aware billing. Solution Architect runs this once for any multi-tenant project; Backend Developer applies the tenant context across every layer.
---

# Multi-Tenancy


<!-- praxis:description:full -->
## Full description

SaaS tenancy model design — silo / pool / bridge — with tenant isolation, per-tenant data, noisy-neighbor controls, tenant-aware observability, tenant-context propagation, and tenant-aware billing. Solution Architect runs this once for any multi-tenant project; Backend Developer applies the tenant context across every layer. Use whenever a project is multi-tenant SaaS, when designing isolation strategy, when investigating tenant cross-talk, or when adding per-tenant features (limits, billing, observability).

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: active
dependencies:
  - architecture-pattern-selection
  - authn-authz
  - data-modeling
  - resilience-patterns
triggers:
  - "designing tenancy model for a new SaaS project"
  - "selecting silo / pool / bridge isolation strategy"
  - "implementing tenant-context propagation through code"
  - "designing noisy-neighbor controls"
  - "designing per-tenant observability and billing"
  - "investigating tenant cross-talk"
outputs:
  - tenancy model decision + ADR (silo / pool / bridge / hybrid)
  - isolation strategy per data store (per-tenant DB / per-tenant schema / row-level)
  - tenant context propagation design (request → service → data layer)
  - noisy-neighbor controls (per-tenant rate limits, quotas)
  - tenant-aware observability design (logs / metrics / traces tagged with tenant_id)
  - tenant-aware billing model (per-tenant usage capture)
consumers:
  - solution-architect (primary author)
  - backend-developer (implements tenant context)
  - data-modeling (consumes for schema decisions)
  - authn-authz (consumes for tenant-scoped authorization)
  - observability (consumes for tenant tagging)
  - cost-finops (consumes per-tenant attribution)
references: []
```
<!-- praxis:metadata:end -->

A SaaS product serves multiple customers (tenants) from shared infrastructure. The tenancy model defines *how shared*: same database? same schema? same row table? Each tier on this spectrum trades isolation against cost.

The principle: **pick the model deliberately per data class, propagate tenant context through every layer, and assume tenants are adversarial to each other.**

## When this skill fires

- A new SaaS project is being designed and the tenancy model is being chosen.
- An existing system is being extended with multi-tenancy (often a brownfield migration).
- A specific data class has different isolation requirements than others (mixed models).
- A tenant cross-talk incident is being investigated.
- Per-tenant features (rate limits, observability, billing) are being added.

## The three tenancy models

| Model | Isolation | Density | Cost | Use when |
|---|---|---|---|---|
| **Silo** | One full stack per tenant. | Low (1 tenant : 1 stack). | High. | Highly-regulated; single-tenant per contract; small number of large tenants. |
| **Pool** | All tenants share infrastructure. | Highest. | Lowest. | Standard SaaS with many small-to-medium tenants. |
| **Bridge** | Per-tenant isolation for *some* resources; shared for others. | Medium. | Medium. | Tier-based products; enterprise tier on isolated DB, others pooled. |

**Default for new SaaS: Pool.** Move to bridge when specific tenants warrant or specific data classes demand it.

### Silo

Each tenant gets a dedicated stack — separate database, separate Kubernetes namespace, possibly separate region. Maximum isolation; no shared blast radius.

Implementation:
- IaC parameterized per tenant; provisioning a new tenant runs a per-tenant deployment.
- Tenant identity often binds to subdomain or path prefix (`customer-a.example.com`, `example.com/customer-a/...`).
- Database per tenant; migrations applied per tenant.

Costs: provisioning overhead, fixed per-tenant cost, per-tenant operational complexity (incident response is per-tenant).

Use when: single-tenant contracts; HIPAA Business Associate Agreement with strict isolation; sovereignty requirements; the product's economics support high per-tenant prices.

### Pool

All tenants share infrastructure. Data is tagged with tenant identity; the application enforces isolation.

Implementation:
- Every table has a `tenant_id` column (typically the leading column of compound indexes).
- Every query is tenant-scoped at the application layer.
- Row-level security (Postgres RLS) or equivalent provides defense-in-depth at the database level.
- Application enforces tenant context propagation through every layer.

Costs: tenant context discipline must be perfect; one missing scope is a data-leak vulnerability.

Use when: many small-to-medium tenants; product economics require shared infrastructure.

### Bridge

Hybrid. Per-tenant for some resources (often the database for enterprise tier), shared for others (compute, message bus).

Implementation:
- Per-tenant databases (or schemas) for sensitive data.
- Shared application tier with tenant routing.
- Tier-based: enterprise tier → silo-like isolation; standard tier → pool.

Costs: complexity of two patterns at once; routing logic.

Use when: tier-based pricing with isolation as a premium feature; one or two large tenants in a sea of small tenants.

## Isolation per data class

The model can vary *per data store*. A common pattern:

- **Primary application database**: pool (row-level, all tenants share).
- **Secrets store**: pool with per-tenant paths.
- **Object storage**: bridge — per-tenant bucket or prefix; key validated on every access.
- **Search index**: pool with tenant-scoped indices or per-tenant indices.
- **Cache**: pool with tenant-prefixed keys.
- **Background job queue**: pool with per-tenant queues for fair-share scheduling.

Document the model per data class explicitly.

## Tenant context propagation

The tenant_id must flow through every layer:

```
Inbound request (HTTP)
  ↓ tenant identified from JWT / session / subdomain
Request handler
  ↓ tenant_id set in MDC / contextvars / AsyncLocalStorage
Application service
  ↓ every method receives tenant_id (explicit parameter; never thread-local-only)
Data layer
  ↓ every query includes WHERE tenant_id = $1 (enforced; defense-in-depth via RLS)
Outbound calls
  ↓ tenant_id forwarded in headers
Background jobs
  ↓ tenant_id captured at enqueue; retrieved on dequeue
```

**Tenant-context discipline** — `tenant_id` is a *required parameter* of every domain operation. Methods that take no tenant_id are either tenant-agnostic (rare) or buggy (common).

### Row-level security

Postgres RLS as defense-in-depth:

```sql
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_tenant_isolation ON orders
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

The application sets `app.current_tenant_id` on every connection (per request). RLS rejects any query that doesn't match — an application bug that forgets the `WHERE tenant_id` becomes a 0-row result instead of a cross-tenant leak.

## Noisy-neighbor controls

In pool model, one heavy tenant can starve others. Controls:

- **Per-tenant rate limits** at ingress: each tenant has a calls/sec budget.
- **Per-tenant quotas** on resource consumption: max storage, max users, max API calls/month.
- **Per-tenant queues with fair-share scheduling**: background work fairly shares processing.
- **Bulkheads in connection pools**: a tenant exceeding its DB connection budget is throttled, not the system.
- **Auto-throttling**: detect a tenant consuming > X% of total resources; degrade gracefully (slower responses, lower priority) before it impacts others.

Without these, the first big customer the product wins becomes the de facto resource hog and degrades everyone else.

## Tenant-aware observability

Every observability signal is tagged with tenant_id:

```
log.info("order placed", order_id=oid, tenant_id=tid, amount=amt)
metric: order_placed{tenant="acme-corp"} +1
trace span: tenant_id="acme-corp" attribute
```

Dashboards filter by tenant. SLOs are global *and* per-tenant (the largest tenants get individual SLO tracking).

Investigating a tenant's complaint is a query, not a forensic exercise.

## Tenant-aware billing

Per-tenant usage is captured per the billing model:

- **Per-seat**: count of users per tenant per period.
- **Per-API-call**: API calls per tenant per period.
- **Per-storage**: storage consumed per tenant.
- **Per-feature**: feature flags / tier enabled per tenant.

Usage events flow to a billing system (Stripe / Chargebee / metered-billing SaaS or in-house). The application emits usage events synchronously with the action (per `data-pipeline`-style outbox for reliability).

## The hard rules

- **Every cross-table query has tenant_id in the predicate**. No exceptions outside explicit admin operations.
- **Every cross-service call carries tenant_id**.
- **Every background job carries tenant_id**.
- **Every log line carries tenant_id**.
- **Admin operations are explicitly marked** and audit-logged with the admin's identity + the targeted tenant.

## Outputs

| Output | Location |
|---|---|
| Tenancy model decision + ADR | `.project/decision/adr-NNN-tenancy-model.md` |
| Per-data-class isolation | `.project/semantic/tenancy-isolation.md` |
| Tenant context propagation design | `.project/operational/tenant-context.md` |
| Noisy-neighbor controls | inline in `iac` (rate limits at ingress) + application config |
| Tenant-aware observability | inline in `observability` instrumentation |
| Billing model | `.project/semantic/billing-model.md` |

## Mode handling (G/B)

**Greenfield.** Design tenancy from day one. Tenant_id everywhere; RLS enabled; routing established.

**Brownfield.** Audit for missing tenant scoping. Common findings: queries missing `WHERE tenant_id`; admin tools that don't scope by tenant; cross-tenant leaks in cache keys. Each finding is a security issue; route through Security Reviewer + `security_finding_waiver` gate.

## What this skill does not do

- Authentication and authorization at the identity level — that's `authn-authz` (this skill consumes it for tenant-scoped authz).
- Database schema decisions per-table — that's `data-modeling`.
- Per-tenant infrastructure provisioning — that's `iac` (consumes this skill's decisions).
- Billing system integration mechanics — that's the application implementation.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We add tenant_id to tables; we're multi-tenant." | Tenant_id without enforcement is a hope. Row-level security, query-time injection, or per-tenant DB are the actual enforcement. |
| "Pool model is fine for everyone." | Pool tenants share fate. One tenant's noisy neighbor problem is everyone's problem. Decide per tenant class. |
| "Silo model is too expensive." | At small scale, yes. At regulated scale, the only viable answer. The cost is buying the per-tenant guarantee. |
| "Tenant isolation is a DB problem." | Isolation is end-to-end: DB, cache, queue, log streams, metrics, dashboards. Anywhere a tenant identifier touches, isolation is required. |
| "We don't need per-tenant rate limits." | One tenant can starve everyone. Per-tenant quotas are the cost-control mechanism. |
| "Tenant onboarding is just a row in a table." | Onboarding requires: data structures provisioned, quotas set, monitoring scoped, billing wired, compliance attestation gathered. Document the procedure. |

## Verification

You are done when:

- [ ] Tenancy model decided (silo / pool / bridge / hybrid) per data store.
- [ ] Tenant identifier present at every layer: request, service, DB, cache, queue, log line, metric label.
- [ ] Row-level security or query-time enforcement configured.
- [ ] Noisy-neighbor controls documented (per-tenant rate limits, quotas, resource caps).
- [ ] Per-tenant observability: dashboards filter by tenant; alerts scoped.
- [ ] Tenant lifecycle procedures: onboard, offboard, suspend, archive — all documented.
- [ ] Cross-tenant access (admin / support) explicitly designed with audit trail.

Evidence to check:
- Pen-test or controlled test: tenant A cannot read tenant B's data through any code path.
- One tenant's traffic spike does not breach SLOs for other tenants (rate limit verification).
- Audit log records every cross-tenant access by an operator.

## Anti-patterns

- "We have tenant_id" stated; not enforced everywhere.
- Admin tools that bypass tenant scoping silently.
- RLS not enabled (no defense in depth).
- Cache keys without tenant prefix (cross-tenant cache hits).
- Background jobs without tenant_id (cross-tenant processing).
- Logs without tenant tagging.
- No noisy-neighbor controls (first big customer hurts everyone).
- Tenant context via thread-local only (lost in async chains).
- Per-tenant subdomains without matching application-level tenant validation.
- Tenancy model changed mid-project as a panic response (silo → pool migration is a multi-quarter project).
