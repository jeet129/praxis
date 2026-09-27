# Deploy / Release — Kubernetes Native Rollouts

Native Kubernetes `Deployment` rollout mechanics — the baseline before reaching for Argo Rollouts (`deploy-release/references/argo-rollouts.md`). Sufficient for most services; graduate to Argo Rollouts when you need metric-gated automated promotion or fine-grained traffic-percentage canaries.

## Deployment strategies

### RollingUpdate (default)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api }
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%          # extra pods allowed during rollout
      maxUnavailable: 0      # zero-downtime — never fewer than desired replicas ready
  selector: { matchLabels: { app: orders-api } }
  template:
    metadata: { labels: { app: orders-api } }
    spec:
      containers:
        - name: orders-api
          image: registry.internal/orders-api:2.7.0
          readinessProbe:
            httpGet: { path: /healthz/ready, port: 8080 }
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
          startupProbe:
            httpGet: { path: /healthz/startup, port: 8080 }
            periodSeconds: 5
            failureThreshold: 30    # up to 150s for slow-starting apps
          livenessProbe:
            httpGet: { path: /healthz/live, port: 8080 }
            periodSeconds: 10
            failureThreshold: 3
```

`maxUnavailable: 0` is the zero-downtime setting — new pods must be ready before old ones terminate. `maxSurge` controls how many extra pods run concurrently during the transition (cost/speed tradeoff — higher surge rolls faster but briefly uses more resources).

### Recreate

```yaml
spec:
  strategy:
    type: Recreate    # all old pods killed before any new ones start
```

Use only when the workload cannot tolerate two versions running concurrently (schema-incompatible singleton, exclusive-lock holder) — accepts downtime during the switch. Rare; most stateless services should never need this.

## Readiness / startup probes as rollout gates

Probes are what make `RollingUpdate` actually safe — without a correct `readinessProbe`, Kubernetes considers a pod "ready" the instant its process starts, routing traffic before the app has finished initializing (DB pool warm-up, cache load).

- **`startupProbe`** — gates when the other probes even begin checking. Essential for slow-starting apps (JVM, large model load) — without it, a slow start gets killed by `livenessProbe` before it ever finishes starting.
- **`readinessProbe`** — gates traffic routing (removes the pod from the Service endpoints when failing, without restarting it). This is the rollout-safety probe: `RollingUpdate` waits for new pods to pass this before terminating old ones.
- **`livenessProbe`** — gates pod restart. Failing this kills and restarts the container. Should check "is the process wedged," not "is a downstream dependency healthy" — a `livenessProbe` that checks the database will restart-loop the whole fleet during a DB outage instead of just failing readiness.

```yaml
readinessProbe:
  httpGet: { path: /healthz/ready, port: 8080 }
  # /healthz/ready checks: DB pool acquired, cache warmed, config loaded
  # NOT: is a downstream API up (that's a liveness anti-pattern too)
```

## PodDisruptionBudgets

Bounds *voluntary* disruption (node drains, cluster upgrades, `kubectl drain`) — protects availability during operational events, distinct from the rollout itself.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: orders-api-pdb }
spec:
  minAvailable: 4          # or maxUnavailable: 2 — pick one
  selector: { matchLabels: { app: orders-api } }
```

Without a PDB, a node drain during a rollout (or a cluster autoscaler scale-down) can evict enough pods simultaneously to violate the service's availability target, even though the `RollingUpdate` strategy itself is configured correctly. Set `minAvailable` from the NFR availability target in `nfr-definition`, not an arbitrary number.

## HPA interplay

Horizontal Pod Autoscaler and rollouts operate on the same `replicas` field — a rollout in progress and an HPA scaling event can race.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: orders-api-hpa }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: orders-api }
  minReplicas: 4
  maxReplicas: 20
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # avoid flapping during rollout traffic dips
```

- The `Deployment`'s `replicas` field becomes advisory once an HPA targets it — don't set `replicas` in CI/CD deploy scripts for HPA-managed Deployments; it fights the HPA on every deploy.
- `maxSurge`/`maxUnavailable` percentages apply against whatever `replicas` the HPA has currently set, not a fixed baseline — a rollout during a scale-up event surges relative to the *current* count.
- Set `stabilizationWindowSeconds` on scale-down to avoid the HPA aggressively removing pods right as a rollout's traffic pattern temporarily shifts.

## Rollback

```bash
# Inspect rollout history
kubectl rollout history deployment/orders-api

# Roll back to the previous revision
kubectl rollout undo deployment/orders-api

# Roll back to a specific revision
kubectl rollout undo deployment/orders-api --to-revision=14

# Watch rollout status (used as a CI gate — exits non-zero on failure/timeout)
kubectl rollout status deployment/orders-api --timeout=5m
```

`kubectl rollout status` with `--timeout` in the CD pipeline is the automated-rollback trigger point: a stuck or failing rollout (pods crash-looping, never passing readiness) times out, the pipeline treats that as a failed deploy and issues `kubectl rollout undo` automatically — don't leave rollback as a manual on-call step for a routine failed-readiness scenario.

```yaml
# CD pipeline snippet
- name: Deploy
  run: |
    kubectl apply -f k8s/orders-api-deployment.yaml
    kubectl rollout status deployment/orders-api --timeout=5m || {
      echo "Rollout failed, rolling back"
      kubectl rollout undo deployment/orders-api
      exit 1
    }
```

## Common violations to flag in review

- `maxUnavailable` left at the Kubernetes default (25%) for a service whose availability NFR requires zero-downtime deploys — should be `0`.
- Missing `readinessProbe` — pods take traffic before they're actually ready, causing request failures during every deploy.
- `livenessProbe` checking a downstream dependency (DB, cache) — turns a dependency outage into a self-inflicted restart storm.
- No `PodDisruptionBudget` on a service with an availability SLA — node drains can violate it even with a correct rollout strategy.
- `replicas` hard-set in deploy manifests/CI for an HPA-managed Deployment — fights the autoscaler on every deploy.
- No automated rollback wired to `kubectl rollout status` failure — rollback left as a manual, slow on-call action.
- `Recreate` strategy used where `RollingUpdate` would work — unnecessary downtime.
