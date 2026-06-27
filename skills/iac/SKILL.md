---
name: iac
description: Infrastructure as Code discipline. Module structure, state management, drift detection, environment composition, policy-as-code guardrails, plan/apply discipline. Per the agnostic-everywhere decision, ships with refs for Terraform (the default for multi-cloud) and Pulumi (when programming-language IaC is preferred).
---

# Infrastructure as Code


<!-- praxis:description:full -->
## Full description

Infrastructure as Code discipline. Module structure, state management, drift detection, environment composition, policy-as-code guardrails, plan/apply discipline. Per the agnostic-everywhere decision, ships with refs for Terraform (the default for multi-cloud) and Pulumi (when programming-language IaC is preferred). Platform/SRE owns the IaC; this is what provisions clouds, K8s clusters, secret stores, registries, and the build infrastructure the rest depends on. Use whenever a new project's infrastructure is being designed, when new resources are being added, when migrating cloud accounts, or when establishing the state-management strategy.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: infra
state: active
dependencies:
 - engineering-standards
 - secrets-config
triggers:
 - "provisioning new cloud infrastructure"
 - "adding new resources to existing infrastructure"
 - "designing the IaC module structure for a project"
 - "establishing remote state + locking"
 - "writing policy-as-code (OPA / Sentinel / Pulumi CrossGuard)"
 - "investigating infrastructure drift"
outputs:
 - IaC modules (Terraform / Pulumi)
 - state strategy (backend, locking, workspaces/stacks)
 - policy-as-code rules
 - plan output (review evidence)
 - apply log (operational audit)
consumers:
 - platform-sre (primary author)
 - secrets-config (provisions the secret store via this skill)
 - environments (uses IaC modules per environment)
 - deploy-release (deploys into infrastructure this provisions)
 - capacity-resource-estimation (consumes IaC to model run cost)
 - security-reviewer (audits IaC for security misconfigurations)
references:
 - terraform.md
 - pulumi.md
