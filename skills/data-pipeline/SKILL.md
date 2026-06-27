---
name: data-pipeline
description: Batch and streaming pipeline design. Ingestion, transformation, materialization, orchestration (Airflow / Dagster / Prefect / Kafka Connect), idempotency, backfills, late-arriving data, schema evolution. Per the agnostic-everywhere decision, ships with refs for the major orchestrators and processing engines. Data Engineer owns this; activates only on engagements with non-trivial data workloads.
---

# Data Pipeline


<!-- praxis:description:full -->
## Full description

Batch and streaming pipeline design. Ingestion, transformation, materialization, orchestration (Airflow / Dagster / Prefect / Kafka Connect), idempotency, backfills, late-arriving data, schema evolution. Per the agnostic-everywhere decision, ships with refs for the major orchestrators and processing engines. Data Engineer owns this; activates only on engagements with non-trivial data workloads. Use whenever a new pipeline is being designed, an ingestion source is added, backfills need planning, or pipeline reliability needs investigation.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: data-engineering
domain: data
state: active
dependencies:
  - engineering-standards
  - data-modeling
  - observability
triggers:
  - "designing a batch or streaming data pipeline"
  - "adding a new ingestion source"
  - "planning a backfill or replay"
  - "handling schema evolution upstream"
  - "investigating late-arriving data"
  - "establishing pipeline reliability targets"
outputs:
  - pipeline DAG (per pipeline)
  - transformation spec (per stage)
  - orchestration config (Airflow / Dagster / Prefect / etc.)
  - backfill / replay plan
  - schema evolution policy (per source + per sink)
  - pipeline SLOs (freshness, completeness, latency)
consumers:
  - data-engineer (primary author)
  - data-warehouse-modeling (consumes pipeline output for analytical models)
  - data-quality (consumes for quality-check placement)
  - data-governance (consumes for lineage tracking)
  - observability (pipeline telemetry; pipeline SLO instrumentation)
references:
  - airflow.md
  - dagster.md
  - prefect.md
  - spark.md
  - beam-flink.md
  - kafka-streams.md
