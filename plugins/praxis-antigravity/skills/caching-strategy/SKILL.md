---
name: caching-strategy
description: "Deliberate caching decisions: when to cache (and when caching is masking a query or design problem that should be fixed instead), which layer to cache at (client/CDN/app/distributed/DB), invalidation strategy (TTL, event-driven, write-through/behind, cache-aside), stampede protection, key design, and staleness budgets tied to NFRs. Use whenever a slow read path is being addressed, a cache is being introduced or its invalidation is being designed, or a cache-related bug (stale data, stampede, unbounded growth) is being diagnosed. Distinct from `frontend-performance` (browser/CDN-specific asset caching and rendering) and `data-modeling` (designs the source-of-truth schema; this skill layers a derived, invalidatable copy on top of it)."
---

# Caching Strategy

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: experimental
dependencies:
  - nfr-definition
  - observability
triggers:
  - "a read path is slow and caching is being considered"
  - "introducing a new cache layer or cache-aside pattern"
  - "designing cache invalidation for a data type"
  - "diagnosing stale-data or cache-stampede incidents"
  - "defining the staleness budget for a cached value"
outputs:
  - caching decision record (cache vs. fix-the-query, with rationale)
  - cache layer + invalidation strategy per data type
  - key design + namespacing convention
  - staleness budget tied to the relevant NFR
  - cache hit-ratio SLI + alert thresholds
consumers:
  - backend-developer (implements the cache-aside/write-through logic)
  - frontend-developer (implements client-side and CDN cache headers)
  - platform-sre (owns distributed cache infrastructure and capacity)
  - observability (receives hit-ratio and staleness metrics)
