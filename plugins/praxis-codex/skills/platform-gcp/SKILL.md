---
name: platform-gcp
description: "GCP cloud-specific reference pack. Managed-service catalog (GKE / Cloud Run / Cloud SQL / Spanner / Bigtable / BigQuery / Cloud Storage / Pub/Sub / Cloud Tasks / Workflows / Cloud Functions), networking (VPC / Cloud Load Balancing / Cloud Armor / Private Service Connect), identity (Cloud IAM / Workload Identity / Secret Manager), observability (Cloud Logging / Cloud Monitoring / Cloud Trace / Error Reporting), DR patterns (multi-zone default; multi-region for global services), cost levers (Committed Use Discounts / Spot VMs / Sustained Use Discounts), GCP Architecture Framework alignment. The deep reference library that iac, deploy-release, reliability-dr, capacity-resource-estimation, cost-finops, and observability consult for GCP-specific implementation. Selected when GCP is the project's cloud per governance.yaml."
---

# Platform — GCP

<!-- praxis:metadata:begin -->
```yaml
capability: platform
domain: infra
state: active
dependencies:
  - iac
  - platform-k8s
  - secrets-config
  - observability
triggers:
  - "GCP is the project's cloud and deployment patterns are being designed"
  - "selecting GCP managed services for a workload"
  - "wiring GCP-native observability (Cloud Operations Suite)"
  - "designing multi-zone / multi-region topology"
  - "applying GCP Architecture Framework"
outputs:
  - managed-service decisions per workload
  - VPC topology
  - Cloud IAM model with Workload Identity
  - Cloud Operations Suite setup
  - DR plan with GCP primitives (regional services, multi-region Spanner, GCS dual-region)
  - cost levers applied
consumers:
  - platform-sre (primary author for GCP deployments)
  - iac (Terraform / Pulumi GCP provider)
  - deploy-release (GCP-specific deploy patterns)
  - reliability-dr (multi-zone / multi-region patterns)
  - cost-finops (GCP Billing + tagging via labels)
references: []
```
<!-- praxis:metadata:end -->

Deep reference for GCP-specific patterns. Similar structure to AWS / Azure packs: managed services, networking, identity, DR primitives, cost levers, Architecture Framework alignment.

GCP's strengths: data + ML services (BigQuery, Vertex AI); global services as defaults (Cloud Storage, Cloud Load Balancing); Spanner for global SQL; strong Kubernetes pedigree (Google created K8s); generous free tiers for small workloads.

## Compute options

| Service | Sweet spot |
|---|---|
| **GKE** | K8s on GCP. Two modes — Standard (you manage node pools) or Autopilot (Google manages). Autopilot for serverless K8s without losing K8s semantics. |
| **Cloud Run** | Serverless containers; HTTP-triggered or job-mode; scales to zero. Default for stateless services without K8s overhead. |
| **App Engine Standard / Flex** | Legacy PaaS. New projects: Cloud Run. |
| **Cloud Functions (2nd gen)** | Event-driven serverless functions. Cloud Functions 2nd gen runs on Cloud Run infrastructure. |
| **Compute Engine** | VMs. For specific workloads needing full instance control. |

Default for new projects: **GKE Autopilot** (per K8s-first cloud decision) or **Cloud Run** for individual services without K8s.

### GKE specifics

- **GKE Autopilot** — fully-managed; per-pod billing; recommended for most new projects.
- **GKE Standard** — node pool control; required for some niche cases (custom kernel, GPU specialization).
- **Workload Identity** — maps K8s ServiceAccount → Google Service Account → Cloud IAM. Best-in-class workload identity.
- **VPC-native clusters** — pod IPs from VPC ranges; default for new clusters.
- **GKE Gateway Controller** — Gateway API support; provisions Cloud Load Balancing.
- **Filestore / Persistent Disk CSI** — for persistent volumes.
- **GKE Backup** — managed backup/restore for K8s state.

### Cloud Run specifics

