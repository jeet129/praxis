# ML Feature Engineering — Feast

Feast is the open-source feature store: it separates feature *definition* (Python, versioned) from feature *storage* (online/offline stores), and guarantees training/serving consistency via point-in-time-correct joins.

## Why a feature store

- **Training/serving skew** is the default failure mode without one — features computed differently (or on stale data) at serving time than at training time silently degrade model quality.
- Feast enforces the same feature definitions and (where possible) the same underlying data for both paths, and gives low-latency online lookups without every service reimplementing a Redis-backed cache.

## Project layout

```
feature_repo/
├── feature_store.yaml       registry + store config
├── entities.py               entity definitions
├── driver_features.py        feature views
└── data_sources.py           offline source definitions
```

## Entities and data sources

```python
# entities.py
from feast import Entity

driver = Entity(
    name="driver_id",
    join_keys=["driver_id"],
    description="A driver in the ride-sharing marketplace",
)
```

```python
# data_sources.py
from feast import FileSource
from feast.data_source import PushSource

driver_stats_source = FileSource(
    name="driver_stats_source",
    path="s3://feature-data/driver_stats.parquet",
    timestamp_field="event_timestamp",
    created_timestamp_column="created",
)

# For low-latency writes from a streaming job directly to online store
driver_stats_push_source = PushSource(
    name="driver_stats_push_source",
    batch_source=driver_stats_source,
)
```

## Feature views

A feature view groups related features computed from one source, tied to an entity, with a TTL that bounds how stale a point-in-time join is allowed to be.

```python
# driver_features.py
from datetime import timedelta
from feast import FeatureView, Field
from feast.types import Float32, Int64
from entities import driver
from data_sources import driver_stats_source

driver_stats_fv = FeatureView(
    name="driver_hourly_stats",
    entities=[driver],
    ttl=timedelta(days=1),
    schema=[
        Field(name="conv_rate", dtype=Float32),
        Field(name="acc_rate", dtype=Float32),
        Field(name="avg_daily_trips", dtype=Int64),
    ],
    online=True,
    source=driver_stats_source,
    tags={"team": "marketplace"},
)
```

On-demand feature views compute derived features at request time from other feature views + request-time inputs (features that can't be precomputed, like "distance from current request location"):

```python
from feast import RequestSource
from feast.on_demand_feature_view import on_demand_feature_view
from feast.types import Float64

input_request = RequestSource(
    name="pickup_location",
    schema=[Field(name="lon", dtype=Float64), Field(name="lat", dtype=Float64)],
)

@on_demand_feature_view(
    sources=[driver_stats_fv, input_request],
    schema=[Field(name="conv_rate_adjusted", dtype=Float64)],
)
def conv_rate_adjusted_fv(inputs: dict) -> dict:
    return {"conv_rate_adjusted": inputs["conv_rate"] * 0.9}
```

## Online vs offline stores

| | Offline store | Online store |
|---|---|---|
| Purpose | Historical, point-in-time-correct training data | Low-latency (single-digit ms) feature lookup for inference |
| Backends | BigQuery, Snowflake, Redshift, file (Parquet/S3), Spark | Redis, DynamoDB, Datastore, Bigtable, SQLite (dev only) |
| Access pattern | Bulk retrieval joined against training labels | Single-entity or small-batch key lookup |
| Config | `feature_store.yaml` `offline_store` | `feature_store.yaml` `online_store` |

```yaml
# feature_store.yaml
project: marketplace
provider: aws
registry: s3://feast-registry/registry.pb
offline_store:
  type: redshift
  cluster_id: feast-cluster
  region: us-east-1
  database: feast
online_store:
  type: redis
  connection_string: "redis.internal:6379"
entity_key_serialization_version: 3
```

## Point-in-time-correct joins (training data generation)

This is Feast's core value: given an entity dataframe with timestamps, it joins each row to the feature values *as they existed at that timestamp* — no future data leaks into training.

```python
from feast import FeatureStore
import pandas as pd

store = FeatureStore(repo_path="feature_repo/")

entity_df = pd.DataFrame({
    "driver_id": [1001, 1002, 1003],
    "event_timestamp": pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03"]),
})

training_df = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "driver_hourly_stats:conv_rate",
        "driver_hourly_stats:acc_rate",
        "driver_hourly_stats:avg_daily_trips",
    ],
).to_df()
```

Every training run re-derives from `get_historical_features` — never hand-join feature tables directly, or the point-in-time guarantee is lost.

## Materialization (offline → online)

```bash
# Full materialization for a date range (backfill)
feast materialize 2026-01-01T00:00:00 2026-07-01T00:00:00

# Incremental — from the last materialized timestamp to now (scheduled, e.g. Airflow/cron)
feast materialize-incremental $(date -u +"%Y-%m-%dT%H:%M:%S")
```

```python
# Programmatic, inside an Airflow DAG task
from feast import FeatureStore
FeatureStore(repo_path="feature_repo/").materialize_incremental(end_date=datetime.utcnow())
```

Materialization cadence matches feature freshness requirements — hourly for `driver_hourly_stats`, near-real-time via `PushSource` for features that must reflect the last few seconds (e.g., fraud signals).

## Online retrieval (serving path)

```python
features = store.get_online_features(
    features=[
        "driver_hourly_stats:conv_rate",
        "driver_hourly_stats:acc_rate",
    ],
    entity_rows=[{"driver_id": 1001}],
).to_dict()
```

This is the call the inference service makes at request time — same feature names and semantics as training, sourced from the low-latency online store.

## Feature registry and CI

```bash
feast apply         # validates + registers feature definitions to the registry
feast plan           # dry-run diff, like terraform plan — use in PR CI
feast teardown        # tears down infra Feast provisioned (careful in prod)
```

Run `feast plan` in CI on every PR touching `feature_repo/` — catches accidental breaking changes to feature schemas (type changes, entity renames) before they hit the registry.

## Common violations to flag in review

- Training data hand-joined from raw tables instead of `get_historical_features` — reintroduces training/serving skew and leakage risk.
- Feature views with no `ttl` — undefined staleness bound in point-in-time joins.
- Online store lookups performed directly against the offline warehouse (latency mismatch — offline stores are not built for single-digit-ms lookups).
- `feast apply` run ad hoc from a laptop instead of via CI — registry drifts from what's in version control.
- On-demand feature views doing expensive computation at request time without a latency budget check against the serving SLA.
- Materialization cadence mismatched to feature freshness needs (hourly materialize for a feature that needs to be real-time).
