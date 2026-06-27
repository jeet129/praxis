---
name: ml-monitoring-drift
description: Production model monitoring. Input-feature distribution drift, prediction drift, performance metrics (with label-arrival lag handled), data-quality regressions, train-serve skew detection, alerting tied to business SLOs, retraining triggers. ML observability is a superset of service observability — pair with `observability` skill; service-level metrics PLUS model-specific drift signals. ML/AI Engineer owns the monitoring design; Platform/SRE wires the collectors; incident-runbook handles model incidents like any other incident. Use whenever a model has been deployed and needs production monitoring, when a drift alert fires, when retraining cadence is being designed, or when investigating model performance regression.
---

# ML Monitoring & Drift


<!-- praxis:metadata:begin -->
```yaml
capability: ml
domain: ml
state: active
dependencies:
  - ml-serving-deployment
  - ml-feature-engineering
  - observability
  - reliability-dr
  - incident-runbook
triggers:
  - "designing monitoring for a newly-deployed model"
  - "drift alert firing in production"
  - "establishing retraining cadence + triggers"
  - "investigating model performance regression"
  - "wiring train-serve skew detection"
  - "labeling label-arrival lag in performance metric computation"
outputs:
  - monitoring dashboard spec (drift signals + business signals + service signals)
  - drift detectors per feature + prediction + label
  - retraining triggers (drift threshold + cadence + manual)
  - alerting rules (severity per drift class)
  - performance-with-label-lag dashboard (delayed-label correctness tracking)
  - feedback loops + closing rate
consumers:
  - ml-ai-engineer (primary author)
  - platform-sre (operates monitoring stack)
  - ml-serving-deployment (consumes monitoring hooks at serving time)
  - responsible-ai (monitoring per-slice production performance — fairness drift)
  - incident-runbook (model incidents follow incident workflow)
  - ml-training-evaluation (retraining triggered by this skill's signals)
references:
  - evidently.md
  - whylabs.md
  - arize.md
  - vertex-model-monitoring.md
```
<!-- praxis:metadata:end -->

The discipline that catches model failures in production. Models can stop working *correctly* while continuing to serve *successfully* — the service is up, predictions return, but the predictions are wrong. Standard observability catches service failures (latency, errors); ML monitoring catches the model-specific class.

The principle: **a model in production without monitoring is uncalibrated trust. Drift is silent and continuous; only instrumentation reveals it.**

## When this skill fires

- A model has been deployed and needs production monitoring.
- A drift alert fires — investigate root cause.
- Retraining cadence is being established or triggers configured.
- Model performance regression is suspected.
- Train-serve skew detection is being wired (continuous parity testing in production).
- Label-arrival lag handling needs design.

## The four monitoring classes

### 1. Input-feature drift

The distribution of input features changes between training and production:

- **Mean / variance shift** — a feature's average moves over time.
- **New categories** — categorical feature gets a new value not in training data.
- **Missing-rate change** — a feature's missingness rate spikes.
- **Outlier emergence** — values outside the training-time range start appearing.

Why it matters: the model is extrapolating outside its training distribution; performance is no longer guaranteed.

Detection methods:

- **Population Stability Index (PSI)** — common for binned features. PSI > 0.1 = moderate drift; > 0.25 = significant.
- **Kolmogorov-Smirnov test** — for continuous features.
- **Chi-square test** — for categorical features.
- **Earth-mover distance / Wasserstein distance** — distribution-distance metrics.

Per-feature drift dashboards with PSI plotted week-over-week.

### 2. Prediction drift

Even without input drift, prediction distributions can shift (rare but possible — model retraining, feature dependency change). Monitor:

- **Prediction histogram** — shape over time.
- **Average prediction** — for regression / probability outputs.
- **Class distribution** — for classification.

If predictions are stable but inputs drift: model may be generalizing OK. If predictions drift without input drift: something's wrong somewhere.

### 3. Performance drift (with label-arrival lag)

The hardest class: model accuracy in production. The challenge: **labels arrive late**.

