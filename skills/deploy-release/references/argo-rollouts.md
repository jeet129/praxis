# Deploy / Release — Argo Rollouts

Argo Rollouts replaces the native `Deployment` controller with a `Rollout` CRD that supports fine-grained canary and blue-green strategies, automated metric-gated promotion via `AnalysisTemplate`, and traffic shaping through a service mesh or ingress controller. Reach for it when `kubernetes-rollouts.md`'s native RollingUpdate isn't precise enough — when you need percentage-based traffic canaries with automated go/no-go decisions, not just pod-readiness-gated rollout.

## Install

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
# kubectl plugin for local rollout inspection/promotion
curl -LO https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
```

## Canary strategy with analysis gates

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata: { name: orders-api }
spec:
  replicas: 10
  strategy:
    canary:
      canaryService: orders-api-canary
      stableService: orders-api-stable
      trafficRouting:
        istio:
          virtualService: { name: orders-api-vsvc, routes: [primary] }
      steps:
        - setWeight: 10
        - pause: { duration: 5m }
        - analysis:
            templates: [{ templateName: success-rate }]
            args: [{ name: service-name, value: orders-api-canary }]
        - setWeight: 25
        - pause: { duration: 5m }
        - analysis:
            templates: [{ templateName: success-rate }]
        - setWeight: 50
        - pause: { duration: 10m }
        - setWeight: 100
  selector: { matchLabels: { app: orders-api } }
  template:
    metadata: { labels: { app: orders-api } }
    spec:
      containers:
        - name: orders-api
          image: registry.internal/orders-api:2.8.0
          readinessProbe: { httpGet: { path: /healthz/ready, port: 8080 } }
```

Each `setWeight` step shifts a percentage of live traffic to the new revision; each `analysis` step queries a metrics provider and halts (or aborts) the rollout automatically if the canary fails the defined success criteria — this is the difference from native rolling updates, which gate only on pod readiness, not on live traffic behavior.

## Blue-green strategy

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata: { name: orders-api }
spec:
  replicas: 6
  strategy:
    blueGreen:
      activeService: orders-api-active
      previewService: orders-api-preview
      autoPromotionEnabled: false          # requires manual or analysis-gated promotion
      prePromotionAnalysis:
        templates: [{ templateName: smoke-test }]
      scaleDownDelaySeconds: 300           # keep old version warm for fast rollback window
```

Blue-green runs the full new version behind a `previewService` (for smoke-testing / internal validation before any live traffic) while `activeService` still points entirely at the old version — promotion flips all traffic at once, versus canary's gradual shift. Use blue-green when partial-traffic exposure of a new version is unacceptable (e.g., schema-migration-coupled releases where mixed-version traffic would corrupt data) and canary when you want gradual, metric-validated exposure.

## Analysis templates and metric providers

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: { name: success-rate }
spec:
  args: [{ name: service-name }]
  metrics:
    - name: success-rate
      interval: 1m
      count: 5
      successCondition: result[0] >= 0.99
      failureLimit: 2
      provider:
        prometheus:
          address: http://prometheus.observability:9090
          query: |
            sum(rate(http_requests_total{service="{{args.service-name}}",code!~"5.."}[1m]))
            /
            sum(rate(http_requests_total{service="{{args.service-name}}"}[1m]))
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata: { name: latency-p99 }
spec:
  metrics:
    - name: p99-latency
      interval: 1m
      count: 5
      successCondition: result[0] < 0.5     # 500ms
      provider:
        prometheus:
          address: http://prometheus.observability:9090
          query: |
            histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{service="orders-api-canary"}[1m])) by (le))
```

Supported providers: Prometheus (most common, pairs with the `observability` skill's Prometheus/Grafana stack), Datadog, New Relic, CloudWatch, Wavefront, web-hook-based custom providers (for anything without a native integration). `failureLimit` caps how many failed measurement windows are tolerated before the rollout auto-aborts.

## Traffic shaping via mesh or ingress

Argo Rollouts doesn't route traffic itself — it drives an underlying traffic-splitting mechanism:

| Traffic router | Mechanism | Use when |
|---|---|---|
| Istio `VirtualService` | Weighted `destination` routes | Service mesh already in place |
| NGINX Ingress | `canary-weight` annotation on a second Ingress | Ingress-only, no mesh |
| SMI (Service Mesh Interface) | `TrafficSplit` CRD | Linkerd or other SMI-compatible mesh |
| AWS ALB / App Mesh | Weighted target groups | AWS-native, no separate mesh |

```yaml
# NGINX Ingress example
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  strategy:
    canary:
      trafficRouting:
        nginx:
          stableIngress: orders-api-ingress
          annotationPrefix: nginx.ingress.kubernetes.io
```

Without a mesh/ingress traffic router configured, Argo Rollouts falls back to *replica-ratio* canarying (weight approximated by pod count ratio, e.g. 1 canary pod out of 10 total ≈ 10%) — coarser-grained and less precise than true percentage-based traffic splitting, but works with zero additional infrastructure.

## Auto-rollback

```yaml
spec:
  strategy:
    canary:
      steps: [...]
      # On analysis failure, Argo Rollouts automatically:
      # 1. Sets canary weight back to 0
      # 2. Marks the Rollout "Degraded"
      # 3. Leaves the stable version fully serving traffic
```

```bash
# Manual controls (used from CI or by an operator during investigation)
kubectl argo rollouts promote orders-api          # skip remaining pauses, promote now
kubectl argo rollouts abort orders-api             # abort, revert to stable
kubectl argo rollouts undo orders-api              # roll back to a prior stable revision
kubectl argo rollouts get rollout orders-api --watch
```

Rollback on analysis failure is automatic by default — no on-call action required for the common case of "canary metrics went bad." Manual `abort`/`undo` are for cases the analysis didn't catch (a slow-burn issue that shows up after full promotion, or an operator-initiated stop).

## Common violations to flag in review

- Canary steps with `setWeight` but no `analysis` gate — traffic shifts on a timer regardless of actual canary health, defeating the purpose of canarying over a plain rolling update.
- `AnalysisTemplate` success conditions with no `failureLimit`/`count` bound — a single noisy metric sample can either block promotion forever or never actually gate anything.
- Blue-green `autoPromotionEnabled: true` on a release that hasn't been validated by `prePromotionAnalysis` — removes the human/metric checkpoint blue-green exists to provide.
- No traffic router configured — relying on unannounced replica-ratio approximation when true percentage-based canarying was assumed by the release plan.
- `scaleDownDelaySeconds` set too low on blue-green — old version scaled down before a fast-rollback window is confirmed safe.
- Metric queries in `AnalysisTemplate` pointed at the wrong service label (measuring aggregate traffic instead of canary-only traffic) — silently defeats the gate.
