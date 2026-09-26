---
name: environments
description: "Define and stand up the environment ladder (dev → test → staging → prod, plus ephemeral preview/PR envs), parity discipline (so what passes staging works in prod), data seeding strategy, access control per environment, and promotion rules between them. Platform/SRE owns the environment definitions; all other agents respect the parity and promotion contracts. Use whenever a new project's environment ladder is being designed, when adding a new environment (e.g., a load-testing env), or when staging behavior diverges from production behavior and parity is being restored."
---

# Environments

<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: infra
state: active
dependencies:
  - iac
  - secrets-config
  - nfr-definition
triggers:
  - "designing the environment ladder for a new project"
  - "adding a new environment (load-testing, demo, dr)"
  - "establishing or improving parity between staging and production"
  - "configuring access control per environment"
  - "defining promotion rules between environments"
outputs:
  - environment matrix (per env: purpose, scale, data, access, lifecycle)
  - parity checklist (how staging mirrors production)
  - data seeding plan (per environment)
  - promotion rules between environments
  - ephemeral environment lifecycle (PR previews / feature envs)
consumers:
  - platform-sre (primary author)
  - deploy-release (consumes the environment ladder for promotion)
  - using-praxis (consumes for slice lifecycle)
  - qa-engineer (acceptance testing happens in specific environments)
  - cicd-pipeline (pipeline stages map to environment promotions)
references: []
```
<!-- praxis:metadata:end -->

The environment ladder is the journey a change takes from a developer's laptop to a paying customer. Each rung exists for a reason; each has a contract; each has a promotion rule. Done right, what passes staging works in production — because staging is *close enough* to production that the differences don't hide bugs. Done wrong, staging is a fairy tale and production is a series of surprises.

## When this skill fires

- A new project's environment ladder is being designed.
- A new environment is being added (load-testing, demo, DR / failover, regional).
- Staging behavior diverges from production behavior; parity is being audited and restored.
- Access control per environment is being established.
- Promotion rules between environments are being defined or revised.

## The standard ladder

Most projects use four permanent environments plus ephemeral PR previews:

```
┌─────────┐   ┌────────┐   ┌─────────┐   ┌────────────┐
│   dev   │ → │  test  │ → │ staging │ → │ production │
└─────────┘   └────────┘   └─────────┘   └────────────┘
     ↑
