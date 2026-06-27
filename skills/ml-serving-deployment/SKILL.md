---
name: ml-serving-deployment
description: Model serving design. Online (low-latency) vs batch vs streaming, A/B + shadow + canary deployment, multi-armed bandits where they fit, model-registry promotion policy, rollback. Online serving consumes resilience-patterns (timeouts, fallbacks, graceful degradation) — a slow model is worse than a missing model. Per the Resolved Decision, ships with refs for SageMaker / Vertex AI / Azure ML / KServe / Triton / BentoML / Ray Serve plus a mode-axis ref for batch vs online vs streaming. ML/AI Engineer owns; Platform/SRE operates infrastructure; deploy-release coordinates production cutover.
---

# ML Serving & Deployment


<!-- praxis:metadata:begin -->
```yaml
capability: ml
domain: ml
state: active
dependencies:
 - ml-training-evaluation
 - ml-feature-engineering
 - resilience-patterns
 - observability
 - deploy-release
triggers:
 - "deploying a model to production"
 - "choosing serving topology (online / batch / streaming)"
 - "designing A/B or shadow or canary rollout"
 - "establishing model-registry promotion policy"
 - "designing rollback for a model release"
 - "wiring observability for model serving"
outputs:
 - serving topology decision (online / batch / streaming) + ADR
 - deployment manifest (K8s / cloud-native serving)
 - registry promotion policy (experimental → staging → production stages)
 - rollback runbook (model-specific)
 - A/B or shadow or canary config for rollout
 - serving SLOs (latency, throughput, fallback policy)
consumers:
 - ml-ai-engineer (primary author)
 - platform-sre (operates serving infrastructure)
 - deploy-release (coordinates model deployment with code deployments)
 - ml-monitoring-drift (consumes serving for production monitoring hooks)
 - responsible-ai (consumes for production fairness monitoring)
references:
 - sagemaker.md
 - vertex-ai.md
 - azure-ml.md
 - kserve.md
 - triton.md
 - bentoml.md
 - ray-serve.md
 - batch-online-streaming.md
```
<!-- praxis:metadata:end -->

The bridge from "the model evaluates well in offline tests" to "the model produces value in production." Serving and deployment for ML are *not* the same as serving a stateless API — there are model-specific concerns (artifact management, A/B testing, shadow deployment, drift triggers) on top of normal service operational concerns.

The principle: **production models follow the same discipline as production services, plus ML-specific concerns. A slow model is worse than a missing model — graceful degradation is non-negotiable.**

## When this skill fires

- A trained model is moving from offline evaluation to production.
- Serving topology is being decided (online vs batch vs streaming).
- A rollout strategy is being designed (A/B, shadow, canary, progressive).
- The model registry promotion policy is being established.
- Rollback discipline is being designed for model releases.

## Serving topology

The first decision: how is the prediction served?

| Mode | Use when |
|---|---|
| **Online (request-time)** | Predictions needed in real time, single requests, low latency. Recommenders, fraud detection, search ranking. |
| **Batch** | Predictions computed in bulk on a schedule; cached for later use. Customer scoring, content classification at ingest. |
| **Streaming** | Predictions on event streams as they arrive; results published to downstream streams. Real-time risk scoring, content moderation streams. |

A single model often serves in multiple modes:

- Train once → batch-score the warehouse for offline analytics → online-serve fresh predictions for real-time use → stream-serve high-priority events.

Per the Resolved Decision, the `batch-online-streaming.md` reference covers the mode-axis specifics in addition to the platform-specific refs.

## Online serving — special concerns

### Latency budget

Per the NFR register, the model's prediction is one component of a larger user-facing operation. Budget:

```
Total user-perceived latency: 200ms
 - Network round-trip: 30ms
 - Auth, routing, business logic: 40ms
 - Feature retrieval: 50ms
 - Model inference: 50ms ← model's budget
 - Response serialization: 20ms
 - Headroom: 10ms
```

If model inference exceeds budget, **the model fails** — even with perfect accuracy. Trade-offs:

- **Smaller / faster model** — quantization, distillation, simpler architecture. Often gives up minimal accuracy for major latency wins.
- **Async pattern** — compute prediction async; respond to user immediately; deliver prediction later (only viable when the use case allows).
- **Precomputed predictions** — batch-score nightly; serve from cache for the common cases.

