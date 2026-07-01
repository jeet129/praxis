---
name: resilience-patterns
description: "Single-component-failure-handling patterns — timeouts, retries with exponential backoff + jitter, circuit breakers, bulkheads, rate limiting, idempotency, outbox, saga. Applied during architecture (where) and implementation (how) to make services tolerant of the inevitable failures of dependencies. Distinct from `distributed-systems-patterns` (which addresses correctness across components — consensus, replication, consistency) and from `chaos-engineering` (which verifies these patterns work). Use whenever a service calls a dependency, when designing failure-mode behavior, or when investigating fragility."
---

# Resilience Patterns

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: active
dependencies:
  - architecture-pattern-selection
  - nfr-definition
  - engineering-standards
triggers:
  - "designing failure handling for a service-to-dependency call"
  - "specifying timeout, retry, or circuit breaker placement"
  - "ensuring idempotent retries for mutations"
  - "designing for graceful degradation"
  - "investigating service fragility under dependency stress"
outputs:
  - resilience design per integration point (timeout, retry, circuit breaker, fallback)
  - idempotency strategy per mutation
  - bulkhead and rate-limit placement
  - graceful-degradation policy
  - outbox/saga design for cross-service consistency
consumers:
  - solution-architect (designs resilience into the architecture)
  - backend-developer (implements per stack pack)
  - chaos-engineering (verifies these patterns)
  - architecture-challenger (reliability-challenger sub-persona attacks these)
  - distributed-systems-patterns (consumes for cross-component correctness)
references: []
```
<!-- praxis:metadata:end -->

The patterns that keep services up when their dependencies aren't. Every service in a distributed system calls dependencies (databases, caches, queues, other services, external APIs); every dependency fails sometimes; the service's behavior under that failure is a design choice.

The principle: **design for "what does this do when its dependency is slow, gone, or wrong?" — and answer is never "crash."**

## When this skill fires

- A service is being designed; for each dependency it will call, the resilience pattern is chosen.
- A new integration is being added.
- A mutation needs an idempotency strategy.
- Graceful-degradation behavior is being designed.
- A service shows fragility — failures in dependency X cascading into service-wide outage — and the fix is a resilience pattern.

## The patterns

### 1. Timeouts (universal default)

Every call to a dependency has a timeout. No exceptions.

- **No timeout** = the call holds the calling thread / connection until the OS gives up, which can be minutes. One slow dependency cascades into resource exhaustion.
- **Bad timeout** = too short, retries succeed but the timeout was the issue.
- **Good timeout** = matches the dependency's SLO + a small buffer.

Timeout placement:
- HTTP client per call type (read vs. write may have different timeouts).
- Database connection pool (connection acquire + query execution).
- Cache lookup (very short — cache is meant to be fast or absent).
- External API (longer, reflects vendor SLO).

Configuration in code:

```typescript
// Per dependency, with explicit values matching its SLO + buffer
const externalApi = {
  connectTimeoutMs: 2000,
  readTimeoutMs: 5000,    // vendor SLO: p99 < 3s; +2s buffer
  totalTimeoutMs: 7000,   // upper bound
};

const internalService = {
  connectTimeoutMs: 200,
  readTimeoutMs: 500,     // internal: p99 < 300ms; +200ms buffer
  totalTimeoutMs: 1000,
};

const cacheLookup = {
  readTimeoutMs: 50,      // very tight; cache is fast or absent
};
```

### 2. Retries with exponential backoff + jitter

Some failures are transient. Retries help — *with discipline*.

```
Without discipline:
  - Retry once
  - Retry immediately
  - Retry forever
  → these are bug patterns

With discipline:
  - Retry only retryable errors (timeout, 503, network reset)
  - Limit retry count (3 typical)
  - Exponential backoff (50ms, 100ms, 200ms, 400ms...)
  - Jitter (randomize within ±30% of computed delay)
  - Respect Retry-After header if present (HTTP)
  - Stop on non-retryable error (400-class HTTP, business-rule rejection)
```

Without jitter, mass retries synchronize and thunder onto the recovering dependency at the same instant — repeating the failure pattern.

Retry budgets (per `resilience-patterns` from `chaos-engineering`'s findings): if a service's retry rate exceeds X% of all calls for a sustained window, retries themselves are the failure mode; circuit-break instead.

### 3. Circuit breaker

When a dependency is consistently failing, retrying makes the failure worse. The circuit breaker pattern:

- **Closed** state: calls pass through; failures counted.
- **Open** state: after threshold (e.g., 50% failures over 10s), calls fail-fast without hitting the dependency. The dependency gets breathing room.
- **Half-open** state: after cool-down (30s typical), allow a single test call. If it succeeds, close; if it fails, open again.

Placement:

- Around every meaningful dependency call (per service-to-service, per database-pool, per external API).
- Per-host when the dependency is sharded (one bad shard shouldn't take out the whole circuit).
- Configurable thresholds per call type.

Libraries:
- Java: Resilience4j (replaces deprecated Hystrix).
- Node: opossum.
- Python: pybreaker.
- Service mesh (Istio): circuit breakers as platform feature.

### 4. Bulkhead

Isolate failure domains so that one dependency's degradation doesn't exhaust resources serving other dependencies.

Examples:

- **Separate connection pools per downstream service** — if downstream A slows down, the thread pool serving A fills up; but the pool serving B is untouched.
- **Separate thread pools per call type** — async background work in one pool, request-response in another.
- **Per-tenant quotas in multi-tenant systems** — one heavy tenant doesn't starve others.

Configuration:

```yaml
order_service_pool:
  max_size: 20
  queue_size: 100
