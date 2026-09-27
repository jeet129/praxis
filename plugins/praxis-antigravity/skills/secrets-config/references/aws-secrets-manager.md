# Reference — AWS Secrets Manager

Loaded by `secrets-config` when AWS Secrets Manager is the chosen secret store.

## When to use

AWS Secrets Manager is the recommended default for new AWS-hosted applications:
- Tight IAM integration; no separate credential management.
- Automatic rotation built in for RDS/Redshift/DocumentDB/Aurora and custom rotation Lambdas.
- VPC endpoint support (no internet egress required).
- Audit via CloudTrail.

Alternatives on AWS:
- **SSM Parameter Store (Standard Tier)**: cheaper, simpler, also OK for secrets — but no automatic rotation.
- **HashiCorp Vault**: better cross-cloud + more features; higher ops cost. See `hashicorp-vault.md`.

## Pricing summary

- $0.40 per secret per month.
- $0.05 per 10K API calls.

This adds up at scale; budget accordingly. Often a few hundred secrets × 12 months × usage = noticeable line item, especially if every microservice has its own credential.

## Secret structure

Secrets store key-value pairs (JSON) up to 64KB:

```json
{
  "username": "app_user",
  "password": "actual-secret-value",
  "host": "db.internal",
  "port": 5432,
  "engine": "postgres"
}
```

Or a single value (string secret). JSON is more flexible.

## Creating secrets

**Via Console**: dev/manual only.

**Via Terraform (per `iac`)**:

```hcl
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "prod/db/orders"
  description = "Order DB credentials"
  
  recovery_window_in_days = 30  # deleted secrets are recoverable for this period
  
  kms_key_id = aws_kms_key.secrets.id  # customer-managed key
  
  tags = {
    Environment = "prod"
    Service     = "orders"
    ManagedBy   = "terraform"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "app_user"
    password = random_password.db_password.result
    host     = aws_db_instance.orders.endpoint
    port     = 5432
    engine   = "postgres"
  })
}
```

DON'T commit `secret_string` content to Terraform state if the state isn't tightly access-controlled. Use rotation + initial bootstrap from a workflow secret.

## IAM access

```hcl
# Service role can read THIS secret only
data "aws_iam_policy_document" "orders_secret_access" {
  statement {
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]
    resources = [aws_secretsmanager_secret.db_credentials.arn]
  }
  
  statement {
    actions = ["kms:Decrypt"]
    resources = [aws_kms_key.secrets.arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.us-east-1.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "orders_secret_access" {
  role   = aws_iam_role.orders_service.id
  policy = data.aws_iam_policy_document.orders_secret_access.json
}
```

Least privilege: a service can only read the secrets it needs, never with wildcards.

## Reading at runtime

### Python (boto3)

```python
import boto3
import json
from functools import lru_cache

@lru_cache(maxsize=1)
def get_db_credentials() -> dict:
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='prod/db/orders')
    return json.loads(response['SecretString'])

# Or with caching library for production
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
cache_config = SecretCacheConfig(secret_refresh_interval=60)  # refresh every 60s
cache = SecretCache(config=cache_config, client=boto3.client('secretsmanager'))

def get_db_credentials():
    secret = cache.get_secret_string('prod/db/orders')
    return json.loads(secret)
```

The caching library handles refresh + reduces API call costs significantly.

### Node.js

```ts
import { SecretsManagerClient, GetSecretValueCommand } from '@aws-sdk/client-secrets-manager';

const client = new SecretsManagerClient({});
let cachedCredentials: any = null;
let cachedAt = 0;

export async function getDbCredentials() {
    if (cachedCredentials && Date.now() - cachedAt < 60_000) {
        return cachedCredentials;
    }
    const response = await client.send(new GetSecretValueCommand({ SecretId: 'prod/db/orders' }));
    cachedCredentials = JSON.parse(response.SecretString!);
    cachedAt = Date.now();
    return cachedCredentials;
}
```

### Java (Spring Boot)

```yaml
# application.yml
spring:
  cloud:
    aws:
      secretsmanager:
        enabled: true
        name: prod/db/orders
```

```java
@Value("${username}")  // from the secret
private String dbUsername;
@Value("${password}")
private String dbPassword;
```

Spring Cloud AWS handles the resolution.

### Kubernetes — External Secrets Operator

For K8s workloads, the cleanest pattern is the External Secrets Operator (per `k8s-external-secrets.md`):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa  # has IAM role via IRSA

---
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: orders-db-credentials
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: orders-db-secret  # the K8s Secret created
  data:
    - secretKey: username
      remoteRef:
        key: prod/db/orders
        property: username
    - secretKey: password
      remoteRef:
        key: prod/db/orders
        property: password
