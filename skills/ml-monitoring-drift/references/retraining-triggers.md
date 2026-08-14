# ML Monitoring / Drift — Retraining Trigger Configs

## 1. Drift-based

When drift metric crosses threshold:

```yaml
trigger:
  type: drift
  feature: customer_30d_purchase_count
  metric: psi
  threshold: 0.25
  action: schedule_retraining
```

## 2. Cadence-based

Periodic regardless of drift:

```yaml
trigger:
  type: cadence
  schedule: monthly_on_first_monday
  action: schedule_retraining
```
