---
name: cicd-pipeline
description: Pipeline-as-code design. The full build → test → scan → package → sign → publish → deploy chain with quality gates, caching, parallelism, branch strategy, and environment promotion. Per the agnostic-everywhere decision, ships with refs for GitHub Actions, GitLab CI, Azure DevOps Pipelines, and Jenkins — same workflow body, per-CI implementation in the references. Platform/SRE runs this; Backend Developer + Frontend Developer consume the pipeline's gates. Use whenever a new project's pipeline is being designed, when adding gates (security scans, perf tests, chaos), or when migrating between CI systems.
---

# CI/CD Pipeline


<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: infra
state: active
dependencies:
 - engineering-standards
 - testing-strategy
 - code-review
 - secure-coding
 - secrets-config
triggers:
 - "designing a new project's CI/CD pipeline"
 - "adding quality gates (SAST / DAST / SCA / coverage / perf)"
 - "configuring branch strategy and promotion"
 - "migrating between CI systems"
 - "wiring container build + sign + publish into the pipeline"
outputs:
 - pipeline-as-code files (per CI system)
 - quality-gate definitions
 - branching policy + promotion rules
 - artifact-publishing flow
 - signature + provenance attestation (SLSA-aligned)
consumers:
 - platform-sre (primary author)
 - backend-developer (consumes pipeline outcomes; reads logs on failure)
 - frontend-developer (consumes pipeline outcomes; same)
 - code-reviewer (verifies pipeline files like any other code)
 - deploy-release (consumes the published artifact)
references:
 - github-actions.md
 - gitlab-ci.md
 - azure-devops.md
 - jenkins.md
```
<!-- praxis:metadata:end -->

The conveyor belt that turns a merged commit into a deployable, verified, signed artifact. Without it, releases are manual rituals; with it, every change ships through identical machinery — which is the precondition for *every* downstream quality property (reliability, security, reproducibility).

The pipeline is **code in the repo**, not a UI configuration. Same review process; same versioning; same rollback discipline.

## When this skill fires

- A new project's pipeline is being designed — Platform/SRE runs this skill.
- New gates are being added (SAST scanning, DAST, SCA, perf tests, chaos pre-prod runs).
- Branch strategy is changing (trunk-based vs. GitFlow vs. release branches).
- A migration between CI systems is being scoped.

## The pipeline stages

The standard chain. Every project's pipeline has these stages; specifics vary per CI system (see references).

```
1. Trigger (push, PR open, manual, scheduled)
 ↓
2. Setup (checkout, install toolchain, restore caches)
 ↓
3. Lint + Format (static checks: language linter, formatter)
 ↓
4. Type check (tsc --noEmit, mypy, javac, etc.)
 ↓
5. Unit tests (fast; under 30s in CI; fails block downstream)
 ↓
6. Build (compile, transpile, bundle; emit artifact)
 ↓
7. SAST + SCA (static security analysis; dependency scan; SBOM gen)
 ↓
8. Integration tests (Testcontainers; under 5 min in CI)
 ↓
9. Container build (multi-stage; non-root; minimal base)
 ↓
10. Container scan (image vuln scan; base-image provenance)
 ↓
11. Sign + attest (cosign / SLSA provenance attestation)
 ↓
12. Publish (artifact registry; image registry)
 ↓
13. Deploy (downstream deploy-release skill handles this)
```

Each stage **gates** the next. A red unit test stops the build before bytes get spent on the rest.

## The discipline

### 1. Pipeline-as-code, in the repo

The pipeline definition (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`) lives in the project repo alongside the code. It is reviewed like code. It versions with the code. UI-configured CI is a violation — invisible to PRs, untestable, unreviewable.

### 2. Cache aggressively, invalidate correctly

The most leveraged optimization. Caches:

- Dependency caches (npm, Maven, pip wheels, Gradle).
- Compiled artifact caches (Webpack output, native compiled units).
- Test result caches (only re-run tests affected by the diff — Nx, Bazel, Turborepo support this).
- Container layer caches (BuildKit cache exports).

