---
name: observability
description: "The three pillars + correlation, instrumented per service. Structured logging, RED/USE metrics, distributed tracing (OpenTelemetry-first), SLI/SLO/error-budget definition, dashboards, and alerting that pages on symptoms not causes. Developers add the instrumentation hooks as they write the code; SRE wires the collectors and dashboards . Use whenever new services or endpoints are being implemented, when defining SLOs from NFRs, or when troubleshooting requires the instrumentation that isn't there yet. Pushy trigger because retrofitting observability is dramatically more expensive than adding it upfront."
---

# Observability

<!-- praxis:metadata:begin -->
```yaml
capability: operations
domain: cross-cutting
state: active
dependencies:
 - engineering-standards
 - nfr-definition
triggers:
 - "implementing a new service or endpoint"
 - "defining SLOs and error budgets from the NFR register"
 - "designing dashboards and alerts for a new service"
 - "instrumenting structured logging in code"
 - "adding distributed tracing to a request path"
 - "troubleshooting a production issue (often surfaces gaps)"
outputs:
 - instrumentation hooks in code (logs, metrics, traces)
 - SLO/SLI document per service
 - dashboard specifications
 - alert rules tied to SLOs (page on symptoms, not causes)
consumers:
 - backend-developer (adds instrumentation)
 - frontend-developer (adds RUM + error tracking)
 - platform-sre (wires collectors and stack)
 - reliability-dr (consumes SLOs)
 - incident-runbook (uses dashboards in response)
references:
 - opentelemetry.md
 - prometheus-grafana.md
 - loki.md
 - tempo.md
 - datadog.md
 - cloud-native.md
```
<!-- praxis:metadata:end -->

Three pillars + the connective tissue between them: **structured logs** that say what happened, **metrics** that show how often and how fast, **traces** that link them across services, and **correlation IDs** that thread one request through all three.

The principle: **alert on symptoms (the user experience), not causes (the metric that breached).** A page that says "CPU is at 95%" is operationally useless if the latency SLO is still met. A page that says "p99 checkout latency exceeded 500ms — error budget burning at 5x" tells the on-call exactly what's happening.

This skill produces *instrumentation in code* (developers add it as they write) and *SLO/dashboard specs* (SRE wires the collectors -4). Code sets the hooks; Practice deepens the practice.

## When this skill fires

- A new service or endpoint is implemented — developers add the instrumentation hooks.
- SLOs are being defined from the NFR register — SA + SRE run this skill to translate NFR numbers into SLI definitions.
- A dashboard or alert is being designed — SRE specifies what's measured and what triggers a page.
- A production incident reveals an observability gap — backfill the missing instrumentation as part of the postmortem follow-up.

## The three pillars

### Logs

- **Structured.** Key-value pairs, not string concatenation. `log.info("order placed", order_id=oid, tenant=tid, amount=amt)`.
- **Levels mean what they say.** `DEBUG` development noise; `INFO` state transitions worth observing in prod; `WARN` recoverable anomalies; `ERROR` failures. `FATAL` for unrecoverable startup failures only.
- **No PII.** Emails, phone numbers, payment data, SSNs, access tokens are redacted at the log boundary. Per `compliance-privacy`.
- **Correlation ID** on every log line. Tenant ID where applicable. No exceptions.
- **One logger per module.** The language's structured logger (Logback + logstash-encoder in Java; pino in Node; structlog in Python).

### Metrics

Two complementary metric vocabularies, both useful:

**RED — for request-driven services:**
- **Rate** — requests per second per endpoint.
- **Errors** — error rate per endpoint (typically % of requests returning 5xx or domain-error responses).
- **Duration** — request latency distribution per endpoint (p50, p95, p99).

**USE — for resource pools:**
- **Utilization** — % of resource in use (CPU, memory, connection pool).
- **Saturation** — queued / pending work waiting on the resource.
- **Errors** — error count of the resource (e.g., connection pool exhausted, OOM kills).

Apply both. The user sees the RED metrics; the operator needs the USE metrics to understand *why* RED metrics deviated.

