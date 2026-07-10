# References Inventory

Searchable inventory of all reference files cited from SKILL frontmatter — both **shipping** (real content) and **missing** (cited but not yet written).

**As of last update:** 117 references cited · 37 shipping · 80 missing.

Use `grep` to find what you need:
- By SKILL: `grep "^| \`<skill>\`" MISSING-INVENTORY.md`
- By tool category: `grep "^### " MISSING-INVENTORY.md` to list categories
- By status: `grep " missing |" MISSING-INVENTORY.md` or `grep " shipping |" MISSING-INVENTORY.md`
- By tool name: `grep "<tool-name>" MISSING-INVENTORY.md`

When you write a missing one, change its **Status** from `missing` to `shipping` and update the count at the top.

---

## Shipping (37 files)

These have real content. The SKILL that cites them can load them via its `references` field.

| File | Cited by | Category | Status |
|---|---|---|---|
| `cicd-pipeline/references/github-actions.md` | `cicd-pipeline` | CI/CD | shipping |
| `cicd-pipeline/references/gitlab-ci.md` | `cicd-pipeline` | CI/CD | shipping |
| `cicd-pipeline/references/azure-devops.md` | `cicd-pipeline` | CI/CD | shipping |
| `engineering-standards/references/java-spring.md` | `engineering-standards`, `code-review`, `secure-coding` | Stack standards | shipping |
| `engineering-standards/references/node-ts.md` | `engineering-standards`, `code-review`, `secure-coding` | Stack standards | shipping |
| `engineering-standards/references/python.md` | `engineering-standards`, `code-review`, `secure-coding` | Stack standards | shipping |
| `engineering-standards/references/web-frontend.md` | `engineering-standards`, `code-review`, `secure-coding` | Stack standards | shipping |
| `api-design/references/rest-openapi.md` | `api-design` | API specs | shipping |
| `performance-testing/references/k6.md` | `performance-testing` | Performance testing | shipping |
| `secrets-config/references/hashicorp-vault.md` | `secrets-config` | Secret store | shipping |
| `secrets-config/references/k8s-external-secrets.md` | `secrets-config` | Secret store | shipping |
| `ml-feature-engineering/references/feast.md` | `ml-feature-engineering` | ML feature store | shipping |
| `ml-monitoring-drift/references/evidently.md` | `ml-monitoring-drift` | ML monitoring | shipping |
| `ml-serving-deployment/references/kserve.md` | `ml-serving-deployment` | ML serving | shipping |
| `ml-serving-deployment/references/batch-online-streaming.md` | `ml-serving-deployment` | ML serving | shipping |
| `deploy-release/references/kubernetes-rollouts.md` | `deploy-release` | Deploy / release | shipping |
| `deploy-release/references/argo-rollouts.md` | `deploy-release` | Deploy / release | shipping |
| `iac/references/terraform.md` | `iac` | IaC | shipping |
| `iac/references/pulumi.md` | `iac` | IaC | shipping |
| `stack-web-frontend/references/react-next.md` | `stack-web-frontend` | Frontend framework | shipping |
| `stack-web-frontend/references/angular.md` | `stack-web-frontend` | Frontend framework | shipping |
| `stack-web-frontend/references/vue-nuxt.md` | `stack-web-frontend` | Frontend framework | shipping |
| `stack-node-ts/references/fastify.md` | `stack-node-ts` | Backend framework | shipping |
| `stack-node-ts/references/express.md` | `stack-node-ts` | Backend framework | shipping |
| `stack-python/references/fastapi.md` | `stack-python` | Backend framework | shipping |
| `stack-java-spring/references/spring-boot-3.md` | `stack-java-spring` | Backend framework | shipping |
| `data-modeling/references/postgres.md` | `data-modeling` | Database | shipping |
| `data-pipeline/references/airflow.md` | `data-pipeline` | Data orchestrator | shipping |
| `data-quality/references/great-expectations.md` | `data-quality` | Data quality | shipping |
| `compliance-privacy/references/soc2.md` | `compliance-privacy` | Compliance regime | shipping |
| `compliance-privacy/references/gdpr.md` | `compliance-privacy` | Compliance regime | shipping |
| `observability/references/opentelemetry.md` | `observability` | Observability | shipping |
| `observability/references/prometheus-grafana.md` | `observability` | Observability | shipping |
| `secrets-config/references/aws-secrets-manager.md` | `secrets-config` | Secret store | shipping |
| `ml-training-evaluation/references/mlflow.md` | `ml-training-evaluation` | ML tracking | shipping |
| `rag-design/references/pgvector.md` | `rag-design` | Vector store | shipping |
| `evaluation-engineering/references/promptfoo.md` | `evaluation-engineering` | LLM eval | shipping |

