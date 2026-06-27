---
name: platform-aws
description: AWS cloud-specific reference pack. Managed-service catalog (EKS / RDS / S3 / Aurora / DynamoDB / EventBridge / SQS / SNS / Step Functions / Lambda / API Gateway), networking (VPC / Transit Gateway / PrivateLink / ALB / NLB / CloudFront), identity (IAM / IRSA / SSO / KMS), observability (CloudWatch / X-Ray), DR topology (multi-AZ default; multi-region patterns), cost levers (Savings Plans /...
---

# Platform — AWS


<!-- praxis:description:full -->
## Full description

AWS cloud-specific reference pack. Managed-service catalog (EKS / RDS / S3 / Aurora / DynamoDB / EventBridge / SQS / SNS / Step Functions / Lambda / API Gateway), networking (VPC / Transit Gateway / PrivateLink / ALB / NLB / CloudFront), identity (IAM / IRSA / SSO / KMS), observability (CloudWatch / X-Ray), DR topology (multi-AZ default; multi-region patterns), cost levers (Savings Plans / Reserved Instances / Spot), Well-Architected Framework alignment. The deep reference library that iac, deploy-release, reliability-dr, capacity-resource-estimation, cost-finops, and observability consult for AWS-specific implementation. Selected when AWS is the project's cloud per governance.yaml.

<!-- praxis:description:end -->


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
  - "AWS is the project's cloud and deployment patterns are being designed"
  - "selecting AWS managed services for a workload"
  - "wiring AWS-native observability (CloudWatch / X-Ray)"
  - "designing multi-AZ / multi-region topology on AWS"
  - "applying Well-Architected Framework"
outputs:
  - managed-service decisions per workload (compute / data / messaging / identity)
  - VPC + connectivity topology
  - IAM model with IRSA / Pod Identity for K8s workloads
  - CloudWatch + X-Ray instrumentation
  - DR plan with AWS-specific primitives (multi-AZ Aurora, S3 CRR, Route 53 failover)
  - cost levers applied (Savings Plans / RIs / Spot / S3 tiering)
consumers:
  - platform-sre (primary author for AWS deployments)
  - iac (Terraform / Pulumi AWS provider)
  - deploy-release (AWS-specific deploy patterns)
  - reliability-dr (multi-AZ / multi-region patterns)
  - cost-finops (AWS Cost Explorer + Budgets + tagging)
references: []
```
<!-- praxis:metadata:end -->

The deep reference library for AWS-specific patterns. Where the cloud-agnostic K8s pack (`platform-k8s`) covers what runs *inside* the cluster, this pack covers what AWS provisions *around* it — managed services, networking, identity, DR primitives — and how to combine them well.

The Well-Architected Framework's six pillars (Operational Excellence / Security / Reliability / Performance / Cost / Sustainability) frame the decisions. AWS published reference architectures for many common patterns — use them as starting points rather than inventing.

## Compute options

| Service | Sweet spot |
|---|---|
| **EKS** | K8s on AWS. Default for stateless services + most stateful patterns. Pair with Karpenter for autoscaling. |
| **ECS Fargate** | Container workloads without K8s operational overhead. Less common when the team already runs K8s elsewhere. |
| **EC2 Auto Scaling Groups** | Legacy or specific workloads that need bare instance access. Rarely the right default for new projects. |
| **Lambda** | Event-driven, low-throughput, latency-tolerant. Cold start matters; provisioned concurrency mitigates. |
| **App Runner / Lightsail** | Simpler than EKS; less control. Internal tools or low-complexity SaaS. |

Default for new projects: **EKS** (per the K8s-first cloud decision) + **Lambda** for genuinely event-driven workloads (SNS subscriptions, S3 events, scheduled jobs).

### EKS specifics

- **Managed node groups** with Karpenter for advanced autoscaling.
- **IRSA** (IAM Roles for Service Accounts) — workload identity binding. Per K8s ServiceAccount → IAM role → AWS resource access.
- **VPC CNI** — pod IPs are VPC IPs. Plan IP space accordingly.
- **AWS Load Balancer Controller** — provisions ALB / NLB per Ingress / Service annotations.
- **EBS CSI / EFS CSI** — for persistent volumes.

## Data services

| Service | Sweet spot |
|---|---|
| **Aurora (Postgres / MySQL)** | Default for relational. Multi-AZ standard; global DB for multi-region. PITR + automated backups. Aurora I/O-Optimized for high-I/O workloads. |
| **RDS (Postgres / MySQL / etc.)** | Standard managed relational. Lower cost than Aurora; similar reliability story. |
| **DynamoDB** | Key-value / document at scale. Single-digit ms latency. Global Tables for multi-region active-active. On-demand vs provisioned capacity. |
| **ElastiCache (Redis / Memcached)** | Caching + session storage. ElastiCache Serverless for variable load. |
| **S3** | Object storage default. Intelligent-Tiering for unknown access patterns. Cross-Region Replication for DR. |
| **OpenSearch Service** | Search + log aggregation. Costly; alternatives (Postgres FTS + pgvector) often sufficient. |
| **Kinesis Data Streams** | Real-time event streams. Kinesis Data Firehose for delivery to S3 / OpenSearch. |
| **MSK (Managed Kafka)** | When the team genuinely needs Kafka semantics. MSK Serverless to reduce ops overhead. |

Default for new transactional data: **Aurora Postgres**.

## Messaging & event services

| Service | Sweet spot |
|---|---|
| **SQS** | Simple queueing; at-least-once delivery; FIFO available. Default for async between services. |
| **SNS** | Pub/sub; fan-out to multiple subscribers. |
| **EventBridge** | Event bus with content-based routing; SaaS partner integrations. Default for event-driven architectures. |
| **Step Functions** | Workflow orchestration. Use for saga orchestration (per `resilience-patterns`). |
| **MSK** | High-throughput streaming when Kafka semantics needed. |

## Identity & secrets

| Service | Use |
|---|---|
| **IAM** | All AWS authorization. Roles, policies, least privilege. |
| **IAM Identity Center (formerly SSO)** | Workforce SSO; replaces IAM users for humans. |
| **IRSA / Pod Identity** | EKS workload → IAM role mapping. Service-account-annotated; no long-lived credentials. |
| **Cognito** | Customer identity (B2C); OIDC provider for end-user auth. |
| **Secrets Manager** | Per `secrets-config`'s aws-secrets-manager reference. Auto-rotation supported. |
| **Systems Manager Parameter Store** | Configuration values; cheaper than Secrets Manager for non-rotated config. |
| **KMS** | Customer-managed encryption keys. Default for at-rest encryption beyond AWS-managed keys. |

IAM discipline:

- **Per-service IAM role** mapped to ServiceAccount via IRSA. Minimum-privilege policies.
- **No IAM users for services** — they're for emergency break-glass only; deprecate.
- **No `*` in production IAM policies** — explicit resource ARNs.
- **AWS Organizations + SCPs** for guardrails across accounts.

## Networking

| Pattern | Use |
|---|---|
| **VPC** | Default network isolation. One VPC per environment per region. |
| **Subnets** | Public (load balancers) vs private (compute) vs database (data services). 3 AZs minimum for production. |
| **Transit Gateway** | Multi-VPC + on-prem connectivity hub. |
| **VPC Peering** | Two-VPC connection; cheaper than TGW for simple cases. |
| **PrivateLink** | Expose / consume services privately; SaaS integrations without internet egress. |
| **ALB** | HTTP/HTTPS load balancing; integrates with WAF; path/host routing. Default for HTTP APIs. |
| **NLB** | TCP / UDP; static IPs; lower latency than ALB. For non-HTTP or extreme throughput. |
| **CloudFront** | CDN + edge logic. Default for static assets + global API edges. |
| **Route 53** | DNS + health-check-based failover. Multi-region failover via failover routing policy. |
| **WAF** | Web Application Firewall; managed rules + custom. |
| **Shield** | DDoS protection; Standard free; Advanced for managed response. |

## Observability

| Service | Use |
|---|---|
| **CloudWatch Logs** | Default log aggregation. Cost grows fast — set retention + use Logs Insights instead of broad searches. |
| **CloudWatch Metrics** | Standard metrics. EMF (Embedded Metric Format) for custom dimensions. |
| **CloudWatch Alarms** | Alert routing. SNS → Slack / PagerDuty. |
| **X-Ray** | Distributed tracing. Pairs with OTel via OTel-AWS exporter. |
| **CloudWatch RUM** | Real User Monitoring. Alternative to Datadog RUM. |
| **CloudWatch Container Insights** | EKS / ECS observability with pod-level metrics. |

For OTel-native: **AWS Distro for OpenTelemetry (ADOT)** — managed collector + AWS exporters; integrates with CloudWatch and X-Ray.

## DR patterns

Default topology:

- **Single region, multi-AZ** — production default. 3 AZs; data services replicated across; ALBs across.
- **Cross-region async replication** — for DR site (S3 CRR, Aurora cross-region replicas, DynamoDB Global Tables).
- **Route 53 failover routing** — automatic DNS cutover on regional health-check failure.

Multi-region active-active (DynamoDB Global Tables, Aurora Global Database read endpoints, S3 Multi-Region Access Points): more expensive; complex consistency; reserve for genuinely required.

Backups:

- **Aurora / RDS** — automated snapshots; PITR; cross-region snapshot copy for DR.
- **S3** — versioning + lifecycle + CRR.
- **EBS** — snapshots (lifecycle-managed via Data Lifecycle Manager).
- **DynamoDB** — PITR enabled by default for production tables.

## Cost levers

| Lever | Saves |
|---|---|
| **Savings Plans** | 30-50% off compute (EC2, Fargate, Lambda) for 1- or 3-year commitment. Most flexible commitment. |
| **Reserved Instances** | RDS / ElastiCache / OpenSearch. 1-year or 3-year. |
| **Spot Instances** | Up to 90% off EC2 for interruption-tolerant workloads. Karpenter handles spot replacement well on EKS. |
| **S3 Intelligent-Tiering** | Automatic tiering based on access. Set once; benefit forever. |
| **S3 Lifecycle** | Manual lifecycle policies — Standard → IA → Glacier → Deep Archive. |
| **Aurora Serverless v2** | Auto-scaling capacity; cheap for variable load. |
| **Gravition instances** | ARM-based; 20-40% better price/perf for compatible workloads. |
| **VPC endpoints** | Avoid NAT Gateway data charges for AWS service access. |

## Well-Architected Framework alignment

Per pillar, key practices for AWS:

- **Operational Excellence** — IaC for everything (Terraform/CDK/Pulumi); GitOps deployments; AWS Systems Manager for runbook automation.
- **Security** — IAM least privilege; KMS at-rest encryption everywhere; WAF on public endpoints; GuardDuty for threat detection; Security Hub for posture.
- **Reliability** — Multi-AZ everything in production; auto-scaling; PITR; tested DR.
- **Performance** — Right-size with Compute Optimizer recommendations; Graviton where compatible; CloudFront for global.
- **Cost** — Cost Explorer + Budgets; Savings Plans; tagging via SCPs; AWS Cost & Usage Reports for analysis.
- **Sustainability** — Right-sizing reduces waste; serverless for spiky workloads; Graviton's lower power.

## Common patterns

### Tier-1 production SaaS

```
- VPC: 3 AZs, private + public subnets.
- EKS cluster with Karpenter (spot for non-critical; on-demand baseline).
- Aurora Postgres (multi-AZ; PITR).
- ElastiCache Redis Cluster Mode (multi-AZ).
- S3 (Intelligent-Tiering; versioned; CRR for important buckets).
- ALB + WAF + CloudFront for public surface.
- Cognito for customer identity; IAM Identity Center for workforce.
- Secrets Manager + KMS for secrets.
- CloudWatch (logs, metrics, alarms); X-Ray for tracing; AWS Distro for OpenTelemetry for OTel-native instrumentation.
- AWS Budgets + Cost Explorer; tagging policy enforced via SCPs.
- Multi-region DR via Aurora cross-region replicas + Route 53 failover.
```

### Event-driven async processing

```
- EventBridge bus receives events (SaaS / EventBridge schemas / direct).
- Step Functions for multi-step workflows.
- Lambda for short tasks; ECS Fargate for longer tasks.
- SQS dead-letter queues for failed events.
- DynamoDB for stateful event tracking.
```

## Outputs

| Output | Location |
|---|---|
| AWS service decisions per workload | `.project/decision/adr-aws-services-{component}.md` |
| VPC + connectivity topology | `.project/operational/network-topology.md` |
| IAM model | `.project/operational/iam-model.md` |
| CloudWatch dashboard set | provisioned via IaC; documented in `.project/operational/dashboards.md` |
| DR plan (AWS-specific primitives) | `.project/operational/dr-plan-{service}.md` |
| Cost levers applied | inline in `.project/operational/cost-model.md` |

## Mode handling (G/B)

**Greenfield.** Apply Well-Architected from day one; default to managed services; document service decisions in ADRs.

**Brownfield.** Audit existing AWS posture. Common findings: IAM users (instead of roles); broad `*` policies; production single-AZ; no PITR; CloudWatch retention forever (cost). Address by severity (security first, reliability second, cost third).

## What this skill does not do

- Replace `iac` — that skill provides the IaC discipline; this provides the AWS-specific service knowledge.
- Replace `platform-k8s` — that pack covers what runs *inside* the K8s cluster; this pack covers what AWS provides *around* it.
- Penetration testing or security audits.
- Negotiate Enterprise Discount Programs (sales / finance).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "IAM is hard; use AdministratorAccess in dev." | Dev IAM patterns leak into prod design. Least-privilege from dev. |
| "Default VPC is fine." | Default VPC has implicit public access. Use a deliberate VPC design. |
| "S3 bucket policies catch everything." | Bucket policy + IAM + ACL + block-public-access all interact. Layer them. |
| "Lambda is serverless = no ops." | Lambda has cold starts, concurrency limits, timeout limits, retry semantics. Read the docs; size deliberately. |
| "RDS is managed; just use defaults." | Backup retention, Multi-AZ, parameter group, encryption all need explicit choices. |
| "CloudWatch is the answer to observability." | CloudWatch is collection; you still need SLOs, dashboards, alert routing. |
| "EKS removes K8s complexity." | EKS removes the control-plane operations. The workload complexity remains. |

## Verification

You are done when:

- [ ] AWS Organizations + accounts structured (separate accounts for prod / non-prod / shared services).
- [ ] IAM follows least-privilege; access keys avoided where IAM roles work.
- [ ] VPC design documented (subnets, routing, gateways, peering).
- [ ] S3 buckets: encrypted, versioned, block-public-access on; bucket policies reviewed.
- [ ] RDS: Multi-AZ for prod, backups + retention set, encryption at rest, parameter group tuned.
- [ ] CloudTrail enabled, multi-region, log-file integrity validation on.
- [ ] GuardDuty enabled; findings routed.
- [ ] Cost tagging strategy applied + enforced.
- [ ] Secrets in Secrets Manager / Parameter Store (per `secrets-config`).
- [ ] Region selection documented (residency + cost + latency).

Evidence to check:
- Security Hub / Inspector findings reviewed; no high-severity open.
- Tagged-resource report covers > 95% of resources.

## Anti-patterns

- IAM users for services (use IAM roles + IRSA).
- `Action: *` or `Resource: *` in production policies.
- Single-AZ production data services.
- CloudWatch Logs retention indefinite (cost runaway).
- No tagging → no cost attribution.
- `s3:GetObject` to public buckets (use CloudFront).
- Lambda cold starts ignored (use provisioned concurrency or warm-up patterns).
- Aurora I/O-Optimized for low-I/O workloads (Aurora Standard is cheaper).
- RDS without Performance Insights enabled (no query-level visibility).
- Multi-region active-active without business justification (huge cost; high complexity).