```
<!-- praxis:metadata:end -->

The discipline that turns raw data sources into reliable, observable, schema-stable, replay-able pipelines. Done well, pipelines fail loud, recover automatically, handle schema changes gracefully, and produce data the downstream warehouse and ML team can trust. Done poorly, pipelines silently drop data, fail without alerting, accumulate technical debt with each schema change, and require heroics to backfill.

The principle: **pipelines are products too — versioned, tested, observable, with SLOs and clear contracts.**

## When this skill fires

- A new batch or streaming pipeline is being designed.
- A new ingestion source is being added (database CDC, SaaS API, file drop, event stream).
- A backfill or replay is being planned.
- An upstream source's schema is changing.
- A pipeline is failing or producing late / wrong data.
- Pipeline SLOs (freshness, completeness, latency) are being established.

## The architecture decisions

### Batch vs. streaming

| Pattern | Use when | Trade-off |
|---|---|---|
| **Batch** (hourly / daily / nightly) | Tolerance for delay measured in hours. Analytics, ML training data, reporting. | Simple; high throughput; replay-friendly. Latency. |
| **Micro-batch** (every minute or two) | Near-real-time analytics; dashboards. | Better latency than batch; lower complexity than streaming. |
| **Streaming** (continuous) | Real-time use cases (fraud detection, alerting, real-time personalization). | Lowest latency. Higher complexity (state management, late data). |

Default: **batch** for analytical workloads; **streaming** only when latency requires it. "We need real-time" is often "we need every-15-minutes" in disguise.

### Orchestrator choice

| Tool | Sweet spot |
|---|---|
| **Airflow** | Most-used; mature ecosystem; many operators. Workflow-as-Python code. |
| **Dagster** | Asset-first paradigm; great for analytics; software-defined assets. |
| **Prefect** | Pythonic; ergonomic; managed offering (Prefect Cloud) lowers ops burden. |
| **Kafka Connect** | When the data is Kafka-shaped; configuration-driven. |
| **dbt Cloud** | SQL-first analytics pipelines; assumes the data is already in the warehouse. |
| **Cloud-native** | Each cloud has its own (AWS Glue, Azure Data Factory, GCP Cloud Composer / Dataflow). |

Default for new analytical projects: **Dagster** (asset-first model fits warehouse work). Default for legacy / broad ecosystem: **Airflow**. For SQL-heavy transformations: **dbt** (often paired with Dagster/Airflow as orchestrator).

### Processing engine (if heavy compute)

| Engine | Sweet spot |
|---|---|
| **Spark** | Distributed batch + streaming. Default for >100GB workloads. |
| **Beam / Flink** | Unified batch + streaming. Strong state management. |
| **dbt** | SQL transformations in the warehouse. Best when the data fits. |
| **Pandas / Polars** | Single-node Python. Polars is the modern faster option. |
| **DuckDB** | Single-node analytical SQL. Great for medium data. |
| **Kafka Streams / ksqlDB** | Stream processing close to Kafka. |

Default: **dbt for transformations that fit SQL**; **Polars / DuckDB for single-node Python work**; **Spark for distributed compute** when scale warrants.

## The disciplines

### 1. Idempotent everywhere

Pipelines must be safe to re-run. The same input run twice produces the same output.

- **Deterministic output paths** — write to date-partitioned paths (`/data/orders/year=2026/month=11/day=15/`). Re-running overwrites or upserts the same partition.
- **Upsert semantics** — for warehouse loads, use MERGE / UPSERT rather than INSERT (re-running an INSERT duplicates).
- **No timestamp-based incrementality without idempotency** — `WHERE created_at > last_run_time` is non-idempotent if `last_run_time` advances mid-failure.

### 2. Backfills as first-class

A pipeline that can't backfill is a bug. Backfills happen when:
- A new pipeline starts and needs historical data.
- A bug is fixed and historical periods need reprocessing.
- A new column is added and needs to be populated for past data.
- An upstream source corrected data.

Backfill discipline:

- **Bounded backfills** — backfill a specific date range, not "everything."
- **Throttled** — backfilling a year of daily partitions in parallel can overwhelm the warehouse; throttle.
- **Tracked** — backfill runs separately from regular runs in the orchestrator (different DAG run config); easy to identify in logs.

### 3. Late-arriving data

In streaming, data arrives late (out of order). The pipeline handles this:

- **Watermarks** — declare how late data can arrive (e.g., "10 minutes"). Events older than the watermark go to a side stream.
- **Event time vs. processing time** — use event time for windowed aggregations.
- **Re-window updates** — when late data arrives within the watermark, update existing aggregates.

In batch, "late" means a partition needs re-processing. Backfill the affected partition.

### 4. Schema evolution

Upstream schemas change. The pipeline survives via:

- **Schema registry** (Confluent Schema Registry / AWS Glue Schema Registry / cloud-native) — version every schema; compatibility-check changes (backward / forward / full).
- **Tolerant readers** — readers accept unknown fields; ignore them.
- **Explicit migration steps** when adding required fields — first add nullable, populate, then make required.
- **Pinned schemas** in code where strict typing is needed; updates are deliberate.

Schema changes are detected and surfaced; they shouldn't silently break pipelines.

### 5. Pipeline SLOs

Per pipeline:

- **Freshness** — how recent is the latest data? Target: e.g., "p99 < 1 hour after upstream event."
- **Completeness** — what % of expected records arrived? Target: e.g., "> 99.9%."
- **Latency** — time from source event to warehouse availability.
- **Failure rate** — % of pipeline runs that fail. Target: e.g., "< 0.5% over 30 days."

SLOs make pipeline health observable and operations measurable. Tracked in `observability`.

### 6. Pipeline as code, reviewed like code

- Pipelines (DAGs) live in version control.
- Reviewed via PR.
- Tested (unit tests for transformations; integration tests against sample data).
- Deployed via CI/CD (the orchestrator picks up the new DAG version).

### 7. Observable failures

- **Structured logs** with correlation IDs across stages.
- **Per-stage metrics** (records processed, time taken, errors).
- **Alerts on SLO breaches** (freshness, completeness, failure rate).
- **Lineage tracking** — when downstream data is wrong, trace upstream to find the source.

### 8. Cost-aware

Pipelines run continuously; cost matters:

- **Right-size compute** — small workloads on small clusters; auto-scale.
- **Use the warehouse's native compute** when possible (dbt + BigQuery / Snowflake / Redshift cheaper than separate Spark).
- **Schedule wisely** — batch jobs during off-peak; avoid all-at-once-at-midnight spikes.
- **Cold storage for raw** — raw data lives in cheap tiered storage; processed data in hot.

## Per-pipeline design template

```markdown
# Pipeline: customer-events-to-warehouse

## Purpose
Ingest customer event stream → transform → land in warehouse for analytics.

