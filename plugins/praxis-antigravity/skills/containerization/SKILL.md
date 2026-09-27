---
name: containerization
description: "Production-grade container image discipline. Minimal/distroless base, multi-stage builds, non-root user, layer caching for build speed, image vulnerability scanning, reproducibility (pinned base + locked deps + provenance attestation), signing. Platform/SRE owns the project's container patterns; developers consume the Dockerfile patterns from the stack packs. Use whenever a Dockerfile is being written, when image base choices are being made, or when supply-chain attestation is being wired into the build."
---

# Containerization

<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: infra
state: active
dependencies:
 - engineering-standards
 - cicd-pipeline
triggers:
 - "writing a new Dockerfile"
 - "evaluating base image choices"
 - "wiring container build into the CI pipeline"
 - "hardening an existing image (non-root, smaller surface)"
 - "configuring SBOM + provenance attestation"
outputs:
 - hardened Dockerfile (multi-stage, distroless or slim base, non-root)
 - image-policy document (acceptable bases, scan thresholds, registry rules)
 - BuildKit cache configuration
 - SBOM + provenance attestation (consumed by deploy-release)
consumers:
 - platform-sre (primary author)
 - backend-developer (consumes Dockerfile from stack pack + this skill)
 - frontend-developer (consumes for FE production builds when containerized)
 - supply-chain-security (consumes SBOM)
 - deploy-release (verifies signatures before pulling)
references: []
```
<!-- praxis:metadata:end -->

The container is the unit of deployment. Build them like you'd deploy them: minimal, immutable, auditable, signed. The Dockerfile is the most-leveraged artifact in the project after the source code itself — its choices determine attack surface, startup time, image size, supply-chain posture, and operational cost.

## When this skill fires

- A new Dockerfile is being written — Platform/SRE designs the patterns; developers in the stack packs apply them.
- Existing images need hardening (smaller base, non-root, scan compliance).
- SBOM + provenance attestation is being wired into the build.
- An image-policy revision affects multiple projects.

## The discipline

### 1. Multi-stage builds, always

Separate the **build** stage (with toolchain, dev dependencies) from the **runtime** stage (minimal, just what the app needs to run). The runtime image carries no compilers, no build tools, no source files, no dev dependencies.

Generic pattern:

```dockerfile
# === Build stage ===
FROM <build-base-with-toolchain> AS build
WORKDIR /workspace
COPY <dependency-manifest> .
RUN <install-deps>
COPY <source>
RUN <build>

# === Runtime stage ===
FROM <minimal-runtime-base> AS runtime
WORKDIR /app
COPY --from=build /workspace/<built-artifact> .
USER nonroot
ENTRYPOINT ["<binary>"]
```

Stack-specific examples are in `stack-java-spring/`, `stack-node-ts/`, `stack-python/`, `stack-web-frontend/` SKILL.md files.

### 2. Minimal runtime base

The default runtime image ships *only* what the app needs.

| Base | Use when |
|---|---|
| **`gcr.io/distroless/<lang>-debian12:nonroot`** | Default. Minimal; no shell; nonroot user built in; tiny attack surface. |
| **`alpine:<ver>`** | When the app needs basic shell utilities; small but includes BusyBox. Note: musl libc can cause subtle issues with some binaries. |
| **`<lang>:<ver>-slim`** | When distroless can't satisfy a runtime requirement (e.g., needs glibc + small toolchain). |
| **`scratch`** | Statically-linked binaries only (Go, Rust). Smallest possible image. |

Never the default fat image (`node:20`, `python:3.11`, `openjdk:21`, etc.) for production. Those include build toolchains and full OS — large attack surface and large size.

### 3. Non-root user

The runtime container runs as a non-root user. Distroless `:nonroot` tags handle this; for other bases, explicit:

```dockerfile
RUN addgroup --gid 10001 --system app \
 && adduser --uid 10001 --system --group app
