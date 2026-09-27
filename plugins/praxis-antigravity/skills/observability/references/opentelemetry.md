# Reference — OpenTelemetry (OTel)

Loaded by `observability` when OpenTelemetry is the chosen instrumentation framework (the recommended default).

## Why OpenTelemetry

OTel is a CNCF graduated project providing **vendor-neutral instrumentation** for traces, metrics, logs (the three pillars). It's the standard:

- Instrument once; export to Jaeger, Tempo, Datadog, New Relic, Honeycomb, Dynatrace, Lightstep, AWS X-Ray, GCP Cloud Trace, etc.
- Switch backends without re-instrumenting.
- Open-source SDKs for every major language.
- Auto-instrumentation libraries for major frameworks.

## The three signals

| Signal | Question it answers | Primary use |
|---|---|---|
| **Traces** | "What did request X do, in what order, and how long did each step take?" | Latency analysis, dependency mapping, root-cause analysis. |
| **Metrics** | "What's happening across all requests over time?" | SLO tracking, dashboards, alerting. |
| **Logs** | "What did this specific operation report?" | Investigation, debugging, audit. |

Per `observability` SKILL, all three need correlation IDs to be useful together.

## Core concepts

- **Span**: a single named operation with start/end timestamps + attributes. Spans nest into a tree.
- **Trace**: the tree of spans for one request, identified by `trace_id`.
- **Span context**: `trace_id` + `span_id` + flags + state — what propagates across service boundaries.
- **Resource**: attributes describing the producer (service.name, service.version, deployment.environment, host.name).
- **Attributes**: structured key-value tags on spans/metrics/logs.
- **Events**: timestamped points within a span (e.g., "cache miss", "retry attempted").
- **Exporter**: ships telemetry to a backend (OTLP-over-gRPC/HTTP is the standard).
- **Collector**: a separate process (sidecar or DaemonSet) that receives, processes, batches, and routes telemetry.

## Architecture pattern (recommended)

```
[App + SDK + auto-instrumentation]
       ↓ OTLP (gRPC)
[OTel Collector] (Deployment or DaemonSet)
       ↓ ↓ ↓
   traces  metrics  logs
       ↓ ↓ ↓
  Tempo  Prom   Loki   (or Datadog, etc.)
       ↓ ↓ ↓
       Grafana
```

The Collector decouples your app from the backend. App always speaks OTLP; backend choice changes only the Collector config.

## Instrumentation patterns

### Auto-instrumentation (start here)

Most languages support auto-instrumentation that wraps common libraries (HTTP servers, DB drivers, message queues) without code changes.

**Python**:
```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install   # install instrumentation packages for your deps

# Run your app with auto-instrumentation
OTEL_SERVICE_NAME=order-service \
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317 \
OTEL_TRACES_EXPORTER=otlp \
opentelemetry-instrument python -m uvicorn main:app
```

**Java**:
```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=order-service \
     -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
     -jar order-service.jar
```

**Node.js**:
```ts
// instrumentation.ts — required before any other import
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';

const sdk = new NodeSDK({
    instrumentations: [getNodeAutoInstrumentations()],
});
sdk.start();
```

```bash
node --require ./instrumentation.js app.js
```

**Go**: no built-in auto-instrumentation (manual). Use `otelhttp`, `otelsql`, etc.

### Manual instrumentation (when needed)

For business-meaningful spans, instrument explicitly:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def place_order(cmd: CreateOrderCommand) -> Order:
    with tracer.start_as_current_span("place_order") as span:
        span.set_attribute("customer.id", cmd.customer_id)
        span.set_attribute("order.item_count", len(cmd.items))
        
        with tracer.start_as_current_span("validate_inventory"):
            await inventory.check(cmd.items)
        
        with tracer.start_as_current_span("charge_payment") as ps:
            charge = await payment.charge(cmd.total)
            ps.set_attribute("payment.provider", "stripe")
            ps.set_attribute("payment.amount_cents", cmd.total)
        
        with tracer.start_as_current_span("persist_order"):
            order = await repo.save(...)
            span.set_attribute("order.id", str(order.id))
        
        return order
