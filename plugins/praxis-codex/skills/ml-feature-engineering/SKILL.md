---
name: ml-feature-engineering
description: "Feature design and operationalization with point-in-time correctness. Feature definitions, train/serve skew prevention, feature-store integration, leakage avoidance, materialization strategy (batch vs online vs streaming). The most-leveraged single technical activity in an ML project; the difference between models that work in notebooks and models that work in production. ML/AI Engineer owns this; Data Engineer integrates feature pipelines with the data plane. Use whenever features are being designed for a model, when investigating train-serve skew, when integrating a feature store, or when handling temporal correctness."
---

# ML Feature Engineering

<!-- praxis:metadata:begin -->
```yaml
capability: ml
domain: ml
state: active
dependencies:
 - ml-problem-framing
 - data-pipeline
 - data-warehouse-modeling
 - data-quality
triggers:
 - "designing features for a new model"
 - "investigating model performance regression that may be feature-related"
 - "integrating a feature store"
 - "preventing train-serve skew"
 - "handling point-in-time correctness in feature pipelines"
 - "materializing features for online serving"
outputs:
 - feature specs (definition + source + transformation + freshness + window)
 - feature store entries (Feast / Tecton / Vertex FS / Databricks FS / SageMaker FS)
 - train/serve parity tests
 - materialization plan (batch / online / streaming per feature)
 - leakage-prevention review (per feature)
consumers:
 - ml-ai-engineer (primary author)
 - data-engineer (operates the feature pipelines)
 - ml-training-evaluation (consumes features for training)
 - ml-serving-deployment (consumes features for serving)
 - ml-monitoring-drift (monitors feature distributions in production)
references:
 - feast.md
 - tecton.md
 - vertex-fs.md
 - databricks-fs.md
 - sagemaker-fs.md
```
<!-- praxis:metadata:end -->

The boundary between data and model. Features are the model's vocabulary; their quality bounds the model's quality. Done well, features are reusable across models, point-in-time correct, and identical at training and serving time. Done poorly, models work in notebooks and fail in production — almost always due to feature problems, not model architecture.

The principle: **feature engineering is the difference between research prototypes and production ML systems.**

## When this skill fires

- New features are being designed for a model.
- Model accuracy regresses in production — investigate train-serve skew first.
- A feature store is being adopted (Feast / Tecton / Vertex FS / Databricks FS / SageMaker FS).
- Point-in-time correctness needs validating.
- Online serving requires materializing features at request time.

## The four big problems

### 1. Train-serve skew

The single most common ML production failure. Features computed differently at training time vs serving time → model sees different inputs in production than it learned from → silent degradation.

Causes:

- **Different code paths** — training uses SQL on the warehouse; serving uses Python on the request payload. Same logic, slightly different.
- **Different time windows** — training uses "last 30 days of activity"; serving uses "last 30 days as of the model load," not "as of right now."
- **Different normalizations** — training normalizes against a fixed mean/std; serving doesn't apply the same.
- **Missing features at serving time** — training had everything; production data sometimes lacks a field.

Defense: **identical feature transformation code at train and serve**. The feature store enforces this by being the source of both training data and serving values.

### 2. Point-in-time correctness (no leakage)

The training data for a prediction must contain *only* information available at the time of the prediction.

Common leak:

```sql
-- BAD: includes today's session count when predicting yesterday's purchase intent
SELECT
 user_id,
 yesterday_purchase_intent_label,
 -- LEAK: today's session count is not knowable when predicting yesterday
 COUNT(*) AS session_count_30d
FROM events
WHERE event_date BETWEEN '2026-01-01' AND '2026-12-01' -- includes future!
GROUP BY user_id
```

The model trains "well," then fails in production because it learned to use future information that's not available at inference time.

Defense: feature pipelines use **as-of joins** — features are computed as of the prediction timestamp:

```sql
-- GOOD: features as of the prediction timestamp
SELECT
 label.user_id,
 label.label,
 -- as-of join: events strictly before the prediction event
 (SELECT COUNT(*) FROM events
 WHERE events.user_id = label.user_id
 AND events.event_time < label.prediction_time
 AND events.event_time >= label.prediction_time - INTERVAL '30 days'
) AS session_count_30d
FROM labels
```

Modern feature stores handle this directly via point-in-time joins.

### 3. Materialization strategy per feature

Where does the feature live, and how is it computed?

| Strategy | Use when |
|---|---|
| **Batch** | Feature computed periodically (hourly / daily); cached in a feature store; served from cache. Suitable when the underlying data updates on a similar cadence. Example: `customer_lifetime_value_90d` updated nightly. |
| **Streaming** | Feature updated continuously from event streams. Lower latency than batch; more complex. Example: `last_5_minutes_click_count` from a clickstream. |
| **Online (request-time)** | Feature computed at request time from the request payload + cached lookups. Lowest latency for inputs only available at request time. Example: `current_cart_total` from the request itself. |
| **Pre-computed** | Feature stored as a column in the warehouse / DB; just read. For features that change rarely. Example: `customer_signup_date`. |

A single model often uses features of all four types. The feature store mediates them.

### 4. Feature store discipline

The feature store provides:

- **Registry** — feature definitions, owners, lineage, descriptions.
- **Training data generation** — point-in-time correct joins for training data.
- **Online serving** — low-latency feature retrieval at inference time.
- **Train-serve parity** — same transformation code at both paths.
- **Versioning** — feature definitions versioned; changes don't break consumers silently.