┌─────────────┐
│ PR previews │  (ephemeral; spun up per PR)
└─────────────┘
```

Each has a distinct purpose, scale, data, access, and lifecycle.

### Dev

- **Purpose:** Developer integration; first place code from main lands.
- **Scale:** Small. One node pool, modest DB.
- **Data:** Anonymized snapshot of staging or synthetic.
- **Access:** All engineers; broad read/write.
- **Lifecycle:** Persistent; redeployed on every main merge.
- **SLO:** No SLO; outages are dev's problem to fix.

### Test (or integration / qa)

- **Purpose:** QA acceptance testing; integration with stable external services.
- **Scale:** Medium. Approximates production's *shape* (multi-AZ, multi-tier) but smaller.
- **Data:** Curated test datasets — covers known edge cases. Reset on a schedule.
- **Access:** Engineers + QA; controlled write access.
- **Lifecycle:** Persistent; deployed on tagged release candidates.
- **SLO:** Best-effort.

### Staging

- **Purpose:** Production-mirror for final verification. Used for chaos / perf / DR tests.
- **Scale:** Approximates production. Same instance types, same multi-AZ, same dependency topology. Often smaller node counts (cost trade-off) but architecturally identical.
- **Data:** Realistic but anonymized or synthetic. NOT real production data unless the compliance regime explicitly allows.
- **Access:** Restricted; service accounts + on-call engineers. No general engineer write access.
- **Lifecycle:** Persistent; deployed on release candidates that have cleared test.
- **SLO:** Production-like; treated as a real environment.

### Production

- **Purpose:** Real users; real load; real consequences.
- **Scale:** Full production. Sized per `capacity-resource-estimation` (Chunk C of this wave).
- **Data:** Live customer data.
- **Access:** Most-restricted. Service accounts + break-glass for incidents. Direct access requires governance approval.
- **Lifecycle:** Continuous; deployed via `deploy-release` (rolling / canary / blue-green).
- **SLO:** Per the NFR register; tracked continuously.

### PR previews / ephemeral environments

- **Purpose:** Per-PR full-stack preview. Useful for FE-heavy work, design review, stakeholder demos before merge.
- **Scale:** Minimal. Just enough to render the change.
- **Data:** Shared with dev or per-preview synthetic.
- **Access:** PR author + reviewers; auto-expire after PR merge / close.
- **Lifecycle:** Created on PR open; destroyed on PR close or after N days idle.
- **SLO:** None.

Not every project needs all rungs. Small projects might collapse `dev` + `test` into one. Highly-regulated projects might add a separate `compliance` environment for audit-bearing tests.

## Parity discipline

The single most important property of the ladder: **staging behavior predicts production behavior**.

Parity is *not* "same number of replicas" — it's structural parity. The list of dimensions to mirror, ranked by importance:

| Dimension | Parity rule |
|---|---|
| Network topology | Same VPC structure, same subnets, same security groups (sized smaller is fine). |
| Instance types | Same family (`m5.xlarge` in prod can be `m5.large` in staging — same family, smaller). NOT `t3` in staging vs. `m5` in prod (different CPU credit behavior). |
| Multi-AZ / regions | Same — single-AZ staging hides AZ-failover bugs. |
| Database engine + version | EXACTLY same (Postgres 16.2 in prod is Postgres 16.2 in staging, not 15.x). |
| Dependency versions | EXACT version pins across environments. |
| Configuration shape | Same env-var names, same secret-store paths, same feature flags. Values differ; shape doesn't. |
| Identity model | Same IAM/RBAC structure; identities differ. |
| Observability stack | Same logging / metrics / tracing tools and instrumentation. |
| Resource limits | Container memory/CPU limits set in staging the same as production (catches OOM patterns). |
| TLS / auth | Same TLS versions, same auth flows. Self-signed certs in staging are fine; the flow is the same. |

Parity is *deliberately* not 1:1 on scale (cost). It IS 1:1 on shape.

## Parity audit

Quarterly (or on schedule per project), a parity audit checks staging against production:

- IaC diff: what's different between `infra/environments/staging/` and `infra/environments/production/`?
- Runtime config diff: what env vars / feature flags differ in shape (not value)?
- Dependency version diff: any unintentional version skew?

Findings go to `tech-debt-management` and are addressed proactively.

## Data seeding strategy

Each environment's data tells a story:

- **Dev** — synthetic or recent anonymized snapshot. Reset weekly.
- **Test** — curated test data; covers happy paths + edge cases + regression cases. Reset before each release candidate.
- **Staging** — realistic-shape synthetic OR anonymized production snapshot. Refreshed on a schedule (monthly / quarterly).
- **Production** — actual customer data; never copied raw to lower environments unless the compliance regime explicitly allows (and even then, anonymize).
- **PR previews** — share dev's data or use synthetic.

**PII never flows downward unanonymized**. Production-to-staging snapshots are anonymized at the transfer boundary. Tools: synthetic data generators (Faker, Hazy, Tonic), or anonymization SQL pipelines. The anonymization itself is reviewed code, not a side-script.

## Promotion rules between environments

Each promotion is a *gated transition*:

| Promotion | Gates |
|---|---|
| dev → test | All unit + integration tests pass. CI pipeline green. |
| test → staging | QA acceptance signed; perf-test smoke passes; canary signals OK. |
| staging → production | `production_go_live` governance gate per `governance.yaml`. Pre-prod readiness: DR drill recent pass, capacity sized, observability live, rollback plan armed. |

The `cicd-pipeline` skill wires these gates. The `deploy-release` skill executes the promotion (rolling / canary / blue-green). The governance matrix (Section 7 of blueprint) names the approvers.

## Access control per environment

| Environment | Engineer write access | Service account scope | Break-glass |
|---|---|---|---|
| Dev | All engineers | broad | n/a |
| Test | All engineers + QA | broad | n/a |
| Staging | Restricted (Platform/SRE; on-call) | scoped per service | logged; reviewed weekly |
| Production | Service accounts only | minimum-privilege per service | logged; reviewed per incident |

Direct human access to production for ad-hoc debugging is the exception (break-glass), not the rule. Every break-glass session is logged and reviewed.

## Ephemeral environment lifecycle

PR previews:

- **Created** on PR open, by a CI workflow that:
  - Provisions a minimal stack (often just the changed app + a fresh K8s namespace + a dev-tier DB or fixture).
  - Deploys the PR's build to that stack.
  - Posts the URL to the PR for reviewers.
- **Destroyed** on PR close (merge or abandon), or after N days of inactivity (resource cleanup).
- **Cost-capped** — alerts if total active previews exceed a budget.

Feature environments (longer-lived than PR previews, shorter than test):

- Spawned on demand for stakeholder demos or long-running parallel work.
- Time-boxed (default 30 days; explicit renewal required).
- Same cleanup discipline.

## Outputs

| Output | Location |
|---|---|
| Environment matrix | `.project/procedural/environments.md` |
| Parity checklist + audit log | `.project/operational/parity-audit-{date}.md` |
| Data seeding plan | `.project/procedural/data-seeding.md` |
| Promotion rules | `.project/procedural/promotion-rules.md` (referenced by cicd-pipeline) |
| Ephemeral environment lifecycle | `.project/procedural/ephemeral-envs.md` |

## Mode handling (G/B)

**Greenfield.** Build the ladder from the standard 4 + ephemeral; calibrate per project shape.

**Brownfield.** Audit the existing ladder. Common findings: dev and staging have drifted from production; ephemeral environments don't exist; data seeding is ad-hoc. Prioritize parity restoration before pursuing other improvements — a staging that doesn't predict production is worse than no staging.

## What this skill does not do

- Provision the infrastructure — that's `iac`.
- Deploy applications into environments — that's `deploy-release`.
- Run tests in environments — that's `testing-strategy` and `performance-testing` / `chaos-engineering`.
- Size environments — that's `capacity-resource-estimation` (Chunk C of this wave).
- Manage secrets per environment — that's `secrets-config`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Dev + staging + prod is enough." | Until you need preview environments per PR, perf testing isolation, or stage-2 staging. Plan the topology deliberately. |
| "Staging is identical to prod." | Almost never. Document the deltas; tests at staging carry caveats. |
| "Use prod data in staging for realism." | Production data in staging is a regulated-data leak. Use synthetic or pseudonymized. |
| "Environments are just config files." | Environments include: infrastructure, data, secrets, monitoring, on-call, access controls. Configure all. |
| "Resource sizing matches prod." | Stage typically smaller — by design. Document scale ratios; test that scale-dependent code doesn't surprise. |
| "Production-only configs are tested in production." | Then they fail in production. Find a way to test them earlier (config validation, dry-run, dedicated mini-prod). |

## Verification

You are done when:

- [ ] Environments enumerated (dev / preview / staging / prod / DR) with purpose per environment.
- [ ] Config externalized per environment; no environment-specific code.
- [ ] Data strategy per environment (sample / synthetic / pseudonymized / production-snapshot).
- [ ] Promotion process documented (artifact promotion vs rebuild).
- [ ] Access controls per environment (who can deploy, who can read data, who can change config).
- [ ] Monitoring + alerting wired per environment (not just prod).
- [ ] Cost limits per non-prod environment.
- [ ] Cleanup policy for preview / ephemeral environments.

Evidence to check:
- A change can be reproduced from one environment to the next without code changes.
- Staging-to-prod delta documented; deltas considered in testing.

## Anti-patterns

- Staging that's "production minus the load-balancer" or "production minus multi-AZ" — hides bugs.
- Real production data copied unanonymized to lower environments.
- Different framework or database versions across environments (skew bugs).
- Engineers debugging production directly without break-glass logging.
- PR previews that never get cleaned up (cost balloon).
- Promotion gates that can be bypassed "for hot-fixes" — emergencies follow the gates with shorter timelines, not bypassed gates.
- Data seeding via ad-hoc scripts not in version control.
- No DR / failover environment when DR is in the NFR register.
