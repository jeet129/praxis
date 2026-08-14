# Resilience Patterns — Worked Examples

Supporting code/config examples for `resilience-patterns/SKILL.md`. Pulled out here to keep the main skill file scannable; referenced by pointer from the relevant pattern sections.

## Timeout configuration in code

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

## Bulkhead pool configuration

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