- Predict "will churn within 30 days" → know in 30 days.
- Predict "is this fraud" → know in days (when chargeback arrives) or maybe never (some fraud is never reported).

Performance monitoring strategies:

- **Delayed-label tracking** — log predictions; join with labels when they arrive; compute lagged performance metrics.
- **Proxy metrics** — metrics computable without labels (prediction calibration, prediction variance).
- **Shadow / champion-challenger** — run a champion model and a known-good challenger; performance gap indicates drift.

Dashboards show performance metrics with label-lag explicitly:

```markdown
# Performance — Fraud Detection v1.4

| Metric | 7-day lagged | 30-day lagged | 90-day lagged |
|---|---|---|---|
| F1 | 0.83 | 0.82 | 0.81 |
| Precision | 0.85 | 0.84 | 0.83 |
| Recall | 0.81 | 0.80 | 0.79 |

(7-day = labels that arrived within 7 days of prediction; 90-day = essentially all labels in)

Last week: 7-day F1 = 0.79 → 4-point drop → triggered investigation.
```

### 4. Train-serve skew detection (production-side)

Per `ml-feature-engineering`'s parity discipline — verify at runtime that production features match training-time computation:

- **Sample requests** — for every Nth request, compute the feature both ways (online + via training pipeline reference) and compare.
- **Diff alerts** — if divergence > threshold, alert.

Catches feature pipeline regressions that the CI parity test missed.

## Tooling

| Tool | Strength |
|---|---|
| **Evidently** | Open-source; rich reports; framework-agnostic; default for self-hosted. |
| **WhyLabs** | Managed; lightweight; works for very large data. |
| **Arize** | Managed; ML observability platform; rich UI. |
| **Vertex AI Model Monitoring** | GCP-native; tight Vertex integration. |
| **SageMaker Model Monitor** | AWS-native. |
| **Fiddler / Truera** | Managed; focus on explainability + monitoring. |

Default for new projects: **Evidently** (self-hosted) or cloud-native (Vertex / SageMaker Model Monitor) for managed.

## Retraining triggers

Three classes:

### 1. Drift-based

When drift metric crosses threshold:

```yaml
trigger:
  type: drift
  feature: customer_30d_purchase_count
  metric: psi
  threshold: 0.25
  action: schedule_retraining
```

### 2. Cadence-based

Periodic regardless of drift:

```yaml
trigger:
  type: cadence
  schedule: monthly_on_first_monday
  action: schedule_retraining
```

### 3. Manual

Operator-initiated for known events (campaign launch, data source changed, business pivot).

Retraining policy per model documents which triggers apply + the retraining workflow (consumes `ml-training-evaluation`).

## Alerting

Drift alerts severity-tagged:

| Severity | Trigger | Response |
|---|---|---|
| **SEV1** | Performance metric below NFR for sustained window | Page; immediate investigation |
| **SEV2** | Significant input drift AND prediction drift AND degraded performance proxy | Page; investigate; possible rollback |
| **SEV3** | Single drift signal (input OR prediction) above moderate threshold | Ticket; investigate within sprint |
| **SEV4** | Drift trending toward threshold but not crossed | Notification; watch |

Alerts include the affected model, the drift signal, the dashboard link, and the runbook reference.

## Dashboard structure

Per model, three tiers:

**Tier 1 — "Is the model healthy?"**
- Service metrics (RED).
- Drift-summary indicators (red / yellow / green).
- Latest performance metrics with label-lag context.

**Tier 2 — "Drift detail"**
- Per-feature drift over time.
- Prediction drift over time.
- Performance lagged metrics.

**Tier 3 — "Investigation"**
- Per-slice metrics (drill into the failing segment).
- Sample errors with input features.
- Comparison vs offline baseline.

Tier 1 lives on the on-call's home screen (alongside service Tier 1).

## Incident response for models

Per `incident-runbook`'s standard workflow:

- Severity per the matrix above.
- Investigation tools: dashboards, drift detail, sampled errors.
- Mitigation options:
  - **Rollback** to previous model version (forward-only via `ml-serving-deployment`).
  - **Disable feature** (flag off the model; fallback path activates).
  - **Threshold tuning** (temporary fix while root cause investigated).
  - **Retraining** with fresh data (slower; may require offline eval before re-deploy).
