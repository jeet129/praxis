# Reference — Great Expectations

Loaded by `data-quality` when Great Expectations is the chosen quality framework.

## When to use

Great Expectations (GX) is one of the strongest defaults for data quality testing when:
- You want Python-native authoring of expectations.
- Your sources span databases + files + dataframes (GX supports all).
- You want generated documentation ("data docs") for stakeholders.

Skip GX when:
- All your data lives in dbt → use dbt-native tests (`dbt-tests.md`).
- You want pure-SQL quality with minimal Python → consider Soda (`soda.md`).

## Core concepts

- **Expectation**: a single assertion about data (`expect_column_values_to_not_be_null('email')`).
- **Expectation Suite**: a collection of expectations for a dataset.
- **Data Source**: how GX connects to data (pandas, SQLAlchemy, Spark, etc.).
- **Data Asset**: a logical dataset (a table, a file pattern, a query).
- **Batch**: a specific run-time instance of a data asset.
- **Validator**: the runtime object that holds (Batch, ExpectationSuite) and produces validation results.
- **Checkpoint**: a runnable validation — usually wired into your orchestrator (per `airflow.md`).
- **Data Docs**: HTML report generated from validation results.

## GX v1 — modern API

The GX v1 API (released 2024) is significantly cleaner than the v0.x "fluent" API. Use v1 for new projects.

```python
# pyproject.toml dependency
# great-expectations >= 1.0

import great_expectations as gx

context = gx.get_context(mode='file', project_root_dir='./gx')

# Add a data source (e.g., Postgres)
data_source = context.data_sources.add_postgres(
    name='warehouse',
    connection_string='postgresql://user:pass@host:5432/db',
)

# Define a data asset (a table)
data_asset = data_source.add_table_asset(name='orders', table_name='orders')

# Define a batch parameter (e.g., partition by date)
batch_def = data_asset.add_batch_definition_daily('daily_orders', column='order_date')

# Create an expectation suite
suite = context.suites.add(gx.ExpectationSuite(name='orders_quality'))

# Add expectations
suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column='order_id'))
suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column='order_id'))
suite.add_expectation(gx.expectations.ExpectColumnValuesToBeInSet(
    column='status',
    value_set=['pending', 'confirmed', 'shipped', 'cancelled'],
))
suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(
    column='total_cents',
    min_value=0,
    max_value=1_000_000_00,
))
suite.add_expectation(gx.expectations.ExpectColumnPairValuesAToBeGreaterThanB(
    column_A='shipped_at',
    column_B='order_date',
    ignore_row_if='either_value_is_missing',
))

# Validate
batch = batch_def.get_batch(batch_parameters={'year': 2026, 'month': 6, 'day': 15})
validator = context.get_validator(batch=batch, expectation_suite=suite)
result = validator.validate()

print(f"Success: {result.success}")
print(f"Statistics: {result.statistics}")
```

## Quality dimensions covered

| Dimension | GX expectations |
|---|---|
| **Completeness** | `expect_column_values_to_not_be_null` |
| **Uniqueness** | `expect_column_values_to_be_unique`, `expect_compound_columns_to_be_unique` |
| **Validity** | `expect_column_values_to_be_in_set`, `expect_column_values_to_match_regex`, `expect_column_values_to_be_of_type` |
| **Consistency** | `expect_column_pair_values_*`, `expect_multicolumn_sum_to_equal` |
| **Accuracy** | `expect_column_mean_to_be_between` (statistical bounds) |
| **Freshness** | `expect_column_max_to_be_between` (timestamp check) |
| **Distribution** | `expect_column_kl_divergence_to_be_less_than` (compare to reference distribution) |

## Wiring into Airflow

```python
# dags/orders_quality.py
from airflow.decorators import dag, task
from datetime import datetime
import great_expectations as gx

@dag(schedule='0 3 * * *', start_date=datetime(2026, 1, 1), catchup=False)
def orders_quality_check():

    @task
    def run_quality_checkpoint(ds: str) -> dict:
        context = gx.get_context(mode='file', project_root_dir='/opt/airflow/gx')
        checkpoint = context.checkpoints.get('orders_daily_checkpoint')
        result = checkpoint.run(batch_parameters={'partition': ds})
        if not result.success:
            failing = [
                exp for exp_result in result.run_results.values()
                for exp in exp_result.results if not exp.success
            ]
            raise AssertionError(f"Quality check failed: {failing}")
        return {
            'success': result.success,
            'statistics': result.statistics,
        }

    run_quality_checkpoint('{{ ds }}')

orders_quality_check()
```

