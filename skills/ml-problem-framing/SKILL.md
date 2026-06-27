---
name: ml-problem-framing
description: Frame the ML problem honestly BEFORE any modeling. Is ML actually the right tool here? Supervised vs unsupervised vs RL choice. Target definition. Label-source plan. Baseline (heuristic / rules / simple model) to beat. Success metric tied to business outcome. Fairness and safety considerations stated upfront. The single most-leveraged step in an ML project — get this wrong, the rest is theatre. Activated only on engagements with ML or LLM workloads. ML/AI Engineer co-runs with PM and SA at the start of every ML feature.
---

# ML Problem Framing


<!-- praxis:metadata:begin -->
```yaml
capability: ml
domain: ml
state: active
dependencies:
 - product-discovery
 - nfr-definition
 - data-modeling
 - data-quality
triggers:
 - "considering ML for a new feature"
 - "framing an ML problem before modeling begins"
 - "defining the target and label-source for a supervised problem"
 - "establishing the baseline a model must beat"
 - "tying ML success metrics to business outcomes"
outputs:
 - problem-framing doc (is-ML-the-right-tool decision; type; target; labels; baseline)
 - primary success metric + business-outcome linkage
 - secondary metrics + counter-metrics
 - baseline (heuristic / rules / simple model) to beat
 - risk log (fairness, safety, harm scenarios)
 - data sufficiency check (do we have data; is it labelable; is it representative?)
consumers:
 - ml-ai-engineer (primary author)
 - product-manager (co-runs the framing; owns success-metric link)
 - solution-architect (consumes for system-design implications)
 - responsible-ai (consumes for fairness/safety planning)
 - ml-training-evaluation (consumes target + metric + baseline)
references: []
```
<!-- praxis:metadata:end -->

The single most-leveraged step in an ML project. Forty-five minutes of disciplined framing prevents weeks of modeling work that solves the wrong problem. This skill runs *before* any data work, model training, or architecture decisions — it answers *what problem are we actually solving, and is ML the right tool?*

The principle: **modeling is the easy part. Framing is where projects succeed or fail.**

## When this skill fires

- A new feature is being considered that *might* be ML-driven.
- An existing rule-based system is being considered for ML replacement.
- The team is being asked to "add AI" to something — frame it first.
- Mid-project, when results don't match expectations and the team suspects the framing was wrong.

## Wave-6 activation

This skill (and the rest of the ML family) activates when `delivery-planner` flags `has_ml = true` OR `has_agentic_ai = true`. Signals:

- A product feature whose value depends on prediction, classification, ranking, generation, or extraction.
- Existing rules-based logic with poor accuracy that data could improve.
- A user-facing feature that benefits from personalization or content understanding.

If neither flag fires, is skipped and the ML/AI Engineer agent doesn't spawn.

## The five-step framing procedure

Time-boxed ~60-90 minutes with the PM + SA + (where relevant) domain experts. Output is short and actionable.

### 1. Is ML actually the right tool?

Before anything else, an honest test. ML is the right tool when:

- **The problem is statistical, not procedural.** "What's the customer's lifetime value?" (statistical). "What's the customer's email address?" (procedural lookup).
- **Patterns exist in data and are too complex or numerous to enumerate.** "Detect fraud" (too many patterns). "Detect transactions over $10K" (one rule).
- **The cost of wrong answers is acceptable.** "Recommend products" (low cost of mistakes). "Decide whether a defendant gets bail" (high cost; ML may not be appropriate even if accurate).
- **You have enough labeled data.** Or can get it.
- **The signal-to-noise ratio is high enough.** Stock price prediction has lots of data and famously bad signal-to-noise; many ML projects there fail.

If ML is *not* the right tool: rules, lookup tables, simpler heuristics, or human-in-the-loop may serve better. Recognizing this is a win, not a failure.

### 2. Choose the ML problem type