- **Scales to zero** by default; first-request cold start. Min instances > 0 for warm.
- **Concurrency** per instance (default 80); tune per workload.
- **Cloud Run Jobs** — for batch / scheduled tasks (alternative to Cloud Scheduler + Cloud Tasks).
- **Cloud Run on GKE** (Anthos) — runs Cloud Run abstraction on your own GKE.

## Data services

| Service | Sweet spot |
|---|---|
| **Cloud SQL (Postgres / MySQL / SQL Server)** | Default for managed relational. HA configurations; cross-region replicas. |
| **Cloud Spanner** | Globally-distributed strongly-consistent SQL. Expensive but unique; no other vendor matches this. For systems that need it; rarely justified for typical SaaS. |
| **AlloyDB** | Postgres-compatible high-performance OLTP. Newer; vendor-specific extensions. |
| **Cloud Bigtable** | Wide-column at extreme scale (Cassandra-like). |
| **Firestore** | Document database; tight Firebase integration; eventually-consistent global access. |
| **Memorystore (Redis / Memcached)** | Managed in-memory store. |
| **Cloud Storage** | Object storage. Standard / Nearline / Coldline / Archive. Multi-regional / Dual-regional / Regional locations. |
| **BigQuery** | Analytics warehouse default for data analytics + ML. Serverless; pay-per-query or capacity. |
| **Pub/Sub** | High-throughput pub-sub messaging; at-least-once delivery; ordering keys. |

Default for new transactional data: **Cloud SQL Postgres**. For analytics: **BigQuery**.

## Messaging & event services

| Service | Sweet spot |
|---|---|
| **Pub/Sub** | Default messaging. At-least-once; ordering keys; dead-letter topics. |
| **Cloud Tasks** | Asynchronous task execution with rate limiting + retries. For HTTP-targeted task queues. |
| **Workflows** | Orchestration; YAML-based; integrates with all GCP services. |
| **Eventarc** | Routes events from GCP services + custom sources via CloudEvents. |

## Identity & secrets

| Service | Use |
|---|---|
| **Cloud IAM** | All authorization. Roles + policies + conditions. Resource-level granularity. |
| **Cloud Identity / Workspace** | Workforce identity. Integrates with SSO providers. |
| **Workload Identity** | GKE ServiceAccount → Google Service Account binding. Best-in-class. |
| **Identity-Aware Proxy (IAP)** | App-layer auth gate for HTTP + TCP services. |
| **Identity Platform** | Customer identity (B2C/B2B); built on Firebase Auth. |
| **Secret Manager** | Per `secrets-config`'s gcp-secret-manager reference. Versioned; access logged. |
| **Cloud KMS** | Customer-managed encryption keys. CMEK supported broadly. |

IAM discipline:

- **Per-workload Google Service Account** with Workload Identity binding.
- **No service account keys** (long-lived) — use Workload Identity Federation for cross-cloud or external identities.
- **No `roles/owner` for service accounts** — use principle of least privilege; predefined roles or custom roles.
- **Organization policies** for guardrails (no public IPs; required CMEK; etc.).

## Networking

| Service | Use |
|---|---|
| **VPC** | Default network isolation. Global VPC scope — subnets in multiple regions share one VPC. |
| **Subnets** | Per-region; can expand without disruption. |
| **Cloud Load Balancing** | Global anycast load balancing — single IP across regions. HTTP(S), TCP, SSL Proxy variants. |
| **Cloud Armor** | WAF + DDoS protection at the edge. Managed rules + custom. |
| **Cloud CDN** | CDN built into Cloud Load Balancing. |
| **Private Service Connect** | Private access to Google services and SaaS partners. |
| **VPC Peering** | Two-VPC connectivity. |
| **Cloud Interconnect / VPN** | On-prem connectivity. |
| **Service Mesh / Anthos** | Managed Istio + multi-cluster + multi-cloud. |

GCP's global load balancing is notable — single anycast IP routes globally with regional health-check awareness. Simpler multi-region than other clouds.