```

Span naming: use the **operation**, not the URL. `place_order` not `POST /orders`.

## Context propagation (the magic that makes distributed tracing work)

The trace context (`trace_id` + `span_id`) propagates across service boundaries via HTTP headers (`traceparent`, `tracestate` per W3C Trace Context) or message headers.

Auto-instrumentation handles propagation automatically for HTTP/gRPC. For message queues, configure explicitly:

```python
# Producer: inject context into message headers
from opentelemetry.propagate import inject
headers = {}
inject(headers)
producer.publish(topic, message, headers=headers)

# Consumer: extract context, start a span linked to upstream
from opentelemetry.propagate import extract
ctx = extract(message.headers)
with tracer.start_as_current_span("handle_message", context=ctx):
    process(message)
```

## Resource attributes (set these once)

```python
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "service.name": "order-service",
    "service.version": "1.2.3",
    "service.namespace": "billing",
    "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
    "service.instance.id": socket.gethostname(),
})
```

Conventional attribute names matter — backends like Datadog/Tempo expect specific keys. Follow the [Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

## Sampling

Tracing every request at 100% in production is too expensive at scale. Choose a sampling strategy:

| Strategy | Use case |
|---|---|
| **AlwaysOn (100%)** | Low-traffic services; debugging. |
| **AlwaysOff (0%)** | Trace export disabled. |
| **TraceIdRatioBased(p)** | Head-based sampling at probability p. Simple but blind to importance. |
| **ParentBased(root)** | Honor parent decision; sample at root using the inner sampler. |
| **Tail-based** (Collector feature) | Decide after seeing the full trace. Sample 100% of errors + slow + N% of normal. The good one. |

Recommended setup:
- App-level: ParentBased(AlwaysOn) — generate every trace.
- Collector: tail-based sampling reduces to ~1-5% of normal traces while keeping all errors + slow.

This requires the Collector to buffer briefly until it sees the trace's end.

## Metrics

OpenTelemetry metrics overlap with Prometheus. Two patterns:

**Pattern 1**: app exposes Prometheus `/metrics` endpoint (via prometheus_client lib); Prometheus scrapes.

**Pattern 2**: app pushes OTel metrics via OTLP; Collector forwards to Prometheus (via prometheus exporter) or Datadog or wherever.

Pattern 2 is more uniform but requires OTel collector. Pattern 1 is the established norm and works well — choose by team preference.

For your custom metrics:

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

orders_placed = meter.create_counter(
    "orders.placed",
    description="Total orders placed",
    unit="1",
)
order_value_cents = meter.create_histogram(
    "order.value_cents",
    description="Order value in cents",
    unit="cents",
)

# In handler:
orders_placed.add(1, {"channel": "web", "tier": "premium"})
order_value_cents.record(order.total_cents, {"channel": "web"})
```

## Logs

OTel logs are newer and less mature than traces/metrics. Two patterns:

**Pattern 1**: standard logger (pino, slf4j, Python logging) → log file → Vector/Fluentd/Promtail → Loki/Elasticsearch. App stays standard; collection happens at the platform.

**Pattern 2**: OTel log handler → OTLP → Collector → backend. Logs share infrastructure with traces.

Pattern 1 is more common and reliable in 2026. Pattern 2 is improving. Per `observability`, the key is **correlation** — include `trace_id` + `span_id` in your log lines regardless of which transport you use.

```python
# Configure log formatter to inject trace context
import logging
from opentelemetry import trace

class TraceContextFilter(logging.Filter):
    def filter(self, record):
        span = trace.get_current_span()
        if span and span.is_recording():
            ctx = span.get_span_context()
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        return True

logger = logging.getLogger()
logger.addFilter(TraceContextFilter())
```

