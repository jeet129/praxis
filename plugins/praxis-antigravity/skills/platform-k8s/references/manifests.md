# Reference — Kubernetes manifest templates

Loaded by `platform-k8s` for the full YAML templates behind each discipline item in the SKILL.md. These are illustrative starting points (namespace `order-service-production`, app `order-service`) — adapt names, resource sizing, and policy scope per service.

## Workload manifest — Deployment (standard stateless service)

A typical stateless service runs as a `Deployment` + `Service` + `ConfigMap` + `Secret` (via External Secrets) + `HorizontalPodAutoscaler` + optionally `PodDisruptionBudget` + `NetworkPolicy`.

The pod-security baseline below (non-root, read-only root filesystem, capabilities dropped, seccomp default) is enforced cluster-wide via Pod Security Standards `restricted` profile and passes that profile.

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
  replicas: 6                        # min for HA across 3 AZs with 2 each
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
          image: ghcr.io/myorg/order-service@sha256:abc123...   # immutable digest
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

## Autoscaling — HorizontalPodAutoscaler

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
          value: 50            # max +50% in 30s
          periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 25            # max -25% in 60s; slower
          periodSeconds: 60
```

VerticalPodAutoscaler (VPA) sizes the *requests/limits themselves* based on observed usage — useful in `recommendation-mode` to inform manual sizing; `auto-mode` requires pod restart. Cluster Autoscaler scales the *nodes* (provisioned by `iac`); HPA's success requires it active or fixed node counts large enough. For event-driven workloads, KEDA scales on external metrics (queue depth, Kafka lag, custom-business signals).

## Network policy — default deny + explicit allow

The cluster's default should be **default-deny** for ingress (with explicit allow-rules per service). Egress policies are also useful but trickier (DNS, external services) — start with ingress, layer egress later.

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
---
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

## Ingress and TLS termination

`Ingress` (legacy) or the Gateway API (modern) defines external traffic routing. TLS termination at the gateway (cert-manager auto-issues certs from Let's Encrypt or an internal CA). Internal pod-to-pod traffic *can* be unencrypted within a trusted cluster but **service mesh (Istio / Linkerd) for mTLS is recommended** for production territory.

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

## Secrets via External Secrets Operator

Cluster-native Secrets are base64, not encrypted. Secrets *originate* in the centralized secret store (AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / Vault); **External Secrets Operator** syncs them to K8s Secrets for runtime consumption. Rotation in the external store propagates automatically (with a refresh delay).

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

## GitOps repo layout (Argo CD / Flux)

Manifests live in a Git repo (separate `infra-gitops` or `deploy/` directory in the app repo). Argo CD / Flux reconcile cluster state to match Git continuously. Image tags update in the GitOps repo (via a release process or Argo CD Image Updater) — the GitOps repo is the source of truth for what's deployed where.

```
deploy/
├── apps/
│   ├── base/                    shared base manifests
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   ├── networkpolicy.yaml
│   │   ├── externalsecret.yaml
│   │   └── kustomization.yaml
│   ├── overlays/
│   │   ├── dev/
│   │   │   ├── kustomization.yaml
│   │   │   └── values.yaml
│   │   ├── staging/
│   │   └── production/
└── argocd/
    └── applications/
        ├── order-service-dev.yaml
        ├── order-service-staging.yaml
        └── order-service-production.yaml
```

## RBAC — ServiceAccount-per-service

Each service has its own ServiceAccount with least-privilege RBAC. For cloud-provider IAM integration (IRSA on EKS, Workload Identity on GKE, Pod Identity on AKS), the ServiceAccount is annotated with the cloud identity — providing the pod with cloud credentials without long-lived keys.

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