## Source
- Apache Kafka topic: `prod.customer-events.v1`
- Schema: Avro, registered in Schema Registry; version current 4.
- Volume: ~10M events/day; peak 1000 events/sec.
- Late data: events may arrive up to 10 min late.

## Pipeline shape
- Streaming via Beam on Dataflow.
- Watermark: 10 min.
- Tumbling 5-minute windows.
- Outputs to: BigQuery table `analytics.customer_events_5min`.

## Idempotency
- Each window writes to its own partition keyed by window-start timestamp.
- Re-runs overwrite the partition.

## Backfill
- Backfill via Beam from Kafka offsets within retention window (7 days).
- For older data, replay from archived S3 (Kafka → S3 sink runs in parallel).

## Schema evolution
- Schema Registry enforces backward compatibility.
- Tolerant readers in the pipeline.
- Adding new fields: nullable first, populate, then enforce.

## SLOs
- Freshness p99 < 5 minutes (within 5 min of source event).
- Completeness > 99.9% (allow 0.1% drop within watermark).
- Failure rate < 0.5% over 30 days.

## Observability
- Per-stage metrics → Cloud Monitoring.
- Structured logs with correlation IDs.
- Alerts: freshness breach, failure rate, queue lag.

## Cost
- Estimated $X/month (Dataflow workers + BigQuery storage).
- Capped via Dataflow max workers (10).
```

## Outputs

| Output | Location |
|---|---|
| Pipeline DAG / definitions | repo's `data-pipelines/` directory |
| Per-pipeline spec | `.project/operational/pipelines/{name}.md` |
| Backfill / replay runbooks | `.project/operational/runbooks/backfill-{pipeline}.md` |
| Pipeline SLOs | `.project/operational/pipeline-slos.md` |
| Schema evolution policy | `.project/procedural/schema-evolution.md` |

## Mode handling (G/B)

**Greenfield.** Design pipelines as products from day one; SLOs + observability + idempotency baked in.

**Brownfield.** Audit existing pipelines. Common findings: non-idempotent; no backfill plan; silent failures; schema drift accumulating. Migrate one pipeline at a time; each rewrite is its own slice.

## What this skill does not do

- Design the analytical warehouse model — that's `data-warehouse-modeling`.
- Define data quality checks — that's `data-quality` (this skill provides the hooks).
- Manage data lineage / catalog — that's `data-governance`.
- ML feature pipelines — that's `ml-feature-engineering` when applicable, though the patterns overlap.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Idempotency is for distributed systems theory." | Pipelines re-run. Re-runs that double-count records cause data incidents. Idempotency is mandatory. |
| "Backfills are one-off scripts." | Until you need them again. Backfills are first-class pipelines with the same rigor. |
| "Late-arriving data is rare." | It isn't, especially across timezones, batch boundaries, queue retries. Plan watermarks + lateness. |
| "Schema-on-read is flexible." | Until consumers fail. Define schemas + evolve them; don't pretend they don't exist. |
| "Daily batch is fine for everything." | Until business demands hourly, then near-real-time. Decide cadence per use case. |
| "Orchestrator just runs the DAG." | Orchestrator handles retries, alerting, backfill, SLAs, dependencies. Choose deliberately. |

## Verification

You are done when:

- [ ] Pipeline diagram exists: sources → transforms → sinks.
- [ ] Idempotency strategy documented per step.
- [ ] Schema management: versioned + compatibility policy.
- [ ] Watermark + lateness handling defined.
- [ ] Backfill plan documented; tested.
- [ ] SLA per pipeline (freshness target + max delay).
- [ ] Alerting on: failure, freshness miss, schema drift.
- [ ] Cost attribution per pipeline (per `cost-finops`).
- [ ] Test data + golden runs verify correctness.

Evidence to check:
- A failed pipeline restarts cleanly without duplicates.
- A schema change in upstream is detected before consumer failure.

## Anti-patterns

- Non-idempotent pipelines.
- Backfills run by hand-edited SQL.
- No schema registry; "we'll handle schema changes when they break."
- No SLOs; failures discovered by downstream complaints.
- Streaming when batch would suffice (operational overhead).
- Batch when latency requires streaming (chronic stale data).
- Pipelines that drop late data silently.
- Orchestrator-driven dependencies hidden in code (DAG implicit).
- One huge DAG (operational complexity); should be smaller cohesive DAGs.
- Pipeline observability via the orchestrator's UI only (no metrics integration).