## Observability — Cloud Operations Suite

| Service | Use |
|---|---|
| **Cloud Logging** | Default log aggregation. Logs Explorer for queries. Log-based metrics for derived signals. |
| **Cloud Monitoring** | Metrics + alerts. Alerting policies; notification channels. |
| **Cloud Trace** | Distributed tracing. OpenTelemetry-compatible. |
| **Error Reporting** | Aggregated error tracking with stack traces + occurrence counts. |
| **Cloud Profiler** | Production code profiler (CPU + heap). |
| **Cloud Debugger** | (deprecated — use logging + tracing). |
| **Managed Service for Prometheus** | Managed Prometheus-compatible monitoring. |
| **Managed Service for Grafana** | Managed Grafana. |

For OTel-native: GCP's OTel exporters are mature; **Managed Service for Prometheus** + Cloud Trace gives an OTel-friendly stack.

## DR patterns

Default topology:

- **Regional services** — most managed services replicate across zones in a region automatically (Cloud SQL HA, GKE regional clusters, Cloud Storage Regional buckets).
- **Multi-regional Cloud Storage** — dual-region for georedundancy; multi-region for global.
- **Cloud Spanner** — multi-region configurations for global SQL with strong consistency.
- **Cross-region replicas (Cloud SQL)** — async replication for DR.
- **Global Load Balancing** — automatic regional failover via health checks.
- **Cloud DNS** — health-check-based routing.

Backups:

- **Cloud SQL** — automated backups + PITR.
- **GCS** — versioning + object lifecycle.
- **Spanner** — backup + import operations; PITR.
- **Persistent Disk** — snapshots scheduled.
- **GKE Backup** — managed K8s state backup.

## Cost levers

| Lever | Saves |
|---|---|
| **Committed Use Discounts** | 30-70% off Compute Engine / Cloud SQL / Spanner for 1- or 3-year commitment. Flexible across instance families. |
| **Sustained Use Discounts** | Automatic up to 30% off for sustained Compute Engine usage. No commitment needed. |
| **Spot VMs** | Up to 91% off Compute Engine for interruption-tolerant workloads. GKE supports spot node pools. |
| **Cloud Run scales to zero** | No cost when idle. Pay-per-100ms-of-execution. |
| **GKE Autopilot per-pod billing** | No node-overhead cost; pay only for pod resources. |
| **GCS lifecycle** | Standard → Nearline → Coldline → Archive. |
| **BigQuery slots vs on-demand** | On-demand for variable workloads; capacity (slots) for predictable. |
| **Network tier (Premium vs Standard)** | Standard tier ~70% cheaper for cold storage and inter-region transfer. |

## GCP Architecture Framework alignment

Per pillar:

- **Operational Excellence** — IaC (Terraform / Pulumi); GitOps; Cloud Build for CI; Cloud Deploy for CD.
- **Security & Compliance** — Workload Identity; CMEK via KMS; Cloud Armor on public endpoints; Security Command Center for posture.
- **Reliability** — Regional services by default; multi-region for global services; tested DR.
- **Cost Optimization** — CUDs + Sustained Use Discounts + Spot; billing alerts; budget rules.
- **Performance Efficiency** — Global Load Balancing + Cloud CDN; Spanner / BigQuery for scale.
- **Sustainability** — GCP's carbon-neutral commitment; region carbon-data informs placement decisions.

## Common patterns

### Tier-1 production SaaS

```
- VPC global with regional subnets.
- GKE Autopilot (regional cluster) OR Cloud Run for stateless services.
- Cloud SQL Postgres with HA (regional) + cross-region read replicas for DR.
- Memorystore Redis (Standard tier).
- Cloud Storage (Regional bucket; dual-regional for important data; lifecycle to Coldline).
- Global Load Balancing + Cloud Armor + Cloud CDN for public surface.
- Identity Platform for customer auth; Cloud Identity for workforce.
- Secret Manager + Workload Identity for access.
- Cloud Operations Suite (Logging, Monitoring, Trace, Error Reporting); Managed Prometheus + Grafana.
- Billing budgets + labels for showback; quarterly CUD purchases.
- DR: cross-region replicas + dual-region GCS + global LB.
```