billing_service_pool:
  max_size: 20
  queue_size: 100
notification_service_pool:
  max_size: 10
  queue_size: 50
external_payment_pool:
  max_size: 5      # smaller; external API has its own rate limit
  queue_size: 20
```

Without bulkheads, all dependencies share the same pool → the slowest dependency consumes everything.

### 5. Rate limiting (incoming and outgoing)

Two directions:

**Incoming rate limiting** — defends the service from being overwhelmed:
- Per-tenant rate limits prevent noisy-neighbor scenarios.
- Per-IP rate limits prevent abuse.
- Per-endpoint rate limits per the endpoint's actual capacity.
- Implementation: ingress (nginx, envoy, cloud-native) + application-level (token bucket via Redis).

**Outgoing rate limiting** — respects the dependency's capacity:
- Per dependency, per service: enforce the client-side rate consistent with the dependency's published limits.
- Especially critical for external APIs with hard rate limits (payment providers, SaaS APIs).
- Implementation: token bucket / leaky bucket pattern.

### 6. Idempotency

Every mutation must be safe to retry — because retries *will* happen (network glitches, timeouts, deliberate retries). Strategies:

**Idempotency by design** — the operation is intrinsically safe to repeat:
- `PUT /orders/{id}` with the full state — repeatable; same input produces same state.
- `DELETE /orders/{id}` — idempotent (deleting again is no-op).

**Idempotency key** — explicit deduplication for non-idempotent operations:
- Client sends `Idempotency-Key: <uuid>` with the request.
- Server checks the key against recently-seen keys; returns cached response on hit.
- Window: 24 hours typical; project-specific.
- Storage: in-memory cache for hot paths; persistent store for critical mutations (payments).

**Natural-key deduplication** — the operation has an inherent unique identifier:
- `client_order_ref` unique constraint on the orders table.
- Duplicate insert violates constraint; service detects and returns the existing record.

Every mutation in the API has one of these. Per `api-design`'s discipline.

### 7. Outbox

For cross-service consistency: a service that needs to *both* persist locally and publish an event must not do these in two separate transactions (the second can fail leaving inconsistent state).

The outbox pattern:

```
WITHIN ONE TRANSACTION:
  1. INSERT INTO orders (...) VALUES (...);
  2. INSERT INTO outbox (event_type, payload) VALUES (...);
COMMIT;

ASYNCHRONOUSLY, A BACKGROUND PROCESS:
  3. SELECT * FROM outbox WHERE published_at IS NULL;
  4. Publish to message bus.
  5. UPDATE outbox SET published_at = NOW() WHERE id = ...;
```

The outbox row is written in the same transaction as the business state. The publisher is at-least-once (idempotent consumers handle duplicates).

This eliminates the "wrote to DB but failed to publish" inconsistency that plagues naive dual-writes.

### 8. Saga

For long-running, cross-service workflows that need to maintain consistency without distributed transactions, the saga pattern decomposes the workflow into local transactions per service + compensating actions for rollback.

```
Workflow: Place Order
  Step 1: Reserve inventory (Inventory service)
    → Compensation: Release reservation
  Step 2: Authorize payment (Payment service)
    → Compensation: Void authorization
  Step 3: Create shipment (Shipping service)
    → Compensation: Cancel shipment

If Step 3 fails:
  - Run Step 2's compensation (void authorization)
  - Run Step 1's compensation (release reservation)
```

Two implementations:
- **Choreography** — services react to events; no central coordinator. Simpler but harder to reason about.
- **Orchestration** — a saga orchestrator (often a workflow engine like Temporal, Camunda) coordinates. More visible state; preferred for complex sagas.

Sagas are inherently eventually-consistent. They don't *prevent* failures; they ensure the system reaches a consistent state (success or compensated-rollback) regardless of mid-workflow failures.

### 9. Graceful degradation

When a dependency is down or slow, what does the service *still* do?

```
Catalog service: "show me products"
  Happy path: real-time inventory check + personalized recommendations
  Inventory service down: show products without inventory levels
  Recommendations service down: show products without personalization
  Both down: show a cached static catalog page

Order service: "place an order"
  Happy path: real-time payment auth + immediate confirmation
  Payment service slow: queue the order; confirm via async email
  Inventory check slow: accept the order; verify async
