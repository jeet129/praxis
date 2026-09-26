# Reference — Apache Airflow

Loaded by `data-pipeline` when Airflow is the chosen orchestrator (the most common default).

## When to use

Airflow is the recommended default for batch ETL/ELT orchestration when:
- Most pipelines are scheduled or DAG-based, not pure streaming.
- Team needs Python-native DAG authoring.
- Mature ecosystem and operator coverage matter.

Skip Airflow when:
- The workload is asset-based (think dbt + observable lineage) → consider Dagster (`dagster.md`).
- The workload is pure streaming → Kafka Streams / Flink / Beam.
- You want minimal infrastructure → Prefect (managed) or simple cron + scripts.

## Core concepts

- **DAG** (Directed Acyclic Graph): the workflow definition.
- **Task**: a unit of work (an operator invocation).
- **Operator**: a class that defines what a task does (PythonOperator, BashOperator, KubernetesPodOperator, etc.).
- **TaskInstance** (TI): a specific run of a task for a specific DAG run.
- **Executor**: how tasks actually run (LocalExecutor, CeleryExecutor, KubernetesExecutor — KubernetesExecutor is the default for new self-hosted).
- **Scheduler**: parses DAGs, schedules runs, queues tasks.
- **Webserver**: UI for monitoring + manual operations.
- **Metadata DB**: usually Postgres; stores DAG state + history.

## TaskFlow API (modern Airflow 2.x)

The TaskFlow API is the recommended authoring pattern — cleaner than the classic Operator pattern:

```python
# dags/orders_etl.py
from datetime import datetime, timedelta
from airflow.decorators import dag, task

DEFAULT_ARGS = {
    'owner': 'data-team',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1),
    'sla': timedelta(hours=2),
}

@dag(
    dag_id='orders_etl',
    schedule='0 2 * * *',                     # 2am daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=['orders', 'etl'],
    max_active_runs=1,
)
def orders_etl_dag():

    @task
    def extract(ds: str) -> dict:
        # Fetch orders for the logical date ds (YYYY-MM-DD)
        rows = fetch_orders_for_date(ds)
        return {'count': len(rows), 's3_path': upload_to_s3(rows, ds)}

    @task
    def transform(extracted: dict) -> str:
        # Read S3, transform, write transformed file
        return apply_transformations(extracted['s3_path'])

    @task
    def load(transformed_path: str, ds: str) -> int:
        # Load to warehouse
        return load_to_warehouse(transformed_path, table='orders_silver', partition=ds)

    @task(trigger_rule='all_success')
    def validate(load_count: int) -> None:
        assert load_count > 0, 'expected at least one row loaded'

    # Define dependencies
    extracted = extract('{{ ds }}')
    transformed = transform(extracted)
    loaded = load(transformed, '{{ ds }}')
    validate(loaded)

dag = orders_etl_dag()
```

## Idempotency — the #1 discipline

Per `data-pipeline` SKILL: pipelines re-run. Make tasks idempotent.

```python
@task
def load(rows: list[dict], ds: str) -> int:
    # ON CONFLICT DO UPDATE — re-run produces the same final state
    with warehouse.connect() as conn:
        conn.execute(
            """INSERT INTO orders_silver (id, status, partition_date)
               VALUES (%s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET
                   status = EXCLUDED.status,
                   partition_date = EXCLUDED.partition_date""",
            [(r['id'], r['status'], ds) for r in rows],
        )
    return len(rows)
```

For appending: include a deduplication key. For overwriting: delete the partition first, then insert.

## Backfills

Backfills are first-class. Two patterns:

**Pattern 1 — Airflow CLI**:
```bash
airflow dags backfill orders_etl --start-date 2026-01-01 --end-date 2026-01-31
```

**Pattern 2 — `catchup=True`**: when you deploy a DAG with a `start_date` in the past, Airflow runs ALL missed schedules. Usually you want `catchup=False` + explicit backfills as needed.

The DAG MUST handle backfills the same as regular runs — idempotency is the gate.

## Configuration via Variables + Connections

```python
from airflow.models import Variable
from airflow.hooks.base import BaseHook

# Variable (key-value config)
schema_name = Variable.get('warehouse_schema', default_var='analytics')

# Connection (URL/credentials)
conn = BaseHook.get_connection('postgres_warehouse')
# conn.host, conn.port, conn.login, conn.password
```

Production secrets via a secrets backend (per `secrets-config`):

```yaml
# airflow.cfg
[secrets]
backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
backend_kwargs = {"connections_prefix": "airflow/connections", "variables_prefix": "airflow/variables"}
```

## KubernetesExecutor + KubernetesPodOperator

The recommended setup for production self-hosted Airflow:
- **KubernetesExecutor** runs each task as a pod — natural isolation + resource limits.
- **KubernetesPodOperator** lets a task spawn its own pod (for non-Python work or heavy isolation).