```
<!-- praxis:metadata:end -->

The infrastructure the project runs on is built, modified, and destroyed exclusively through code in the repo. Cloud-console clicks for production resources are a violation — they're invisible to PRs, lack history, drift silently from intent. With IaC, the infrastructure is reviewed, versioned, diffable, rollback-able, and reproducible across accounts.

This skill produces the IaC patterns that provision *everything*: clusters, networks, secret stores, registries, databases, CDNs, monitoring stacks, identity policies. Per the project's choice (set in `governance.yaml`), Terraform or Pulumi; both are first-class supported.

## When this skill fires

- A new project's infrastructure is being designed.
- New resources are being added to existing infrastructure (a new service needs a database; an environment needs a new region).
- Module structure is being refactored for reuse across projects or environments.
- A new policy-as-code rule is being added (block public S3 buckets, require encryption at rest, etc.).
- Drift is detected and needs reconciliation.
- Infrastructure is being migrated between accounts or clouds.

## The discipline

### 1. Code in the repo, reviewed like code

- The IaC is in the project repo (or a dedicated infra repo per organization preference).
- Pull requests modify infrastructure; reviewers verify the *plan* output (the diff that would be applied) before merge.
- The plan is part of the PR artifact (CI generates it on every PR touching IaC).
- Apply happens from CI after merge — humans do not run `terraform apply` from laptops against production.

### 2. Module structure

Modules are the reusable building blocks. The shape:

```
infra/
├── modules/ reusable building blocks
│ ├── network/ VPC / VNet / VPC-equivalent
│ ├── cluster/ K8s cluster + node pools
│ ├── database/ managed Postgres / etc.
│ ├── secret-store/ the secrets-config secret store
│ ├── registry/ container registry
│ ├── observability/ log/metric/trace stack
│ └── ...
├── environments/ per-environment composition
│ ├── dev/
│ │ ├── main.tf or main.go|ts|py
│ │ ├── variables.tf
│ │ └── terraform.tfvars (or env-specific stack config)
│ ├── test/
│ ├── staging/
│ └── production/
├── policies/ policy-as-code rules (OPA / Sentinel / CrossGuard)
└── shared/ cross-environment resources (DNS zones, central IAM, etc.)
```

**Modules are the abstraction unit; environments are the composition unit.** The `cluster` module is the same across environments; environments parameterize it (cluster size, node pool count, autoscaler settings).

### 3. State management

State is the IaC's memory of what it has provisioned. **Never local state for shared resources.**

- **Remote state backend** — S3 + DynamoDB lock (AWS), Azure Blob + lease (Azure), GCS + GCS lock (GCP), or Terraform Cloud / HashiCorp Cloud.
- **State per environment** — `dev/`, `test/`, `staging/`, `production/` each have separate state files (called *workspaces* in Terraform Cloud, *stacks* in Pulumi). Blast-radius isolation: a state corruption in dev doesn't affect prod.
- **State locking** — every backend must support locking (mandatory). Two concurrent applies that don't lock corrupt state.
- **State encryption at rest** — the state file contains secrets (sometimes — depends on resources). Encrypt the backend.
- **State versioning** — backends with versioning support recovery from accidental destructive applies.
- **No state in the repo, ever.** Never commit `.tfstate` files or Pulumi state JSON. Use the backend.

### 4. Plan / apply discipline

Two phases per change:

- **Plan** — the IaC computes the diff: what would change, in what order. Produces a human-readable summary plus a machine-parsable plan file.
- **Apply** — the IaC executes the plan. Atomic-ish: each resource transitions individually, but the apply is sequenced by dependencies.

The discipline:

- **Plan in CI for every PR touching IaC.** The plan output is posted to the PR for reviewer scrutiny.
- **Apply only from CI on merge to main.** Never `apply` from a developer laptop against shared environments.
- **Apply with a saved plan file**, not by re-planning at apply time. The plan reviewed is the plan applied.
- **Production applies gate.** The `production_go_live` governance gate (and any per-change production-apply gate) requires explicit approval before the apply runs.

### 5. Policy-as-code

Policies enforced *before* apply, not after. Examples:

- "S3 buckets must be private (no public ACLs)."
- "All databases must have encryption at rest."
- "Resources must carry the `project`, `environment`, `owner`, `cost-center` tags."
- "EBS volumes must use customer-managed KMS keys."
- "Security groups must not have `0.0.0.0/0` ingress for ports other than 80/443."

Implemented via OPA (Open Policy Agent), HashiCorp Sentinel, Pulumi CrossGuard, or Checkov for Terraform.

Policies live in `infra/policies/` and run as part of the CI pipeline's IaC-PR validation. A policy violation blocks merge.

### 6. Drift detection

Drift = the actual state diverges from the IaC's intended state. Causes: emergency manual changes ("we'll fix it in IaC later"), out-of-band changes by another tool, console clicks.

Drift detection runs on a schedule (daily / weekly) — re-plan against production, report any non-empty diff. Drift is itself an incident (`incident-runbook`); it should never accumulate silently.

### 7. Tagging strategy

Every resource carries tags / labels:

| Tag | Value |
|---|---|
| `project` | the project name |
| `environment` | dev / test / staging / production |
| `owner` | team or individual owning the resource |
| `cost-center` | for FinOps allocation |
| `criticality` | low / medium / high / critical (drives on-call routing) |
| `compliance` | regimes that apply (e.g., `pci`, `hipaa`) |
| `managed-by` | `iac` (vs. manual, indicating drift candidates) |

Tagging is enforced via policy-as-code; resources without required tags fail the plan validation.

### 8. Secrets in IaC

IaC often *creates* secrets (database passwords, API keys for managed services). The discipline:

- **Generate secrets in IaC** — random_password resources, secrets manager auto-rotation, etc.
- **Write secrets to the secret store** — IaC creates the resource and stores its credential in the secret store; consumer services read from the secret store, not from IaC outputs.
- **Don't surface secrets in plan output** — the IaC must mark sensitive outputs to redact them in plan logs.
- **Don't store secrets in state** — when unavoidable, encrypt the state backend.

### 9. Reversibility

Every change should have a path back:

- **Plans show destructive operations explicitly.** Destruction prompts mandatory acknowledgment in CI.
- **Destructive operations are gated.** Removing a production database without an explicit ADR is a violation.
- **Backup before destroy.** Snapshots for databases; soft-delete-with-retention for object stores; etc.
- **`prevent_destroy` lifecycle rules** on critical resources (production databases, KMS keys, DNS zones).

### 10. Cost awareness

IaC is where infrastructure spend is decided. Each module / resource considers:

- Sized appropriately for the environment (dev resources are smaller than production).
- Right-sized for actual workload (informed by `capacity-resource-estimation` — Chunk C of this wave).
- Spot / preemptible where workload tolerates it.
- Reserved / committed-use for predictable steady-state load (decided in `cost-finops`; this skill exposes the right knobs).

Cost estimation runs in CI on every IaC PR (Infracost, Pulumi's cost preview, cloud-native pricing APIs). Estimated monthly cost delta is part of the PR review.

## Module composition pattern

Environments compose modules with environment-specific parameters:

```
# Conceptual — see references for Terraform / Pulumi specifics