---

## Missing — by category (80 files)

### API specs

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `api-design/references/grpc-proto.md` | `api-design` | gRPC service definition, Proto3 idioms, breaking-change rules | medium | missing |
| `api-design/references/graphql.md` | `api-design` | Schema design, federation, N+1 mitigations | medium | missing |
| `api-design/references/asyncapi-events.md` | `api-design` | AsyncAPI spec for event-driven contracts | low | missing |

### CI / CD

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `cicd-pipeline/references/jenkins.md` | `cicd-pipeline` | Declarative pipelines, shared libraries, plugin discipline | low | missing |

### Compliance regimes

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `compliance-privacy/references/hipaa.md` | `compliance-privacy` | HIPAA controls, BAAs, PHI handling | high (if healthcare) | missing |
| `compliance-privacy/references/pci-dss.md` | `compliance-privacy` | PCI-DSS scope, cardholder data, tokenization | high (if payments) | missing |
| `compliance-privacy/references/iso-27001.md` | `compliance-privacy` | ISMS controls, Annex A | medium | missing |
| `compliance-privacy/references/ccpa.md` | `compliance-privacy` | CA Privacy Act; opt-out + DSAR | medium | missing |
| `compliance-privacy/references/nist-csf.md` | `compliance-privacy` | NIST Cybersecurity Framework | medium (US gov) | missing |
| `compliance-privacy/references/fedramp.md` | `compliance-privacy` | FedRAMP controls, ATO process | low (US gov only) | missing |

### Data — databases

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `data-modeling/references/mysql.md` | `data-modeling` | MySQL/MariaDB schema + perf patterns | medium | missing |
| `data-modeling/references/mongodb.md` | `data-modeling` | Document modeling, sharding, secondary indexes | medium | missing |
| `data-modeling/references/dynamodb.md` | `data-modeling` | Single-table design, GSIs, access patterns | medium | missing |
| `data-modeling/references/polyglot-persistence.md` | `data-modeling` | When/how to combine stores; tradeoff catalog | low | missing |

### Data — orchestrators

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `data-pipeline/references/dagster.md` | `data-pipeline` | Asset-based orchestration, software-defined assets | medium | missing |
| `data-pipeline/references/prefect.md` | `data-pipeline` | Flow + task model, hybrid deployment | medium | missing |
| `data-pipeline/references/spark.md` | `data-pipeline` | Spark application patterns, partitioning, perf | medium | missing |
| `data-pipeline/references/beam-flink.md` | `data-pipeline` | Streaming with Apache Beam / Flink | low | missing |
| `data-pipeline/references/kafka-streams.md` | `data-pipeline` | Stream processing with Kafka Streams | medium | missing |

### Data — quality + governance

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `data-quality/references/dbt-tests.md` | `data-quality` | dbt-native tests, custom generic tests | medium | missing |
| `data-quality/references/soda.md` | `data-quality` | Soda Core / Cloud for SQL-based quality | low | missing |
| `data-governance/references/datahub.md` | `data-governance` | DataHub catalog + lineage | low | missing |
| `data-governance/references/collibra.md` | `data-governance` | Collibra DG (enterprise) | low | missing |
| `data-governance/references/unity-catalog.md` | `data-governance` | Databricks Unity Catalog | medium | missing |
| `data-governance/references/purview.md` | `data-governance` | Microsoft Purview | low | missing |

### Data — warehouse engines

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `data-warehouse-modeling/references/bigquery.md` | `data-warehouse-modeling` | BigQuery: partitioning, clustering, cost control | medium (GCP) | missing |
| `data-warehouse-modeling/references/snowflake.md` | `data-warehouse-modeling` | Snowflake: clustering keys, warehouses, RBAC | medium | missing |
| `data-warehouse-modeling/references/redshift.md` | `data-warehouse-modeling` | Redshift: distkey/sortkey, vacuum, cluster sizing | medium (AWS) | missing |
| `data-warehouse-modeling/references/synapse.md` | `data-warehouse-modeling` | Azure Synapse: dedicated SQL pools, distribution | low (Azure) | missing |
| `data-warehouse-modeling/references/databricks-sql.md` | `data-warehouse-modeling` | Databricks SQL warehouses on Lakehouse | medium | missing |