USER app
```

Kubernetes' `runAsNonRoot: true` security context enforces this at the platform level; the image needs to support it (`platform-k8s`).

### 4. Layer caching for build speed

Order layers from **least frequently changing** to **most frequently changing**:

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app

# Layer 1: package manifests (change rarely)
COPY package*.json ./
RUN npm ci

# Layer 2: source code (changes frequently)
COPY src ./src
COPY tsconfig.json ./
RUN npm run build
```

With BuildKit cache exports, the dependency layer is reused across builds even after source changes. The build speed delta is dramatic — every CI run benefits.

### 5. Reproducibility

A Dockerfile built from the same commit + same inputs produces a byte-identical image. Requirements:

- **Pin the base image to a SHA**, not just a tag:
 ```dockerfile
 FROM gcr.io/distroless/java21-debian12:nonroot@sha256:abc123...
 ```
 Tags float; SHAs don't. The lock file equivalent for base images.
- **Lock the dependencies** — every stack pack's lock file is the source of truth.
- **Set timestamps deterministically** — `--build-arg SOURCE_DATE_EPOCH=<commit-timestamp>` so file mtimes don't vary.
- **Avoid `ADD` for remote URLs** — output depends on what's at the URL at build time; non-reproducible.

### 6. Image scanning

Image scans run in the CI pipeline (per `cicd-pipeline`):

- **Vuln scanning** — Trivy / Grype / Snyk / cloud-native scanners. Fail the build on new High/Critical CVEs.
- **Misconfiguration scanning** — checks for risky Dockerfile patterns (`USER root`, `:latest` tags, sensitive secrets in env).
- **Secret scanning** — gitleaks / trufflehog at image build to catch accidentally embedded credentials.