**Metric naming convention:** `<domain>_<entity>_<measurement>_<unit>` (Prometheus style). `billing_orders_placed_total` (counter), `billing_orders_latency_seconds` (histogram). Labels for dimensions (endpoint, status_code, tenant_tier).

### Traces (distributed tracing)

- **OpenTelemetry-first.** Cross-vendor standard; collectors fan out to the chosen backend (Tempo, Jaeger, Datadog APM, etc.).
- **Auto-instrumentation** where the framework supports it (Spring Boot's OpenTelemetry starter; Node's `@opentelemetry/auto-instrumentations-node`; Python's opentelemetry-instrumentation).
- **Manual spans** for business-meaningful operations the framework can't infer (e.g., a domain workflow with multiple substeps).
- **Trace IDs** are the correlation ID — propagated via W3C Trace Context headers and into the logging context.

## The fourth pillar: correlation

The pillars without correlation are three disconnected piles of data. With it, they're a single observable system.

Every request gets a correlation ID (from `traceparent` header, or generated at the ingress if absent). The ID flows:

- Into the **logger's MDC / contextvars / AsyncLocalStorage** so every log line carries it.
- Into the **trace span** so the span graph is queryable by correlation ID.
- Into **outbound requests** (propagated to downstream services).
- Into **error responses** to the client so a support ticket links to internal context.

Without correlation, debugging a multi-service issue is excavation. With it, it's a lookup.

## SLI / SLO / error budget

From the NFR register's targets:

**SLI (Service Level Indicator)** — the measurement. A specific metric that tracks user experience.
- Example: "Fraction of `POST /orders` requests returning 2xx in under 500ms, measured over a rolling 5-minute window."

**SLO (Service Level Objective)** — the target for the SLI.
- Example: "99.9% of `POST /orders` requests succeed within 500ms over any rolling 30-day window."

**Error budget** — the inverse of the SLO. A 99.9% SLO permits 0.1% failures = ~43 minutes of "bad" per month.

Error budgets drive prioritization. If the budget is burning fast, slow down feature work and invest in reliability. If the budget is mostly intact, ship more features. This is `reliability-dr`'s territory but the *budget definition* lives here.

**Document per service:** which user journeys are SLI-tracked, the SLI definitions, the SLO targets, the error budget, the policy (what happens when budget burns at rate X).

## Dashboards

Two dashboard tiers per service:

**Tier 1 — "Is the user happy?"**
- The four RED metrics by endpoint.
- The SLO status (am I meeting it? error budget remaining).
- Top errors by class and frequency.
- Visible on a wall; the on-call's home screen.

**Tier 2 — "Why are they happy or unhappy?"**
- USE metrics for each resource (DB, cache, queue, external deps).
- Dependency latency (downstream services and external APIs).
- Recent deploys overlay.
- Business metrics if applicable (orders/min, signups/min).

Dashboard specs live in repo as code (Grafana JSON, Cloud-native dashboards via IaC). Provisioned via `iac` skill.

## Alerting that pages on symptoms

The alert *pages a human* when the user experience is bad. Don't page on internal metrics.

**Good alerts:**
- "p99 checkout latency exceeded 500ms for 5 minutes — error budget burning at 5x."
- "Order placement success rate dropped below 99% in the last 10 minutes."
- "Payment webhook delivery failure rate > 5%."

**Bad alerts:**
- "CPU is at 95%." (Not a symptom; might be expected during a batch job.)
- "Database query p99 hit 2 seconds." (Not necessarily symptomatic if cached at a higher layer.)
- "Pod restarted." (Pods restart; only matters if it's restart-looping.)

Alerts have:
- A **severity** (page vs. notify).
- A **runbook link** (the responder knows what to do).
- A **dashboard link** (the responder can see the context).
- A **suppression rule** during planned maintenance windows.

Alert routing and on-call rotation live in `incident-runbook`; this skill defines *what should alert and what shouldn't*.

## Code-level hooks (developer responsibility, scope)

When implementing a new endpoint or service, the developer adds:

1. **Structured log statements** at entry, key decisions, and exit of the operation.
2. **Metrics** for the RED quartet (rate, errors, duration) at the controller / handler level — typically via framework instrumentation that emits these automatically.
3. **Manual spans** for business-meaningful work the framework doesn't auto-trace.
4. **Correlation ID propagation** through async chains (stack-specific — MDC, contextvars, AsyncLocalStorage).
5. **Error tracking** with a backend (Sentry, errorception, etc.) for surfacing unhandled errors with full context.

These hooks are what `platform-sre` wires into the actual collectors and storage. ensures the *code* is observable; Operations ensures the *system* observes it.

## Stack references

- `references/opentelemetry.md` — OTel SDK setup per language, propagation, custom spans.
- `references/prometheus-grafana.md` — Prometheus exposition format, Grafana dashboard provisioning.
- `references/loki.md` — Loki log aggregation patterns.
- `references/tempo.md` — Tempo trace storage.
- `references/datadog.md` — Datadog if managed.
- `references/cloud-native.md` — CloudWatch / Azure Monitor / Cloud Operations per cloud.

## Mode handling (G/B)

**Greenfield.** Instrument by construction. Every service has the hooks from day one.

**Brownfield.** Read `.repo-intel/` for the existing observability surface. Add hooks to *new* code in the same style as the existing system; create an inventory of *missing* observability in `.project/working/observability-debt.md` for backfill via `tech-debt-management`.

## What this skill does not do

- Operate the observability stack — that's SRE + `platform-*` packs.
- Define the reliability practice — that's `reliability-dr`; this skill provides the inputs.
- Page humans — `incident-runbook` owns on-call; this skill defines what *should* page.
- Track ML-specific observability — that's `ml-monitoring-drift`.

## Verification

You are done when:

- [ ] SLOs defined per service (from `nfr-definition`).
- [ ] SLIs instrumented: request rate, error rate, latency distribution (RED), saturation per component.
- [ ] Structured logging with correlation IDs across services.
- [ ] Distributed traces (OpenTelemetry or equivalent) sampled appropriately.
- [ ] Dashboards organized by audience: on-call (Tier-1), team (Tier-2), investigation (Tier-3).
- [ ] Alerts symptom-based, not cause-based; runbook linked from each alert.
- [ ] Error budget burn rate tracked.
- [ ] Logs retain per compliance regime; sensitive data redacted.

Evidence to check:
- A typical incident can be diagnosed from dashboards + traces within target MTTD.
- Alert noise rate (alerts that did not require action) under target.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We'll add observability later when we need it." | When you need it, you're already in an incident. The instrumentation should ship with the code. |
| "Logs are enough; we don't need metrics or traces." | Logs answer "what happened to this request"; metrics answer "what's happening across all requests"; traces answer "where in the call graph." Different questions, different tools. |
| "Print statements are temporary observability." | Print statements ship to production and become the default observability for years. Structured logs from the start. |
| "Dashboards are for SRE." | Dashboards are for whoever's on call — which on the slice DoD is the team that shipped it. |
| "Alerts on every threshold are safe." | Alert fatigue is the failure mode. Alert on symptoms (user-visible impact); not every cause. |
| "SLOs are for big companies." | SLOs are how the team decides "is this fast enough?" without hand-waving. Define them; use them. |
| "The user will tell us if something's wrong." | They will; in a churn report next quarter. Instrument before users do the QA. |

## Anti-patterns

- Log lines without correlation IDs.
- Logging full request/response bodies that may contain PII.
- Metrics named ad hoc (`my_thing_count_v2`) — naming convention applies everywhere.
- Alerts on internal metrics that don't reflect user experience.
- Dashboards built per-incident-as-needed rather than provisioned upfront. Build once; reuse.
- Zero observability on a new service "we'll add it later." Adding it later costs 10x as much as adding it during development.
- Pages without runbook links. The on-call shouldn't have to guess.