For non-blocking checks (capture results but don't fail the DAG), wrap the checkpoint run in a try/except and emit a metric instead.

## Wiring into dbt

GX integrates with dbt as a post-run quality layer:

```yaml
# dbt_project.yml
on-run-end:
  - "{{ run_gx_checkpoint('orders_quality_checkpoint') }}"
```

Or run GX as a separate Airflow task after the dbt task — usually cleaner.

## Data Docs (the HTML reports)

GX renders validation results into static HTML:

```python
context.build_data_docs()
# By default writes to ./gx/uncommitted/data_docs/
```

Host the data docs on S3/GCS/Azure Blob behind your internal docs site. Producers see what consumers expect; consumers see what producers actually deliver.

## Configuring stores

GX maintains state in stores: expectation suites, validation results, data docs.

For team workflows, point them at S3/GCS (not local files):

```yaml
# gx/great_expectations.yml
stores:
  expectations_store:
    class_name: ExpectationsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: my-gx-store
      prefix: expectations
  validations_store:
    class_name: ValidationsStore
    store_backend:
      class_name: TupleS3StoreBackend
      bucket: my-gx-store
      prefix: validations
```

## Performance

GX runs expectations against batches; for SQL sources it pushes down many expectations to SQL (fast). For pandas/Spark, expectations run in-process.

- **SQL backend**: most expectations push down → ~native query speed.
- **Pandas backend**: in-memory; OK for small-medium data.
- **Spark backend**: distributed; suitable for large data.

For very large datasets, sample-then-validate is acceptable for some expectations; document the sampling strategy.

## Common patterns

### Per-partition checks
Use `add_batch_definition_daily` / `_monthly` / etc.; check each partition separately.

### Expectation generation from profiling
```python
result = validator.profile()
# Generates expectations based on observed data; review before promoting to suite
```

Usually you write the suite by hand for production checks; profiling is a starting-point aid.

### Slack/email notifications
```yaml
action_list:
  - name: send_slack
    action:
      class_name: SlackNotificationAction
      slack_webhook: ${SLACK_WEBHOOK_URL}
      notify_on: failure
      renderer:
        module_name: great_expectations.render.renderer.slack_renderer
        class_name: SlackRenderer
```

## Gotchas

- **GX v0.x → v1 is a major rewrite**. Don't mix old + new docs; many tutorials are still v0.
- **Expectation suite + data asset coupling** — changing column names breaks suites. Plan suite versioning.
- **Performance on wide tables** — running many expectations on a 200-column table is slow even on SQL push-down. Be selective.
- **`mostly` parameter** — many expectations accept `mostly=0.99` (passes if 99% conform). Useful for noisy real-world data but document the threshold.
- **`unexpected_index_query`** — when failures happen, GX captures sample failing rows. Configure storage so you can investigate; don't just log "failed."

## Alternatives

- **dbt tests** — if your stack is dbt-centric, native tests + dbt-expectations package are simpler.
- **Soda Core** — SQL-first checks; minimal Python; good fit for SQL-only teams.
- **Custom + Pydantic** — for in-pipeline validation of small payloads, sometimes simpler.

## Common rationalizations

| Thought | Counter |
|---|---|
| "Pipeline succeeded; data is good." | Pipeline success means it ran. Quality means it's correct. Different signals. |
| "Quality is the producer's responsibility alone." | Producer publishes; consumer validates expectations. Both. |
| "We don't need GX; we have unit tests." | Unit tests check the code; GX checks the data. The code can be right and the data wrong. |
| "Profile once; set expectations forever." | Distributions drift; revisit suite definitions on a cadence. |
| "Suite is too strict; reduce thresholds." | Strict suites that fail honestly are better than loose suites that pass useless data. |

## Official sources

- Great Expectations documentation (v1): https://docs.greatexpectations.io
- GitHub: https://github.com/great-expectations/great_expectations
- Expectation gallery: https://greatexpectations.io/expectations/
- dbt-expectations (port to dbt): https://github.com/calogica/dbt-expectations
