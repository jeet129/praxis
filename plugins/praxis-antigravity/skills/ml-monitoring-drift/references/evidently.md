# ML Monitoring / Drift — Evidently

Evidently (OSS) computes data drift, prediction drift, and data-quality metrics by comparing a current data window against a reference window, and renders them as reports (human-readable) or test suites (pass/fail, CI-friendly).

## Core concepts

- **Reference dataset** — the baseline (typically training data, or last-known-good production window).
- **Current dataset** — the window under evaluation (yesterday's inference inputs/outputs, this week's batch).
- Every check compares current against reference; there is no drift metric without a reference.

## Install

```bash
pip install evidently
```

## Reports: human-readable, exploratory

```python
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, DataQualityPreset, TargetDriftPreset
import pandas as pd

reference = pd.read_parquet("data/reference_2026_q1.parquet")
current = pd.read_parquet("data/current_2026_07_08.parquet")

report = Report(metrics=[
    DataDriftPreset(),
    DataQualityPreset(),
    TargetDriftPreset(columns=["prediction", "target"]),
])
report.run(reference_data=reference, current_data=current)
report.save_html("reports/drift_2026_07_08.html")
report.save_json("reports/drift_2026_07_08.json")
```

Reports are for humans in a debugging loop — a data scientist investigating "why did the model start behaving oddly" opens the HTML, sees per-column distribution shifts, drift scores, and correlation changes.

## Test suites: pass/fail, CI-friendly

Test suites are the automatable form — each check has an explicit condition and produces a boolean result, meant to gate a scheduled job or a CI pipeline, not to be eyeballed.

```python
from evidently.test_suite import TestSuite
from evidently.tests import (
    TestNumberOfDriftedColumns,
    TestColumnDrift,
    TestShareOfMissingValues,
    TestColumnValueMin,
)

suite = TestSuite(tests=[
    TestNumberOfDriftedColumns(lt=3),               # fail if 3+ columns drifted
    TestColumnDrift(column_name="prediction"),
    TestShareOfMissingValues(column_name="income", lte=0.02),
    TestColumnValueMin(column_name="age", gte=18),
])
suite.run(reference_data=reference, current_data=current)

if not suite.as_dict()["summary"]["all_passed"]:
    raise SystemExit("Data quality / drift test suite failed")
```

## Data drift vs prediction drift vs data quality — three distinct signal types

| Signal | What it measures | Detects | Typical action |
|---|---|---|---|
| **Data drift** | Distribution shift in *input features* between reference and current | Upstream data pipeline changes, population shift, sensor/schema changes | Investigate source; may not need retraining if model is robust to the shift |
| **Prediction drift** | Distribution shift in the *model's output* | Model behavior change even without input drift (concept drift, model bug) | Higher-urgency — directly affects downstream decisions |
| **Data quality** | Missing values, duplicate rows, schema violations, out-of-range values, type mismatches | Pipeline bugs, upstream schema breaks, ingestion failures | Usually a pipeline bug, not a model problem — page data eng, not ML |

Prediction drift *without* corresponding input drift is the most actionable signal — it usually means the model itself has changed behavior (bad deploy, feature-pipeline bug feeding stale features) rather than the world changing.

## Drift detection methods

Evidently auto-selects a statistical test per column type and sample size, but can be pinned:

```python
from evidently.calculations.stattests import StatTest
from evidently.metrics import ColumnDriftMetric

ColumnDriftMetric(
    column_name="transaction_amount",
    stattest="wasserstein",     # numerical, large samples
    stattest_threshold=0.1,
)
ColumnDriftMetric(
    column_name="payment_method",
    stattest="psi",             # categorical — Population Stability Index
    stattest_threshold=0.2,     # PSI > 0.2 = significant shift (industry convention)
)
```

Common defaults: **PSI** or **Jensen-Shannon** for categorical, **Kolmogorov-Smirnov** or **Wasserstein distance** for numerical (small vs. large samples respectively — Evidently switches automatically based on sample size unless pinned).

## Thresholds — tie to model risk, not arbitrary defaults

- Set per-column thresholds based on how sensitive the model is to that feature (check feature importance from `ml-training-evaluation`'s model card) — a drifted low-importance column is noise; a drifted top-3-importance column is signal.
- Start permissive, tighten based on observed false-positive rate over the first few weeks in production — an alert that fires every day gets ignored (`llm-safety`/`observability` have the same alert-fatigue lesson).
- Document threshold rationale next to the test suite definition; thresholds are a modeling decision, not a monitoring-team default.

## Scheduled runs

```python
# monitoring/run_drift_check.py — invoked by Airflow/cron, not manually
import sys
from evidently.test_suite import TestSuite
from evidently.test_preset import DataDriftTestPreset

def main():
    reference = load_reference_window()
    current = load_current_window(hours=24)

    suite = TestSuite(tests=[DataDriftTestPreset()])
    suite.run(reference_data=reference, current_data=current)
    suite.save_html(f"reports/{current_date()}.html")

    result = suite.as_dict()
    if not result["summary"]["all_passed"]:
        send_alert(result)   # pages the ML on-call per incident-runbook
        sys.exit(1)

if __name__ == "__main__":
    main()
```

```yaml
# Airflow DAG snippet
drift_check = PythonOperator(
    task_id="daily_drift_check",
    python_callable=run_drift_check,
    dag=dag,
)
```

Run cadence matches the inference cadence and business risk: daily for most batch-scored models, hourly for high-risk real-time models (fraud, credit decisioning), weekly is acceptable for low-risk, low-traffic models.

## Reference window refresh

The reference dataset itself goes stale — pin it to the training data snapshot at model-deploy time, and refresh it deliberately on retrain (never silently), otherwise "drift from reference" starts measuring drift from an outdated baseline rather than the live model's actual training distribution.

## Common violations to flag in review

- No reference dataset versioned/pinned — drift comparisons against a silently-shifting "current minus 30 days" window instead of the actual training snapshot.
- Test suite thresholds copy-pasted defaults with no connection to feature importance or business risk.
- Reports (HTML, for humans) used as the CI gate instead of test suites (pass/fail booleans) — reports don't fail a pipeline on their own.
- Prediction drift ignored while only input drift is monitored — prediction drift is the higher-urgency signal.
- No alerting wired from failed test suites to `incident-runbook` on-call.
- Drift checks run at a cadence mismatched to the model's inference frequency and business risk.