### Graceful degradation

When the model fails or is too slow, what does the system do? Per `resilience-patterns`:

- **Fallback to a baseline** — heuristic, rules, or the previous model version.
- **Fallback to default** — "show popular items" when recommender fails.
- **Fail-loud** — return an explicit "prediction unavailable" rather than a guess.

The choice depends on the application. **Returning a stale or wrong prediction silently is almost always worse than returning a known-default value with a flag.**

### Feature freshness at serving time

Online predictions consume features from the feature store. Per `ml-feature-engineering`:

- Online cache must be warm and up-to-date.
- Missing features → graceful default per feature spec.
- Feature staleness > threshold → warn or fail per policy.

## Rollout strategies for models

Distinct from code-deployment strategies (per `deploy-release`). ML rollouts add model-specific patterns:

### Shadow deployment

The new model runs alongside the old, scoring the same requests, but its predictions are **logged, not served**. The old model's predictions are served.

```
Request → Old Model (serves) → Response
 → New Model (logged for analysis) → comparison logs
```

After collecting enough comparison data: analyze new vs old offline. If the new model is better, promote.

Shadow is the safest first step for any model change. It surfaces production issues (latency, errors, feature problems) without risking customer impact.

### A/B testing

Split traffic between models (e.g., 90% old / 10% new). Measure outcomes per user-affecting metric (conversion, revenue, engagement).

A/B testing measures *business impact*, not just model metrics. The new model may have higher offline F1 but lower user retention — A/B exposes this.

Requirements:

- Random assignment per user (or per session, per the unit of analysis).
- Sufficient sample size for statistical power.
- Pre-registered hypothesis (avoid p-hacking).
- Duration sufficient to capture novelty effects.

### Canary deployment

Per `deploy-release`'s canary pattern, applied to models. Roll out new model to 5% → observe → 25% → 50% → 100%. Roll back at any stage if metrics degrade.

Canary is simpler than A/B and doesn't require random assignment; trade-off is less statistical rigor.

### Multi-armed bandits

For continuous optimization: traffic is dynamically allocated to model variants based on observed performance. The best-performing variant gets more traffic over time.

Bandits are powerful but complex; reserve for problems where:

- You have many model variants to compare.
- The objective is well-defined and quickly observable.
- The team has the statistical sophistication to interpret bandit outputs.

### Progressive delivery (model + flag)

Combine canary deployment with feature flags. The model is deployed dark; the feature flag controls who sees its predictions. Flag flips by user cohort, geography, tenant tier.

This is the modern default for high-stakes model releases.

## Model registry + promotion policy

Per `cicd-pipeline` and `containerization`'s artifact discipline, applied to models. Every trained model:

- **Registered** in the model registry (MLflow / Vertex / SageMaker / etc.).
- **Tagged with version** + reproducibility manifest.
- **Signed** (cosign signature attached).
- **Carries model card** (per `ml-training-evaluation`).

Promotion stages:

```
Experimental → Staging → Production
```

- **Experimental** — fresh from training; for offline evaluation and shadow deployment.
- **Staging** — passed offline gates; deployed to staging environment; running shadow against production.
- **Production** — passed staging gates; serving live traffic.

Promotion criteria are explicit per stage. Production promotion typically requires:

- Offline metrics passed against baseline.
- Shadow deployment results acceptable.
- Responsible-AI review complete (per `responsible-ai`).
- Production-go-live gate per `governance.yaml` evidence pack.

## Rollback

Every model deploy ships with explicit rollback:

- **Forward-only rollback** — re-deploy the previous model version. Simplest; works for most cases.
- **Feature-flag rollback** — flip flag to disable the new model; fallback path activates.
- **Traffic re-shift (canary / A/B)** — shift traffic back to old model; no re-deploy needed.

Rollback triggers documented per model:

- Online metric breach (latency, error rate).
- Business metric drop (conversion, revenue).
- Drift alert (per `ml-monitoring-drift`).
- Responsible-AI alert (fairness regression).
- Manual on-call discretion.

The first rollback must not be a production incident. Rehearse in staging.

## Observability for model serving

Per `observability` applied to ML:

