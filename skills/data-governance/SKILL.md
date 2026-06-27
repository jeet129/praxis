---
name: data-governance
description: Lineage, cataloging, classification, access control, retention, PII handling at the data layer. The data-side enforcement of what `compliance-privacy` declares. Data Engineer owns; Security Reviewer audits; Tech Writer maintains the catalog as living documentation. Activated on engagements with non-trivial data workloads + compliance requirements (most regulated SaaS has both). Use whenever new data sources are being added, when data classification is being established, when responding to data-subject requests, or when an auditor asks "where does this data come from / who can see it / how long do we keep it?"
capability: data
domain: data
state: active
dependencies:
 - data-pipeline
 - data-warehouse-modeling
 - compliance-privacy
 - authn-authz
triggers:
 - "adding a new data source"
 - "establishing data classification taxonomy"
 - "responding to a data-subject request (GDPR / CCPA)"
 - "auditor asks for lineage / access / retention evidence"
 - "designing access control at the data layer"
 - "setting up data catalog (DataHub / Collibra / Unity Catalog / Purview)"
outputs:
 - data catalog entries (per table + per dataset)
 - lineage graph (data flow source → consumer)
 - classification labels (per column / per dataset)
 - access policies (who can read what)
 - retention enforcement (per dataset)
 - data-subject request runbooks (specific to data layer; pair with compliance-privacy)
consumers:
 - data-engineer (primary author + executor)
 - security-reviewer (audits access posture)
 - compliance-privacy (uses data-layer evidence for control-coverage matrix)
 - tech-writer (maintains the catalog narrative)
 - solution-architect (consumes for data-architecture decisions)
references:
 - datahub.md
 - collibra.md
 - unity-catalog.md
 - purview.md
---

# Data Governance

The discipline that makes data discoverable, traceable, and protected. Without it, an auditor asks "where did this number come from?" and the team spends a week investigating. With it, the catalog + lineage + access policies answer in minutes — and consumers can find the data they need without bothering the Data Engineer.

The principle: **data is governed continuously; documentation is generated, not written separately; access is least-privilege by default.**

## When this skill fires

- A new data source is being added — register in the catalog with classification + lineage.
- Data classification taxonomy is being established (paired with `compliance-privacy`).
- A data-subject request (GDPR / CCPA) needs the data-layer answer ("where is this person's data?").
- An auditor asks for lineage / access / retention evidence.
- Access control at the data layer is being designed (warehouse / lake permissions).
- A data catalog is being adopted (DataHub / Collibra / Unity Catalog / Purview).

## The four pillars

### 1. Catalog — what data exists

Every dataset (raw source, intermediate, mart, model output) is in the catalog:

- **Name + description** — human-readable; what it represents.
- **Owner** — the team or person responsible.
- **Schema** — columns + types + nullability + classification per column.
- **Source** — where the data came from (other dataset, upstream system, external API).
- **Update cadence** — daily / streaming / event-triggered.
- **Consumers** — downstream tables, dashboards, ML pipelines, exports.
- **Tags** — domain, sensitivity, status (production / experimental / deprecated).
- **Documentation links** — schema docs, runbooks, dashboards.

Tools (per refs):

- **DataHub** — open-source; broad metadata model; LinkedIn-originated.
- **Collibra** — enterprise; rich governance workflow.
- **Unity Catalog** (Databricks) — tight Databricks integration.
- **Purview** (Azure) — unified across Azure data services.
- **Open-source alternatives**: OpenMetadata, Amundsen, Marquez.

Default for new projects: **DataHub** (broad and open) or **Unity Catalog** (if on Databricks).

### 2. Lineage — how data flows

Per dataset, the full lineage:

- **Upstream**: which sources contributed (column-level when possible).
- **Downstream**: which datasets consume (which dashboards, models, exports).
- **Transformations**: what dbt models or pipelines transformed it.

```
sources.orders_raw
 → stg_orders (staging)
 → int_orders_enriched (intermediate)
 → fct_orders (mart, core)
 → finance__monthly_revenue (mart, domain)
 → dashboard: Executive Revenue
 → ml_feature: customer_ltv
```

Lineage is captured automatically by modern tools:
- dbt manifests → lineage at table + column level.
- OpenLineage standard — orchestrator-emitted lineage events.
- Pipeline tooling (Airflow, Dagster, Prefect) emits OpenLineage events.

Manual lineage gets stale; **prefer auto-extracted lineage** wherever possible.

### 3. Classification — what data is sensitive

Paired with `compliance-privacy`'s data classification taxonomy:

| Class | Examples | Catalog tag |
|---|---|---|
| Public | Product catalog | `pii:none, sensitivity:public` |
| Internal | Aggregated metrics | `pii:none, sensitivity:internal` |
| Confidential | Customer info | `pii:none, sensitivity:confidential` |
| Restricted (PII) | Name, email, phone, address | `pii:true, sensitivity:restricted` |
| Highly Restricted | PHI, PCI cardholder data, SSN | `pii:true, sensitivity:highly_restricted, regime:hipaa|pci` |

Classification at the **column level** (not just table level). One table may have public, confidential, and PII columns mixed.

Tooling enforces consequences of classification:
- **Encryption at rest** — required for restricted+ classes.
- **Access control** — restrictive policies for restricted+ classes.
- **Audit logging** — every access to restricted+ classes logged.
- **Masking / tokenization** — PII columns optionally masked in non-prod environments.
- **Retention** — restricted classes have shorter retention windows by default.

