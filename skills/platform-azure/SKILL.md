---
name: platform-azure
description: "Azure cloud-specific reference pack. Managed-service catalog (AKS / Azure SQL / Cosmos DB / Service Bus / Event Grid / App Service / Functions / Container Apps / API Management), networking (VNet / Application Gateway / Front Door / Private Link / VPN), identity (Entra ID / Managed Identity / Key Vault), observability (Azure Monitor / Application Insights / Log Analytics), DR patterns (Availability Zones default; paired regions for DR), cost levers (Reservations / Spot VMs / Hybrid Benefit), Azure Well-Architected Framework alignment. The deep reference library that iac, deploy-release, reliability-dr, capacity-resource-estimation, cost-finops, and observability consult for Azure-specific implementation. Selected when Azure is the project's cloud per governance.yaml."
---

# Platform — Azure

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
  - "Azure is the project's cloud and deployment patterns are being designed"
  - "selecting Azure managed services for a workload"
  - "wiring Azure-native observability (Application Insights / Log Analytics)"
  - "designing AZ / paired-region topology"
  - "applying Azure Well-Architected Framework"
outputs:
  - managed-service decisions per workload
  - VNet topology + private connectivity
  - Entra ID / Managed Identity model
  - Application Insights + Log Analytics workspace
  - DR plan with Azure primitives (Geo-Redundant Storage, paired regions, Azure Site Recovery)
  - cost levers applied
consumers:
  - platform-sre (primary author for Azure deployments)
  - iac (Terraform / Pulumi / Bicep Azure provider)
  - deploy-release (Azure-specific deploy patterns)
  - reliability-dr (AZ / paired-region patterns)
  - cost-finops (Azure Cost Management + tagging)
