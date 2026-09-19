# Reference — Model Card & Per-Slice Reporting Templates

Loaded by `ml-training-evaluation` for the worked example of per-slice metrics reporting and the full model card template.

## Per-slice F1 example

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

## Model card template

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