### Deploy / release

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `deploy-release/references/aws-codedeploy.md` | `deploy-release` | CodeDeploy: appspec, lifecycle hooks | low (AWS) | missing |
| `deploy-release/references/feature-flags.md` | `deploy-release` | LaunchDarkly/Unleash/OpenFeature; flag lifecycle | medium | missing |

### LLM eval / safety / cost

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `evaluation-engineering/references/langsmith.md` | `evaluation-engineering` | LangChain LangSmith: traces, datasets, eval | medium | missing |
| `evaluation-engineering/references/braintrust.md` | `evaluation-engineering` | Braintrust eval platform | low | missing |
| `evaluation-engineering/references/deepeval.md` | `evaluation-engineering` | DeepEval (Confident AI) framework | low | missing |
| `evaluation-engineering/references/inspect-ai.md` | `evaluation-engineering` | UK AISI Inspect — research-grade eval | low | missing |
| `llm-safety/references/llama-guard.md` | `llm-safety` | Meta Llama Guard input/output classifier | medium | missing |
| `llm-safety/references/nemo-guardrails.md` | `llm-safety` | NVIDIA NeMo Guardrails DSL | medium | missing |
| `llm-safety/references/guardrails-ai.md` | `llm-safety` | Guardrails AI (Python framework) | medium | missing |
| `llm-safety/references/lakera.md` | `llm-safety` | Lakera Guard managed safety | low | missing |
| `llm-cost-optimization/references/litellm.md` | `llm-cost-optimization` | LiteLLM multi-provider gateway | medium | missing |
| `llm-cost-optimization/references/portkey.md` | `llm-cost-optimization` | Portkey managed gateway | low | missing |
| `llm-cost-optimization/references/helicone.md` | `llm-cost-optimization` | Helicone observability + caching | low | missing |

### ML — feature stores

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `ml-feature-engineering/references/tecton.md` | `ml-feature-engineering` | Tecton managed feature store | low | missing |
| `ml-feature-engineering/references/vertex-fs.md` | `ml-feature-engineering` | Vertex AI Feature Store | medium (GCP) | missing |
| `ml-feature-engineering/references/databricks-fs.md` | `ml-feature-engineering` | Databricks Feature Store | medium | missing |
| `ml-feature-engineering/references/sagemaker-fs.md` | `ml-feature-engineering` | SageMaker Feature Store | medium (AWS) | missing |

### ML — monitoring

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `ml-monitoring-drift/references/whylabs.md` | `ml-monitoring-drift` | WhyLabs managed observability | low | missing |
| `ml-monitoring-drift/references/arize.md` | `ml-monitoring-drift` | Arize AI managed monitoring | low | missing |
| `ml-monitoring-drift/references/vertex-model-monitoring.md` | `ml-monitoring-drift` | Vertex Model Monitoring (GCP) | medium (GCP) | missing |

### ML — serving

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `ml-serving-deployment/references/sagemaker.md` | `ml-serving-deployment` | SageMaker endpoints, MMEs, async | medium (AWS) | missing |
| `ml-serving-deployment/references/vertex-ai.md` | `ml-serving-deployment` | Vertex AI prediction (GCP) | medium (GCP) | missing |
| `ml-serving-deployment/references/azure-ml.md` | `ml-serving-deployment` | Azure ML endpoints | medium (Azure) | missing |
| `ml-serving-deployment/references/triton.md` | `ml-serving-deployment` | NVIDIA Triton Inference Server | medium | missing |
| `ml-serving-deployment/references/bentoml.md` | `ml-serving-deployment` | BentoML packaging + serving | low | missing |
| `ml-serving-deployment/references/ray-serve.md` | `ml-serving-deployment` | Ray Serve scaling | low | missing |

### ML — training tracking

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `ml-training-evaluation/references/wandb.md` | `ml-training-evaluation` | Weights & Biases experiment tracking | medium | missing |
| `ml-training-evaluation/references/vertex-experiments.md` | `ml-training-evaluation` | Vertex AI Experiments | low | missing |
| `ml-training-evaluation/references/sagemaker-experiments.md` | `ml-training-evaluation` | SageMaker Experiments | low | missing |
| `ml-training-evaluation/references/comet.md` | `ml-training-evaluation` | Comet ML tracking | low | missing |

