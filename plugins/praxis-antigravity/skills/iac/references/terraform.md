# IaC — Terraform / OpenTofu

Terraform-specific patterns for the shared IaC discipline.

OpenTofu (the open-source Terraform fork) is fully compatible; this reference applies to both. Pick one per project; both are stable.

## Module structure

```
infra/
├── modules/
│   ├── network/
│   │   ├── main.tf              resources
│   │   ├── variables.tf         input contract
│   │   ├── outputs.tf           output contract
│   │   ├── versions.tf          provider + Terraform version pins
│   │   └── README.md            module documentation
│   ├── cluster/
│   ├── database/
│   └── ...
├── environments/
│   ├── dev/
│   │   ├── main.tf              composes modules
│   │   ├── backend.tf           remote state config
│   │   ├── variables.tf
│   │   ├── terraform.tfvars     environment-specific values (no secrets)
│   │   └── versions.tf
│   ├── test/
│   ├── staging/
│   └── production/
├── policies/                    OPA / Checkov rules
└── shared/                      cross-env (DNS zones, central IAM)
```

## Module contract

```hcl
# modules/cluster/variables.tf
variable "name" {
  type        = string
  description = "Cluster name; used for resource naming and tagging."
}

variable "network_id" {
  type        = string
  description = "ID of the network this cluster runs in."
}

variable "node_pool_size" {
  type        = number
  description = "Initial node count."
  default     = 3
}

variable "node_instance_type" {
  type        = string
  description = "Instance type for nodes."
}

variable "autoscaler_max" {
  type        = number
  description = "Max nodes for the cluster autoscaler."
  default     = 10
}

variable "tags" {
  type        = map(string)
  description = "Required tags: project, environment, owner, cost-center, criticality."
}

# modules/cluster/outputs.tf
output "id" {
  value       = aws_eks_cluster.this.id
  description = "Cluster ID."
}

output "endpoint" {
  value       = aws_eks_cluster.this.endpoint
  description = "Cluster API endpoint."
}

output "kubeconfig_command" {
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.this.name}"
  description = "Command to update local kubeconfig."
}
```

The variables file is the *contract*. Required variables have no default; optional ones do. Outputs are the published surface for consumers.

## State backend

Per environment, the remote state config:

```hcl
# environments/production/backend.tf
terraform {
  backend "s3" {
    bucket         = "company-iac-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "company-iac-state-lock"
    encrypt        = true
  }
}
```

State buckets are bootstrapped manually once per organization (chicken-and-egg) and then managed by IaC for ongoing changes.

## Workspaces or per-env state files

For multi-environment projects, prefer **per-environment state files** (one backend block per env) over workspaces. Reasons:

- Clearer blast-radius isolation.
- Easier RBAC (each env's backend has separate IAM policies).
- Doesn't conflate "different environment" with "different version of same environment."

```hcl
# environments/production/main.tf
module "network" {
  source = "../../modules/network"

  cidr     = "10.0.0.0/16"
  az_count = 3

  tags = local.common_tags
}

module "cluster" {
  source = "../../modules/cluster"

  name               = "prod-app"
  network_id         = module.network.id
  node_pool_size     = 10
  node_instance_type = "m5.2xlarge"
  autoscaler_max     = 50

  tags = local.common_tags
}

locals {
  common_tags = {
    project     = "app"
    environment = "production"
    owner       = "platform-team"
    cost-center = "engineering"
    criticality = "critical"
    managed-by  = "terraform"
  }
}
```

## Plan + apply in CI

```yaml
# (GitHub Actions example; see cicd-pipeline references)
- name: Terraform plan
  run: |
    terraform init
    terraform plan -out=plan.tfplan
  working-directory: infra/environments/${{ matrix.env }}

- name: Comment plan on PR
  uses: actions/github-script@v7
  with:
    script: |
      // Read plan output and post to PR for reviewer scrutiny

# Apply only happens on merge, gated by manual approval for production
- name: Terraform apply
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  run: terraform apply plan.tfplan
  working-directory: infra/environments/${{ matrix.env }}
```

## Policy-as-code with OPA / Checkov

```yaml
# CI pipeline step
- name: Checkov
  uses: bridgecrewio/checkov-action@master
  with:
    directory: infra/
    framework: terraform
    soft_fail: false

- name: OPA conftest
  run: |
    conftest test --policy infra/policies/ infra/environments/${{ matrix.env }}/*.tf
```

## Sensitive outputs

```hcl
output "db_password" {
  value     = random_password.db.result
  sensitive = true   # redacted from plan/apply output
}
```

But *don't* output secrets at all if you can avoid it. Better pattern: IaC writes the secret directly to the secret store.

```hcl
resource "random_password" "db" {
  length = 32
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "production/db/password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db.result
}

# Application reads from Secrets Manager at startup; never sees the raw value via IaC outputs.
```

## Version pinning

```hcl
# modules/cluster/versions.tf
terraform {
  required_version = ">= 1.6.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}
```

Pin Terraform and provider versions. Floating versions cause non-reproducible plans.

## Drift detection

A scheduled CI job (daily or weekly):

```yaml
- name: Terraform plan (drift check)
  run: |
    terraform init
    terraform plan -detailed-exitcode -out=plan.tfplan
  continue-on-error: true

- name: Alert on drift
  if: steps.plan.outputs.exit-code == '2'   # exit code 2 = changes detected
  run: |
    # Send to incident channel / PagerDuty
```

Exit code 2 from `terraform plan -detailed-exitcode` indicates drift; the alert routes to on-call.

## Common violations to flag in review

- Inline resource definitions in environment files instead of modules (no reuse).
- `count` instead of `for_each` for resource sets (count breaks on reorderings).
- Hardcoded ARNs / IDs (use data sources or variables).
- Missing `tags` on resources (policy-as-code should block, but reviewer catches).
- `aws_iam_policy_document` JSON inline instead of `data` blocks (less reviewable).
- Local state in shared infrastructure.
- `terraform apply -auto-approve` in CI for production.
- Provider versions without upper bounds (`>= 5.0` instead of `~> 5.30`).
- Modules with too many input variables (god-modules; split them).
- Output of sensitive values without `sensitive = true`.

## Tooling

- **terraform** / **tofu** — the binary.
- **tflint** — linter for common issues.
- **terraform-docs** — auto-generated module documentation.
- **checkov** — policy / misconfiguration scanner.
- **conftest** + OPA — custom policy rules.
- **infracost** — cost estimation in PRs.
- **tfsec** — security-focused scanner.
- **terragrunt** — DRY wrapper for multi-env compositions when modules don't suffice (use sparingly; modules + composition usually do).