Cache invalidation: keyed on lock-file hashes (`package-lock.json`, `pom.xml` hash, `pyproject.toml` + lock). When the lock changes, cache rebuilds. Stale caches are bugs; correctly-keyed caches are the difference between 30-second and 30-minute CI runs.

### 3. Parallelize across cores AND across stages

- **Within a stage**, parallelize across modules/projects (test sharding, multi-module builds).
- **Across stages**, run independent stages in parallel (lint can run while unit tests run; image build can start while SAST runs).
- **Across PRs**, the CI system handles concurrent runs; ensure runners scale.

Pipeline latency is the team's feedback loop. A 5-minute pipeline gets used; a 45-minute pipeline gets gamed.

### 4. Quality gates (the merge-blocking ones)

Each gate has a *threshold* and a *policy on breach*:

| Gate | Threshold | On breach |
|---|---|---|
| Lint | zero warnings on new code | block |
| Type check | zero errors | block |
| Unit tests | 100% pass | block |
| Coverage | per `testing-strategy` (e.g., 70% global, 80% domain) | block (with exception path) |
| Integration tests | 100% pass | block |
| SAST | no new High/Critical findings | block on new; track existing |
| SCA | no new High/Critical CVEs | block on new; track existing per `supply-chain-security` |
| Container scan | no new High/Critical CVEs in image | block on new |
| License check | only approved licenses | block on unapproved |

Gate definitions live in code (`.coverage-threshold.yml`, `sonar-project.properties`, etc.), not as CI-system buttons.

### 5. Branch strategy

Default: **trunk-based with short-lived feature branches**.

- Main is always shippable.
- Feature branches < 3 days old; merge or close.
- PRs run the full pipeline before merge.
- Merge requires green pipeline + Code Reviewer PASS + Security Reviewer PASS (when applicable) + QA acceptance.
- Tag-based releases promote a green main commit to a release branch (optional) or directly to staging/prod.

GitFlow is the exception, used when:
- Multiple release versions must be supported simultaneously.
- A genuine release-branch lifecycle is needed (long QA windows, multiple stakeholders).

Most SaaS products use trunk-based.

### 6. Container build

If the artifact is a container:

- **Multi-stage Dockerfile** — separate build stage (with toolchain) from runtime stage (minimal base).
- **Minimal base** — distroless or `alpine`/`slim` variants. Never the default JDK / Node image with full OS.
- **Non-root user** — `USER nonroot` in the runtime stage.
- **Layer ordering** — change-frequent layers last (so frequent layers re-build but base layers cache).
- **Reproducibility** — pinned base image SHAs; locked dependencies.
- **BuildKit cache** — exported to the registry for cross-pipeline reuse.

### 7. Sign and attest (SLSA-aligned)

Each published artifact:

- **Signed** via `cosign` (or platform-equivalent) using a keyless signing flow (Fulcio + Rekor) or a managed-key flow.
- **SBOM attestation** — the SBOM from `supply-chain-security` is signed and attached to the image as an attestation.
- **Build provenance** — SLSA-Build-L3 provenance attestation (which commit, which builder, which dependencies — signed by the builder).

The deployment side (`deploy-release`) verifies signatures and attestations before pulling images. End-to-end integrity from commit → production.

### 8. Secrets handling in the pipeline

- Pipeline secrets (registry credentials, signing keys, deploy tokens) live in the CI system's secret store. **Never in code.**
- Rotation policy per `secrets-config`.
- Scoped to minimum privilege — a build job doesn't need deploy credentials.
- Audited — every secret access is logged.

### 9. Notifications

- **Failures notify** the PR author (and the reviewers if the PR is open).
- **Production-pipeline failures** notify the on-call (per `incident-runbook`).
- **Notifications include** the commit, the failing step, the log link, the failure category.
- **Quiet success** — green pipelines don't notify; absence is the signal.

### 10. Reproducibility

A pipeline run from the same commit, given the same inputs, produces *byte-identical* artifacts. Inputs include:

