# Reference — MLflow

Loaded by `ml-training-evaluation` when MLflow is the chosen experiment tracking + model registry tool.

## Why MLflow

MLflow is the recommended default for ML experiment tracking when:
- You want OSS + self-hostable + cloud-agnostic.
- You need tracking + registry + serving in one tool.
- Team is comfortable with Python ecosystem.

Alternatives:
- **Weights & Biases**: stronger UX + collaboration; SaaS or self-hosted (`wandb.md`).
- **Vertex AI Experiments**: GCP-native (`vertex-experiments.md`).
- **SageMaker Experiments**: AWS-native (`sagemaker-experiments.md`).
- **Comet**: comparable; less common (`comet.md`).

## Components

| Component | What |
|---|---|
| **Tracking** | Log experiments, parameters, metrics, artifacts, source code, environment. |
| **Projects** | Package code for reproducible runs. |
| **Models** | Package trained models in a standard format. |
| **Model Registry** | Versioned model store with stages (Staging, Production). |

You can use just the tracking + registry components — that's the most common pattern.

## Tracking server architecture

```
[Training script]
   ↓ logs to MLflow tracking URI
[MLflow tracking server]
   ├── Metadata: PostgreSQL/MySQL
   ├── Artifacts: S3/GCS/Azure Blob
   └── UI: at the tracking URI
```

For team use, run a managed tracking server backed by Postgres + S3. Don't use local SQLite + filesystem in production.

## Setting up

```bash
pip install mlflow

# Production setup: tracking server + Postgres + S3
mlflow server \
    --backend-store-uri postgresql://user:pass@db/mlflow \
    --default-artifact-root s3://my-mlflow-bucket/artifacts \
    --host 0.0.0.0 --port 5000
```

For Kubernetes deployment, use the official Helm chart.

In your training script:
```python
import mlflow
import mlflow.sklearn

mlflow.set_tracking_uri("http://mlflow-server:5000")
mlflow.set_experiment("/orders-fraud-detection")  # creates if not exists
```

## Logging a run

```python
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# All inside the run context
with mlflow.start_run(run_name="rf-baseline") as run:
    # Log parameters
    params = {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 5,
        "random_state": 42,
    }
    mlflow.log_params(params)
    
    # Train
    model = RandomForestClassifier(**params)
    model.fit(X_train, y_train)
    
    # Log metrics
    y_pred = model.predict(X_test)
    mlflow.log_metric("accuracy", accuracy_score(y_test, y_pred))
    mlflow.log_metric("precision", precision_score(y_test, y_pred))
    mlflow.log_metric("recall", recall_score(y_test, y_pred))
    mlflow.log_metric("f1", f1_score(y_test, y_pred))
    
    # Log per-slice metrics (per `responsible-ai`)
    for slice_name, slice_mask in slices.items():
        slice_pred = model.predict(X_test[slice_mask])
        slice_y = y_test[slice_mask]
        mlflow.log_metric(f"f1_slice_{slice_name}", f1_score(slice_y, slice_pred))
    
    # Log artifacts (plots, confusion matrices, etc.)
    fig = plot_confusion_matrix(y_test, y_pred)
    mlflow.log_figure(fig, "confusion_matrix.png")
    
    # Log the dataset version (per `ml-training-evaluation` reproducibility)
    mlflow.log_param("dataset_version", DATASET_VERSION)
    mlflow.log_param("dataset_sha", DATASET_SHA)
    
    # Log the model
    mlflow.sklearn.log_model(
        model,
        artifact_path="model",
        registered_model_name="fraud-detector",  # auto-registers to model registry
        signature=infer_signature(X_train, y_pred),
        input_example=X_train.iloc[:5],
    )
    
    # Log source environment
    mlflow.log_artifact("requirements.txt")
```

The `signature` + `input_example` are critical for downstream serving — they document the model's expected input/output shape.

## Reproducibility checklist (per `ml-training-evaluation`)

For every run, log:
- ✅ Code version (git SHA): `mlflow.log_param("git_sha", subprocess.check_output(["git", "rev-parse", "HEAD"]).strip())`
- ✅ Data version: dataset name + version + content hash
- ✅ Hyperparameters: all of them
- ✅ Random seed: `mlflow.log_param("random_seed", 42)`
- ✅ Environment: `mlflow.log_artifact("requirements.txt")` + Python version
- ✅ Hardware: GPU type, CPU count (optional but useful)

These together let you reproduce any historical run.

## Experiment organization

```python
# Hierarchical naming via slashes
mlflow.set_experiment("/orders/fraud-detection/2026-q2")
mlflow.set_experiment("/orders/fraud-detection/baselines")
mlflow.set_experiment("/orders/fraud-detection/feature-engineering")
```

Tag runs for searching:
```python
mlflow.set_tag("model_family", "tree_based")
mlflow.set_tag("approach", "supervised")
mlflow.set_tag("trainer", "alice@example.com")
mlflow.set_tag("feature_set", "v3-with-velocity-features")
```

Search later via UI or API:
```python
runs = mlflow.search_runs(
    experiment_names=["/orders/fraud-detection/2026-q2"],
    filter_string="tags.model_family = 'tree_based' AND metrics.f1 > 0.85",
    order_by=["metrics.f1 DESC"],
    max_results=10,
)
```

## Model Registry

Models progress through stages:

