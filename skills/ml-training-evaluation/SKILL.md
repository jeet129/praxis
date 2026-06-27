---
name: ml-training-evaluation
description: Reproducible training plus rigorous evaluation. Experiment tracking, data + code + config versioning, eval harness (holdout, cross-validation, slice-based metrics, calibration, error analysis), confidence intervals and statistical significance vs baseline. The model card is part of the deliverable, not a postscript. Per the Resolved Decision, ships with refs for MLflow / W&B / Vertex Experiments / SageMaker Experiments / Comet. ML/AI Engineer owns this; the trained model + model card flow to ml-serving-deployment for productionization. Use whenever a model is being trained, when evaluating against a baseline, when comparing model variants, or when assembling the responsible-AI evidence pack.
---

# ML Training & Evaluation


<!-- praxis:metadata:begin -->
```yaml
capability: ml
domain: ml
state: active
dependencies:
 - ml-problem-framing
 - ml-feature-engineering
 - engineering-standards
triggers:
 - "training a new model"
 - "evaluating a model against the baseline"
 - "comparing model variants for selection"
 - "running cross-validation or holdout testing"
 - "computing slice-based metrics (per-segment performance)"
 - "calibrating predicted probabilities"
 - "assembling the model card"
outputs:
 - trained model artifact (versioned + signed)
 - eval report (overall + per-slice metrics + calibration + error analysis)
 - experiment-tracking entries (every run logged)
 - model card (describes what was built, how, what it does well + poorly, intended use)
 - confidence intervals + significance vs baseline
 - reproducibility manifest (data version + code commit + config + seeds)
consumers:
 - ml-ai-engineer (primary author)
 - ml-serving-deployment (consumes model artifact + card for productionization)
 - responsible-ai (consumes per-slice metrics + model card for fairness audit)
 - ml-monitoring-drift (consumes baseline distributions for production monitoring)
 - product-manager (consumes eval results vs business metric)
references:
 - mlflow.md
 - wandb.md
 - vertex-experiments.md
 - sagemaker-experiments.md
 - comet.md
```
<!-- praxis:metadata:end -->

The discipline that turns training code into a reproducible system and evaluation into honest evidence. Without it, "the model is good" is a story; with it, it's a documented claim with confidence intervals, per-slice breakdowns, and calibration.

The principle: **train reproducibly; evaluate honestly; produce a model card that lets future readers understand what was built and why.**

## When this skill fires

- A new model is being trained.
- Model variants are being compared for selection.
- Evaluation results are needed against the baseline from `ml-problem-framing`.
- Slice-based metrics need computation (per-segment, per-cohort, per-protected-class).
- Calibration of predicted probabilities is being assessed.
- A model card is being assembled for the responsible-AI gate.

## Reproducibility — the foundation

Without reproducibility, evaluation is opinion. The components:

### 1. Code versioning

Training code lives in the repo. The trained model artifact carries the git commit it was trained from. Re-running from that commit (with the same data + config + seeds) produces an identical model.

### 2. Data versioning

The training dataset is identified by:

- **Data version** — typically a snapshot identifier in the feature store + warehouse.
- **Feature versions** — feature definitions at training time (per `ml-feature-engineering`).
- **Filter / sampling logic** — captured in code.

Tools: DVC, lakeFS, Delta Lake time-travel, warehouse snapshot IDs.

### 3. Config versioning

Hyperparameters, training settings, evaluation thresholds — all in a config file in the repo, versioned with the code.

### 4. Seed control

Every source of randomness (data shuffling, weight initialization, dropout, etc.) uses an explicit seed. Same seed + same data + same code = same model.

### 5. Environment pinning

Python + library versions pinned (per `engineering-standards`). Container image SHA-pinned.

## Experiment tracking

Every training run is logged to an experiment tracker:

- **What was tried** — hyperparameters, data version, config.
- **What happened** — metrics during training (loss curves), final eval metrics.
- **Artifacts** — model checkpoints, eval reports, confusion matrices.

Tool choice (per refs, agnostic decision):

- **MLflow** — open-source; broad ecosystem; default for self-hosted.
- **Weights & Biases** — managed; rich UI; collaboration features.
- **Vertex AI Experiments** — GCP-native.
- **SageMaker Experiments** — AWS-native.
- **Comet** — managed alternative.

