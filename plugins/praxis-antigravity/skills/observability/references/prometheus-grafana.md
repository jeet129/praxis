# Reference — Prometheus + Grafana

Loaded by `observability` when the metrics + dashboards stack is Prometheus + Grafana (the de facto OSS standard).

## Why this stack

Prometheus + Grafana is the **default open-source observability stack**:
- Prometheus: pull-based metrics + time-series DB + alerting.
- Grafana: visualization + dashboarding + multi-data-source.
- Together with Loki (logs) + Tempo (traces): the "Grafana LGTM stack."

Choose this stack when:
- You want self-hosted control.
- Existing Kubernetes infrastructure (Helm charts mature).
- Cost predictability matters (no per-host pricing).

Choose Datadog or similar managed when:
- You don't want to operate observability infrastructure.
- The vendor's per-host cost is acceptable.
- The team is small and ops time is the constraint.

## Architecture

```
[App + /metrics endpoint]
       ↑ HTTP scrape (every 15s)
[Prometheus]
   ├── stores time series locally (or remote_write to Cortex/Mimir)
   ├── evaluates alerting rules
   └── ↓ exports to
[Alertmanager] → routes alerts to Slack/PagerDuty/email

[Grafana]
   └── queries Prometheus via PromQL → renders dashboards
```

## Prometheus model

- **Metric**: name + labels + value + timestamp.
- **Time series**: unique combination of name + labels.
- **Sample**: one (timestamp, value) point.
- **Job**: a logical group of targets (a service across replicas).
- **Target**: a single scrape endpoint (one replica).

Example:
```
http_requests_total{method="GET", status="200", route="/orders"} 1234 @ 2026-06-15T10:30:00Z
```

Name: `http_requests_total`. Labels: `{method=..., status=..., route=...}`. Value: 1234. Timestamp.

## Metric types

| Type | Use | Example |
|---|---|---|
| **Counter** | Monotonic increasing total. | Requests handled, errors observed. |
| **Gauge** | Current value (can go up or down). | Connections open, queue depth, memory usage. |
| **Histogram** | Distribution of observations + buckets + sum + count. | Request duration, response size. |
| **Summary** | Like histogram but client-side quantiles. | Use histograms in 95%+ of cases (better for aggregation). |

## Instrumenting your app

**Python (prometheus_client)**:

```python
from prometheus_client import Counter, Histogram, Gauge, start_http_server

REQUESTS = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'route', 'status'],
)
LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'route'],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
INFLIGHT = Gauge(
    'http_requests_inflight',
    'In-flight HTTP requests',
    ['method', 'route'],
)

# Expose on a port (or use /metrics with your framework)
start_http_server(9090)

# In handler:
@LATENCY.labels(method='POST', route='/orders').time():
    INFLIGHT.labels(method='POST', route='/orders').inc()
    try:
        result = handle_order(request)
        REQUESTS.labels(method='POST', route='/orders', status='200').inc()
        return result
    finally:
        INFLIGHT.labels(method='POST', route='/orders').dec()
```

**Java (Micrometer + Spring Boot Actuator)** — built into Spring Boot starter (see `stack-java-spring/references/spring-boot-3.md`).

**Node.js**:

```ts
import { Counter, Histogram, Registry } from 'prom-client';

const register = new Registry();
const httpRequestsTotal = new Counter({
    name: 'http_requests_total',
    help: 'Total HTTP requests',
    labelNames: ['method', 'route', 'status'],
    registers: [register],
});

// Expose at /metrics
app.get('/metrics', async (req, res) => {
    res.set('Content-Type', register.contentType);
    res.end(await register.metrics());
});
```

## Label cardinality — the #1 footgun

Each unique combination of labels creates a separate time series. **Never use unbounded values as labels.**

❌ `user_id` (millions of users)
❌ `request_id` (every request)
❌ `URL with raw query string`

✅ `route="/orders/:id"` (template, not the specific URL)
✅ `status="200"` (small set)
✅ `endpoint_class="critical"` (categorized)

A few thousand series per metric: fine. A few million: Prometheus dies.

## PromQL — the query language

Core operations:

