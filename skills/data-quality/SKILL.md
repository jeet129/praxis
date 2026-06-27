---
name: data-quality
description: "Data contracts and tests as code. Schema enforcement, freshness / completeness / uniqueness / range checks, anomaly detection on key metrics, alerting on data-SLO breaches. Treat data like product — versioned, tested, with explicit consumers + producers + SLOs. Distinct from `testing-strategy` (which tests application code); this skill tests data correctness continuously as it flows through pipelines and warehouses. Data Engineer owns this; analysts consume the contracts; alerts route through incident-runbook. Use whenever new tables are being added, when data quality issues surface in dashboards, or when establishing data-SLOs."
---

# Data Quality

<!-- praxis:metadata:begin -->
```yaml
capability: data
domain: data
state: active
dependencies:
  - data-pipeline
  - data-warehouse-modeling
  - observability
  - testing-strategy
triggers:
  - "adding tests to new tables or models"
  - "designing data contracts between producer and consumer"
  - "investigating data-quality issues surfacing in dashboards"
  - "setting data-SLOs (freshness, completeness, accuracy)"
  - "wiring anomaly detection on key metrics"
outputs:
  - data contract per producer/consumer pair (schema + SLOs + breakage policy)
  - test suite (dbt tests / Great Expectations / Soda)
  - data SLOs per table (freshness, completeness, uniqueness)
  - alert configuration (route + severity per breach class)
  - anomaly-detection rules (week-over-week drift, sudden drops/spikes)
consumers:
  - data-engineer (primary author)
  - data-pipeline (wires checkpoints into pipeline runs)
  - data-warehouse-modeling (tests run against models)
  - observability (alerts on SLO breaches)
  - incident-runbook (data incidents follow same workflow as service incidents)
references:
  - dbt-tests.md
  - great-expectations.md
  - soda.md
```
<!-- praxis:metadata:end -->

The discipline that turns "we hope the data is right" into "we know the data is right because every test passed continuously." Without it, data bugs surface in executive dashboards a week after they started; with it, they're caught at pipeline run time and fixed before downstream consumers see them.

The principle: **data is a product with contracts, tests, and SLOs — just like services.**

## When this skill fires

- A new table or dbt model is being added — tests written alongside.
- A data contract between producer and consumer is being designed.
- A data-quality issue surfaced in a dashboard — root cause + prevent recurrence.
- Data SLOs are being established for a table.
- Anomaly detection is being wired (week-over-week drift, sudden drops/spikes).

## Data contracts

A **data contract** is the formal agreement between producer (the pipeline writing the data) and consumer (the model, dashboard, ML pipeline reading it). Like API contracts, broken changes need versioning and migration.

A contract specifies:

- **Schema** — column names, types, nullability, enums.
- **Semantics** — what each column means in the domain (definition, units, source of truth).
- **Freshness SLO** — how recent the data must be (`updated within last 30 minutes`).
- **Completeness SLO** — what fraction of expected rows must be present (`>= 99% of expected daily rows`).
- **Uniqueness** — primary key + unique-set constraints.
- **Value ranges** — accepted values, range bounds, format rules.
- **Breakage policy** — what happens when the producer breaks the contract (alert, rollback, etc.).
- **Versioning** — schema version + migration path for breaking changes.

Contracts live with the producing pipeline in version control. Consumers reference them.

## The four test classes

### 1. Schema enforcement

Does the column exist? Right type? Nullability correct?

- **dbt schema.yml** — `not_null`, `unique`, `accepted_values`, `relationships` (foreign-key integrity).
- **Great Expectations** — `expect_column_to_exist`, `expect_column_values_to_be_of_type`.
- **Soda** — schema checks via SodaCL.

These run on every pipeline run; failures stop the pipeline (or quarantine the bad data, per the breakage policy).

### 2. Completeness checks

Did we get all the rows we expected?

```yaml
# dbt schema.yml
models:
  - name: fct_orders
    tests:
      - dbt_utils.fewer_rows_than:
          compare_model: ref('stg_orders')
      - dbt_expectations.expect_table_row_count_to_be_between:
          min_value: 1000
          max_value: 50000
```

- Row count vs expectation.
- Row count vs prior day / week / month (relative completeness).
- Per-partition checks (each date partition has at least X rows).

### 3. Freshness checks

Is the data current?

```yaml
sources:
  - name: orders
    tables:
      - name: orders_raw
        freshness:
          warn_after: { count: 1, period: hour }
          error_after: { count: 6, period: hour }
        loaded_at_field: updated_at
```

- Source freshness (data has arrived from the source within SLO).
- Pipeline freshness (the pipeline has run within SLO).
- End-to-end freshness (consumer sees data within total budget).

### 4. Value-quality checks

Are the values themselves correct?

- **Ranges** — amounts between 0 and 1B; dates between 2020 and now.
- **Patterns** — emails match regex; phone numbers match format.
- **Referential integrity** — foreign keys exist in their reference tables.
- **Business rules** — `total_amount = sum(line_item.amount * line_item.quantity) +/- $0.01`.
- **Consistency across tables** — sum of order amounts in `fct_orders` matches sum from `fct_revenue`.

## Anomaly detection

Beyond hard rules, statistical anomaly detection on key metrics:

- **Week-over-week** — total rows changed by more than X% from last week's same day.
- **Day-over-day** — sudden drops/spikes that don't match the seasonal pattern.
- **Distribution shift** — categorical distribution changed materially (new category absorbing 30%, etc.).
- **Forecasted vs actual** — using historical data, expected range for today's value; alert on out-of-range.