Default for new projects: **MLflow** (self-hosted) or the cloud-native option matching the platform.

The experiment tracker becomes the team's institutional memory. "Why didn't we use this approach?" → search the tracker; the failed experiment is there with its results.

## Evaluation discipline

### Train / validation / test splits

Three sets, used in three distinct phases:

- **Training set** — model fits these.
- **Validation set** — used to choose hyperparameters and stop training early. Look at often.
- **Test set** — held out completely until final evaluation. **Touched once per model release**, not per experiment.

The test set is sacred. Looking at test results during model iteration leaks information; you optimize for the test set unintentionally, and the test set stops being a fair evaluation.

For temporal data (time-series, recommendations, churn): split *by time*, not random. Training data must precede test data in time, mirroring production.

### Cross-validation

When data is small: k-fold cross-validation provides more robust metrics. For time-series: time-series CV (each fold's test set is later in time than its train set).

### Per-slice metrics

Aggregate metrics hide problems. Always compute per-slice:

- **Per-segment** — customer tier, geography, product category.
- **Per-cohort** — new vs returning users, by acquisition channel, by time period.
- **Per-protected-class** — race, gender, age (when relevant per `responsible-ai`).
- **Per-difficulty** — easy vs hard examples (often defined by where the baseline succeeds vs fails).

Example:

```markdown
## Per-slice F1

| Slice | F1 | Volume | vs Baseline |
|---|---|---|---|
| Overall | 0.84 | 1,000,000 | +0.12 |
| Customer tier: Free | 0.78 | 700,000 | +0.10 |
| Customer tier: Pro | 0.91 | 250,000 | +0.18 |
| Customer tier: Enterprise | 0.95 | 50,000 | +0.20 |
| Geography: US | 0.86 | 600,000 | +0.13 |
| Geography: EU | 0.83 | 250,000 | +0.11 |
| Geography: ROW | 0.74 | 150,000 | +0.05 | ← weak; investigate
```

The overall metric looks good; one slice ("ROW" — Rest of World) is performing far worse and barely beating the baseline. **Aggregate metrics would have hidden this.**

### Calibration

For probability outputs: does "the model says 0.7" actually mean 70% probability?

Plot calibration curves. Compute expected calibration error (ECE).

When uncalibrated: temperature scaling, Platt scaling, isotonic regression to fix. Calibration matters when:

- Probabilities are consumed by downstream decisions (thresholds, expected values).
- Costs of FP / FN differ.
- Probabilities are exposed to users or other systems.

### Confidence intervals + statistical significance

"Model A's F1 = 0.84; Model B's F1 = 0.85" — is B actually better?

- **Bootstrap confidence intervals** — resample the test set; compute the metric; CI from the distribution.
- **Significance vs baseline** — paired test (McNemar for classification; permutation test broadly).

Don't claim improvement without statistical evidence. Many "improvements" don't survive a CI.

### Error analysis

Beyond aggregate numbers: look at the model's mistakes. Categorize them:

- What kinds of inputs does it fail on?
- Are failures systematic (specific data patterns) or random?
- Are some errors more harmful than others?

Error analysis often drives the next iteration's data work (more examples of failure modes) or feature work (new features that distinguish hard cases).

## The model card

The deliverable's final piece. A model card describes the model in plain language:

```markdown
# Model Card: Fraud Detection v1.4

## Intended use
- Real-time scoring of e-commerce transactions for fraud risk.
- Output: probability of fraud (calibrated).
- Consuming system: payments authorization service.

## Intended NOT to be used for
- Account / identity decisions (separate models exist).
- Cross-border or B2B transactions (training data is consumer DTC only).
- Manual review prioritization (post-hoc analysis differs from real-time).

## Performance
- Overall F1 = 0.84 [95% CI: 0.82, 0.86]
- Versus baseline (rules) F1 = 0.72; improvement statistically significant (p < 0.001).
- Latency p99 = 35ms (within 50ms NFR).

## Per-slice performance
(table)

## Calibration
- ECE = 0.03 (well-calibrated after temperature scaling).

## Training data
- 24 months of transactions (2024-01 through 2025-12).
- 1.2M positive examples; 50M negative examples.
- Data freezes: monthly retraining cadence.

## Known limitations
- Performance degrades on transactions in regions where training data is sparse.
- Adversarial robustness: not evaluated; assume fraudsters adapt.
- Fairness: per-segment performance reviewed; no disparate impact at current thresholds. See responsible-ai/audit.

## Ethical considerations
- False positives cause friction for legitimate customers.
- Decisions are recommended; final hold/release decision made by downstream logic + human review for high-value.

## Maintenance
- Owner: ML Platform team.
- Retraining: monthly + on-demand on data drift detection.
- Sunset criteria: F1 below 0.78 in production for 2 consecutive weeks.
```

The model card is *required output* of training. It's the foundation for the responsible-AI review and feeds production monitoring.

## Outputs

| Output | Location |
|---|---|
| Trained model artifact | model registry (MLflow / Vertex / SageMaker) — versioned, signed |
| Eval report | `.project/operational/ml-models/{model}-eval-{version}.md` |
| Experiment-tracking entries | tracker (every run) |
| Model card | `.project/operational/ml-models/{model}-card.md` |
| Reproducibility manifest | committed alongside training code |

## Mode handling (G/B)

**Greenfield.** Reproducibility + experiment tracking + model cards from the first training run.

**Brownfield.** Audit existing ML systems. Common findings: no experiment tracking; data versions not pinned; "the team knows" what data was used; no model cards; aggregate metrics only. Address by adopting the discipline for the next training run; backfill model cards opportunistically.

## What this skill does not do

- Frame the problem — that's `ml-problem-framing`.
- Build features — that's `ml-feature-engineering`.
- Serve the model — that's `ml-serving-deployment`.
- Monitor production drift — that's `ml-monitoring-drift`.
- Fairness audit — that's `responsible-ai` (this skill produces the per-slice metrics that skill uses).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Reproducibility is nice-to-have." | A model you can't reproduce is a model you can't debug. Versioning of code + data + config + seeds + env is mandatory. |
| "Test set leakage is unlikely." | It happens easily — temporal leakage, group leakage, feature derived from target. Audit. |
| "Aggregate metric improvement is enough." | Aggregate can rise while critical slices regress. Per-slice always. |
| "Calibration doesn't matter; we threshold." | Threshold-based decisions need calibrated probabilities for fair comparison + business-utility tuning. |
| "Confidence intervals are statistician's domain." | A 2% improvement with ±3% CI is noise. Report CIs; act on signal. |
| "Model card is documentation polish." | Model card is the record of what was trained + how + on what. Required for downstream consumers + audits. |
| "Time-based split is when we have time-series data." | Most data has temporal structure. Random splits leak future into training. Default to time-based. |

## Verification

You are done when:

- [ ] Training reproducible: code + data + config + seed + environment all versioned.
- [ ] Experiment tracking (MLflow / W&B / Vertex / SageMaker / Comet).
- [ ] Train / validation / test discipline; test set touched once per release.
- [ ] Split strategy appropriate (random / time-based / group).
- [ ] Per-slice metrics computed across protected + relevant cohorts.
- [ ] Calibration measured (ECE).
- [ ] Confidence intervals + statistical significance vs baseline.
- [ ] Model card complete (intended use, training data, performance, limits).
- [ ] Error analysis surfaces non-trivial failure cases.

Evidence to check:
- Re-running training from the artifact produces equivalent metrics.
- Per-slice breakdown surfaces at least one slice where aggregate hid an issue.

## Anti-patterns

- Test set looked at during iteration (information leak; test metrics no longer fair).
- Aggregate-only metrics (per-slice problems hidden).
- "Model improved" without confidence intervals or significance.
- No model card (future readers can't reconstruct intent or limitations).
- Hyperparameters tuned ad-hoc, not logged.
- Data version untracked ("we used the warehouse table" — but which version?).
- Notebooks as the system of record (research code; not reproducible).
- Random splits on time-series data (future leaks into past).
- Calibration ignored when probabilities matter.
- "Beat the baseline" satisfied without statistical evidence.