references: []
```
<!-- praxis:metadata:end -->

Caching trades correctness (a cache can lie) for speed. That trade is only worth making deliberately, per data type, with an explicit invalidation strategy and a staleness budget — not reflexively bolted onto every slow endpoint.

## When this skill fires

- A read path is slow and caching is proposed as the fix.
- A new cache layer (in-process, Redis/Memcached, CDN) is being introduced.
- Cache invalidation for a data type is being designed or is producing stale-data bugs.
- An incident involves a cache stampede, unbounded cache growth, or serving stale data past its acceptable window.
- The staleness budget for a cached value needs to be tied to its NFR.

## Step 1: should this be cached at all?

Before choosing a strategy, rule out that caching is masking a fixable problem:

- **Is the query itself the bottleneck?** Missing index, N+1 query, unbounded result set, chatty round-trips — fix these first. A cache in front of a bad query hides the problem until the cache misses (cold start, invalidation, capacity eviction) and the bad query hits full traffic anyway.
- **Is this data cheap to compute correctly on every request?** If so, caching adds invalidation risk for marginal gain — don't.
- **Does correctness matter more than latency here?** Financial balances, permission checks, inventory counts at checkout — these need care; caching them requires an explicit staleness budget signed off against the NFR, not a default TTL picked without thought.

Only once the underlying access pattern is confirmed to be legitimately expensive (and not just unoptimized) does the question become *which* caching strategy.

## Layers

| Layer | What it caches | Invalidation control | Typical staleness |
|---|---|---|---|
| **Client** | API responses, computed UI state | Weakest — you control TTL/headers, not eviction timing | Seconds–minutes |
| **CDN** | Static assets, cacheable API responses at the edge | Cache-Control headers + purge API | Minutes–hours |
| **App (in-process)** | Hot, small, per-instance data (config, feature flags, lookup tables) | Full control, but not shared across instances | Seconds–minutes |
| **Distributed (Redis/Memcached)** | Shared computed results, session data, rate-limit counters | Full control, shared across instances | Configurable per key |
| **DB (query cache, materialized views)** | Expensive query results | Tied to the DB's own refresh/invalidation mechanism | Depends on refresh strategy |

Pick the layer closest to the consumer that can still meet the staleness budget — client/CDN caching is cheapest and fastest when data can tolerate looser consistency; distributed caching is needed when data must be consistent across instances and correctness matters more.

## Invalidation strategies

| Strategy | Mechanism | Trade-off |
|---|---|---|
| **TTL (time-to-live)** | Entry expires after a fixed duration | Simple; staleness window is bounded but data can be wrong for up to the full TTL |
| **Event-driven** | Write path publishes an invalidation/update event; cache reacts | Tighter staleness bound; adds coupling between writer and cache, and a missed event means indefinitely stale data unless a TTL backstop exists |
| **Write-through** | Write goes to cache and DB synchronously, in the same request | Cache is never stale for writes through this path; adds write latency |
| **Write-behind** | Write goes to cache immediately, DB write is async | Fast writes; risk of data loss if the async write fails before flushing |
| **Cache-aside (lazy load)** | App checks cache first; on miss, reads DB and populates cache | Most common default; first request after eviction pays the full DB cost |

Default to **cache-aside with a TTL backstop even on event-driven invalidation** — the TTL catches missed invalidation events so staleness is always bounded, never unbounded.

## Stampede protection

A cache stampede happens when a hot key expires and many concurrent requests all miss simultaneously, hitting the backing store at once. Mitigations:

- **Request coalescing / single-flight.** Only one request per key recomputes on miss; concurrent requests wait for that result instead of each hitting the DB.
- **Early/probabilistic refresh.** Refresh the value slightly before TTL expiry (jittered), so it rarely reaches a hard miss under load.
- **Jittered TTLs.** Add randomness to TTLs for keys created in bulk at the same time, so they don't all expire in the same instant.
- **Stale-while-revalidate.** Serve the stale value while refreshing in the background, when the staleness budget allows it.

## Key design and namespacing

- Keys are namespaced by data type and version: `<service>:<entity>:<id>:<schema-version>` — the version segment lets you invalidate en masse on a schema change without a manual sweep.
- Keys encode every input that affects the cached value (locale, tenant ID, feature-flag variant) — a missing dimension causes cross-contamination between users/tenants.
- Multi-tenant systems: tenant ID is always part of the key, never assumed from context — see `multi-tenancy` for isolation requirements this feeds into.
- Document the key schema in one place; ad hoc key formats scattered across the codebase make bulk invalidation and debugging impossible.

## Consistency trade-offs and staleness budgets

Every cached data type gets an explicit staleness budget, derived from its NFR (`nfr-definition`), not a default:

| Data type example | Staleness budget | Rationale |
|---|---|---|
| Product catalog listing | Minutes | Low cost of being briefly stale |
| User session/auth state | Near-zero | Security-sensitive; stale = wrong access decisions |
| Inventory count at checkout | Near-zero, or read-through with lock | Overselling is a business-critical correctness failure |
| Dashboard aggregate metrics | Minutes–hours | Explicitly analytical, staleness is expected and labeled |

State the budget next to the cache implementation, not just in a design doc — a comment or config constant that says "max staleness: 5 min" so the next engineer doesn't silently widen the TTL.

## Cache observability

- **Hit ratio** is a first-class SLI per cache/key-space, not just infra dashboard noise — a sustained drop signals either a capacity problem or an invalidation bug flooding the cache with misses.
- **Eviction rate** and **memory pressure** are alerted on for distributed caches — silent eviction under memory pressure degrades hit ratio without an obvious cause.
- **Staleness violations** (serving data older than the budget) are measurable and alerted where the mechanism allows it (e.g., event-driven invalidation with a dead-letter or lag metric).
- Wire these into `observability`'s standard dashboards, not a one-off chart nobody checks.

## Mode handling (G/B)

**Greenfield.** Decide the caching strategy per data type as part of the initial architecture, with the staleness budget set alongside the NFR it serves — don't defer caching decisions to a later performance-fix pass if the access pattern is predictably hot from day one.

**Brownfield.** Existing caches often have no documented invalidation strategy or staleness budget — reverse-engineer and document the current behavior before changing it. A cache that's been silently serving stale data for years may have workarounds built around its staleness elsewhere in the system; changing invalidation behavior without checking for those is a regression risk, not a pure improvement.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "This query is slow, let's just cache it." | Check whether the query is unoptimized first. Caching a bad query hides it until the cache can't save you. |
| "TTL of 5 minutes is a reasonable default everywhere." | Staleness tolerance varies wildly by data type. Set the budget from the NFR, not a copy-pasted default. |
| "We don't need stampede protection, traffic isn't that high." | Stampedes are triggered by concurrency at the moment of expiry, not average traffic — a single popular key can stampede at any traffic level. |
| "Cache invalidation is hard, let's just use a short TTL and call it done." | A short TTL is a legitimate strategy — but state it as a deliberate choice with a documented staleness budget, not a way to avoid designing invalidation. |
| "Multi-tenant keys don't need the tenant ID, we scope by service already." | Service-level scoping isn't tenant isolation. Omitting tenant ID from the key is a data-leak risk. |

## Verification

You are done when:

- [ ] A caching decision record exists showing the underlying query/access pattern was checked before choosing to cache.
- [ ] The cache layer and invalidation strategy are chosen explicitly per data type, not defaulted.
- [ ] Every cached data type has a stated staleness budget tied to its NFR.
- [ ] Stampede protection is in place for any key with realistic concurrent-miss exposure.
- [ ] Key design includes all dimensions that affect the value (tenant, locale, version) and is documented in one place.
- [ ] Hit ratio and staleness are wired into `observability` as monitored SLIs.

Evidence to check:
- A cache-related incident can be diagnosed from hit-ratio/eviction dashboards without reading application code first.
- No cached data type is missing a staleness budget in its design doc or code comment.

## Anti-patterns

- Adding a cache as the first response to any slow endpoint, without profiling the actual bottleneck.
- Using the same default TTL for every data type regardless of correctness sensitivity.
- Cache keys missing tenant/locale/variant dimensions, causing cross-contamination.
- No stampede protection on a key known to be hot and shared across many concurrent requests.
- Treating cache hit ratio as a vanity metric instead of an alertable SLI.

## What this SKILL does NOT do

- Design the source-of-truth schema — that's `data-modeling`; this skill layers a derived, invalidatable copy on top of an already-modeled store.
- Configure browser/CDN-specific asset caching, bundling, or rendering strategy — that's `frontend-performance`; this skill covers the general layered-caching decision, of which CDN is one layer.
- Set the underlying latency/availability targets — that's `nfr-definition`; this skill derives staleness budgets from those targets, it doesn't set them.
- Provision or size the distributed cache infrastructure — that's `platform-sre`'s capacity work, informed by this skill's key design and expected hit ratio.
