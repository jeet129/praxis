# ML Serving / Deployment — KServe

KServe is the Kubernetes-native model-serving layer built on Knative Serving — declarative `InferenceService` CRDs, standardized (V1/V2) inference protocols across frameworks, scale-to-zero, and canary rollout as a first-class field.

## Why KServe over hand-rolled deployments

- One CRD (`InferenceService`) abstracts Triton, TorchServe, TF Serving, SKLearn, XGBoost, and custom runtimes behind the same interface — swapping model frameworks doesn't mean rewriting deployment manifests.
- Scale-to-zero and request-driven autoscaling (via Knative) fit spiky inference traffic without paying for idle GPU/CPU.
- Canary traffic splitting is a field on the spec, not a separate service-mesh configuration project.

## InferenceService — predictor

Minimal predictor-only deployment:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: fraud-classifier
  namespace: ml-serving
spec:
  predictor:
    sklearn:
      storageUri: "s3://models/fraud-classifier/v3/"
      resources:
        requests: { cpu: "1", memory: "2Gi" }
        limits: { cpu: "2", memory: "4Gi" }
    minReplicas: 1
    maxReplicas: 10
```

Custom runtime (arbitrary container, e.g. a FastAPI wrapper around a PyTorch model):

```yaml
spec:
  predictor:
    containers:
      - name: kserve-container
        image: registry.internal/fraud-classifier-server:1.4.0
        ports: [{ containerPort: 8080, protocol: TCP }]
        resources:
          requests: { cpu: "2", memory: "4Gi", nvidia.com/gpu: "1" }
          limits: { cpu: "4", memory: "8Gi", nvidia.com/gpu: "1" }
        env:
          - name: MODEL_PATH
            value: /mnt/models
```

## Transformers and explainers

`transformer` runs pre/post-processing (feature encoding, response shaping) as a separate scalable component ahead of the predictor — decouples data-prep compute from model-inference compute so each scales independently.

```yaml
spec:
  transformer:
    containers:
      - name: transformer
        image: registry.internal/fraud-feature-transformer:2.1.0
        resources:
          requests: { cpu: "500m", memory: "512Mi" }
  predictor:
    sklearn:
      storageUri: "s3://models/fraud-classifier/v3/"
  explainer:
    containers:
      - name: explainer
        image: registry.internal/fraud-shap-explainer:1.0.0
```

`explainer` (SHAP, Alibi) serves explanation requests on a separate path (`/v1/models/:predict` vs `/v1/models/:explain`) — only invoked when explanation is requested, keeping the hot predict path's latency unaffected.

## Autoscaling, including scale-to-zero

KServe rides on Knative's request-based autoscaler (KPA) by default — scales on concurrent requests per pod, not CPU, which fits inference workloads better than CPU-based HPA (a GPU-bound model can be CPU-idle while GPU-saturated).

```yaml
spec:
  predictor:
    minReplicas: 0                      # scale-to-zero enabled
    maxReplicas: 20
    scaleTarget: 10                     # target concurrent requests per pod
    scaleMetric: concurrency
    containerConcurrency: 10
```

- `minReplicas: 0` — scales to zero after an idle window (default 30s, tunable via `revisionTimeoutSeconds` / Knative config); the first request after idle pays a cold-start penalty. Use for low-traffic, non-latency-critical models (batch-adjacent, internal tooling).
- `minReplicas: 1+` — always-warm, for latency-sensitive or SLA-bound endpoints. Scale-to-zero is a cost optimization, not a default — apply it deliberately per model's traffic and latency profile.
- Cold start with large models (GPU, multi-GB weights) can be tens of seconds — mitigate with `minReplicas: 1` or a smaller "always-warm" replica pool sized to expected baseline traffic.

## Canary rollout

Traffic percentage split between the current and a new revision, controlled declaratively:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata: { name: fraud-classifier }
spec:
  predictor:
    sklearn:
      storageUri: "s3://models/fraud-classifier/v4/"
    minReplicas: 1
  # canaryTrafficPercent is set on the InferenceService revision annotation
---
# Applied as an update — 10% to v4, 90% stays on the last-known-good revision
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: fraud-classifier
  annotations:
    serving.kserve.io/canaryTrafficPercent: "10"
spec:
  predictor:
    sklearn: { storageUri: "s3://models/fraud-classifier/v4/" }
```

Promote by increasing `canaryTrafficPercent` toward 100 as metrics stay healthy; roll back by reverting `storageUri` / setting the percent to 0. For metric-gated automated promotion (not just manual percent bumps), pair with `argo-rollouts` analysis templates driving the same traffic-split mechanism — see `deploy-release/references/argo-rollouts.md`.

## GPU packing

- **Multi-Instance GPU (MIG)** on A100/H100 — partition a physical GPU into isolated slices, request `nvidia.com/mig-1g.5gb` etc. in `resources`, when a model doesn't need a full GPU.
- **Time-slicing** — multiple pods share a GPU via NVIDIA's k8s device-plugin time-slicing config, when workloads are latency-tolerant and don't need MIG's hard isolation.
- **Batch inference server** (Triton via `predictor.triton`) — dynamic batching packs concurrent single-item requests into GPU batches transparently, dramatically improving GPU utilization for many-small-requests traffic patterns:

```yaml
spec:
  predictor:
    triton:
      storageUri: "s3://models/fraud-classifier-triton/"
      resources:
        requests: { nvidia.com/gpu: "1" }
      runtimeVersion: "24.05-py3"
    minReplicas: 1
```

Node pool taints/tolerations + `nodeSelector` pin GPU-requiring `InferenceService`s to GPU node pools, keeping CPU-only workloads off expensive nodes.

## Common violations to flag in review

- `minReplicas: 0` on a latency-SLA-bound endpoint — cold start violates the SLA on the first request after idle.
- No `resources.limits` set — a runaway model container can starve co-located pods.
- Canary rollout skipped entirely for a model-weight update — model updates are code deploys and deserve the same staged rollout as any other release.
- GPU requested without MIG/time-slicing consideration for models that don't need a full GPU — wasted spend.
- `containerConcurrency` left at the framework default without load-testing the actual per-replica capacity (see `performance-testing/references/k6.md`).
- Transformer logic embedded inside the predictor container instead of split out — couples pre-processing scaling to model-inference scaling unnecessarily.