## Collector configuration (example)

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024
  memory_limiter:
    limit_mib: 512
    spike_limit_mib: 128
    check_interval: 5s
  resource:
    attributes:
      - key: cluster
        value: prod-us-east-1
        action: insert

  # Tail-based sampling
  tail_sampling:
    decision_wait: 30s
    policies:
      - name: errors-and-slow
        type: composite
        composite:
          max_total_spans_per_second: 1000
          policy_order: [errors, slow, probabilistic]
          composite_sub_policy:
            - name: errors
              type: status_code
              status_code: { status_codes: [ERROR] }
            - name: slow
              type: latency
              latency: { threshold_ms: 1000 }
            - name: probabilistic
              type: probabilistic
              probabilistic: { sampling_percentage: 5 }

exporters:
  otlphttp/tempo:
    endpoint: http://tempo:4318
  prometheus:
    endpoint: 0.0.0.0:8889
  loki:
    endpoint: http://loki:3100/loki/api/v1/push

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, tail_sampling, batch]
      exporters: [otlphttp/tempo]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [prometheus]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [loki]
```

## Deployment patterns

| Pattern | Use case |
|---|---|
| **Sidecar (DaemonSet per node)** | Each node has a Collector; apps send to localhost. Lowest latency; resource cost per node. |
| **Gateway (centralized Deployment)** | Pool of Collectors behind a service; apps send to service DNS. Centralized config; potential bottleneck. |
| **Both** (agent → gateway) | DaemonSet collects + forwards to centralized gateway for tail sampling + routing. The standard for production. |

## Gotchas

- **Cardinality explosion** — every unique attribute combination is a new metric series. Never use `user_id` as a metric attribute; always use as a span/log attribute.
- **Sampling without tail-sampling = lose all errors** — head-based 1% sampling drops 99% of errors. Use tail-based.
- **Span context not propagating** — auto-instrumentation must run before the imports that need it. Configure carefully per language.
- **`trace_id` is 16 bytes** — log it as 32-char hex (lowercase, no dashes), per W3C standard.
- **Don't put PII in attributes** — they're searchable; that's a privacy risk. Hash if you need to correlate.
- **Histogram buckets matter** — default exponential buckets serve most uses; for SLO tracking, set specific bucket boundaries.

## Common rationalizations

| Thought | Counter |
|---|---|
| "We have Prometheus; we don't need OTel." | OTel and Prometheus are complementary. OTel gives you traces + propagation; Prometheus is metrics. Use both. |
| "Vendor SDK is easier than OTel." | True initially. When you change vendor, you re-instrument. Lock-in cost is real. |
| "Sample at 1% to save costs." | Without tail-sampling, you lose almost all errors. Use tail-based or scale the backend. |
| "Manual instrumentation is too much work." | Auto-instrumentation covers framework boundaries. Add manual for business-meaningful spans (the ones you'd want to know about in an incident). |
| "Logs in OTel are too new." | True; pattern 1 (standard logger + correlation IDs) is fine. Don't block on OTel logs maturity. |

## Verification (per `observability` SKILL)

- [ ] Every service has `service.name`, `service.version`, `deployment.environment` set.
- [ ] HTTP / gRPC / DB / message-queue calls auto-instrumented.
- [ ] Business-meaningful operations have manual spans.
- [ ] Trace context propagates across service boundaries.
- [ ] Tail-based sampling configured if production volume warrants.
- [ ] Logs include `trace_id` + `span_id`.
- [ ] Collector deployed (sidecar or gateway).
- [ ] At least one backend wired (Tempo, Datadog, etc.).
- [ ] Sample trace shows complete request flow across services.

## Official sources

- OpenTelemetry: https://opentelemetry.io
- Semantic Conventions: https://opentelemetry.io/docs/specs/semconv/
- Collector: https://opentelemetry.io/docs/collector/
- W3C Trace Context: https://www.w3.org/TR/trace-context/
- Per-language SDKs: https://opentelemetry.io/docs/languages/