### Observability

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `observability/references/loki.md` | `observability` | Grafana Loki logs | medium | missing |
| `observability/references/tempo.md` | `observability` | Grafana Tempo traces | medium | missing |
| `observability/references/datadog.md` | `observability` | Datadog managed observability | medium | missing |
| `observability/references/cloud-native.md` | `observability` | CNCF observability landscape overview | low | missing |

### Performance testing

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `performance-testing/references/gatling.md` | `performance-testing` | Gatling load testing (Scala/JVM) | low | missing |
| `performance-testing/references/locust.md` | `performance-testing` | Locust load testing (Python) | medium | missing |

### Per-language standards variants

`code-review` and `secure-coding` previously cited own-directory `java-spring.md` / `node-ts.md` / `python.md` / `web-frontend.md` files that never existed; both SKILL.md files now cite `../engineering-standards/references/<file>.md` directly (all four now shipping — see Shipping table), so there is nothing left missing for those two skills in this category.

`testing-strategy` cites genuinely distinct, still-missing testing-framework references (not a redirect — these need real test-framework-specific content):

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `testing-strategy/references/java-junit5.md` | `testing-strategy` | JUnit 5 + AssertJ + Testcontainers patterns | medium | missing |
| `testing-strategy/references/node-vitest.md` | `testing-strategy` | Vitest + supertest patterns | medium | missing |
| `testing-strategy/references/python-pytest.md` | `testing-strategy` | pytest + fixtures + parametrize | medium | missing |

### RAG — vector stores

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `rag-design/references/qdrant.md` | `rag-design` | Qdrant: collections, payload, filtering | high (self-host) | missing |
| `rag-design/references/weaviate.md` | `rag-design` | Weaviate: schema, modules | medium | missing |
| `rag-design/references/pinecone.md` | `rag-design` | Pinecone managed vector DB | medium | missing |
| `rag-design/references/vespa.md` | `rag-design` | Vespa large-scale + complex ranking | low | missing |
| `rag-design/references/elasticsearch.md` | `rag-design` | Elasticsearch dense_vector + hybrid | medium | missing |

### Secrets

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `secrets-config/references/azure-key-vault.md` | `secrets-config` | Azure Key Vault | medium (Azure) | missing |
| `secrets-config/references/gcp-secret-manager.md` | `secrets-config` | GCP Secret Manager | medium (GCP) | missing |

### Stack — backend frameworks

| File | Cited by | Description | Priority | Status |
|---|---|---|---|---|
| `stack-java-spring/references/quarkus.md` | `stack-java-spring` | Quarkus (alternative to Spring Boot) | low | missing |
| `stack-node-ts/references/nestjs.md` | `stack-node-ts` | NestJS (opinionated framework) | medium | missing |
| `stack-python/references/django.md` | `stack-python` | Django (web framework + ORM) | medium | missing |
| `stack-python/references/flask.md` | `stack-python` | Flask (micro framework) | low | missing |

---

## How to grow this list

When you write a missing reference:

1. Move its row from a `## Missing` section to the `## Shipping` section.
2. Update the `Status` cell to `shipping`.
3. Update the totals at the top of this file.
4. Validate that the SKILL that cites it can actually find it (`bash scripts/validate-skills.sh`).

When you discover a new reference need:

1. Add its row to the appropriate `## Missing` section (or create a new category).
2. Add the reference filename to the citing SKILL's `references:` frontmatter field.
3. Don't write the content yet — keep it as "missing" until a real project needs it.

This keeps the inventory honest: never aspirational citations without a tracked TODO; never missing references without visibility.

## Missing — untracked citations reconciled 2026-07-09

| Reference | Cited by | Priority | Status | Notes |
|---|---|---|---|---|
| `adaptive-model-routing/references/llm-cost-optimization.md` | adaptive-model-routing | low | missing | Likely should cite the llm-cost-optimization SKILL instead of a reference file |
| `factory-evaluation/references/factory-metrics-catalog.md` | factory-evaluation | medium | missing | Metrics catalog backing the factory scorecard |
| `stack-flutter/references/riverpod.md` | stack-flutter | medium | missing | State management reference |
| `stack-flutter/references/streaming-voice.md` | stack-flutter | low | missing | Streaming/voice UI patterns |
| `stack-flutter/references/senior-first-ui.md` | stack-flutter | low | missing | Accessibility-first UI patterns |
| `stack-node-ts/references/nestjs.md` | stack-node-ts | medium | missing | Framework variant reference |
| `stack-java-spring/references/quarkus.md` | stack-java-spring | low | missing | Framework variant reference |
