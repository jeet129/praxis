---
name: secrets-config
description: Twelve-factor configuration + secret management. No secrets in code, no secrets in config files, no secrets in commit history. Centralized secret store at runtime; injection at app startup or per-call; rotation cadence; minimum-privilege scoping; audit logging. Stack-pack-agnostic body with platform-specific refs (AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / K8s External Secrets / HashiCorp Vault). Use whenever code needs configuration that varies by environment or contains sensitive data, when designing the secret-injection pattern, or when establishing rotation policy.
---

# Secrets & Config


<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: infra
state: active
dependencies:
 - engineering-standards
 - secure-coding
triggers:
 - "designing the project's config + secret-injection pattern"
 - "adding a new service that needs config or secrets"
 - "rotating credentials"
 - "scoping secret access (least privilege)"
 - "auditing existing secret handling"
outputs:
 - config schema (per service)
 - secret-store integration (per environment + service)
 - rotation policy + cadence
 - access policy (which service reads which secrets)
 - audit log requirements
consumers:
 - platform-sre (primary author for infra-side wiring)
 - backend-developer (consumes config + secrets in code)
 - frontend-developer (consumes public config only — no secrets in FE)
 - secure-coding (verifies no-secrets-in-code)
 - cicd-pipeline (consumes pipeline secrets per scope)
 - iac (provisions the secret store;)
references:
 - aws-secrets-manager.md
 - azure-key-vault.md
 - gcp-secret-manager.md
 - k8s-external-secrets.md
 - hashicorp-vault.md
```
<!-- praxis:metadata:end -->

The discipline that keeps credentials out of code, out of repos, out of commit history, out of CI logs, and out of error messages. Done right, the codebase has no secrets in it; secrets are loaded at runtime from a centralized store; access is least-privilege; rotation is automated. Done wrong, a stolen laptop or leaked CI log compromises production.

## When this skill fires

- Designing the project's config + secret pattern at the start.
- Adding a service that needs new config or new secrets.
- Establishing or revising the rotation policy.
- Scoping access (which service reads which secrets).
- Auditing existing secret handling.

## The twelve-factor baseline

Config that varies by environment lives outside the code:

- **Code** in the repo, identical across environments.
- **Config** injected at runtime from environment variables, mounted files, or a secret store.
- **Build artifact** is the same image promoted across environments; only config differs.

This is twelve-factor #3 (Config in environment) made concrete. Violations:

- Hardcoded URLs (DB host, API endpoint) that differ between dev and prod.
- Different code paths per environment (`if (env === 'production') { ... }` — that should be config).
- Config files committed with prod values.

## The discipline

### 1. Categorize the values

Three categories. Each handled differently:

| Category | Examples | Where it lives |
|---|---|---|
| **Public config** | Logging level, feature flags, region, public URLs | Repo (per-environment files) or runtime environment |
| **Sensitive config** | DB connection strings (with creds), API keys (yours), webhook signing secrets | Secret store |
| **Identity secrets** | Service-to-service auth (mTLS certs, OIDC client secrets, signing keys) | Secret store + identity provider |

Never mix: public config in the secret store wastes the store's overhead; sensitive config in the repo is a blocker violation.

### 2. The secret store is the source of truth

The secret store (managed cloud or self-hosted) is authoritative. Code never reads secrets from anywhere else.

**Managed secret stores** (per platform):

- AWS Secrets Manager or Parameter Store (see `references/aws-secrets-manager.md`)
- Azure Key Vault (`references/azure-key-vault.md`)
- GCP Secret Manager (`references/gcp-secret-manager.md`)

**Self-hosted / cross-platform:**

- HashiCorp Vault (`references/hashicorp-vault.md`)
- Kubernetes-native: External Secrets Operator pulling from any of the above into K8s Secrets (`references/k8s-external-secrets.md`)

Pick one per project; the agnostic-everywhere stance ships refs for all.

### 3. Injection patterns

Three patterns, in increasing security strength:

| Pattern | Description | When |
|---|---|---|
| **Env var at startup** | Secret loaded by orchestrator, set as env var, app reads. | Simple. Default for most services. |
| **Mounted file at startup** | Secret loaded as a file mount, app reads file path. | Better for large secrets (TLS certs); enables some rotation patterns. |
| **Per-call retrieval** | App authenticates to secret store at each access. | High-security; supports automatic rotation without app restart. |

Env-var injection is the default. Per-call retrieval is used when rotation must be transparent (e.g., signing keys rotated without service restart).

### 4. Application code reads through a config layer

Code never reads `process.env.DB_PASSWORD` directly throughout the codebase. There's a **config layer** (one module / class / namespace) that reads from the environment, validates, and exposes typed config to the rest of the code:

```typescript
// src/lib/config.ts
import { z } from 'zod';