Scan thresholds are project-specific (set in `nfr-definition`'s security section) but the baseline: **no new HIGH or CRITICAL** in production images.

### 7. SBOM and provenance attestation

Every published image carries:

- **SBOM** (Software Bill of Materials) — what's inside the image. Tools: `syft`, `cyclonedx-cli`, Docker Buildx's `--sbom=true`. Format: CycloneDX or SPDX.
- **Provenance attestation** — SLSA-Build-L3 metadata describing how the image was built (commit, builder, dependencies, build parameters). Tools: `cosign attest`, Docker Buildx's `--provenance=true`.

Both are signed and pushed to the registry alongside the image. The deployment side (`deploy-release`) verifies them before pulling.

### 8. Signing

Images are signed via cosign (keyless via Sigstore/Fulcio or with a managed key):

```bash
cosign sign --yes <registry>/<image>:<tag>
cosign attest --predicate sbom.cyclonedx.json --type cyclonedx <registry>/<image>:<tag>
```

Verification (in `deploy-release`):

```bash
cosign verify --certificate-identity-regexp '^https://github\.com/<org>/.*$' \
 --certificate-oidc-issuer-regexp '^https://token\.actions\.githubusercontent\.com$' \
 <registry>/<image>:<tag>
```

The OIDC-bound keyless flow ties signatures to the CI identity — no long-lived signing keys to rotate or leak.

### 9. Image tagging

- **Immutable tags** — every image has a tag derived from the commit SHA (`<image>:<short-sha>` or `<image>:<sha>`). This is the canonical reference.
- **Mutable convenience tags** — `:latest`, `:main`, `:staging` may exist but are pointers; production deploys reference the immutable SHA-tag.
- **No `:latest` in production manifests** — references must be reproducible across rollbacks and audit.

### 10. Registry hygiene

- **Pull-through cache** at the cluster boundary so the registry isn't a deploy-time dependency.
- **Vulnerability re-scanning** of stored images on a cadence (registries support this) — CVEs are discovered after the image is built.
- **Image retention policy** — keep release candidates for some period (e.g., 90 days) for rollback; prune older ones.

## The standard Dockerfile (stack-neutral template)

```dockerfile
# === Build ===
FROM <build-base>@sha256:... AS build
WORKDIR /workspace
COPY <manifests> ./
RUN <install-deps>
COPY <source>
RUN <build>

# === Runtime ===
FROM gcr.io/distroless/<lang>-debian12:nonroot@sha256:...
WORKDIR /app
COPY --from=build /workspace/<artifact> ./
USER nonroot
EXPOSE <port>
ENTRYPOINT ["<binary>"]
```

Stack-specific Dockerfiles live in the stack-pack skill files (`stack-java-spring/SKILL.md`, etc.).

## Image policy document

The project's image policy lives in `.project/procedural/image-policy.md`:

```markdown
# Image Policy

## Allowed bases
- `gcr.io/distroless/java21-debian12:nonroot` (production)
- `eclipse-temurin:21-jdk-jammy` (build only)
- ... (per stack)

## Scanning
- Trivy fs + image; HIGH/CRITICAL block.
- Re-scan in registry every 7 days; alert on new findings.

## Signing
- All production images signed via cosign keyless OIDC.
- Verification policy in deploy-release.

## Tags
- Immutable: `<image>:<commit-sha>`.
- Mutable convenience: `<image>:latest` (main branch only), `<image>:staging`, `<image>:production`.
- Production deploys reference immutable tags only.

## Retention
- Production images: 90 days.
- Staging images: 30 days.
```

## Outputs

| Output | Location |
|---|---|
| Dockerfile per service | service repo root |
| Image policy | `.project/procedural/image-policy.md` |
| BuildKit cache config | CI pipeline (per `cicd-pipeline` reference) |
| SBOM attestation | published with image |
| Provenance attestation | published with image |

## Mode handling (G/B)

**Greenfield.** Apply all disciplines from day one.

**Brownfield.** Read `.repo-intel/` for existing Dockerfiles. Inventory existing images against the policy; flag gaps in `.project/working/container-debt.md`. Migrate one image at a time as slices touch them.

## What this skill does not do

- Deploy the image — that's `deploy-release`.
- Provision the registry — that's `iac`.
- Run vulnerability scans deeply — that's `supply-chain-security`; this skill *wires* the scans into the build.
- Manage runtime cluster configuration — that's `platform-k8s` and `cloud-native` references.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Latest base image tag is fine." | Latest moves under you. Pin base images to digests, not tags. |
| "Run as root inside the container; it's isolated." | Container escapes happen. Run as non-root; least privilege. |
| "One container per VM; no overhead." | The overhead of an idle container is small; the benefit of process isolation is large. |
| "Image size doesn't matter; we have fast networks." | Image size affects pull time, registry cost, attack surface, startup latency. Smaller is better. |
| "Stuff secrets into the env at build time." | Secrets baked into images leak through registries. Inject at runtime per `secrets-config`. |
| "Multi-stage builds are over-engineering." | Multi-stage gives slim runtime images + build-time tooling. Standard discipline. |
| "Dev image == prod image." | Dev image typically has shell, debug tools. Prod image should not. Different artifacts. |

## Verification

You are done when:

- [ ] Dockerfile uses multi-stage build; final image is minimal.
- [ ] Base image pinned to digest (not tag).
- [ ] Image runs as non-root user (USER directive).
- [ ] Healthcheck defined.
- [ ] Image scanned for CVEs in CI; severity blocks merge.
- [ ] SBOM generated per image (per `supply-chain-security`).
- [ ] Image signed (cosign or equivalent).
- [ ] Secrets are NOT in the image; injected at runtime.
- [ ] Image size documented + tracked (regression alarm if growth exceeds threshold).
- [ ] OCI-compliant labels populated (source, version, license).

Evidence to check:
- `docker history` shows no sensitive content.
- Image runs in production with read-only root filesystem.

## Anti-patterns

- Using `:latest` tags in production manifests.
- `USER root` in the runtime stage.
- Fat base images (`node:20`, `python:3.11`) in production.
- Copying the entire repo into the image (use `.dockerignore`).
- Secrets baked into image layers (`ENV API_KEY=...` is permanently in the layer history).
- Build args passing secrets (visible in image metadata; use BuildKit secrets).
- Dockerfile without `HEALTHCHECK` or equivalent for orchestrator liveness/readiness.
- Single-stage builds for compiled languages (drags toolchain into production).
- `ADD` with remote URLs (non-reproducible).
- Missing SBOM and provenance attestation.