- Postmortem per `incident-runbook` discipline; blameless; action items tracked.

ML incidents follow the same workflow as service incidents — they're not a special class.

## Feedback loops

Models often create feedback loops in production:

- Recommender → users click recommended items → those items dominate the next training data → recommender narrows further.
- Fraud model → blocks transactions → blocked transactions never observed as legit → model loses signal on edge cases.

Detect feedback loops via:

- **Exposure tracking** — log what was shown vs not shown; correct for selection bias in training data.
- **Counterfactual evaluation** — what would have happened if we'd shown different recommendations?
- **Randomized exploration** — small fraction of traffic shows random / non-model selections to maintain training signal.

Feedback loops are subtle; design for them at framing time (per `ml-problem-framing`'s risk log).

## Outputs

| Output | Location |
|---|---|
| Monitoring dashboard spec | provisioned via IaC; documented in `.project/operational/ml-monitoring-{model}.md` |
| Drift detectors | configured in monitoring tool |
| Retraining triggers | `.project/procedural/retraining-policy-{model}.md` |
| Alerting rules | configured in monitoring + alert routing tool |
| Performance-with-label-lag dashboard | provisioned and documented |
| Feedback-loop instrumentation | per model design doc |

## Mode handling (G/B)

**Greenfield.** Monitoring from day one; drift detectors live before first production request.

**Brownfield.** Audit existing ML deployments. Common findings: zero monitoring; "the model works" because no one's checking; drift discovered when business metrics regress. Address by instrumenting one model at a time.

## What this skill does not do

- Train models — that's `ml-training-evaluation`.
- Serve models — that's `ml-serving-deployment`.
- Fairness monitoring — that's `responsible-ai` (this skill provides infrastructure for per-slice metrics; that skill defines the fairness criteria).
- Service-level observability — that's `observability` (this skill extends with ML-specific signals).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Service metrics are enough." | A model can serve perfectly and produce wrong predictions. Drift signals are the ML-specific layer. |
| "Drift only matters if labels arrive late." | Drift on inputs + predictions matters even without labels. Performance drift is one of three classes. |
| "We'll retrain quarterly regardless." | Cadence-only retraining over-trains or under-trains. Drift-triggered + cadence + manual together. |
| "Train-serve skew is checked once at deploy." | Pipelines drift. Production parity verification is continuous. |
| "Feedback loops are unavoidable." | They are; recognizable, instrumentable, sometimes mitigable. Recognize first. |
| "PSI thresholds are universal." | Tune per feature and use case. Generic thresholds cause alert fatigue or missed signals. |

## Verification

You are done when:

- [ ] Monitoring covers: input drift, prediction drift, performance (with label-lag), train-serve skew.
- [ ] Per-feature drift detectors with tuned thresholds.
- [ ] Performance dashboard handles label-arrival lag (lagged metrics).
- [ ] Retraining triggers documented: drift / cadence / manual.
- [ ] Alerting tied to business SLOs; severity matrix defined.
- [ ] Feedback-loop instrumentation where applicable.
- [ ] Three-tier dashboards: health → drift detail → investigation.
- [ ] Tooling integrated (Evidently / WhyLabs / Arize / vendor).

Evidence to check:
- A planted drift triggers detection within window.
- Alert routes to ML/AI Engineer + Security on-call (per `responsible-ai`'s harm signal where applicable).

## Anti-patterns

- No monitoring beyond service-level metrics.
- Drift detected only when business metrics regress (lagging signal).
- Retraining on a fixed cadence without drift triggers (over-retrain or under-retrain).
- Performance metric computed without label-lag context.
- Alerts that don't lead to action (alert fatigue).
- Feedback loops unrecognized.
- Drift detectors with thresholds never tuned (false alarms or missed signals).
- Production train-serve parity not measured.
- Champion-challenger setup never analyzed.
- ML incidents treated as a special class (not in `incident-runbook` workflow).