### 4. Access control

Who can see what. Per `authn-authz`'s patterns applied to the data layer:

- **Role-based access** — analyst role vs PII-cleared role vs admin.
- **Attribute-based** — region-based access (EU analysts see EU data only); tenancy-based.
- **Column-level masking** — sensitive columns hidden / hashed for unauthorized roles.
- **Row-level security** — analysts see only their assigned data subsets.

Warehouse-specific:
- **Snowflake** — dynamic data masking + row access policies.
- **BigQuery** — column-level access controls + row access policies.
- **Databricks Unity Catalog** — fine-grained access at table / column / row level.
- **Redshift** — column-level grants + RLS.
- **Synapse** — SQL Server-style permissions + dynamic data masking.

Per `multi-tenancy`'s discipline: every cross-tenant query includes the tenant scope; defense-in-depth via row-level security.

## Retention

Per `compliance-privacy`'s policy, enforced at the data layer:

- **Lifecycle policies** on warehouse tables — TTL on streaming tables; partition expiry on partitioned tables.
- **Soft-delete** patterns for restricted data — mark as deleted; hard-delete after grace period.
- **Backup retention** — separate policy; longer for most cases; but PII still purged per regime.

Retention is **automatic**. Manual retention is not retention.

## Data-subject requests (data-layer side)

Per `compliance-privacy`'s DSR runbooks, the data-layer specifics:

```markdown
# Data Layer — GDPR Right to Erasure

## Locate the subject's data
- Query the catalog for tables tagged `pii:true` that reference `customer_id` (or other PK).
- Lineage graph identifies derived tables.

## Erase in the warehouse
- For each PII column: replace with `[ERASED]` marker; preserve customer_id for FK integrity.
- For derived aggregates: re-run with the erased data; the aggregate naturally doesn't include the subject anymore.
- For ML features: remove the subject's features; flag affected model versions for re-training consideration.
- For backups: per backup retention — purge from active backups; document retention-window erasure plan.

## Verify
- Query the catalog for any tables still referencing the subject's PII.
- Run the dedicated verification script.

## Document
- Record the action in `.project/operational/dsr-log.md` (cross-referenced with compliance-privacy).
```

The catalog + lineage make this answerable in minutes vs. days.

## Outputs

| Output | Location |
|---|---|
| Data catalog | external tool (DataHub / Unity / etc.); seed config in repo |
| Lineage graph | auto-generated; visible in catalog |
| Classification labels | column-level metadata in catalog + dbt schema.yml |
| Access policies | warehouse-specific GRANTs + masking policies via IaC |
| Retention enforcement | configured in warehouse + lifecycle policies |
| DSR runbook (data-layer) | `.project/operational/runbooks/dsr-data-layer.md` |
| Governance config | `.project/procedural/data-governance.md` |

## Mode handling (G/B)

**Greenfield.** Catalog from day one — every new dataset registered, classified, lineage-tracked.

**Brownfield.** Audit existing data posture. Common findings: no catalog (knowledge in people's heads); PII columns unclassified; no access controls beyond "everyone can SELECT *"; retention policies on paper only. Prioritize highest-classification data first.

## What this skill does not do

- Build the pipelines or models — that's `data-pipeline` + `data-warehouse-modeling`.
- Test data correctness — that's `data-quality`.
- Compliance attestation across the broader system — that's `compliance-privacy` (this skill provides the data-layer evidence).
- Identity provider integration — that's `authn-authz`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Lineage is a nice-to-have." | Lineage answers "where did this number come from?" — critical for debugging, audits, regulator questions. |
| "Catalog is for analysts." | Catalog is also for engineers, ML, compliance. One catalog; many consumers. |
| "PII is well-known and obvious." | New columns get added; PII classification drifts. Re-classify periodically; tag at write time. |
| "DSR procedures are theoretical." | They become real (and fast) when a regulator asks. Exercise them. |
| "Retention policies are storage's problem." | They're a regulatory + architectural concern. Engineering enforces them. |
| "Owners are obvious — whoever produced the data." | Ownership transitions; produces vs maintains vs decides. Make it explicit. |

## Verification

You are done when:

- [ ] Data catalog covers production data assets (tables, topics, streams, files).
- [ ] Lineage graph generated (upstream → downstream).
- [ ] PII / PHI / regulated data classified; tags propagate through lineage.
- [ ] Ownership documented per dataset (producer / steward / consumer).
- [ ] Retention policy documented + enforced per data class.
- [ ] DSR runbook exists + last-exercised within target cadence.
- [ ] Access controls audited; access logs sent to SIEM.
- [ ] Quality SLAs per dataset (where applicable) tracked.

Evidence to check:
- A specific column's lineage can be traced upstream + downstream in minutes.
- A DSR can be fulfilled within regulated SLA.

## Anti-patterns

- No catalog ("ask Bob; he knows").
- Manual lineage (gets stale).
- PII columns unclassified (no special protection).
- "Everyone can SELECT *" access posture.
- Retention policy documented but not enforced.
- DSR responses ad-hoc per request (no catalog → no fast answer).
- Backups omitted from retention thinking (PII lives in backups too).
- Column-level classification skipped (only table-level → false confidence).
- Catalog stale because manual updates lag (use auto-extraction).
- Lineage missing column-level detail ("data went somewhere").
