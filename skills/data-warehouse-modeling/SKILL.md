---
name: data-warehouse-modeling
description: Analytical modeling for warehouses. Star and snowflake schemas, slowly changing dimensions, fact-table grain choice, dbt-style modular SQL, semantic layer, marts vs core layering. Per the Resolved Decision, ships with refs for BigQuery / Snowflake / Redshift / Synapse / Databricks SQL. Distinct from `data-modeling` (which is transactional / OLTP). Data Engineer owns this; analysts and PM consume the marts. Use whenever a warehouse is being designed, when analytics tables are being added, when designing dbt project layout, or when building a semantic layer.
capability: data
domain: data
state: active
dependencies:
  - data-modeling
  - data-pipeline
  - engineering-standards
triggers:
  - "designing a new data warehouse"
  - "adding new analytics tables or marts"
  - "designing dbt project layout"
  - "building a semantic layer"
  - "modeling slowly-changing dimensions"
  - "choosing fact-table grain"
outputs:
  - logical analytical model (per business domain)
  - physical schema (warehouse-specific DDL via dbt models)
  - dbt project layout (staging / intermediate / marts / dim+fact)
  - semantic-layer definitions (Cube / dbt Semantic Layer / LookML / similar)
  - marts catalog
consumers:
  - data-engineer (primary author)
  - solution-architect (consumes for analytics architecture)
  - data-pipeline (materializes via pipelines)
  - data-quality (tests run against these models)
  - business analysts (consumers of marts; outside scope of agents)
references:
  - bigquery.md
  - snowflake.md
  - redshift.md
  - synapse.md
  - databricks-sql.md
---

# Data Warehouse Modeling

The discipline of organizing analytical data so it answers questions fast, stays consistent across consumers, and evolves with the business without breaking dashboards.

Transactional models (per `data-modeling`) are optimized for fast individual operations; analytical models are optimized for **slicing, aggregating, joining across time and dimensions**. They're different shapes; this skill produces the analytical one.

The principle: **the warehouse is the team's analytical memory. Treat its schema like a public API — versioned, documented, stable.**

## When this skill fires

- A new warehouse is being established.
- New analytics tables (marts) are being added.
- dbt project layout is being designed or refactored.
- A semantic layer is being built (Cube, dbt Semantic Layer, LookML, etc.).
- Slowly-changing dimensions need handling.
- Fact-table grain is being decided for a new domain.

## The dimensional modeling primer

### Facts and dimensions

- **Fact tables** — measurements / events. One row per measurement, narrow + tall. Columns: foreign keys to dimensions + numeric measures.
- **Dimension tables** — descriptive attributes. One row per entity, wide + short. Columns: surrogate key + natural key + descriptive attributes.

Classic star schema: one fact table at the center, dimension tables around it.

```
       dim_date
            \
   dim_customer --- fact_orders --- dim_product
            /
       dim_store
```

`fact_orders` has: `date_key, customer_key, product_key, store_key, quantity, amount, discount`. One row per order line.

### Snowflake schema

Like star but with dimensions further normalized. `dim_product → dim_product_category → dim_product_segment`. Reduces storage; increases query joins; less common in modern warehouses where storage is cheap.

Default: **star**. Snowflake when there's specific compression benefit + the joins don't hurt query patterns.

### Grain

The grain of a fact table = what one row represents. Be explicit:

- "One row per order line item per day."
- "One row per page view per session."
- "One row per shipment per status change."

Multiple grains → multiple fact tables. Don't mix grains in one table.

### Slowly-changing dimensions (SCD)

Customer changes their email — what does `dim_customer` do?

| Type | Behavior |
|---|---|
| **Type 0** | Never changes. Original value preserved. |
| **Type 1** | Overwrite — only current value kept. History lost. |
| **Type 2** | New row per change. `valid_from`, `valid_to`, `is_current` columns. Full history. |
| **Type 3** | New column per change (e.g., `email`, `previous_email`). Limited history. |
| **Type 4** | Separate history table. |
| **Type 6** | Hybrid (Type 1 + 2 + 3). |

Default for most dimensions: **Type 2** for things that need history (customer state, product category); **Type 1** for cosmetic attributes (display name) where the latest value is fine.

The choice is per-attribute, not per-table. Often one dimension table has both: `name` is Type 1, `tier` is Type 2.

## dbt-style project layout

The de facto standard for warehouse transformations is **dbt** (or its alternatives — SQLMesh, Dataform). The recommended layout:

```
dbt-project/
├── models/
│   ├── staging/              one-to-one with sources; lightly cleaned (rename, cast)
│   │   ├── stg_orders.sql
│   │   ├── stg_customers.sql
│   │   └── ...
│   ├── intermediate/         multi-step transformations; not consumed directly
│   │   ├── int_orders_aggregated.sql
│   │   └── ...
│   └── marts/                final consumed tables (dimensional + facts)
│       ├── core/             dimensions and facts (canonical)
│       │   ├── dim_customer.sql
│       │   ├── dim_product.sql
│       │   ├── dim_date.sql
│       │   └── fct_orders.sql
│       ├── finance/          domain-specific marts (subset / re-aggregation of core)
│       └── marketing/
├── tests/                    custom tests beyond schema.yml
├── macros/                   reusable SQL macros
├── snapshots/                SCD Type 2 tracking via dbt snapshots
└── seeds/                    static reference data (countries, etc.)
```

