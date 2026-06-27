---
name: deploy-release
description: Release workflow and deployment strategies. Rolling / blue-green / canary / progressive delivery, feature flags, semantic versioning + changelog discipline, rollback discipline, image-signature verification before pull, post-deploy verification, and the production_go_live gate evidence package. Platform/SRE owns deployments; Backend + Frontend Developers consume the deploy pipeline as the path their artifacts take to production. Use whenever a release is being designed, when a new deployment strategy is being chosen, or when a rollback is being planned.
capability: build-and-deploy
domain: infra
state: active
dependencies:
 - cicd-pipeline
 - containerization
 - iac
 - environments
 - secrets-config
 - observability
triggers:
 - "designing the release workflow for a new project"
 - "choosing a deployment strategy (rolling / blue-green / canary / progressive)"
 - "establishing the rollback plan for a service"
 - "wiring feature flags into the release process"
 - "preparing the production_go_live gate evidence"
 - "executing a deployment"
outputs:
 - release plan per service
 - deployment strategy decision + ADR
 - rollout config (manifests / GitOps repo content / cloud-native deploy specs)
 - rollback runbook
 - post-deploy verification checklist
 - production_go_live evidence package
consumers:
 - platform-sre (primary author and executor)
 - delivery-lead (coordinates the slice's deployment)
 - qa-engineer (verifies post-deploy)
 - incident-runbook (consumes rollback runbook)
 - reliability-dr (consumes for DR coordination)
references:
 - kubernetes-rollouts.md
 - argo-rollouts.md
 - aws-codedeploy.md
 - feature-flags.md
---

# Deploy & Release

The artifact is built (per `cicd-pipeline`), packaged into a signed image (`containerization`), and the infrastructure is provisioned (`iac`). This skill takes the artifact and *runs it in production* — safely, observably, reversibly. Done right, deployments are routine; done wrong, they're the primary source of outages.

The principle: **every deploy is a hypothesis ("this change is safe"); the rollout strategy is the experimental design that tests the hypothesis with minimum blast radius.**

## When this skill fires

- A new project's release workflow is being designed.
- A new deployment strategy is being chosen for a service.
- A rollback plan is being established or revised.
- Feature flags are being wired into the release process.
- The production_go_live gate evidence is being assembled.
- A deployment is being executed.

## The deployment strategies

Three patterns + their combinations. Pick per service based on traffic characteristics, statefulness, and risk tolerance.

### 1. Rolling deployment

The default for stateless services on Kubernetes (the most common case that skill).

- Replace pods/instances **N at a time** while keeping the rest serving.
- New pods come up; pass health checks; receive traffic; old pods drain and terminate.
- No second copy of the service running in parallel; no extra cost.
- Rollback: re-deploy the previous version with the same rolling pattern.

Tradeoff: bad releases reach 100% of traffic incrementally but quickly (typically minutes). Some traffic always hits the new version.

### 2. Blue-green deployment

Two full environments (blue = current, green = new). Switch traffic instantly between them.

- Deploy the new version to the inactive environment (green) without traffic.
- Verify it (smoke tests, internal traffic shadow).
- Switch the load balancer / DNS to point at green; blue becomes the standby.
- Rollback: switch back to blue (seconds).

Tradeoff: 2× infrastructure cost during the switch. Database schema changes are hard (both versions read/write the same DB during the switch — schema must be backward-compatible during the cutover, which is the `data-modeling` skill's expand-contract pattern). Excellent rollback time.

### 3. Canary deployment

A subset of traffic goes to the new version; the rest stays on the old.

- Deploy new version alongside old (e.g., 5% of pods are new, 95% old).
- Route 5% of traffic to the new version.
- Observe key metrics (error rate, latency, business signals).
- If healthy after a soak period (minutes to hours), progressively expand (10%, 25%, 50%, 100%).
- If unhealthy, roll back the canary; full traffic remains on old version.

Tradeoff: complex routing; needs traffic-shifting infrastructure (service mesh / weighted-Service / Argo Rollouts / managed deploy services). Excellent risk reduction.

### 4. Progressive delivery (canary + feature flags)

Decouples *deployment* from *release*: code ships to production behind feature flags; the flag is flipped to expose the feature progressively (% of users, by cohort, by region).

- Deploys the *code* via canary or rolling (low-risk; the change is dark).
- Flips the *feature flag* progressively (1% → 10% → 50% → 100% of users / by criteria).
- Observe metrics per cohort; halt or roll back the flag rollout if signals degrade.

This is the modern best practice for high-velocity teams. Requires feature-flag infrastructure (LaunchDarkly, Unleash, ConfigCat, OpenFeature, or self-hosted).

### Picking a strategy

| Service shape | Recommended |
|---|---|
| Stateless, K8s-native, modest scale | Rolling |
| Stateless, K8s-native, large scale + low-risk-tolerance | Canary |
| Stateful (DBs, brokers) | Blue-green with backward-compatible schema; or no-rolling singletons |
| User-facing features with experimentation needs | Progressive delivery (canary + flags) |
| Batch jobs / cron | Just deploy the new version; rollback via re-deploy of the old version |

Decisions go in the project's release-strategy ADR.

## Rollback discipline

Every deployment must have an explicit rollback path *before* it deploys.

**Forward-only rollback** (preferred for most cases): rolling-deploy the previous image SHA. This is the simplest, lowest-risk approach when:

- The change has no schema mutation (or the schema change is backward-compatible).
- The deployment took minutes; rolling back takes the same minutes.

**Instant rollback** (blue-green): switch traffic back. Used when the rollback must complete in seconds (e.g., a global outage).

**Feature-flag rollback**: flip the flag off. Used in progressive delivery; doesn't require a redeploy.

**Database rollback**: schema rollbacks are expensive (data may have been written in the new shape). The discipline: schema changes follow the **expand-contract** pattern from `data-modeling` — never destructive in one deploy. Application code rolls back; schema stays expanded; contract phase happens later.

The rollback plan is part of every deploy's evidence:

```markdown
# Rollback plan — release vX.Y.Z

## Trigger conditions
- p99 latency > 500ms for 5 minutes
- 5xx error rate > 1%
- Manual: on-call discretion

## Procedure
1. Disable the feature flag (if applicable): <flag-name> → false.
2. If not flag-only: re-deploy previous image SHA (<prev-sha>).
3. Verify recovery (next 10 minutes of dashboards).
4. Write postmortem if customer-impacting.

## Expected duration to recovery
< 5 minutes (flag flip) / 10 minutes (re-deploy).
```

## Pre-deploy verification (before the deploy starts)

The pre-deploy checks happen automatically in the pipeline (`cicd-pipeline`):

- Image signature verified (cosign / equivalent).
- SBOM + provenance attestation verified.
- Vulnerability scan passed (or risk-acceptance ADR in place).
- Target environment is healthy (no in-flight incidents).
- Database migrations needed? Apply expand phase first; verify; then deploy app.
- Feature flags relevant to this release configured (default off in production until flip).

## Post-deploy verification (after the deploy completes)

Automated, not optional. Per service:

- **Smoke tests** — a small set of acceptance-style tests run against the deployed environment. Fast (under 5 minutes). Failure triggers automatic rollback.
- **SLO check** — current SLO status from `observability`. If error budget is burning rapidly post-deploy, halt the rollout.
- **Business-metric check** — order rate, sign-up rate, etc., depending on the service. Sudden anomalies trigger investigation.
- **Soak time** — for canary, the soak period before progressing to the next traffic percentage.

If post-deploy verification fails, the rollback procedure kicks in automatically (for canary/progressive) or alerts on-call (for rolling).

## Versioning and changelog

Every release has:

- **Semantic version** (`vMAJOR.MINOR.PATCH`) — bumped per semver rules.
- **Git tag** matching the version (immutable; signed).
- **Changelog entry** in `.project/operational/changelog.md` — what changed, who shipped it, what the rollback ref is.
- **Release notes** — user-facing summary for customers when the change is customer-visible.

The version is set in the artifact's metadata (image label, container annotation) and visible from a `/version` endpoint at runtime.

## Feature flags

Flags decouple deployment from release. Discipline:

- **Flag taxonomy:**
 - **Release flags** — for progressive rollout. Removed after full release.
 - **Experiment flags** — for A/B tests. Removed after experiment.
 - **Permission flags** — for permanent per-user gating. Long-lived.
 - **Kill switches** — for emergency feature-off. Long-lived.
- **Default-off in production** — new flags default to off until explicit flip.
- **Owner per flag** — each flag has a named owner and an expected lifetime.
- **Cleanup discipline** — release flags removed after full rollout. Stale flags (months past their expected lifetime) flagged by `tech-debt-management`.
- **Flag evaluation in observability** — every flag evaluation is observable; experiments measurable.

## The production_go_live gate evidence

When a release reaches the `production_go_live` gate per `governance.yaml`, the evidence package includes:

1. **All pre-prod gates cleared** — Code Review, Security Review, QA Acceptance, staging verification, perf test (if NFR-bearing), chaos engineering (if applicable +).
2. **DR drill recent pass** — within the project's drill cadence.
3. **Capacity sizing verified** — per `capacity-resource-estimation`.
4. **Observability wired** — SLOs defined, dashboards live, alerts armed.
5. **Rollback plan documented** — explicit, with trigger conditions and procedure.
6. **Chaos engineering pass recent** — if the change touches resilience-critical paths.
7. **Compliance evidence** — for regulated environments (HIPAA, PCI, etc.).

The Platform/SRE assembles the evidence; the named approver per the governance matrix signs the gate.

## Outputs

| Output | Location |
|---|---|
| Release strategy decision | `.project/decision/adr-NNNN-deployment-strategy.md` via `adr-decision-records` |
| Rollout config (manifests / GitOps) | repo's `deploy/` directory or GitOps repo |
| Rollback runbook | `.project/operational/runbooks/rollback-{service}.md` |
| Smoke test suite | `tests/smoke/` |
| Release record per release | `.project/operational/releases/release-vX.Y.Z.md` |
| production_go_live evidence pack | `.project/operational/releases/release-vX.Y.Z-evidence.md` |

## Platform-specific references

How the strategy is implemented per runtime:

- **Kubernetes-native rollouts** — `references/kubernetes-rollouts.md` (Deployment rolling, recreate, blue-green via Services)
- **Argo Rollouts** — `references/argo-rollouts.md` (canary + analysis + progressive delivery on K8s)
- **AWS CodeDeploy / cloud-native** — `references/aws-codedeploy.md` (for cloud-managed runtimes like ECS, Lambda, App Service)
- **Feature flags** — `references/feature-flags.md` (LaunchDarkly / Unleash / OpenFeature patterns)

Picked per the `platform-k8s` and cloud choice (+ cloud packs).

## Mode handling (G/B)

**Greenfield.** Design the release strategy from the standard set; align with `platform-k8s` and the cloud pack.

**Brownfield.** Audit the existing release process. Common findings: manual steps, no rollback rehearsal, no signed artifacts, no smoke tests. Migrate incrementally — each improvement is its own slice. Don't change the deployment strategy and the schema migration pattern in the same release.

## What this skill does not do

- Build the artifact — `cicd-pipeline` + `containerization`.
- Provision the infrastructure — `iac`.
- Manage runtime cluster — `platform-k8s` (Chunk C) and cloud packs.
- Verify reliability targets — `reliability-dr`.
- Run perf or chaos tests — `performance-testing` / `chaos-engineering`.
- Coordinate on-call response to deploy failures — `incident-runbook`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Blue/green is too expensive." | At cost-bounded scale, canary or in-place with rollback is fine. Pick deliberately. |
| "We can roll back later if needed." | Rollback procedures untested are rollback procedures broken. Rehearse. |
| "Canary 10% then 100% is the canary." | Canary is gradual + observed at each step (1→10→50→100), with abort criteria. Not a two-step process. |
| "Manual deploys are safer." | Until the one Friday afternoon when steps get skipped. Automate; the human becomes the approver, not the operator. |
| "Feature flags solve everything." | Flags enable gradual rollout but add code complexity. Flag lifecycle (creation → cleanup) is its own discipline. |
| "DB migrations + code deploy can be the same step." | Schema changes precede or follow code, never the same atomic step. Expand-migrate-contract pattern. |
| "Production smoke is the test." | Smoke is verification, not the test. Tests run pre-prod; smoke confirms what passed there is now live. |

## Verification

You are done when:

- [ ] Deployment strategy documented per service (rolling / canary / blue-green / progressive).
- [ ] Rollback procedure documented + last rehearsed within target cadence.
- [ ] Pre-deploy checks: artifact signature verified; SBOM present; gates cleared.
- [ ] Post-deploy verification: smoke tests + key metric stability window.
- [ ] Abort criteria for canary: latency / error / business-metric thresholds.
- [ ] Feature flag lifecycle managed: creation, ownership, cleanup tracked.
- [ ] DB migration plan: expand-migrate-contract or equivalent zero-downtime pattern.
- [ ] Deploy events logged to change-record (per `production_go_live` evidence).

Evidence to check:
- Last rollback rehearsal was within target cadence.
- Canary actually rolls back when abort criterion triggered (tested in staging).

## Anti-patterns

- Deploying without a rollback plan.
- Schema changes deployed in one shot with the app change (no expand-contract).
- Manual deploys to production.
- Pulling unsigned images.
- Smoke tests skipped "because the change was small."
- Feature flags that live forever uncleaned.
- Rolling out canary without observability to decide pass/fail (faith-based deploys).
- Blue-green with shared DB and a forward-incompatible schema change (the brief moment both versions run breaks).
- No rollback rehearsal — the first time you roll back in prod should NOT be in a real incident.
