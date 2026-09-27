# Secrets Config — External Secrets Operator (K8s)

External Secrets Operator (ESO) syncs secrets from an external store (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) into native Kubernetes `Secret` objects — so workloads consume secrets the normal k8s way (env var / volume mount) while the source of truth stays outside the cluster.

## Why ESO over storing secrets directly in K8s

- Kubernetes `Secret` objects are base64-encoded, not encrypted, unless the cluster has encryption-at-rest configured — they are not a secret *store*, just a delivery mechanism.
- ESO keeps the external store as the single source of truth; the k8s `Secret` is a synced, disposable projection. Rotate in the store, ESO propagates it.
- One controller, many providers — a single pattern (`ExternalSecret` CRD) works whether the backend is Vault, AWS, GCP, or Azure, which matters for multi-cloud or migrating teams.

## Install

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace
```

## SecretStore CRD

Namespace-scoped (`SecretStore`) or cluster-scoped (`ClusterSecretStore`) — use `ClusterSecretStore` for a provider config shared across namespaces/teams; `SecretStore` when a namespace needs its own credentials to the backend.

### Vault provider

```yaml
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: vault-backend
  namespace: billing
spec:
  provider:
    vault:
      server: "https://vault.internal:8200"
      path: "app-secrets"
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: billing-service
          serviceAccountRef:
            name: billing-service
```

### AWS Secrets Manager provider

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata: { name: aws-secrets-manager }
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-irsa
            namespace: external-secrets-system
```

Requires IRSA (IAM Roles for Service Accounts) binding the k8s service account to an IAM role scoped to `secretsmanager:GetSecretValue` on the relevant secret ARNs only.

### GCP Secret Manager provider

```yaml
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata: { name: gcp-secret-manager }
spec:
  provider:
    gcpsm:
      projectID: my-gcp-project
      auth:
        workloadIdentity:
          clusterLocation: us-central1
          clusterName: prod-cluster
          serviceAccountRef:
            name: external-secrets-wi
            namespace: external-secrets-system
```

## ExternalSecret CRD

The actual sync directive — maps a remote secret (or several) into a k8s `Secret`.

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: billing-db-credentials
  namespace: billing
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: billing-db-secret          # the k8s Secret created/managed by ESO
    creationPolicy: Owner            # ESO owns lifecycle; deleted on ExternalSecret delete
    template:
      type: Opaque
      data:
        DATABASE_URL: "postgresql://{{ .username }}:{{ .password }}@postgres:5432/billing"
  data:
    - secretKey: username
      remoteRef:
        key: billing/db
        property: username
    - secretKey: password
      remoteRef:
        key: billing/db
        property: password
```

`dataFrom` pulls an entire secret's keys without enumerating each one — convenient, but be deliberate: it syncs whatever the remote secret contains, including fields the workload doesn't need.

```yaml
  dataFrom:
    - extract:
        key: billing/db
```

## Refresh and drift

- `refreshInterval` controls polling cadence (`1h` is a reasonable default; shorter for secrets that rotate frequently via Vault dynamic credentials — match it to the credential TTL).
- ESO polls, it doesn't push — a secret rotated in the backend takes up to one `refreshInterval` to land in the cluster. For dynamic Vault leases, set `refreshInterval` comfortably under the lease TTL so credentials never go stale mid-window.
- On sync, ESO diffs remote vs. the owned k8s `Secret` and patches only on change — pods mounting the secret as a volume see the update via kubelet's periodic resync (~1 min); pods using it as an env var do **not** get live updates (env vars are snapshotted at container start) — a rolling restart is required for env-var consumers, or switch to volume mounts + an app-side file-watcher for live rotation.
- `creationPolicy: Owner` means deleting the `ExternalSecret` deletes the synced `Secret` — intentional cleanup, but be aware in namespaces with manual secret overrides.

## Detecting drift / sync failures

```bash
kubectl get externalsecret -n billing billing-db-credentials -o jsonpath='{.status.conditions}'
# Look for: Ready=True and the SecretSynced reason

kubectl describe externalsecret -n billing billing-db-credentials
# Events show the last sync error (auth failure, path not found, provider timeout)
```

Alert on `ExternalSecret` conditions where `Ready=False` for longer than one `refreshInterval` — that means the workload is running on a stale (possibly soon-to-expire dynamic) credential.

## Multi-provider / migration pattern

Because `SecretStoreRef` is swappable independently of the `ExternalSecret`'s consuming workloads, migrating providers (e.g., AWS Secrets Manager → Vault during a cloud migration) is a `SecretStore` config change plus updating `remoteRef.key` paths — the workload's `Secret` name and shape stay stable, so no application changes are required.

## Common violations to flag in review

- `ExternalSecret` with no `refreshInterval` set (defaults vary by version; be explicit).
- Env-var-consuming Deployments with no restart trigger on secret rotation (stale credentials silently used past rotation).
- `creationPolicy: Merge` used where `Owner` is intended (or vice versa) — Merge leaves orphaned data if the ExternalSecret is deleted, Owner deletes secrets other things might depend on.
- Cluster-wide `ClusterSecretStore` credentials scoped broader than the namespaces that actually need them.
- No alerting wired to `ExternalSecret` sync-failure conditions.
- Secrets templated into a `ConfigMap` instead of a `Secret` (loses at-rest encryption and RBAC secret-specific protections).