Tools:
- **Great Expectations** — has anomaly-detection profiles.
- **Soda** — SodaCL anomaly checks.
- **Monte Carlo / Bigeye / Anomalo / Metaplane** — managed data observability platforms.
- **Custom** — many teams write SQL anomaly checks scheduled in the orchestrator.

## Tool choice

| Tool | Sweet spot |
|---|---|
| **dbt tests** | Integrated with dbt projects. Inline with model definitions. Default for projects on dbt. |
| **Great Expectations** | Standalone; rich expectations library; works without dbt. |
| **Soda** | Lightweight SQL-first DSL (SodaCL); good for non-dbt projects. |
| **Managed (Monte Carlo / Anomalo / etc.)** | Higher cost; richer anomaly detection; less coding. For larger data platforms. |

Default for projects on dbt: **dbt tests + dbt_utils + dbt_expectations**. Reach for Great Expectations or Soda for non-dbt pipelines.

## Data SLOs

Like service SLOs, per the `reliability-dr` skill's framework, applied to data:

```markdown
# Data SLO — fct_orders

## Freshness
- Target: data is < 30 minutes behind real time.
- SLI: time since last successful pipeline run.
- Budget: 99% within target / 30-day rolling.

## Completeness
- Target: ≥ 99.5% of expected rows present per hour.
- SLI: row_count_actual / row_count_expected.
- Budget: 99% within target / 30-day rolling.

## Accuracy
- Target: all value-quality tests pass.
- SLI: % of test runs passing.
- Budget: 99.9% within target / 30-day rolling.

## Breach response
- Page on freshness > 1 hour stale (warning) or > 6 hours (page).
- Page on completeness < 90% for one hour.
- Ticket on accuracy failures; quarantine affected partition.
```

## Quarantine pattern

When a quality check fails:

- **Hard fail** — stop the pipeline; nothing downstream sees the bad data. Use when data correctness is critical (financial, compliance).
- **Quarantine** — move the failing rows to a separate quarantine table; continue with the good rows. Use when partial progress is acceptable and the bad rows can be investigated offline.
- **Warn + continue** — log the failure but proceed. Use rarely; for low-stakes warnings.

Default: **hard fail for blocker tests, quarantine for major, warn for minor**.

## CI for data

Per the `cicd-pipeline` skill applied to data:

- **PR triggers**: dbt run + test against a development environment.
- **Schema-change tests**: run against a frozen snapshot; verify backward compatibility.
- **Performance tests**: model build time within budget.

Gates: merge requires green dbt run + tests + (where applicable) backward-compatibility check.

## Outputs

| Output | Location |
|---|---|
| Data contracts | `data-contracts/` in repo |
| Test definitions | inline in dbt schema.yml; Great Expectations expectation suites; Soda checks |
| Data SLOs | `.project/operational/data-slos.md` |
| Alert configuration | configured per `observability` tooling |
| Anomaly-detection rules | as scheduled queries / managed-platform configurations |
| Quarantine tables | warehouse-specific; documented per pipeline |

## Mode handling (G/B)

**Greenfield.** Tests + contracts + SLOs from day one. New tables don't merge without tests.

**Brownfield.** Audit existing data-quality posture. Common findings: zero tests; metric definitions drift across dashboards; bad data discovered only by analysts noticing weird numbers. Start with the most-consumed tables; add tests incrementally.

## What this skill does not do

- Build the pipelines — that's `data-pipeline`.
- Build the warehouse models — that's `data-warehouse-modeling`.
- Catalog data — that's `data-governance` (this skill produces SLO data; that skill records lineage).
- Application-code testing — that's `testing-strategy`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Pipeline succeeded; data is good." | Success means it ran. Quality means it's correct + complete + fresh. Different signals. |
| "Quality is the producer's responsibility." | Producer publishes; consumer validates expectations. Both. |
| "Tests catch quality issues." | Tests catch known issues. Production has unknown issues; that's what monitors catch. |
| "We don't need contracts for internal data." | Internal consumers depend on shapes. Contracts make breakage visible. |
| "Anomaly detection is overkill." | At scale, manual review can't keep up. Automated detection on key signals is the only path. |
| "Quality issues are rare." | They aren't, especially with upstream changes. Visibility is the whole point. |

## Verification

You are done when:

- [ ] Data contracts defined per dataset (schema + invariants + freshness).
- [ ] Quality dimensions tested: completeness, uniqueness, validity, consistency, accuracy, freshness.
- [ ] Tool wired: Great Expectations / Soda / dbt tests / custom.
- [ ] Quality runs scheduled + alerts configured.
- [ ] SLAs per dataset (per `data-governance`) reported.
- [ ] Anomaly detection on key business metrics.
- [ ] Quality incident response: who, what, escalation.
- [ ] Quality dashboard accessible to producers + consumers.

Evidence to check:
- A planted-bad-data test triggers an alert within SLA.
- Quality regression caught at the boundary, not by downstream complaints.

## Anti-patterns

- No tests; bad data discovered downstream weeks later.
- Tests written but never run.
- Tests run but failures ignored (alerts fatigue).
- Hard fail on every minor finding (pipelines never run).
- Anomaly detection thresholds too loose (everything passes) or too tight (everything fails).
- Quality checks in BI tool only (consumer-side; doesn't prevent bad data, just detects after).
- "We trust the source" (source bugs are common).
- Schema changes without contracts → downstream consumers break silently.
- Data SLOs undefined ("what does broken mean?").
- Quarantined data never investigated (data debt).