environment "production" {
 network = module "network" {
 cidr = "10.0.0.0/16"
 az_count = 3
 }

 cluster = module "cluster" {
 network_id = network.id
 node_pool_size = 10
 node_instance_type = "m5.2xlarge"
 autoscaler_max = 50
 }

 secret_store = module "secret-store" {
 network_id = network.id
 rotation_enabled = true
 }

 database = module "database" {
 network_id = network.id
 instance_class = "db.r5.2xlarge"
 multi_az = true
 backup_retention_days = 30
 }
}

environment "dev" {
 network = module "network" {
 cidr = "10.10.0.0/16"
 az_count = 1
 }

 cluster = module "cluster" {
 network_id = network.id
 node_pool_size = 2
 node_instance_type = "t3.medium"
 autoscaler_max = 5
 }

 # ... smaller / cheaper variants
}
```

Same modules; different parameters per environment.

## Outputs

| Output | Location |
|---|---|
| IaC modules | `infra/modules/` |
| Environment compositions | `infra/environments/<env>/` |
| Policies | `infra/policies/` |
| Plan output (per PR) | CI artifact; archived to `.project/operational/iac-plans/` for production |
| State (backend) | Remote: S3 + DynamoDB / Azure Blob / GCS / TFC |
| Cost estimate (per PR) | CI artifact + PR comment |

## Choice of tool

Per `governance.yaml` and `Resolved Decisions` (Section 14 of the blueprint), the project picks Terraform or Pulumi (or ships refs for both per the agnostic decision). The shared body above is tool-neutral; per-tool patterns are in references:

- **Terraform / OpenTofu** — `references/terraform.md`
- **Pulumi** — `references/pulumi.md`

Both are first-class. Terraform is the most-common default; Pulumi is preferred when teams want IaC in real languages with full IDE support and the engineering team is comfortable with the chosen language (TypeScript / Python / Go).

## Mode handling (G/B)

**Greenfield.** Build the IaC from scratch following the module structure.

**Brownfield.** Critical: **import the existing infrastructure into IaC before making changes**. Importing all at once is overwhelming; do it incrementally — when a slice touches a piece of infrastructure, import that piece into IaC and bring it under management. Document the "not yet under IaC" list in `.project/working/iac-import-debt.md`. Drift is impossible to detect on resources not under IaC.

## What this skill does not do

- Provision the cluster's workloads — that's `platform-k8s` (Chunk C) and `deploy-release`.
- Configure runtime applications — that's `secrets-config` + the stack packs.
- Run penetration tests on infrastructure — that's an audit activity, but `security-reviewer` audits IaC for misconfigurations.
- Estimate capacity — that's `capacity-resource-estimation` (Chunk C); this skill provisions what that skill sizes.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Click-ops once; codify later." | Click-ops is drift. Codify from the first resource. |
| "Pulumi vs Terraform doesn't matter; pick one." | True at small scale; at any scale that matters, decide the team's mental model (DSL vs SDK) deliberately. |
| "State file in S3 is enough." | State file needs versioning, locking, encryption, access controls. The recommended setup, not the minimum. |
| "Inline everything in one big config." | Module discipline matters. Reusable modules + per-environment composition. |
| "Plan reviews are formalities." | Plan is the only artifact that says what changes. Review it carefully; require approval for destroy / replace. |
| "Drift detection is nice-to-have." | Without drift detection, your code says X and reality says Y. Schedule scans. |
| "Provider versions don't matter." | Providers introduce breaking changes between minor versions. Pin them. |

## Verification

You are done when:

- [ ] Infrastructure code in repo (Terraform / Pulumi / CDK).
- [ ] Modules versioned + referenced by version, not branch.
- [ ] Provider + module versions pinned.
- [ ] State backend: remote, versioned, locked, encrypted.
- [ ] Per-environment composition (workspaces, stacks, or directories).
- [ ] Plan review required for changes; destroy / replace operations require explicit approval.
- [ ] Drift detection scheduled; alerts on divergence.
- [ ] Resource tagging standard documented + applied (per `cost-finops` attribution).
- [ ] Secrets referenced from secret store; never hardcoded in IaC.

Evidence to check:
- Re-running plan produces no changes (idempotent).
- Drift detection ran within the past 30 days.

## Anti-patterns

- Cloud-console clicks for production resources.
- Local state files for shared infrastructure.
- Re-planning at apply time (instead of applying the plan reviewed).
- Apply from developer laptops against shared environments.
- Same state file for all environments (no blast-radius isolation).
- IaC modules that hard-code environment-specific values (parameterize them).
- Resources without tags (no cost attribution, no ownership clarity).
- `prevent_destroy: false` on production databases / KMS / DNS.
- Missing policy-as-code (lets misconfigurations through).
- Cost estimation skipped for "small" changes (small changes accumulate).