references: []
```
<!-- praxis:metadata:end -->

Deep reference for Azure-specific patterns. Like the AWS pack, this covers Azure managed services, networking, identity, DR primitives, cost levers, and Azure Well-Architected Framework alignment.

Azure's strengths: enterprise / Microsoft-shop integration; hybrid scenarios; Entra ID for unified identity; strong compliance certifications. Azure-native services tend to integrate well with each other; cross-cloud integration is often via standard protocols.

## Compute options

| Service | Sweet spot |
|---|---|
| **AKS** | K8s on Azure. Default for stateless services + complex orchestration. Pair with KEDA for event-driven autoscaling. |
| **Azure Container Apps** | Serverless containers; Dapr-integrated; KEDA-based autoscaling. Less operational overhead than AKS; great for microservices without full K8s. |
| **Azure Container Instances** | Single-container quick-runs; bursty batch. Not for long-running services. |
| **App Service** | PaaS for web apps. Slot-based deployments; auto-scaling. Good for monoliths and traditional web tiers. |
| **Azure Functions** | Event-driven. Cold start matters; Premium plan for warm instances. |
| **Virtual Machine Scale Sets** | Legacy or specific workloads. Spot VMs supported. |

Default for new projects: **AKS** (per K8s-first cloud decision) or **Container Apps** for microservices without K8s operational burden.

### AKS specifics

- **Managed identity binding** — Workload Identity (replaces deprecated Pod Identity). Per ServiceAccount → managed identity → Azure RBAC.
- **Azure CNI** vs **kubenet** vs **Cilium** — networking modes. Azure CNI Powered by Cilium for modern setups.
- **Application Gateway Ingress Controller** (AGIC) — provisions Application Gateway via Ingress.
- **Azure Disk / Files CSI** — for persistent volumes.
- **KEDA** — built-in support for event-driven autoscaling.

## Data services

| Service | Sweet spot |
|---|---|
| **Azure SQL Database** | Managed SQL Server. Geo-replication; auto-failover groups. |
| **Azure Database for PostgreSQL Flexible Server** | Default for Postgres on Azure. HA configurations. |
| **Cosmos DB** | Global-scale multi-model (document, key-value, graph, column-family). Multi-region active-active. Five consistency models. |
| **Azure Cache for Redis** | Managed Redis. Premium for cluster + persistence. |
| **Azure Blob Storage** | Object storage. Hot/Cool/Cold/Archive tiers. GRS / RA-GRS for redundancy. |
| **Azure Data Lake Storage Gen2** | Hierarchical namespace over Blob Storage. For analytics workloads. |
| **Cognitive Search / Azure AI Search** | Managed search with vector + hybrid retrieval. |
| **Service Bus** | Enterprise messaging; queues + topics + sessions + dead-lettering. |
| **Event Hubs** | High-throughput event ingest. Kafka protocol compatible. |

Default for new transactional data: **Azure Database for PostgreSQL Flexible Server**.

## Messaging & event services

| Service | Sweet spot |
|---|---|
| **Service Bus** | Enterprise queueing + pub/sub. Sessions, dead-lettering, scheduling. Default for async between services. |
| **Event Grid** | Pub/sub for Azure events; CloudEvents-compatible; SaaS integration. |
| **Event Hubs** | High-throughput streaming. Kafka-protocol compatible. |
| **Logic Apps** | Workflow orchestration with broad SaaS connector library. |
| **Durable Functions** | Code-first workflow orchestration. |

## Identity & secrets

| Service | Use |
|---|---|
| **Entra ID (formerly Azure AD)** | All identity. Workforce + customer (via External ID) + service identities. |
| **Managed Identity** | Workload identity for Azure-hosted compute. System-assigned (lifecycle bound to resource) or user-assigned (shareable). |
| **Workload Identity (AKS)** | Maps K8s ServiceAccount → Entra ID identity → Azure RBAC. Replaces Pod Identity. |
| **Azure RBAC** | All authorization at the Azure resource layer. |
| **Key Vault** | Per `secrets-config`'s azure-key-vault reference. Auto-rotation supported. |
| **App Configuration** | Configuration values; tier-aware feature flags. |
| **Managed HSM** | Customer-managed keys with FIPS 140-2 Level 3. |

Identity discipline:

- **No service principals with client secrets for production workloads** — use Managed Identity / Workload Identity.
- **Per-workload Managed Identity** with minimum-privilege RBAC.
- **Conditional Access policies** on workforce identities; MFA always.
- **Entra ID Privileged Identity Management (PIM)** for elevated access.

## Networking

| Service | Use |
|---|---|
| **VNet** | Default network isolation. One VNet per environment per region. |
| **Subnets** | Per tier (app, data, gateway). Network Security Groups (NSGs) for L3/L4 rules. |
| **Application Gateway** | Layer 7 load balancing + WAF + URL routing. Default for HTTP APIs. |
| **Azure Front Door** | Global edge + CDN + WAF + load balancing. For multi-region public surface. |
| **Azure Load Balancer** | Layer 4. For non-HTTP or specific protocols. |
| **Private Link** | Expose / consume services privately; PaaS-to-VNet connectivity. |
| **VNet Peering** | Two-VNet connectivity. |
| **VPN Gateway / ExpressRoute** | On-prem connectivity. |
| **Azure Firewall** | Managed L3-L7 firewall. |
| **DDoS Protection Standard** | Beyond default basic DDoS protection. |

## Observability

| Service | Use |
|---|---|
| **Log Analytics workspace** | Default log + metric store. KQL for queries. Set retention per regime + cost. |
| **Application Insights** | APM for applications. Auto-instrumentation for .NET / Node / Java / Python. |
| **Azure Monitor** | Metrics + alerts. Action groups → email / Slack / PagerDuty / webhook. |
| **Container Insights** | AKS observability with pod-level metrics. |
| **Network Watcher** | Network flow logs + connection troubleshooting. |
| **Microsoft Sentinel** | SIEM built on Log Analytics. |

For OTel-native: **Application Insights OTel exporter** (preview / GA depending on language); standard OpenTelemetry collector deployable in AKS.

## DR patterns

Default topology:

- **Availability Zones** — production default within a region. 3 AZs.
- **Geo-Redundant Storage (GRS / RA-GRS)** — for blob storage; async replication to paired region.
- **Paired regions** — Azure's concept of region pairs (e.g., East US ↔ West US). Used for DR; ordered updates (Azure updates one before the other).
- **Auto-failover Groups (Azure SQL)** — multi-region database failover with read endpoints.
- **Cosmos DB multi-region** — active-active across regions with explicit consistency models.
- **Azure Site Recovery** — for VM-level DR (less relevant for containerized / PaaS workloads).

Backups:

- **Azure Backup** — for VMs, files, SQL, AKS persistent volumes.
- **Azure SQL automated backups** — PITR with 7-35 day retention; long-term retention to Blob.
- **Cosmos DB** — continuous backup mode (PITR) or periodic.
- **Blob Storage** — soft-delete + versioning + immutable storage for compliance.

## Cost levers

| Lever | Saves |
|---|---|
| **Reservations** | 30-65% off compute and managed services for 1- or 3-year commitment. |
| **Spot VMs** | Up to 90% off VMs for interruption-tolerant workloads. AKS supports spot node pools. |
| **Azure Hybrid Benefit** | Use existing Windows Server / SQL Server licenses on Azure. Large saving for Microsoft-shop migrations. |
| **Dev/Test pricing** | Cheaper rates for non-production subscriptions. |
| **Auto-scaling** | App Service / Functions / AKS HPA / VMSS autoscale. |
| **Blob lifecycle** | Hot → Cool → Cold → Archive. |
| **Right-sizing** | Azure Advisor recommendations. |

## Azure Well-Architected Framework alignment

Per pillar, key practices:

- **Reliability** — Multi-AZ; geo-replication for stateful services; tested DR; defensive coding.
- **Security** — Entra ID + Managed Identity; Key Vault for secrets; Defender for Cloud for posture; private endpoints.
- **Cost Optimization** — Reservations + Spot + Hybrid Benefit; Azure Advisor; tag-based showback via Cost Management.
- **Operational Excellence** — IaC (Bicep / Terraform / Pulumi); GitOps via Argo CD / Flux; Azure DevOps or GitHub for CI/CD; Azure Monitor for observability.
- **Performance Efficiency** — Right-size with Advisor; Azure-native caching; CDN via Front Door; Cosmos DB for global-scale data.

## Common patterns

### Tier-1 production SaaS

```
- VNet: 3 AZs, app + data + gateway subnets.
- AKS with Workload Identity (system pool + spot pool).
- PostgreSQL Flexible Server with HA (zone-redundant).
- Azure Cache for Redis (Premium, cluster mode).
- Blob Storage (Standard with lifecycle to Cool/Archive; GRS).
- Application Gateway + WAF + Front Door for public surface.
- Entra ID External ID for customer auth.
- Key Vault for secrets; Workload Identity for access.
- Application Insights + Log Analytics; Azure Monitor alerting.
- Cost Management with budgets + tag policies.
- DR: paired region with read replicas + GRS + auto-failover groups.
```

### Microsoft-shop migration

```
- Hybrid Benefit on Windows Server / SQL Server licenses.
- AKS or App Service for new workloads.
- Entra ID for unified identity (existing AD synced).
- Defender for Cloud for security posture.
- Sentinel for SIEM.
- Cost Management with departmental showback.
```

## Outputs

| Output | Location |
|---|---|
| Azure service decisions per workload | `.project/decision/` |
| VNet + connectivity topology | `.project/operational/network-topology.md` |
| Entra ID + Managed Identity model | `.project/operational/identity-model.md` |
| Application Insights + Log Analytics setup | provisioned via IaC; documented in `.project/operational/observability.md` |
| DR plan with Azure primitives | `.project/operational/dr-plan-{service}.md` |
| Cost levers applied | inline in `.project/operational/cost-model.md` |

## Mode handling (G/B)

**Greenfield.** Apply Well-Architected; default to managed services; document service decisions.

**Brownfield.** Audit existing posture. Common findings: service principals with client secrets (use Managed Identity); GRS not enabled on critical storage; no PITR on databases; broad RBAC; missing Defender. Address by severity.

## What this skill does not do

- Replace `iac` — `iac` discipline; this is Azure-specific.
- Replace `platform-k8s` — that covers AKS workload manifests; this covers AKS configuration + surrounding Azure services.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Subscription-per-environment is enough governance." | Management groups + policy assignments + RBAC inheritance need explicit design. |
| "Service principals are the right identity for everything." | Managed identities are preferred for Azure-native; service principals for federated. Both have their place. |
| "Storage accounts are simple." | Storage account has many tiers, kinds, redundancy options, access modes. Defaults rarely fit. |
| "Azure SQL is just SQL Server." | Azure SQL has DTU vs vCore, serverless options, geo-replication patterns; different cost + perf modes. |
| "Resource locks prevent all accidents." | Locks prevent delete + read-only changes; don't prevent in-tenant misconfiguration. Use plus policy. |
| "Network Watcher = observability." | Network Watcher diagnoses; Monitor + Log Analytics + App Insights are the observability platform. |

## Verification

You are done when:

- [ ] Tenant + management group + subscription hierarchy documented.
- [ ] Azure Policy assignments cover org standards (encryption, tagging, region).
- [ ] RBAC + managed identities preferred over service principals.
- [ ] Network design: VNets, subnets, NSGs, private endpoints documented.
- [ ] Storage: encryption at rest + in transit; soft-delete + versioning + redundancy chosen.
- [ ] SQL: backup retention, geo-replication, security baseline.
- [ ] Defender for Cloud enabled; recommendations triaged.
- [ ] Activity log retained + forwarded to SIEM.
- [ ] Cost tagging + budget alerts.
- [ ] Region selection documented.

Evidence to check:
- Defender severity findings reviewed.
- Tag coverage > 95%.

## Anti-patterns

- Service principals with client secrets for service identities.
- Single-zone production data services.
- LRS (locally-redundant storage) on production data without justification.
- Broad `Owner` RBAC role for service principals.
- App Service without Always On for production.
- Cosmos DB without explicit consistency model decision.
- Azure SQL without auto-failover group for tier-1.
- Log Analytics retention not set (defaults to 31 days; may not meet compliance).
- No Tags / Tag Policies (no cost attribution).
- Hybrid Benefit available but not applied.