```promql
# Rate of requests per second (counter → rate)
rate(http_requests_total[1m])

# Sum across all instances by route
sum by (route) (rate(http_requests_total[1m]))

# Error rate (errors / total)
sum(rate(http_requests_total{status=~"5.."}[1m])) 
  / 
sum(rate(http_requests_total[1m]))

# 99th percentile latency from histogram
histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))

# Per-route 99th
histogram_quantile(0.99, sum by (le, route) (rate(http_request_duration_seconds_bucket[5m])))

# Memory usage trend
node_memory_MemAvailable_bytes{instance="$instance"}

# Alert when error rate > 1% over 5 min
sum(rate(http_requests_total{status=~"5.."}[5m])) 
  / 
sum(rate(http_requests_total[5m])) > 0.01
```

`rate()` requires a counter and a time window. The window should be at least 2-4x your scrape interval.

## RED method (per `observability`)

For request-handling services:

| Metric | PromQL pattern |
|---|---|
| **R**ate | `sum(rate(http_requests_total[1m]))` |
| **E**rrors | `sum(rate(http_requests_total{status=~"5.."}[1m]))` |
| **D**uration | `histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))` |

## USE method

For resources:

| Metric | What it measures |
|---|---|
| **U**tilization | Percentage of resource in use. |
| **S**aturation | Queue depth / backpressure. |
| **E**rrors | Error count. |

## Alerting rules

```yaml
# prometheus/alerts.yml
groups:
  - name: order-service
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: |
          (sum(rate(http_requests_total{job="order-service",status=~"5.."}[5m]))
           / sum(rate(http_requests_total{job="order-service"}[5m]))) > 0.01
        for: 5m
        labels:
          severity: page
          team: orders
        annotations:
          summary: Order service error rate > 1% for 5 minutes
          description: "Error rate is {{ $value | humanizePercentage }}"
          runbook_url: https://docs.internal/runbooks/order-service-errors

      - alert: P99LatencyHigh
        expr: |
          histogram_quantile(0.99, 
            sum by (le) (rate(http_request_duration_seconds_bucket{job="order-service"}[5m]))
          ) > 1.0
        for: 10m
        labels:
          severity: warn
          team: orders
        annotations:
          summary: P99 latency above 1s for 10 minutes
```

Alertmanager routes alerts to receivers (Slack, PagerDuty, email) based on labels.

## SLO + error budget

Per `observability` SKILL — calculate error budget from SLO:

```promql
# SLO: 99.9% success rate over 30 days
# Error budget: 0.1% = 1 - 0.999

# Current 30-day success rate
1 - (
  sum(increase(http_requests_total{status=~"5.."}[30d])) 
  /
  sum(increase(http_requests_total[30d]))
)

# Burn rate (fraction of budget consumed per hour, normalized)
# Burn rate > 1 means at this rate, you'll exhaust 30-day budget within 30 days
(
  sum(rate(http_requests_total{status=~"5.."}[1h])) 
  / sum(rate(http_requests_total[1h]))
) / 0.001
```

Fast-burn alerts (e.g., 2% of budget consumed in 1 hour) page on-call.

## Grafana

Dashboards as code (per `iac` discipline):

```json
{
  "title": "Order Service - Overview",
  "panels": [
    {
      "title": "Request Rate",
      "targets": [
        {"expr": "sum(rate(http_requests_total{job=\"order-service\"}[1m]))"}
      ]
    },
    {
      "title": "Error Rate %",
      "targets": [
        {"expr": "100 * sum(rate(http_requests_total{job=\"order-service\",status=~\"5..\"}[5m])) / sum(rate(http_requests_total{job=\"order-service\"}[5m]))"}
      ]
    },
    {
      "title": "P50/P95/P99 Latency",
      "targets": [
        {"expr": "histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))", "legendFormat": "p50"},
        {"expr": "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))", "legendFormat": "p95"},
        {"expr": "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))", "legendFormat": "p99"}
      ]
    }
  ]
}
```

Provision via Grafana provisioning (datasources + dashboards as files in a config map) or Terraform's `grafana_dashboard` resource.

## Per-tier dashboard pattern (per `observability`)