```

The pod consumes the K8s Secret normally; ESO handles syncing from AWS.

## Rotation

### Built-in rotation (RDS/Aurora/Redshift/DocumentDB)

```hcl
resource "aws_secretsmanager_secret_rotation" "db_rotation" {
  secret_id           = aws_secretsmanager_secret.db_credentials.id
  rotation_lambda_arn = "arn:aws:lambda:us-east-1:account:function:SecretsManagerRDSPostgreSQLRotationSingleUser"
  
  rotation_rules {
    automatically_after_days = 30
  }
}
```

Two strategies:
- **Single-user**: the same user's password rotates. Existing connections drop on rotation; new connections get new password.
- **Alternating-user** ("two-user"): two users alternate; one is always valid while the other is being rotated. Zero-downtime but more complex.

For most workloads, single-user with proper connection pool retry handles it fine.

### Custom rotation (everything else)

For non-RDS secrets, write a custom Lambda. AWS provides templates. The Lambda must implement 4 steps:

1. **createSecret**: generate the new secret value as `AWSPENDING`.
2. **setSecret**: update the secret in the target system (e.g., update API key in third-party).
3. **testSecret**: verify the new secret works.
4. **finishSecret**: promote `AWSPENDING` to `AWSCURRENT`.

Failure handling: the Lambda retries; Secrets Manager won't promote until `finishSecret` succeeds.

## Encryption

By default Secrets Manager uses an AWS-managed KMS key. For customer-managed keys:

```hcl
resource "aws_kms_key" "secrets" {
  description             = "Secrets Manager encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/secrets-manager-secrets"
  target_key_id = aws_kms_key.secrets.id
}
```

CMK lets you:
- Audit decrypt operations separately in CloudTrail.
- Restrict decryption to specific principals or conditions.
- Manage key lifecycle separately from AWS.

## Audit logging

CloudTrail captures every `GetSecretValue` call:

```json
{
  "eventTime": "2026-06-15T10:30:00Z",
  "eventName": "GetSecretValue",
  "userIdentity": {...},
  "requestParameters": {"secretId": "prod/db/orders"},
  ...
}
```

Per `compliance-privacy` SKILL — forward CloudTrail to SIEM; alert on anomalies (after-hours access, unusual principals).

## VPC endpoint

For VPC-only access (no internet egress):

```hcl
resource "aws_vpc_endpoint" "secrets_manager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.us-east-1.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true
}
```

Apps in the VPC now resolve `secretsmanager.us-east-1.amazonaws.com` to the endpoint; traffic stays inside AWS.

## Cross-account access

To share a secret between accounts:

```hcl
resource "aws_secretsmanager_secret_policy" "cross_account_read" {
  secret_arn = aws_secretsmanager_secret.shared.arn
  policy     = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::OTHER_ACCOUNT_ID:role/some-role"
      }
      Action   = "secretsmanager:GetSecretValue"
      Resource = "*"
    }]
  })
}
```

The KMS key policy must also grant decrypt to the cross-account principal.

## Recovery from accidental deletion

Default behavior: deleting a secret gives a 30-day window for recovery (configurable: `recovery_window_in_days` 7-30, or 0 for immediate).

For mission-critical secrets, set 30 days.

## Gotchas

- **API call cost** — naive code that calls `GetSecretValue` per request adds up fast. Cache.
- **Pricing for SSM Parameter Store Standard tier is $0** (Advanced tier is $0.05/parameter/month). For static configuration, prefer SSM. Secrets Manager when you need rotation or larger payloads.
- **`secret_string` JSON parsing on the client** — Secrets Manager doesn't validate JSON; if you store invalid JSON, your app fails at parse time, not at write time.
- **Cross-region replication** is opt-in; configure if your DR plan requires it.
- **IAM resource ARN includes a random suffix** — `arn:aws:secretsmanager:us-east-1:account:secret:prod/db/orders-AbCdEf`. Use wildcards in policies (`prod/db/orders-*`) or get the ARN from Terraform output.

## Common rationalizations

| Thought | Counter |
|---|---|
| "SSM Parameter Store is cheaper; use it for everything." | SSM lacks rotation + native database integration. Use SSM for static config, Secrets Manager for rotating secrets. |
| "Read secret on every request." | Cache. API calls cost money; cold-start latency hurts. 60-second cache is usually fine. |
| "AWS-managed KMS is fine." | For most use cases yes. For compliance-bearing workloads, customer-managed key gives you audit + lifecycle control. |
| "Hardcode secret ID for now." | Templating via Terraform variables. Hardcoded strings in code become brittle. |
| "Custom rotation Lambda is complex; skip rotation." | Manual rotation breaks during turnover. Build the Lambda once; it pays for itself. |

## Verification (per `secrets-config` SKILL)

- [ ] No secrets in code / configs / commit history (verified by git-secrets or equivalent).
- [ ] Rotation policy documented per secret class.
- [ ] Rotation tested at least once (not just configured).
- [ ] IAM follows least-privilege; service can only access its own secrets.
- [ ] CloudTrail forwards GetSecretValue events to SIEM.
- [ ] Customer-managed KMS key used (for compliance-bearing workloads).
- [ ] VPC endpoint configured (if internet egress restricted).
- [ ] Disaster recovery — cross-region replication if RPO requires.

## Official sources

- AWS Secrets Manager: https://docs.aws.amazon.com/secretsmanager/
- aws-secretsmanager-caching libraries: https://github.com/aws/aws-secretsmanager-caching-python (similar for other langs)
- Rotation templates: https://github.com/aws-samples/aws-secrets-manager-rotation-lambdas
- IAM permissions reference: https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access_iam-policies.html
- VPC endpoints: https://docs.aws.amazon.com/secretsmanager/latest/userguide/vpc-endpoint-overview.html
