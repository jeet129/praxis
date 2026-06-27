---
name: platform-k8s
description: Cloud-agnostic Kubernetes pack — workload manifests, resource requests/limits, probes, HPA/VPA, network policy, ingress, secrets, GitOps deployment patterns, cluster conventions. The Layer-4 reference pack that the deployment-side skills (deploy-release, iac, observability, secrets-config) consult for K8s-specific implementation.
---

# Platform — Kubernetes


<!-- praxis:description:full -->
## Full description

Cloud-agnostic Kubernetes pack — workload manifests, resource requests/limits, probes, HPA/VPA, network policy, ingress, secrets, GitOps deployment patterns, cluster conventions. The Layer-4 reference pack that the deployment-side skills (deploy-release, iac, observability, secrets-config) consult for K8s-specific implementation. Selected as the first cloud pack per the Resolved Decision (K8s-only first, cloud-agnostic). Use whenever K8s manifests are being written, when establishing cluster-level conventions, or when integrating with the K8s-native deployment ecosystem (Helm, Kustomize, Argo CD, External Secrets Operator).

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: platform
domain: infra
state: active
dependencies:
 - containerization
 - deploy-release
 - secrets-config
 - observability
triggers:
 - "writing K8s manifests for a service"
 - "establishing cluster-level conventions (namespaces, RBAC, network policy)"
 - "wiring GitOps deployment (Argo CD / Flux)"
 - "configuring HPA / VPA autoscaling"
 - "integrating External Secrets Operator with the secret store"
 - "designing ingress and TLS termination"
outputs:
 - K8s workload manifests (Deployment, Service, ConfigMap, Secret, Ingress)
 - Helm chart or Kustomize overlay structure per service
 - cluster conventions (namespace strategy, RBAC, network policy templates)
 - GitOps repo layout (Argo CD applications / Flux Kustomizations)
 - Pod resource configuration (requests, limits, probes, security context)