### Data/ML-heavy workload

```
- BigQuery for analytics (capacity slots for predictable workloads).
- Vertex AI for ML training + serving.
- Pub/Sub + Dataflow for streaming ingest.
- Cloud Storage Data Lake.
- Spanner for transactional global state when justified.
- BigQuery ML for in-warehouse ML where appropriate.
```

### Global multi-region

```
- Cloud Spanner multi-region for global strongly-consistent SQL.
- Cloud Storage multi-region for global asset distribution.
- Global Load Balancing with regional backends.
- Cloud Run Anthos or GKE multi-cluster across regions.
- Cross-region async replication for non-Spanner data.
```

## Outputs

| Output | Location |
|---|---|
| GCP service decisions per workload | `.project/decision/` |
| VPC + connectivity topology | `.project/operational/network-topology.md` |
| Cloud IAM + Workload Identity model | `.project/operational/identity-model.md` |
| Cloud Operations Suite setup | provisioned via IaC; documented in `.project/operational/observability.md` |
| DR plan with GCP primitives | `.project/operational/dr-plan-{service}.md` |
| Cost levers applied | inline in `.project/operational/cost-model.md` |

## Mode handling (G/B)

**Greenfield.** Apply Architecture Framework; default to Autopilot or Cloud Run; document service decisions.

**Brownfield.** Audit existing GCP posture. Common findings: service account keys instead of Workload Identity; no Organization Policies; Cloud Logging retention indefinite. Address by severity.

## What this skill does not do

- Replace `iac` — `iac` discipline; this is GCP-specific.
- Replace `platform-k8s` — that covers GKE workload manifests; this covers GKE configuration + surrounding GCP services.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Project-per-environment is enough governance." | Org + folders + IAM inheritance need explicit design. |
| "Workload Identity is optional." | Workload Identity binds K8s SAs to GCP SAs; avoid long-lived service-account keys. |
| "Cloud SQL defaults are fine." | High availability, automated backups, point-in-time recovery, maintenance windows — all need explicit choices. |
| "GCS lifecycle policies are optional." | Without lifecycle, storage cost compounds. Set tier transitions + deletion. |
| "VPC Service Controls add latency." | VPC SC reduces exfiltration risk for regulated workloads. Trade-off, not always-no. |
| "Cloud Logging captures everything." | Aggregation + retention + sinks + alerting still need design. |

## Verification

You are done when:

- [ ] Org + folder + project hierarchy documented.
- [ ] Org policies enforce standards (uniform bucket access, OS Login, region).
- [ ] IAM follows least-privilege; service account keys avoided where Workload Identity works.
- [ ] VPC + Private Google Access + Cloud NAT designed.
- [ ] Cloud SQL: HA + backups + PITR + maintenance window set.
- [ ] GCS: lifecycle policies, uniform access, versioning, retention as needed.
- [ ] Cloud Logging + Monitoring routed; alerts configured.
- [ ] Security Command Center enabled; findings triaged.
- [ ] Cost labels + budget alerts.
- [ ] Region selection documented.

Evidence to check:
- SCC severity findings reviewed.
- Workload Identity usage covers > 90% of services.

## Anti-patterns

- Service account keys (long-lived) instead of Workload Identity.
- `roles/owner` on service accounts.
- Single-zone production data services.
- Cloud SQL without HA in production.
- Cloud Storage Standard tier for cold data without lifecycle.
- BigQuery on-demand pricing for high-volume predictable workloads (use slots / capacity).
- Global Load Balancing's anycast IP not used when multi-region (gives up GCP's network advantage).
- Cloud Logging retention indefinite (cost).
- No labels for cost attribution.
- CUDs not purchased for predictable steady-state usage (leaves money on the table).
