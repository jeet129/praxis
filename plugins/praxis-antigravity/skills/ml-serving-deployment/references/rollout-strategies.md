# ML Serving / Deployment — Rollout Strategies for Models

Distinct from code-deployment strategies (per `deploy-release`). ML rollouts add model-specific patterns:

## Shadow deployment

The new model runs alongside the old, scoring the same requests, but its predictions are **logged, not served**. The old model's predictions are served.

```
Request → Old Model (serves) → Response
        → New Model (logged for analysis) → comparison logs
```

After collecting enough comparison data: analyze new vs old offline. If the new model is better, promote.

Shadow is the safest first step for any model change. It surfaces production issues (latency, errors, feature problems) without risking customer impact.

## A/B testing

Split traffic between models (e.g., 90% old / 10% new). Measure outcomes per user-affecting metric (conversion, revenue, engagement).

A/B testing measures *business impact*, not just model metrics. The new model may have higher offline F1 but lower user retention — A/B exposes this.

Requirements:

- Random assignment per user (or per session, per the unit of analysis).
- Sufficient sample size for statistical power.
- Pre-registered hypothesis (avoid p-hacking).
- Duration sufficient to capture novelty effects.

## Canary deployment

Per `deploy-release`'s canary pattern, applied to models. Roll out new model to 5% → observe → 25% → 50% → 100%. Roll back at any stage if metrics degrade.

Canary is simpler than A/B and doesn't require random assignment; trade-off is less statistical rigor.

## Multi-armed bandits

For continuous optimization: traffic is dynamically allocated to model variants based on observed performance. The best-performing variant gets more traffic over time.

Bandits are powerful but complex; reserve for problems where:

- You have many model variants to compare.
- The objective is well-defined and quickly observable.
- The team has the statistical sophistication to interpret bandit outputs.

## Progressive delivery (model + flag)

Combine canary deployment with feature flags. The model is deployed dark; the feature flag controls who sees its predictions. Flag flips by user cohort, geography, tenant tier.

This is the modern default for high-stakes model releases.
