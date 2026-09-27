# ML Monitoring / Drift — Dashboard Templates

## Performance-with-label-lag dashboard example

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

## Dashboard structure — three-tier template

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