```python
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

heavy_etl = KubernetesPodOperator(
    task_id='heavy_etl',
    name='heavy-etl',
    image='myregistry/heavy-etl:1.2.3',
    cmds=['python', '/app/etl.py'],
    arguments=['--date', '{{ ds }}'],
    resources={'request_memory': '4Gi', 'request_cpu': '2', 'limit_memory': '8Gi', 'limit_cpu': '4'},
    in_cluster=True,
    namespace='airflow-tasks',
    get_logs=True,
    is_delete_operator_pod=True,
)
```

## SLAs + observability

Set SLAs on critical DAGs:
```python
@dag(default_args={'sla': timedelta(hours=2)})
```

Airflow sends an SLA miss notification (configure via `sla_miss_callback`).

For deeper observability per `observability` SKILL:
- StatsD/Prometheus metrics: scheduler heartbeat, task duration, queue depth.
- Logs: ship to centralized logging via Fluentd/Vector sidecar.
- Traces: OpenTelemetry support added in Airflow 2.7+.

## Testing

```python
# tests/dags/test_orders_etl.py
from airflow.models import DagBag

def test_orders_etl_dag_loads_no_errors():
    dag_bag = DagBag(dag_folder='dags/', include_examples=False)
    assert 'orders_etl' in dag_bag.dags
    assert not dag_bag.import_errors

def test_orders_etl_dag_structure():
    dag_bag = DagBag(dag_folder='dags/', include_examples=False)
    dag = dag_bag.get_dag('orders_etl')
    assert len(dag.tasks) == 4
    assert dag.schedule == '0 2 * * *'
```

For task logic, unit-test the task functions directly (they're just Python). For E2E, run a local Airflow with `airflow standalone` or use the official Docker Compose.

## Gotchas

- **`schedule_interval` is deprecated** — use `schedule`.
- **`PythonVirtualenvOperator` and `@task.virtualenv`** for tasks needing isolated Python deps — slower startup, but better than dependency drift.
- **DAGs must be deterministic to parse** — don't read external state at parse time; the scheduler parses constantly.
- **XCom is not for large data** — payloads > a few KB should write to S3/object storage and pass the URI.
- **`start_date` in DAG must be static** — `datetime.now()` at parse time = constantly-moving start date = broken scheduling.
- **`catchup=True` with `start_date` years ago** = scheduler tries to run thousands of historical runs. Always default to `catchup=False`.
- **Timezone gotcha** — Airflow uses UTC by default; the `ds` template is the UTC date. Configure `default_timezone` if you need local-time schedules.

## Operational notes

- **Scheduler** is single-active in older versions; HA scheduler is available in 2.0+. Run multiple schedulers for resilience.
- **Webserver** is stateless; scale horizontally.
- **Workers** scale per the executor (Celery: multiple worker pods; Kubernetes: per-task pods).
- **Metadata DB** is the bottleneck at high task volumes — provision generously; use Postgres (MySQL is supported but Postgres is the modern default).

## Migrations

Airflow DB migrations happen automatically on `airflow db upgrade`. Run before any version bump.

For DAG changes that alter task identity (renamed tasks, removed tasks), expect orphaned history. Plan deletions explicitly.

## When to consider alternatives

| Symptom | Alternative |
|---|---|
| "We want lineage as a first-class concept." | Dagster (`dagster.md`) |
| "We want managed; minimal ops." | Prefect Cloud (`prefect.md`) |
| "Workload is mostly streaming." | Flink / Kafka Streams / Beam |
| "Pipelines are just dbt." | dbt Cloud + lightweight orchestration |
| "We're already heavily on a specific cloud's tooling." | AWS Step Functions, GCP Composer (=Airflow managed), Azure Data Factory |

## Common rationalizations

| Thought | Counter |
|---|---|
| "Tasks don't need to be idempotent; we'll just rerun." | Re-runs that double-count are data incidents. Idempotency is mandatory. |
| "Backfills are one-off scripts." | Backfills are pipelines. Same rigor: idempotent, observable, tested. |
| "We don't need SLAs." | SLAs are how downstream consumers know what to expect. Define them. |
| "XCom can hold the dataframe." | XCom serializes to metadata DB; large payloads kill the scheduler. Use object storage. |

## Official sources

- Airflow documentation: https://airflow.apache.org/docs/
- TaskFlow API: https://airflow.apache.org/docs/apache-airflow/stable/tutorial/taskflow.html
- Providers index: https://airflow.apache.org/docs/apache-airflow-providers/
- Airflow Improvement Proposals (AIPs): https://cwiki.apache.org/confluence/display/AIRFLOW/Airflow+Improvement+Proposals