- Pinned toolchain version (`.nvmrc`, `.python-version`, `.tool-versions`, JDK version).
- Pinned base images (SHA, not `:latest`).
- Locked dependencies (`package-lock.json`, `poetry.lock`, `Cargo.lock`, `go.sum`).
- Build flags captured in the artifact's provenance.

Non-reproducible builds are debt; they limit rollback and forensic analysis.

## Outputs

| Output | Location |
|---|---|
| Pipeline-as-code | `.github/workflows/*.yml` (or `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`) |
| Coverage threshold config | `.coverage-threshold.yml` or tool-specific |
| SAST / SCA / container-scan configs | project root (sonar, semgrep, snyk, trivy configs) |
| SBOM | published as image attestation |
| Provenance | published as image attestation |
| Branch strategy doc | `.project/procedural/branch-strategy.md` |

## CI-specific references

The shared workflow body above is identical across CI systems. Per-system implementation lives in:

- **GitHub Actions** — `references/github-actions.md`
- **GitLab CI** — `references/gitlab-ci.md`
- **Azure DevOps Pipelines** — `references/azure-devops.md`
- **Jenkins** — `references/jenkins.md`

The Platform/SRE picks the CI system per `governance.yaml` (the project's CI of record); the reference for that system loads.

## Mode handling (G/B)

**Greenfield.** Design the pipeline from the standard chain; pick the CI system; configure per the reference.

**Brownfield.** Read `.repo-intel/` for the existing pipeline. Migrate incrementally — add new gates to the existing pipeline; refactor whole-system only when the existing pipeline is genuinely beyond extension. Pipeline migrations are high-risk; plan them like data migrations (expand-contract; verify in parallel before cutover).

## What this skill does not do

- Provision infrastructure — that's `iac`.
- Define environments — that's `environments`.
- Deploy artifacts — that's `deploy-release`.
- Define security scans deeply — that's `supply-chain-security`; this skill wires them into the pipeline.
- Define perf tests — that's `performance-testing`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "CI is fine if it builds and runs tests." | CI is also linting, security scanning, SBOM gen, artifact signing, contract tests. Each is a quality gate. |
| "Long pipelines are OK; they catch more." | Long pipelines = slow feedback = developers wait or skip. Optimize for the fast feedback loop. |
| "Flaky tests are part of life." | Flakes erode trust in CI. Quarantine or fix immediately; don't normalize. |
| "Branches build off main." | Branches should test what's about to merge, not what already merged. Use merge queue / merge train if available. |
| "Manual approval gates are sufficient." | Manual gates without enforcement are skipped under pressure. Encode policy in the pipeline. |
| "Artifacts can be rebuilt from source." | Maybe, but timestamps + transitive deps change. Build once, promote; never rebuild for prod. |
| "Cache aggressively for speed." | Cache poisoning is real. Cache scope, invalidation, and trust are all design decisions. |

## Verification

You are done when:

- [ ] Pipeline definitions live in repo (not platform UI clicks).
- [ ] Stages: lint → build → unit test → integration test → security scan → SBOM → artifact sign → contract test → deploy.
- [ ] Every gate fails the build on violation; no soft warnings on critical checks.
- [ ] Build artifact is immutable; promoted across environments (build-once-deploy-many).
- [ ] Flaky tests quarantined within 24 hours; ticket opened.
- [ ] Pipeline runtime budget set; alerts on exceedance.
- [ ] Secrets injected per `secrets-config`; never hardcoded in pipeline.
- [ ] Pipeline observability: success rate, runtime distribution, failure-class breakdown.

Evidence to check:
- A pipeline failure can be reproduced locally with the same artifact + inputs.
- The signed artifact deployed to prod matches the one tested in staging.

## Anti-patterns

- UI-configured CI (clicks instead of code).
- Pipelines that don't sign artifacts.
- Caches keyed on branch name (stale-cache bugs).
- Sequential stages that could parallelize (slow feedback).
- Slow pipelines with no SLA on duration (devs game them).
- Skipping gates "just for this PR" (the gate exists for a reason; either fix or escalate).
- Pipeline secrets in environment files (the secret store exists; use it).
- Non-reproducible builds (limits forensic analysis and rollback).