```

The discipline: catalog the dependencies; for each, decide what degradation is acceptable; design for it explicitly.

### 10. Health checks for the integration

The three K8s probes from `platform-k8s`:

- **Liveness** — "am I still running?" Don't include dependency calls — a slow dependency shouldn't restart pods.
- **Readiness** — "am I ready to serve traffic?" Include dependency calls for *critical* dependencies; exclude for non-critical (a recommendation service can serve when its DB is slow but can't when its core data store is down).
- **Startup** — "am I done starting?" Includes initial connections, cache warming.

Designed at the resilience-pattern level; implemented at the stack-pack level.

## Per-integration design template

For each dependency the service calls:

```markdown
## Dependency: External Payment API

- **Timeout**: connect 2s; read 5s; total 7s.
- **Retries**: 2 retries with exponential backoff (100ms, 200ms) + 30% jitter. Retry on: 429, 503, network errors. No retry on: 400, 401, 402 (payment declined is final).
- **Circuit breaker**: opossum; threshold 50% failure in 30 reqs / 30s; cool-down 60s.
- **Bulkhead**: separate connection pool (max 5, queue 20).
- **Idempotency**: idempotency-key from client; 24h window; stored in Redis.
- **Rate limit (outgoing)**: respect vendor's 100 RPS limit (token bucket via Redis).
- **Fallback (degradation)**: queue payment for async retry; respond to customer with "processing" state; reconcile asynchronously.
- **Observability**: per-call duration, success/failure tags, circuit-breaker state metric.
```

## Outputs

| Output | Location |
|---|---|
| Per-integration resilience design | inline in service's design doc; ADR for non-obvious choices |
| Idempotency policy | per mutation in the API design |
| Bulkhead config | in the service's config layer |
| Circuit breaker config | per integration in code |
| Graceful-degradation policy | service's runbook (per `incident-runbook`) |

## Mode handling (G/B)

**Greenfield.** Design resilience into every integration from day one.

**Brownfield.** Audit existing integrations; common findings: no timeouts, no retries, no circuit breakers, dual-writes without outbox. Prioritize by NFR-bearing surface (the critical user paths first); each integration's resilience is its own slice if non-trivial.

## What this skill does not do

- Verify the patterns actually work — that's `chaos-engineering`.
- Define correctness across components — that's `distributed-systems-patterns`.
- Implement per stack — that's the stack pack patterns.
- Run on-call — that's `incident-runbook`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Our deps are reliable; we don't need circuit breakers." | "Reliable" means 99.9%. At 1000 QPS that's 1 failure/sec. Without breakers, those failures cascade. |
| "Timeouts will be set at the load balancer." | Load balancer timeouts catch infra failures; in-process timeouts catch app-level hangs. Both needed. |
| "Retries are simple — just wrap in a loop." | Naive retries amplify outages (every client retries simultaneously). Use exponential backoff + jitter; budget the retries. |
| "Bulkheads are over-engineering for one service." | Bulkheads protect one tenant's traffic from another's outage. Necessary the moment you have shared resources. |
| "Graceful degradation can be added later." | Graceful degradation requires designing the fallback paths; bolting them on later means designing twice. |
| "Health checks tell us the service is OK." | Liveness ≠ readiness ≠ business-readiness. Three different checks for three different orchestration responses. |
| "We don't have an SLO; resilience targets are vague." | Resilience targets follow from SLOs (per `nfr-definition`). No SLO = no target = no informed decisions. |

## Verification

You are done when:

- [ ] Every external call has a timeout (no implicit-infinite).
- [ ] Critical-path external calls have circuit breakers configured (state + thresholds + recovery).
- [ ] Retry policy is documented per call class (which retries; how many; backoff; jitter).
- [ ] Bulkheads identified for tenant / class-of-traffic isolation.
- [ ] Graceful degradation paths designed for each critical dependency (what serves when X is down).
- [ ] Liveness + readiness + (where applicable) startup health checks defined.
- [ ] Resilience targets tied to NFRs; deviation from NFR documented per ADR.
- [ ] Chaos exercise (per `chaos-engineering`) verified at least one fault-injection scenario.

Evidence to check:
- Logs show circuit-breaker state transitions, not just hit/miss counts.
- Retry storm test: with all retries firing, system degrades gracefully not catastrophically.
- Synthetic readiness probe verifies actual business-readiness (DB pool, cache warm, etc.).

## Anti-patterns

- No timeouts (calls hang indefinitely).
- Infinite retries.
- Retries without jitter (synchronized thundering herd).
- Circuit breaker with thresholds that never trip.
- One shared connection pool for all dependencies.
- Mutations without idempotency strategy.
- Dual-writes to DB + message bus without outbox.
- Health checks that include all dependencies in liveness (restart-storm risk).
- "Graceful degradation" stated but never tested under load.
- Resilience patterns implemented but never verified by chaos engineering.