consumers:
 - platform-sre (primary author)
 - deploy-release (consumes for K8s-native rollout strategies)
 - iac (provisions the cluster; this skill's manifests run inside)
 - secrets-config (consumes for External Secrets integration)
 - observability (consumes for instrumentation deployment patterns)
references: []
```
<!-- praxis:metadata:end -->

The cloud-agnostic K8s reference pack. Where `iac` provisions the *cluster*, this pack defines what runs *inside* the cluster — workloads, services, ingress, network policy, autoscaling, secrets integration, GitOps deployment patterns. Manifests live in the repo (or a GitOps repo); they are code-reviewed and applied via continuous reconciliation.

The decision to use K8s and *which* K8s (managed EKS / GKE / AKS vs. cloud-agnostic) was made per the project's cloud choice. This skill is **cloud-agnostic K8s**; cloud-specific extensions (e.g., AWS Load Balancer Controller patterns) live in the per-cloud packs that ship in later waves.

## When this skill fires

- A service is being deployed to K8s for the first time — manifests / Helm chart are written.
- Cluster-level conventions are being established (namespaces, RBAC, network policy, ingress).
- GitOps is being wired (Argo CD or Flux).
- Autoscaling (HPA / VPA / Cluster Autoscaler) is being configured per service.
- External Secrets Operator is being integrated with the project's secret store.

## The discipline

### 1. Namespace strategy

One namespace per logical scope. Common patterns:

- **Per-environment-per-service** (preferred for clarity): `order-service-dev`, `order-service-staging`, `order-service-production`. Easy RBAC; easy quotas.
- **Per-environment with services as namespaces inside**: `production` namespace contains all production services. Simpler for small projects.
- **Per-team**: `team-alpha`, `team-beta`. For multi-team clusters.

Whatever the choice, **namespace = boundary of resource quota, network policy, RBAC, and secrets scope**. Pods don't reach across namespaces without explicit policy.

### 2. Workload manifests — the standard service

A typical stateless service runs as a `Deployment` + `Service` + `ConfigMap` + `Secret` (via External Secrets) + `HorizontalPodAutoscaler` + optionally `PodDisruptionBudget` + `NetworkPolicy`.

```yaml
# deploy/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
 name: order-service
 labels:
 app: order-service
 component: api
 managed-by: argocd
spec:
 replicas: 6 # min for HA across 3 AZs with 2 each
 strategy:
 type: RollingUpdate
 rollingUpdate:
 maxSurge: 25%
 maxUnavailable: 25%
 selector:
 matchLabels: { app: order-service }
 template:
 metadata:
 labels: { app: order-service, component: api }
 spec:
 serviceAccountName: order-service
 securityContext:
 runAsNonRoot: true
 runAsUser: 10001
 fsGroup: 10001
 seccompProfile: { type: RuntimeDefault }
 topologySpreadConstraints:
 - maxSkew: 1
 topologyKey: topology.kubernetes.io/zone
 whenUnsatisfiable: DoNotSchedule
 labelSelector:
 matchLabels: { app: order-service }
 containers:
 - name: app
 image: ghcr.io/myorg/order-service@sha256:abc123... # immutable digest
 imagePullPolicy: IfNotPresent
 ports:
 - name: http
 containerPort: 8080
 resources:
 requests:
 cpu: 250m
 memory: 512Mi
 limits:
 cpu: 500m
 memory: 768Mi
 securityContext:
 allowPrivilegeEscalation: false
 readOnlyRootFilesystem: true
 capabilities: { drop: [ALL] }
 env:
 - name: LOG_LEVEL
 value: info
 - name: DB_URL
 valueFrom: { secretKeyRef: { name: order-service-secrets, key: db-url } }
 livenessProbe:
 httpGet: { path: /healthz/live, port: http }
 initialDelaySeconds: 30
 periodSeconds: 10
 timeoutSeconds: 2
 failureThreshold: 3
 readinessProbe:
 httpGet: { path: /healthz/ready, port: http }
 initialDelaySeconds: 5
 periodSeconds: 5
 timeoutSeconds: 2
 failureThreshold: 2
 startupProbe:
 httpGet: { path: /healthz/started, port: http }
 initialDelaySeconds: 0
 periodSeconds: 5
 failureThreshold: 60
 volumeMounts:
 - name: tmp
 mountPath: /tmp
 volumes:
 - name: tmp
 emptyDir: {}
```

The pod-security baseline (non-root, read-only root filesystem, capabilities dropped, seccomp default) is enforced cluster-wide via Pod Security Standards `restricted` profile. The above passes that profile.

### 3. Probes — three distinct concepts

K8s has three probes; they do different things:

| Probe | Question | Failure consequence |
|---|---|---|
| **liveness** | Is the pod still running correctly? | K8s restarts the pod. |
| **readiness** | Is the pod ready to serve traffic? | K8s removes the pod from the Service's endpoints. |
| **startup** | Has the pod finished starting? | Liveness/readiness don't fire until startup passes. |

Use all three. Common mistakes:
- One probe doing all three jobs (usually too aggressive for liveness, too lax for readiness).
- Liveness probe that checks downstream dependencies — restart-storms when a dependency is slow.
- Readiness that doesn't actually check the readiness condition (just returns 200) — sends traffic to broken pods.

### 4. Autoscaling — HPA + Cluster Autoscaler

HorizontalPodAutoscaler scales pods:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
 name: order-service
spec:
 scaleTargetRef:
 apiVersion: apps/v1
 kind: Deployment
 name: order-service
 minReplicas: 6
 maxReplicas: 50
 metrics:
 - type: Resource
 resource:
 name: cpu
 target: { type: Utilization, averageUtilization: 60 }
 - type: Resource
 resource:
 name: memory
 target: { type: Utilization, averageUtilization: 75 }
 behavior:
 scaleUp:
 stabilizationWindowSeconds: 60
 policies:
 - type: Percent
 value: 50 # max +50% in 30s
 periodSeconds: 30
 scaleDown:
 stabilizationWindowSeconds: 300
 policies:
 - type: Percent
 value: 25 # max -25% in 60s; slower
 periodSeconds: 60
```

VerticalPodAutoscaler (VPA) sizes the *requests/limits themselves* based on observed usage. Useful in `recommendation-mode` to inform manual sizing; in `auto-mode` it requires pod restart.

Cluster Autoscaler scales the *nodes*. Lives at the cluster level (provisioned by `iac`). HPA's success requires Cluster Autoscaler to be active or fixed node counts large enough.

For event-driven workloads, KEDA (Kubernetes Event-Driven Autoscaling) scales on external metrics — queue depth, Kafka lag, custom-business signals. Worth knowing about; activate when relevant.

### 5. Network policy — default deny

The cluster's default should be **default-deny** for ingress (with explicit allow-rules per service). This enforces the principle that *internal services need authorization too*.

```yaml
# default-deny across the cluster (applied at namespace level)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
 name: default-deny-ingress
 namespace: order-service-production
spec:
 podSelector: {}
 policyTypes: [Ingress]

# allow ingress from ingress controller and from other specific services
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
 name: allow-from-ingress
 namespace: order-service-production
spec:
 podSelector:
 matchLabels: { app: order-service }
 policyTypes: [Ingress]
 ingress:
 - from:
 - namespaceSelector:
 matchLabels: { name: ingress-system }
 podSelector:
 matchLabels: { app: nginx-ingress }
 ports:
 - port: 8080
 protocol: TCP
```

Egress policies are also useful but trickier (DNS, external services). Start with ingress; layer egress later.

### 6. Ingress and TLS termination

`Ingress` (legacy) or the Gateway API (modern) defines external traffic routing.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
 name: order-service
spec:
 parentRefs:
 - name: main-gateway
 sectionName: https
 hostnames:
 - api.example.com
 rules:
 - matches:
 - path: { type: PathPrefix, value: /orders }
 backendRefs:
 - name: order-service
 port: 8080
```

TLS termination at the gateway (cert-manager auto-issues certs from Let's Encrypt or an internal CA). Internal pod-to-pod traffic *can* be unencrypted within a trusted cluster but **service mesh (Istio / Linkerd) for mTLS is recommended** for production territory.

### 7. Secrets via External Secrets Operator

Cluster-native Secrets are base64, not encrypted. The discipline (per `secrets-config`):

- Secrets *originate* in the centralized secret store (AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / Vault).
- **External Secrets Operator** syncs them to K8s Secrets for runtime consumption.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
 name: order-service-secrets
spec:
 secretStoreRef:
 name: aws-secrets-manager
 kind: ClusterSecretStore
 refreshInterval: 1h
 target:
 name: order-service-secrets
 creationPolicy: Owner
 data:
 - secretKey: db-url
 remoteRef: { key: production/order-service/db-url }
 - secretKey: api-key
 remoteRef: { key: production/order-service/external-api-key }
```

Rotation in the external store propagates automatically (with a refresh delay).

### 8. GitOps with Argo CD or Flux

Manifests live in a Git repo (separate `infra-gitops` or `deploy/` directory in the app repo). Argo CD / Flux reconcile cluster state to match Git continuously.

```
deploy/
├── apps/
│ ├── base/ shared base manifests
│ │ ├── deployment.yaml
│ │ ├── service.yaml
│ │ ├── hpa.yaml
│ │ ├── networkpolicy.yaml
│ │ ├── externalsecret.yaml
│ │ └── kustomization.yaml
│ ├── overlays/
│ │ ├── dev/
│ │ │ ├── kustomization.yaml
│ │ │ └── values.yaml
│ │ ├── staging/
│ │ └── production/
└── argocd/
 └── applications/
 ├── order-service-dev.yaml
 ├── order-service-staging.yaml
 └── order-service-production.yaml
```

Image tags update in the GitOps repo (via a release process or Argo CD Image Updater) — the GitOps repo is the source of truth for what's deployed where.

### 9. Resource discipline

- **Always set requests AND limits**. No-limits pods can starve neighbors.
- **Requests ≈ measured workload**. Limits = requests × 1.5–2× for CPU, × 1.2 for memory.
- **Use PriorityClass** for critical workloads (the scheduler evicts lower-priority pods first under resource pressure).
- **PodDisruptionBudget** ensures voluntary disruptions (node drains, autoscaling) don't take more than N pods down simultaneously.

### 10. RBAC and ServiceAccount-per-service

Each service has its own ServiceAccount. The ServiceAccount's RBAC is least-privilege:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
 name: order-service
 namespace: order-service-production
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
 name: order-service-role
 namespace: order-service-production
rules:
 - apiGroups: [""]
 resources: ["configmaps"]
 verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
 name: order-service
 namespace: order-service-production
subjects:
 - kind: ServiceAccount
 name: order-service
roleRef:
 kind: Role
 name: order-service-role
 apiGroup: rbac.authorization.k8s.io
```

For cloud-provider IAM integration (IRSA on EKS, Workload Identity on GKE, Pod Identity on AKS), the ServiceAccount is annotated with the cloud identity — providing the pod with cloud credentials without long-lived keys.

## Helm vs Kustomize

Both are supported.

| | Helm | Kustomize |
|---|---|---|
| **Strength** | Templating; package distribution; rich ecosystem. | Pure YAML; no templating language to learn; bases + overlays. |
| **Tradeoff** | Templating obscures; chart complexity grows. | Less powerful for highly-dynamic manifests. |
| **When** | Off-the-shelf operators (cert-manager, ingress-nginx, etc.); reusable component charts. | App's own manifests with per-env overlays. |

Most projects: Kustomize for the app's manifests, Helm for third-party operators.

## Outputs

| Output | Location |
|---|---|
| Base manifests + overlays | `deploy/apps/base/` + `deploy/apps/overlays/<env>/` |
| Argo CD / Flux applications | `deploy/argocd/applications/` (or Flux equivalent) |
| Cluster conventions doc | `.project/procedural/k8s-conventions.md` |
| RBAC / network policy templates | `deploy/cluster/` (project-scoped) or in `iac` (cluster-scoped) |

## Mode handling (G/B)

**Greenfield.** Build manifests from the standard patterns; GitOps from day one.

**Brownfield.** Audit existing manifests; common findings: no resource limits, no network policy, no PDB, missing security context. Migrate one service at a time as slices touch them.

## What this skill does not do

- Provision the cluster — that's `iac`.
- Build the images — that's `containerization`.
- Deploy beyond K8s (cloud-native PaaS) — that's the cloud-specific packs (AWS / Azure / GCP).
- Service mesh (Istio / Linkerd patterns).
- Multi-cluster federation — advanced topic.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Kubernetes is overkill; use a simpler runtime." | Sometimes correct. K8s pays off at scale + complexity; at toy scale, use Fly / Render / ECS. |
| "Helm charts are the only way to package." | Kustomize, plain YAML, Pulumi-K8s, CDK8s are all valid. Pick deliberately. |
| "Default resource requests are fine." | Defaults cause OOMs and noisy-neighbors. Set requests + limits per workload. |
| "Liveness = readiness." | Liveness restarts the pod; readiness removes from load balancer. Different semantics; different probes. |
| "Service mesh adds value to every cluster." | Mesh adds value when you need mTLS / advanced routing / observability. Below that bar, it's complexity. |
| "Operators are the cloud-native pattern." | Operators are powerful + complex. Use existing operators; write your own only with strong justification. |
| "ConfigMaps for secrets." | ConfigMaps are not encrypted. Use Secrets resource + sealed-secrets or external-secrets controller. |

## Verification

You are done when:

- [ ] Namespace-per-environment isolation.
- [ ] RBAC documented per service account.
- [ ] Network policies enforce least-privilege ingress/egress.
- [ ] Resource requests + limits set per workload.
- [ ] Liveness + readiness probes correctly configured.
- [ ] Horizontal pod autoscaler configured where applicable.
- [ ] PodDisruptionBudgets defined for critical services.
- [ ] Pod security policy / PSA enforced (restricted profile by default).
- [ ] Manifests reviewed against Kubernetes best practices (kube-linter or equivalent).
- [ ] Cluster autoscaling configured.
- [ ] Observability integrated (metrics, logs, traces).

Evidence to check:
- A pod restart doesn't cascade into a cluster issue.
- Resource saturation alerts before OOMKill / eviction.

## Anti-patterns

- Pods without resource requests/limits.
- Liveness probe that checks downstream dependencies (restart-storm risk).
- Latest tags (`image: myorg/app:latest`) — non-reproducible.
- ConfigMaps with secret values (use Secrets via External Secrets).
- Cluster-wide `allow-all` network policy (no microsegmentation).
- ServiceAccount `default` used for app workloads (per-service SA only).
- `imagePullPolicy: Always` with mutable tags (defeats reproducibility).
- Missing PodDisruptionBudget on multi-replica services.
- HPA targeting CPU only when actual scaling driver is memory or queue depth.
- Direct kubectl apply for production (only GitOps reconciliation).