const ConfigSchema = z.object({
 db: z.object({
 url: z.string.url,
 poolSize: z.coerce.number.int.positive.default(10),
 }),
 redis: z.object({
 url: z.string,
 }),
 externalApi: z.object({
 baseUrl: z.string.url,
 apiKey: z.string.min(1),
 }),
 logLevel: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export type Config = z.infer<typeof ConfigSchema>;

export function loadConfig: Config {
 const raw = {
 db: { url: process.env.DB_URL, poolSize: process.env.DB_POOL_SIZE },
 redis: { url: process.env.REDIS_URL },
 externalApi: { baseUrl: process.env.EXTERNAL_API_URL, apiKey: process.env.EXTERNAL_API_KEY },
 logLevel: process.env.LOG_LEVEL,
 };
 return ConfigSchema.parse(raw); // throws on missing/invalid; fail fast at startup
}
```

Single point of contact with the environment. Validated at startup. Typed thereafter.

### 5. Rotation

Every secret has a rotation policy:

| Secret class | Rotation cadence |
|---|---|
| Service-to-service auth tokens | 90 days (or shorter) |
| Database passwords | 90 days |
| External-service API keys | per vendor; manual if vendor doesn't support automation |
| Signing keys (JWT, webhook) | 180 days with key-rollover window |
| TLS certificates | per CA; typically 90 days with cert-manager auto-rotation |
| Encryption keys (data at rest) | 365 days (KMS-rotated; key envelope) |

Automated rotation preferred over manual. The platform's secret store often provides this (AWS Secrets Manager rotation, GCP Secret Manager versions + alias, Vault dynamic secrets).

### 6. Access policy (least privilege)

Each service reads only the secrets it needs:

- **Per-service identity** — services authenticate to the secret store as themselves (workload identity, K8s service accounts with IRSA / Workload Identity / IAM).
- **Per-secret access policy** — IAM/RBAC granting read-only access to specific secrets only.
- **No god accounts** — no single identity reads all secrets except an explicitly-scoped break-glass role.

The access policy is in `iac` (provisioned alongside the secret store) and audited in `compliance-privacy`.

### 7. Audit logging

The secret store logs every access:

- **Who** read the secret (service identity).
- **When** (timestamp).
- **What** (which secret version).
- **From where** (caller IP / network identity).

Logs are immutable, retained per the compliance regime, and reviewable. Unusual patterns (e.g., a service reading a secret it never used before) feed the security review.

### 8. Pipeline secrets

CI/CD pipeline secrets follow the same discipline:

- Stored in the CI system's secret manager (GitHub Secrets, GitLab CI variables, Azure DevOps variable groups linked to Key Vault).
- Scoped to the minimum jobs that need them.
- Production deploy credentials NOT available in PR builds.
- OIDC federation to cloud providers (no long-lived cloud creds in CI; ephemeral tokens issued per build).

### 9. Local development

Developers need *some* config to run the app locally. The pattern:

- `.env.example` checked into the repo with the *shape* of required env vars and dummy values.
- `.env.local` (gitignored) with the developer's actual values.
- For secrets that need to be real (e.g., dev API keys), use a developer-secrets-vault flow (e.g., `direnv` + `aws sso` for AWS; `gh` for GitHub Actions OIDC tokens locally).
- Never sharing `.env` files via Slack / email / Notion.

### 10. Audit gates

`secure-coding` audits include:

- **No secrets in code** — gitleaks / trufflehog in pre-commit + CI.
- **No secrets in logs** — log scanning at the boundary; PII + credential patterns redacted.
- **No secrets in error responses** — error handlers never echo internal config.
- **No secrets in image layers** — image scanning checks ENV vars baked into layers.

Any finding is a blocker.

## Outputs

| Output | Location |
|---|---|
| Config schema (per service) | `src/lib/config.ts` (or stack equivalent) |
| Secret-store integration | platform-specific reference; provisioned via `iac` |
| Rotation policy | `.project/procedural/secrets-rotation-policy.md` |
| Access policy (per-service) | provisioned in `iac`; documented in `.project/operational/secrets-access.md` |
| `.env.example` | repo root |

## Platform-specific references

Concrete integration patterns per secret store:

- **AWS Secrets Manager / Parameter Store** — `references/aws-secrets-manager.md`
- **Azure Key Vault** — `references/azure-key-vault.md`
- **GCP Secret Manager** — `references/gcp-secret-manager.md`
- **K8s External Secrets Operator** — `references/k8s-external-secrets.md`
- **HashiCorp Vault** — `references/hashicorp-vault.md`

## Mode handling (G/B)

**Greenfield.** Apply the discipline from day one. The config layer exists before any feature code does.

**Brownfield.** Audit the existing secret-handling posture (`secure-coding` brownfield mode). Migrate one secret class at a time; each migration is its own slice. Hardcoded prod credentials are blocker-debt; secrets in logs are blocker-debt; commit history with leaked secrets requires history rewrite + rotation.

## What this skill does not do

- Provision the secret store — that's `iac`.
- Implement the secret-store SDK calls — those are language-specific and live in the stack packs or in the config-layer code.
- Enforce policy on the secret store — that's a platform-level concern via IAM/RBAC, provisioned in `iac`.
- Run penetration tests against the secret-handling — that's an audit activity.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "It's just dev; secrets in .env are fine." | Dev .env files end up committed, shared via slack, screenshot in bug reports. Use a secrets manager from day one. |
| "Encryption-at-rest is enough." | Without rotation, key management, and access policies, encrypted-at-rest is one credential away from exposed. |
| "We'll rotate manually quarterly." | Manual rotation breaks during turnover. Automate rotation or accept that it won't happen. |
| "Env vars are the secret store." | Env vars leak via process listing, crash dumps, child processes. Use a manager that injects on read, not at process start. |
| "The cloud secret manager is the source of truth." | True at runtime. But who reviews access policies? Audit them like code. |
| "Secret access logs aren't useful." | They're the only signal that detects compromised credentials. Send to SIEM. |
| "Rotation breaks dependencies; postpone." | Designing for rotation IS the discipline. Without it, secrets never rotate. |

## Verification

You are done when:

- [ ] All secrets stored in a managed secret store (AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / Vault).
- [ ] Zero secrets in code / configs / commit history (verified with `git secrets` or equivalent).
- [ ] Rotation policy documented per secret class (API keys: 90 days; DB creds: 30 days; etc.).
- [ ] Rotation tested at least once (not just configured).
- [ ] Access policy follows least-privilege; access reviewed.
- [ ] Secret access logged to centralized audit.
- [ ] Application reads secrets at runtime (not bake-time); cache TTL respects rotation.
- [ ] Disaster recovery: how to recover access if the secret store fails.

Evidence to check:
- `git log -p --all -S<secret-fragment>` shows no historical exposures.
- Rotation runbook exists and was last exercised within target cadence.

## Anti-patterns

- Secrets in code, config files, or commit history.
- `.env` files committed to the repo.
- "Dev secrets are fine in Slack" — they're a foothold; rotate them.
- Long-lived static cloud credentials in CI (use OIDC federation).
- Reading `process.env.*` throughout the codebase (centralize in config layer).
- No rotation policy. Set one even if "we'll automate later" — manual cadence is better than none.
- Logging secrets, even at DEBUG level (DEBUG logs end up in production sometimes).
- Failing silently when a secret is missing (fail fast at startup is the correct behavior).