```python
from mlflow.tracking import MlflowClient

client = MlflowClient()

# Promote a model version to Staging
client.transition_model_version_stage(
    name="fraud-detector",
    version=3,
    stage="Staging",
    archive_existing_versions=True,  # archive old Staging versions
)

# After validation, promote to Production
client.transition_model_version_stage(
    name="fraud-detector",
    version=3,
    stage="Production",
    archive_existing_versions=True,
)
```

For serving (per `ml-serving-deployment` SKILL):

```python
# Load the current Production model
model = mlflow.sklearn.load_model(model_uri="models:/fraud-detector/Production")

# Or a specific version
model = mlflow.sklearn.load_model(model_uri="models:/fraud-detector/3")
```

## Model signatures

```python
from mlflow.models.signature import infer_signature

signature = infer_signature(X_train, model.predict(X_train))
mlflow.sklearn.log_model(model, "model", signature=signature)
```

Signatures encode the input + output schema. Serving infrastructure can:
- Validate incoming requests against the schema.
- Convert types as needed.
- Generate API documentation.

## Autologging (when you want minimal code)

```python
mlflow.sklearn.autolog()
# Now all sklearn fit() calls auto-log params, metrics, model

with mlflow.start_run():
    model.fit(X_train, y_train)
    # All logged automatically
```

Supported: scikit-learn, XGBoost, LightGBM, PyTorch, TensorFlow/Keras, Spark MLlib, fastai, statsmodels, Prophet, transformers, langchain, OpenAI.

Use autolog for fast iteration; explicit logging for production-bound experiments where you control what's captured.

## Per-slice metrics + responsible AI integration

Per `responsible-ai` SKILL — log per-slice metrics for fairness audits:

```python
slices = {
    "age_18_30": (X_test["age"] >= 18) & (X_test["age"] < 30),
    "age_30_50": (X_test["age"] >= 30) & (X_test["age"] < 50),
    "age_50_plus": X_test["age"] >= 50,
    "region_us": X_test["region"] == "US",
    "region_eu": X_test["region"] == "EU",
}

for slice_name, mask in slices.items():
    if mask.sum() < 100:
        continue  # skip tiny slices
    sf1 = f1_score(y_test[mask], y_pred[mask])
    sp = precision_score(y_test[mask], y_pred[mask])
    sr = recall_score(y_test[mask], y_pred[mask])
    mlflow.log_metric(f"f1_{slice_name}", sf1)
    mlflow.log_metric(f"precision_{slice_name}", sp)
    mlflow.log_metric(f"recall_{slice_name}", sr)
```

The model card (per `responsible-ai`) consumes these in the fairness audit section.

## Integration with CI/CD

```yaml
# .github/workflows/train.yml
jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt
      - run: python train.py
        env:
          MLFLOW_TRACKING_URI: ${{ secrets.MLFLOW_TRACKING_URI }}
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}  # for artifact S3
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Comparing runs

```python
import mlflow

runs = mlflow.search_runs(
    experiment_names=["/orders/fraud-detection/2026-q2"],
    max_results=20,
    order_by=["metrics.f1 DESC"],
)

# DataFrame with all runs + params + metrics
print(runs[["run_id", "params.n_estimators", "params.max_depth", "metrics.f1", "metrics.precision"]])
```

The MLflow UI does this visually with parallel coordinates + scatter plots.

## Production gotchas

- **Tracking server scale**: at high run rates (hundreds per day) the Postgres backend matters. Plan capacity.
- **Artifact storage growth**: large model artifacts add up. Lifecycle policy on the S3 bucket.
- **Stage transitions are now Aliases in MLflow 2.x** — `Staging`/`Production` are being deprecated in favor of free-form aliases (`@champion`, `@challenger`). Migrate when you can.
- **Don't store secrets in run params** — they're queryable forever. Pass via env vars; log a redacted reference.
- **`mlflow.start_run()` without `with`** — you must call `mlflow.end_run()` explicitly. Use the context manager.

## Common rationalizations

| Thought | Counter |
|---|---|
| "Notebooks are good enough for tracking." | Notebooks accumulate forgotten state. MLflow makes runs auditable + reproducible. |
| "I'll log only the metrics; data version is in git." | Data sometimes isn't in git (too large, separate pipeline). Log the version explicitly. |
| "Use local file URI; we don't need a server." | Works for solo experimentation. Breaks the moment two people compare runs. |
| "Autolog logs everything; I don't need to tag." | Autolog logs what the library knows. Manual tags (model_family, approach) are what makes search useful. |
| "Promotion to Production happens in UI." | UI for ad-hoc; CI/CD for repeatable. Automate the promotion logic; gate on real criteria. |

## Verification (per `ml-training-evaluation` SKILL)

- [ ] Tracking server centralized + backed by Postgres + S3 (not local SQLite).
- [ ] Every run logs: code SHA, data version, hyperparameters, seed, environment.
- [ ] Per-slice metrics logged for fairness-relevant cohorts.
- [ ] Model registered with signature + input example.
- [ ] Model registry stages used (Staging → Production).
- [ ] Promotion criteria documented + enforced (don't promote on metric > X alone).
- [ ] Model card generated from the registered model + artifacts.

## Official sources

- MLflow documentation: https://mlflow.org/docs/latest/index.html
- MLflow on Kubernetes: https://github.com/mlflow/mlflow/tree/master/examples/kubernetes
- MLflow Helm chart (community): https://github.com/community-charts/helm-charts/tree/main/charts/mlflow
- Databricks-managed MLflow: native option for Databricks workspaces.