| Type | Question |
|---|---|
| **Supervised — classification** | "Is this transaction fraud?" "What category is this product?" |
| **Supervised — regression** | "What will this customer's lifetime value be?" "How long until this customer churns?" |
| **Supervised — ranking** | "Which 10 products should we recommend?" "What's the relevance of these search results?" |
| **Unsupervised — clustering** | "Group customers by behavior." "Find segments without prior labels." |
| **Unsupervised — anomaly detection** | "Flag transactions that don't fit normal patterns." |
| **Recommender (matrix factorization / two-tower)** | "Which products is this user likely to want?" |
| **Sequence (NLP / time-series)** | "Predict next token / next month sales / classify document." |
| **Reinforcement learning** | "Optimize an agent's behavior over a sequence of actions." (Rarely the right choice for typical SaaS.) |
| **Generative (LLM / diffusion / image)** | "Generate text / image / code." → routes to agentic AI family (Chunk B). |

Be honest. Most teams reach for the trendy option (generative AI today) when classification or rules would suffice.

### 3. Define the target (for supervised problems)

The target is *what the model predicts*. Three sub-questions:

- **What's the exact target variable?** Not "customer engagement" but `monthly_active_minutes` or `binary_logged_in_within_30_days`.
- **How is it observable?** Where does this signal live in data? When does the label become known?
- **Label delay matters.** If you're predicting 90-day churn, you have to wait 90 days to know if the prediction was right. Plan for it.

Label-source plan:

- **Direct labels** — logs / databases capture the outcome (clicks, purchases, churn).
- **Human-annotated labels** — annotators tag examples (slow, expensive; needed for some problems).
- **Weak supervision** — heuristic rules generate noisy labels at scale.
- **Self-supervised** — labels derived from data structure (next-token prediction).
- **Semi-supervised** — small labeled set + large unlabeled set.

Document the label source and its known biases.

### 4. Establish the baseline

The model must beat a baseline. Specify it before any modeling:

- **Heuristic baseline**: "Predict the majority class" (for classification). "Predict the median" (for regression). "Recommend the most popular items" (for recommenders).
- **Rules baseline**: existing business rules, if any.
- **Simple model baseline**: logistic regression, decision tree, single-feature model.

If your model can't beat the heuristic baseline, **you don't need ML for this problem yet** — the heuristic does just as well at lower cost.

Many ML projects skip this step. Then they ship a "10% better" model that's actually worse than a one-line heuristic. Don't.

### 5. Tie success metric to business outcome

The model's metric (accuracy, F1, RMSE, NDCG) must connect to *something that matters*:

```markdown
## Primary metric
- F1 on fraud detection (precision + recall balance).

## Business outcome it drives
- $X fraud loss prevented per month, with Y false-positive rate
 (which causes Z legitimate transaction declines worth $W).

## Trade-off
- Higher recall (catch more fraud) → more false positives (more customer friction).
- Higher precision (fewer false positives) → miss more fraud.
- Business chose target: F1 with 2:1 precision:recall weight per ROC analysis.

## Secondary metrics
- Precision by fraud-type segment (don't only catch easy cases).
- Recall by transaction amount (catch high-value fraud).
- Latency: prediction within 50ms (NFR target).

## Counter-metrics (must not get worse)
- Customer support tickets related to legitimate-blocked.
- Average transaction approval time for legitimate customers.
```

Without business-linked metrics, "the model improved" doesn't translate to "the business benefited."

## Fairness and safety risk log

Stated upfront, *before* modeling:

- **Protected attributes**: race, gender, age, disability, geography per regulation. Is the model used in a context where disparate impact is a legal or ethical concern?
- **Harm scenarios**: what's the worst thing this model can do if it's wrong? Or right but used badly?
- **Feedback loops**: does the model's prediction affect future training data? (Recommenders create this.)
- **Adversarial scenarios**: can users game the model to extract value or harm others?