| Tier | Audience | Content |
|---|---|---|
| **Tier 1** | On-call (red/yellow/green at a glance) | Top-level RED + SLO burn + saturation. ~6 panels. |
| **Tier 2** | Team (deeper investigation) | Per-route RED, dependency latencies, error breakdowns. ~15-20 panels. |
| **Tier 3** | Investigation (incident response) | Per-instance details, downstream call detail, slow query logs. ~30+ panels. |

## Storage + retention

Prometheus stores ~1-2 KB per series-day. At 1M active series, that's ~30GB/month.

- **Local TSDB**: ~15 day retention default. Configurable up to ~2 weeks per disk realistically.
- **Long-term storage**: remote_write to Cortex / Mimir / Thanos / VictoriaMetrics for months/years.

For SOC 2 + post-incident analysis, keep at least 30-90 days. Use remote storage.

## Scaling Prometheus

Single Prometheus handles ~1-2M active series + ~100K samples/sec. Beyond that:

- **Sharding**: split scraping across multiple Prometheus instances.
- **Thanos** / **Cortex** / **Mimir** — multi-tenant + horizontally scalable.
- **VictoriaMetrics** — faster + simpler alternative.

## Common patterns

### Recording rules — pre-compute expensive queries

```yaml
groups:
  - name: order-service-aggregates
    interval: 30s
    rules:
      - record: order_service:http_requests:rate1m
        expr: sum by (route, status) (rate(http_requests_total{job="order-service"}[1m]))
```

Pre-computed series query much faster. Use for dashboards + alerts that hit aggregates often.

### Service discovery

Don't hardcode targets. Use:
- Kubernetes service discovery (Prometheus reads pod/service annotations).
- Consul / etcd.
- Cloud-specific (EC2, GCE).
- File-based (for static envs).

```yaml
# prometheus.yml (Kubernetes service discovery)
scrape_configs:
  - job_name: kubernetes-pods
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
```

Then annotate pods:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/path: "/metrics"
  prometheus.io/port: "9090"
```

## Gotchas

- **Counter resets** — when a pod restarts, the counter goes back to 0. `rate()` handles this correctly (samples the deriv); `increase()` over the reset window may underreport.
- **`scrape_interval` consistency** — change it and your historical aggregates skew. Pick once.
- **Out-of-order samples** — Prometheus 2.x rejects them. Mimir + remote storage handle it.
- **`for:` clause on alerts** — only fires if the condition holds for the duration. Useful for noise reduction; don't set too high or you miss real issues.
- **Histogram buckets matter** — default 10ms-10s buckets miss precision. Define explicitly for your SLI.

## Common rationalizations

| Thought | Counter |
|---|---|
| "We don't need cardinality limits yet." | At 100K series Prometheus is fine. At 1M+ it's not. Budget cardinality early. |
| "Summaries are fine; same as histograms." | Summaries don't aggregate across instances. Use histograms unless you have a specific reason. |
| "Alert on individual metrics." | Alert on user-visible symptoms (error rate, latency). Causes generate noise without explaining impact. |
| "Dashboards are designer's job." | They're observability tooling. Engineering owns them. |
| "Storage retention is free." | At meaningful series counts, it costs real money. Plan retention + remote storage. |

## Verification (per `observability` SKILL)

- [ ] Every service exposes `/metrics`.
- [ ] RED metrics implemented (rate, errors, duration).
- [ ] Cardinality bounded (route templates, no user_id labels).
- [ ] Dashboards per tier (T1 on-call, T2 team, T3 investigation).
- [ ] Alerts symptom-based + linked to runbooks.
- [ ] SLO + error-budget tracking implemented.
- [ ] Long-term storage configured (remote_write to Thanos/Mimir/VictoriaMetrics).

## Official sources

- Prometheus: https://prometheus.io
- Grafana: https://grafana.com
- PromQL basics: https://prometheus.io/docs/prometheus/latest/querying/basics/
- Alertmanager: https://prometheus.io/docs/alerting/latest/alertmanager/
- Thanos: https://thanos.io
- Mimir: https://grafana.com/oss/mimir/
- VictoriaMetrics: https://victoriametrics.com