Layers:

- **Staging** — clean and rename. One staging model per source table. Tests: not_null, unique on natural keys, accepted_values for enums.
- **Intermediate** — multi-step combos. Not exposed to BI tools.
- **Marts** — consumable. Dimension + fact in `core/`; domain-specific marts derive from core.

The discipline: **BI tools query marts, never staging or intermediate**. Marts are the API.

## Semantic layer

The semantic layer is the bridge between marts and consumers (dashboards, ad-hoc queries):

- Defines **metrics** (revenue = sum of `fct_orders.amount`).
- Defines **dimensions** (revenue by customer = group by `fct_orders.customer_key → dim_customer`).
- Centralizes the **business definitions** — every consumer sees the same number for "monthly active users."

Tools:

- **dbt Semantic Layer** (was MetricFlow) — natively integrated with dbt projects.
- **Cube** — open-source semantic layer.
- **LookML** (Looker) — embedded in BI tool.
- **MetricFlow / Lightdash** — alternatives.

For projects starting with dbt: **dbt Semantic Layer**. Avoid hand-rolled "metric definitions in dashboard tool only" — definitions drift across dashboards.

## Naming convention

Per dbt convention + general warehouse hygiene:

- `stg_<source>` — staging models.
- `int_<concept>` — intermediate.
- `dim_<entity>` — dimensions.
- `fct_<event>` or `fact_<event>` — facts.
- `<domain>__<purpose>` — domain-specific marts (`finance__monthly_revenue`).
- Column names: snake_case; primary key `<table>_id` or `<table>_key`; foreign keys match.

Consistency matters more than the specific choice. Document the convention; enforce in PR review.

## Warehouse references

Per the Resolved Decision (agnostic refs for all):

- **`references/bigquery.md`** — partitioning + clustering; slot management; INFORMATION_SCHEMA; BI Engine.
- **`references/snowflake.md`** — virtual warehouses; clustering keys; zero-copy clones; Time Travel.
- **`references/redshift.md`** — distribution + sort keys; Redshift Spectrum; concurrency scaling.
- **`references/synapse.md`** — Dedicated SQL pools; serverless pools; integration with Azure ML.
- **`references/databricks-sql.md`** — SQL warehouses; Photon engine; Unity Catalog integration.

Each ref covers the warehouse-specific patterns for tuning + cost + observability.

## Outputs

| Output | Location |
|---|---|
| Logical analytical model | `.project/semantic/warehouse-model.md` |
| dbt project | `dbt-project/` in repo |
| dbt model schemas (yml) | colocated with models (test definitions inline) |
| Semantic layer definitions | dbt models or Cube YAML or equivalent |
| Marts catalog | `.project/semantic/marts-catalog.md` |

## Mode handling (G/B)

**Greenfield.** Build the dbt project from day one with the staging / intermediate / marts layering.

**Brownfield.** Audit existing warehouse posture. Common findings: no layering (transformations directly on raw); duplicate metric definitions across dashboards; no SCD strategy. Refactor one domain at a time.

## What this skill does not do

- Pipeline orchestration — that's `data-pipeline` (this skill defines the *models* the pipeline materializes).
- Data quality checks — that's `data-quality`.
- Catalog and lineage — that's `data-governance`.
- BI dashboard design — that's the analyst's craft, outside the platform's scope.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Star schema is old-fashioned." | Star schema is what BI tools assume. Modern variants (data vault) layer on top, not replace. |
| "Flat tables are simpler." | Until queries take minutes + denormalization spreads. Star schema is the queryable shape. |
| "SCD types are complicated." | SCD types (1/2/3/6) are vocabulary, not rocket science. Pick per attribute; document the choice. |
| "Time zones are easy." | Until they're not. UTC at storage; convert at presentation. Store the offset / IANA zone. |
| "Grain is obvious from the data." | Grain is a design choice. Document it; non-obvious grain causes wrong aggregations. |
| "ELT > ETL means we skip transforms." | ELT means transforms happen in warehouse instead of pre-load. Still happens. |

## Verification

You are done when:

- [ ] Dimensional model documented: facts, dimensions, grain per fact.
- [ ] SCD types decided per dimension attribute (1: overwrite; 2: history; etc.).
- [ ] Naming conventions documented + applied.
- [ ] Conformed dimensions identified (shared across facts).
- [ ] Time-zone handling documented.
- [ ] Surrogate key strategy.
- [ ] Aggregate tables planned for performance.
- [ ] Partition + clustering strategy per warehouse engine.
- [ ] Documentation accessible to BI users.

Evidence to check:
- A new analyst can write a correct query from the documented model.
- Common aggregations meet performance SLO.

## Anti-patterns

- Transformations in BI tool (definitions drift).
- One giant denormalized table for everything ("the spreadsheet pattern").
- No SCD strategy (history silently lost).
- Mixed grains in one fact table.
- BI tools querying staging or intermediate (no layering protection).
- Metric definitions duplicated across dashboards.
- No naming convention (every analyst names things differently).
- Marts depend on raw data (no buffer for upstream changes).
- dbt project with no tests.
- Warehouse-specific features used without abstraction (lock-in by accident).