Tool choice (per refs):

- **Feast** — open-source; pluggable backends; lightweight. Default for self-hosted.
- **Tecton** — managed; enterprise; productionizes streaming features.
- **Vertex AI Feature Store** — GCP-native.
- **Databricks Feature Store** — tight Databricks integration; Unity Catalog-aware.
- **SageMaker Feature Store** — AWS-native.

Default for new projects: **Feast** (self-hosted) or the cloud-native option matching the platform.

## Feature design discipline

### Feature definition template

Per feature:

```yaml
name: customer_30d_purchase_count
description: Number of completed purchases by the customer in the last 30 days as of the feature timestamp.
owner: ml-platform-team
source: warehouse.fct_orders
transformation: |
 COUNT(*) FROM orders
 WHERE orders.customer_id = entity.customer_id
 AND orders.status = 'completed'
 AND orders.completed_at < feature_timestamp
 AND orders.completed_at >= feature_timestamp - INTERVAL '30 days'
freshness: batch_daily # this feature updates daily; expected staleness < 1 day at serving
window: 30d
type: int64
default: 0
serving_storage: online_cache (Redis)
training_storage: warehouse
tests:
 - not_null
 - range: [0, 10000]
 - completeness: >= 99% of expected entities have non-default values
```

### Naming convention

`<entity>_<aggregation>_<window>_<measure>` — e.g., `customer_avg_7d_order_value`, `product_top_30d_category`.

Consistent naming makes feature reuse possible. Inconsistent naming produces duplicates with the same semantics.

### Reuse > recompute

Features should be reusable across models. The feature store's catalog lets the team find existing features:

- New model needs "customer purchase count last 30 days" → check the store; if it exists, use it.
- Not in the store → create it as a *registered* feature (not inline in the model code) so the next team can reuse.

Inline features (computed in model training code, not in the store) are an anti-pattern at scale.

## Train-serve parity tests

For each feature, a parity test runs in CI:

1. Compute the feature from training-time code (warehouse query).
2. Compute the feature from serving-time code (online lookup or request-time computation).
3. Assert they're identical for the same entity + timestamp.

Failures block deploy. This is the single most leveraged test in ML systems.

## Feature monitoring (handoff to `ml-monitoring-drift`)

In production, feature distributions are tracked:

- Distribution drift on each feature (week-over-week comparison).
- Missingness rate.
- Range and percentile drift.

When a feature distribution shifts, the model may not generalize. `ml-monitoring-drift` handles the production monitoring; this skill ensures the right *instrumentation* exists at feature definition time.

## Outputs

| Output | Location |
|---|---|
| Feature specs | feature store registry + `.project/semantic/feature-catalog.md` |
| Feature store entries | external store (Feast / Tecton / cloud-native) |
| Train/serve parity tests | CI suite |
| Materialization plan | inline in feature spec |
| Leakage-prevention review | per feature in PR review |

## Mode handling (G/B)

**Greenfield.** Feature store from day one; every feature registered; parity tests enforced.

**Brownfield.** Audit existing features. Common findings: inline feature code per model (duplicated, drifting); train-serve skew never measured; leakage in training data. Migrate one model at a time to the feature store; parity tests are the migration acceptance test.

## What this skill does not do

- Frame the problem — that's `ml-problem-framing`.
- Train the model — that's `ml-training-evaluation`.
- Serve the model — that's `ml-serving-deployment`.
- Monitor drift in production — that's `ml-monitoring-drift`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Train-serve skew is a theoretical concern." | It's the #1 source of "works in notebook, fails in prod." Test parity in CI. |
| "Point-in-time correctness is for academic ML." | Future leakage at training time = inflated metrics + production disappointment. Real concern. |
| "Feature store is overkill." | At one model yes; at multiple models sharing features, the store prevents drift between teams. |
| "Online features can be computed on-demand." | Until latency budget says no. Materialization strategy is a design choice. |
| "Late features are OK with imputation." | Imputation in production introduces bias not in training. Test parity. |
| "Schema drift is detectable later." | Yes, by users. Catch at the feature pipeline boundary. |

## Verification

You are done when:

- [ ] Features documented: name, source, transformation, freshness, materialization strategy.
- [ ] Train-serve parity tested in CI (same input → same feature both online + offline).
- [ ] Point-in-time correctness: as-of joins use the timestamp known at prediction time.
- [ ] Materialization decided per feature (batch / streaming / online / pre-computed).
- [ ] Feature store integration documented (per project's choice).
- [ ] Schema versioning + evolution policy.
- [ ] Backfill capability for new features.
- [ ] Tests cover key edge cases (missing, late, malformed).

Evidence to check:
- A model trained on point-in-time-correct data has consistent train + holdout performance.
- Online serving feature values match offline computation for sampled requests.

## Anti-patterns

- Inline feature code per model (no reuse; drift across models).
- Training features computed in SQL; serving features computed in Python (skew guaranteed).
- Future-leakage in training data.
- "Just use the latest aggregate" at serving time (no point-in-time correctness).
- Missing features at serving time handled silently (predictions on wrong inputs).
- Feature store adopted but bypassed by model teams ("it's faster to compute inline").
- No parity tests (skew surfaces in production only).
- Feature names that hide their semantics (`feat_42`).
- Features with no owner.
- Reusable features sitting in one team's repo because no one knows they exist.