Each risk gets a mitigation plan or an explicit acceptance (per `responsible-ai`'s discipline). Risks identified later are 10x more expensive to address.

## Data sufficiency check

Before greenlighting the project:

- **Volume** — do you have enough examples? Roughly: 10x your feature count for traditional ML; much more for deep learning. Specific to problem.
- **Coverage** — does the data represent the production population? (Training only on one customer segment then deploying broadly is a common failure.)
- **Recency** — is the data current? Stale labels predict stale behavior.
- **Quality** — per `data-quality` — are the features and labels themselves correct?
- **Ethics / legal** — is the data legally usable for this purpose? Did users consent?

A "no" on any of these means *frame the data work first* before frame-then-model.

## Outputs

| Output | Location |
|---|---|
| Problem framing doc | `.project/semantic/ml-framing-{project-name}.md` |
| Primary metric + business linkage | `.project/semantic/ml-success-metrics.md` |
| Baseline definition | `.project/working/ml-baseline.md` |
| Risk log | `.project/operational/ml-risk-log.md` (consumed by `responsible-ai`) |
| Data sufficiency assessment | `.project/working/ml-data-check.md` |

## Mode handling (G/B)

**Greenfield.** Run framing before any modeling work. PM + SA + ML/AI Engineer in the room together.

**Brownfield.** Many existing ML systems were never properly framed. Audit: what's the target? What's the baseline? What's the business linkage? Often the framing exercise reveals the existing model isn't actually optimizing for what the business wants. That's a finding, not an attack.

## What this skill does not do

- Build features — that's `ml-feature-engineering`.
- Train models — that's `ml-training-evaluation`.
- Serve models — that's `ml-serving-deployment`.
- LLM / agentic system framing — those are different in important ways; see `agentic-architecture` and `evaluation-engineering` (Chunk B).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "ML is obviously the right tool here." | The honest check is step 1. Most "ML problems" are better solved with rules + heuristics + statistics. |
| "We have data; we can train." | Data sufficiency is checkable. Volume, label availability, label quality, recency — all matter. |
| "Target is whatever metric we have." | Target follows from business outcome, not data availability. Frame the business goal first. |
| "Baseline isn't necessary; we'll beat it." | Baseline (heuristic, rule, simple model) is the bar. Without it, "model improved by 3%" is meaningless. |
| "Labels arrive when they arrive." | Label delay shapes the model + monitoring + retraining cadence. Plan for it. |
| "Fairness comes later." | Fairness considerations affect target choice + feature choice. Frame at framing time. |

## Verification

You are done when:

- [ ] "Is ML actually the right tool?" honest check completed; rules / heuristics / statistics considered.
- [ ] Problem type identified (supervised / unsupervised / recommender / sequence / RL / generative).
- [ ] Target variable defined with label source + label delay characterization.
- [ ] Baseline defined (heuristic / rule / simple model the new model must beat).
- [ ] Business metric linkage documented (which lever does the model move?).
- [ ] Risk log: fairness, safety, drift, feedback loops.
- [ ] Data sufficiency check: volume, quality, recency assessed.
- [ ] Open questions logged.

Evidence to check:
- The framing document can be read by PM + SA without ML background.
- The baseline is implementable in a day or two.

## Anti-patterns

- Modeling before framing ("let's try gradient boosting and see").
- "Improve the model" as a goal (improvement is meaningless without baseline + business metric).
- Target chosen because it's easy to measure rather than what matters.
- Baseline skipped (then can't tell if the model is actually useful).
- Business metric assumed identical to model metric ("we want accuracy" — but the cost of FP vs FN is asymmetric).
- Label-delay ignored (model takes 6 months to evaluate; only realized too late).
- Risk log skipped (fairness failures surface in production headlines).
- Data sufficiency assumed rather than checked.
- "ML is the new thing; let's use it" (when rules would suffice).
- Framing done by ML Engineer alone (without PM owning the business metric).