- **Service metrics** — RED quartet (rate, errors, duration) per endpoint.
- **Model metrics** — prediction distributions, prediction-vs-feature joint distributions (drift inputs).
- **Business metrics** — outcome metrics (conversion, revenue) tied to model versions for A/B comparison.
- **Feature metrics** — feature distributions at serving time (drift inputs).

Hooks for `ml-monitoring-drift` (this catalog area — next skill): every prediction logs the features used + the prediction value + (eventually) the observed outcome. The drift monitor consumes these logs.

## Tooling

| Platform | Strength |
|---|---|
| **SageMaker** | AWS-native; broad ML lifecycle integration; managed inference endpoints. |
| **Vertex AI** | GCP-native; tight BigQuery + dataflow integration; Vertex Pipelines. |
| **Azure ML** | Azure-native; integrates with AKS for custom serving; AutoML. |
| **KServe** | K8s-native model serving; multi-framework; gRPC + REST. |
| **Triton** | NVIDIA's high-performance inference server; multi-framework; GPU-optimized. |
| **BentoML** | Python-native; framework-agnostic; flexible packaging. |
| **Ray Serve** | Python-native; complex serving pipelines; flexible scaling. |

Default for new projects: **cloud-native** when on a single cloud (SageMaker / Vertex / Azure ML) or **KServe** for K8s-agnostic / multi-cloud.

## Outputs

| Output | Location |
|---|---|
| Serving topology + ADR | `.project/decision/adr-NNN-ml-serving-topology.md` |
| Deployment manifest | repo: `serving/` |
| Promotion policy | `.project/procedural/model-promotion-policy.md` |
| Rollback runbook | `.project/operational/runbooks/model-rollback-{name}.md` |
| Rollout config (A/B, shadow, canary) | repo: `serving/rollout-{model}.yaml` |
| Serving SLOs | `.project/operational/ml-serving-slos.md` |

## Mode handling (G/B)

**Greenfield.** Apply discipline from the first deploy; shadow before A/B; A/B before full rollout; explicit rollback every time.

**Brownfield.** Audit existing ML deployments. Common findings: models deployed via "copy the file"; no rollback; no fallback path; no A/B. Migrate one model at a time to the discipline.

## What this skill does not do

- Train models — that's `ml-training-evaluation`.
- Build features — that's `ml-feature-engineering`.
- Monitor production drift — that's `ml-monitoring-drift`.
- Fairness audit — that's `responsible-ai`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Batch serving is sufficient." | Until latency-sensitive use cases emerge. Decide per use case; can hybrid. |
| "Shadow deploy is over-engineering." | Shadow catches correctness regressions invisible to canary. Cheap insurance. |
| "Canary at 10% is enough." | Canary is gradual (1→10→50→100) with per-step abort criteria. Two-step is not canary. |
| "Model registry is bureaucracy." | Registry is the trail of "what's deployed where and why." Auditable. |
| "Rollback is just deploying the old artifact." | Rollback needs trigger criteria, decision authority, communication. Run a drill. |
| "We don't need feature-flag fallback." | When the model is wrong + you can't roll back fast enough, the flag is the kill switch. |

## Verification

You are done when:

- [ ] Serving topology decided (online / batch / streaming) with rationale.
- [ ] Latency budget allocated per stage (preprocess / inference / postprocess).
- [ ] Graceful degradation: what serves when the model is unavailable?
- [ ] Rollout strategy: shadow → A/B → canary → progressive.
- [ ] Model registry stages used (experimental → staging → production).
- [ ] Rollback plan: trigger criteria + procedure + rehearsed.
- [ ] Observability hooks feed `ml-monitoring-drift`.
- [ ] Feature freshness verified at serving time.

Evidence to check:
- Last canary actually rolled back when criteria triggered (tested in staging).
- Registry shows current prod version + last rollback option.

## Anti-patterns

- Models served without graceful-degradation fallback.
- Online inference exceeding latency budget (model fails at production speed).
- Models deployed without shadow first.
- A/B test concluded before reaching statistical power.
- Rollback path untested.
- "Canary" that's 50% of traffic on first deploy.
- Model registry adopted but bypassed (ad-hoc model files).
- Promotion policy implicit ("ML Engineer says it's ready").
- Stale feature cache silently feeding production.
- No observability on model serving (can't tell if it's broken).
