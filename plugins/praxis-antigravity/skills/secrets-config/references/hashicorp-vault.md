# Secrets Config — HashiCorp Vault

Vault (self-hosted or HCP Vault) as the secret store of record. Static KV, dynamic short-lived credentials, and identity-based auth methods — the goal is that no long-lived secret exists in a config file or environment variable checked into anything.

## KV v2: versioned static secrets

KV v2 (not v1) — every write is versioned, supports soft-delete + undelete, and check-and-set to prevent lost updates.

```bash
# Enable KV v2 at a path (per environment / team)
vault secrets enable -path=app-secrets -version=2 kv

# Write a secret
vault kv put app-secrets/billing/db \
  username=billing_svc \
  password="$(openssl rand -base64 32)"

# Read (latest version)
vault kv get app-secrets/billing/db

# Read a specific version (rollback support)
vault kv get -version=3 app-secrets/billing/db

# Soft-delete then destroy (two-step, auditable)
vault kv delete app-secrets/billing/db
vault kv destroy -versions=2,3 app-secrets/billing/db
```

Application access via the API, never `vault kv get` baked into a deploy script that logs output:

```python
import hvac

client = hvac.Client(url="https://vault.internal:8200")
client.auth.kubernetes.login(role="billing-service", jwt=open("/var/run/secrets/kubernetes.io/serviceaccount/token").read())

secret = client.secrets.kv.v2.read_secret_version(path="billing/db", mount_point="app-secrets")
db_password = secret["data"]["data"]["password"]
```

## Dynamic database credentials

Prefer dynamic over static wherever the backend supports it — Vault generates a short-lived, unique credential per lease, and revokes it automatically. A compromised credential is worthless within its TTL.

```bash
# Enable the database secrets engine
vault secrets enable database

vault write database/config/billing-postgres \
  plugin_name=postgresql-database-plugin \
  connection_url="postgresql://{{username}}:{{password}}@postgres.internal:5432/billing" \
  allowed_roles="billing-readwrite" \
  username="vault_admin" \
  password="$VAULT_ADMIN_PG_PASSWORD"

vault write database/roles/billing-readwrite \
  db_name=billing-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl=1h \
  max_ttl=4h
```

```bash
# App requests a lease at startup / on rotation
vault read database/creds/billing-readwrite
# -> username=v-billing-readwrite-a1b2c3, password=..., lease_duration=3600
```

Applications renew the lease before expiry (`vault lease renew <lease_id>`) or re-request on TTL expiry — the app's DB connection pool must handle credential rotation without a restart (short-lived connections, or a pool that swaps credentials on renewal).

## Kubernetes auth method

Pods authenticate with their service-account JWT — no static Vault token baked into an image or secret.

```bash
vault auth enable kubernetes

vault write auth/kubernetes/config \
  kubernetes_host="https://$KUBERNETES_SERVICE_HOST:$KUBERNETES_SERVICE_PORT" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
  token_reviewer_jwt=@/var/run/secrets/kubernetes.io/serviceaccount/token

vault write auth/kubernetes/role/billing-service \
  bound_service_account_names=billing-service \
  bound_service_account_namespaces=billing \
  policies=billing-read \
  ttl=1h
```

```hcl
# policies/billing-read.hcl
path "app-secrets/data/billing/*" {
  capabilities = ["read"]
}
path "database/creds/billing-readwrite" {
  capabilities = ["read"]
}
```

## Agent Injector vs Secrets Store CSI Driver

Two K8s-native patterns for getting secrets from Vault into a pod without the app talking to Vault's API directly:

| | Vault Agent Injector | Secrets Store CSI Driver |
|---|---|---|
| Mechanism | Sidecar container renders secrets to a shared `emptyDir` volume | CSI volume plugin mounts secrets directly, no sidecar |
| Renewal | Agent handles lease renewal + template re-render automatically | Requires periodic remount (`rotationPollInterval`) — no push |
| K8s Secret sync | Optional, via agent | Optional, via `secretObjects` (creates a native k8s Secret mirror) |
| Overhead | Extra container per pod | No extra container, but requires the CSI driver + provider DaemonSet cluster-wide |
| Best for | Apps needing live-reload on secret change (agent supports SIGHUP-style triggers) | Simpler footprint; teams already using CSI-driver pattern for other providers (AWS/GCP too) |

```yaml
# Agent Injector: annotations on the pod spec
metadata:
  annotations:
    vault.hashicorp.com/agent-inject: "true"
    vault.hashicorp.com/role: "billing-service"
    vault.hashicorp.com/agent-inject-secret-db-creds: "database/creds/billing-readwrite"
    vault.hashicorp.com/agent-inject-template-db-creds: |
      {{- with secret "database/creds/billing-readwrite" -}}
      export DB_USER="{{ .Data.username }}"
      export DB_PASS="{{ .Data.password }}"
      {{- end -}}
```

```yaml
# CSI Driver: SecretProviderClass
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata: { name: billing-vault-db }
spec:
  provider: vault
  parameters:
    vaultAddress: "https://vault.internal:8200"
    roleName: "billing-service"
    objects: |
      - objectName: "db-password"
        secretPath: "app-secrets/data/billing/db"
        secretKey: "password"
```

## Rotation

- **Static secrets**: rotate on a schedule (90 days default, shorter for high-sensitivity) via `vault kv put` with a new value, coordinated with a rolling app restart or hot-reload.
- **Dynamic secrets**: rotation is inherent — every lease is a new credential; `default_ttl` controls the cadence.
- **Root/admin credentials Vault itself uses** (e.g., the Postgres admin user in the DB engine config) — rotate via `vault write -force database/rotate-root/billing-postgres`; Vault then holds the only copy, nobody else knows the new password.
- **PKI secrets engine** for short-lived TLS certs, same dynamic-credential model.

## Break-glass

- A sealed Vault requires unseal keys (Shamir-split, quorum threshold e.g. 3-of-5) held by separate humans/HSM — document who holds shares and the unseal runbook in `incident-runbook`.
- A dedicated `root` token is generated only for emergency recovery, used once, and revoked immediately after (`vault token revoke <token>`). It is never a standing credential.
- Break-glass access is logged to the audit device (`vault audit enable file file_path=/var/log/vault_audit.log`) and reviewed post-incident — every break-glass use gets a retro entry.
- Maintain an emergency-access policy separate from day-to-day roles, gated by a second approver, per the governance matrix.

## Common violations to flag in review

- Static long-lived DB credentials used where the database secrets engine supports dynamic ones.
- Vault tokens with no TTL (`ttl=0` / non-expiring) issued to a service.
- Application code that logs the full secret payload (even at DEBUG).
- KV v1 used for new secrets (no versioning, no soft-delete).
- Policies granting `*` or overly broad path globs instead of least-privilege per service.
- Root token used for routine application access instead of a scoped auth-method role.
- No audit device enabled — Vault access with no audit trail.
