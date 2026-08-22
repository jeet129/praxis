---
name: supply-chain-security
description: "Dependency hygiene and build-provenance discipline. SCA scanning, SBOM generation + attestation, pinned/locked dependencies, license checks, base-image provenance, SAST and DAST wiring, signed artifacts (cosign), SLSA-Build-L3 provenance. Platform/SRE wires the scans into cicd-pipeline; Security Reviewer audits findings; tech-debt-management tracks unpatched CVEs. Use whenever a project's pipeline is being designed, when adding new dependencies, when investigating an SCA finding, or when establishing the dependency-policy and rotation cadence."
---

# Supply Chain Security

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
 - cicd-pipeline
 - containerization
 - secure-coding
triggers:
 - "wiring SCA / SAST / DAST into the build pipeline"
 - "generating and signing SBOM + provenance attestation"
 - "investigating an SCA finding (CVE in a dependency)"
 - "establishing dependency policy + rotation cadence"
 - "auditing existing dependencies + base images for known CVEs"
 - "license compliance check"
outputs:
 - SBOM (CycloneDX / SPDX) per build, signed and attested
 - SLSA provenance attestation per build
 - SCA scan reports (dependencies)
 - SAST scan reports (own code)
 - DAST scan reports (deployed surface)+
 - dependency policy (allowed licenses, vendor allowlist, version pinning rules)
 - vulnerability response plan (severity → response time)
consumers:
 - platform-sre (wires the scans)
 - security-reviewer (audits findings)
 - code-reviewer (consumes scan results in PR review)
 - compliance-privacy (uses SBOM + provenance for compliance evidence)
 - deploy-release (verifies signatures before pull)
 - tech-debt-management (tracks unpatched CVEs)
references: []
```
<!-- praxis:metadata:end -->

The discipline that defends the code from the *dependencies it brings in*. Modern applications are 80–95% third-party code by volume; a vulnerability or malicious package upstream is a vulnerability in the application. This skill keeps the supply chain visible, signed, and auditable end-to-end.

The principle: **trust nothing implicitly; sign everything; track everything; respond fast.**

## When this skill fires

- A project's CI pipeline is being designed — wire SCA / SAST / DAST gates.
- A new dependency is being added — verify licensing, security posture, signing.
- An SCA finding (CVE) appears — assess severity, plan remediation.
- Dependency policy is being established or revised.
- Existing dependencies are being audited (brownfield onboarding; post-incident).
- SBOM + provenance attestation needs verification at deploy time.

## The components

### 1. Dependency scanning (SCA)

Software Composition Analysis: identify known vulnerabilities in dependencies.

Tools:
- **Trivy / Grype** — fast, open-source, broad CVE database coverage.
- **Snyk** — managed; deeper context; commercial.
- **Dependabot / Renovate** — automated PR generation for updates.
- **OSV-scanner** — Google's curated vulnerability database.

Wiring into `cicd-pipeline`:
- Per PR: scan dependencies; fail build on new High/Critical CVEs.
- Scheduled (daily): re-scan production-deployed dependencies; alert on new CVEs that affect them.
- Result: SCA report stored per build; severity-tagged.

### 2. Static application security testing (SAST)

Scan the application's *own code* for security patterns.

Tools:
- **Semgrep** — fast, pattern-based, rule-customizable. Default for most projects.
- **CodeQL** (GitHub) — deeper analysis; semantic queries; longer runtime.
- **SonarQube** — commercial; broader code-quality + security.
- Language-specific: gosec (Go), bandit (Python), ESLint security plugin (JS/TS), SpotBugs (Java).

Wiring:
- Per PR: scan changed files + their references; fail on new findings above threshold.
- Comments inline on PR for findings.
- Result: SAST report; findings tagged with severity + suggested fix.

### 3. Dynamic application security testing (DAST)

Scan the *deployed application* for vulnerabilities that only manifest at runtime.

Tools:
- **OWASP ZAP** — open-source web app scanner; baseline + active scans.
- **Burp Suite** — commercial; deeper.
- Cloud-native: AWS Inspector, Azure Defender, etc.

Wiring: typically runs against staging on a schedule (daily or weekly), not per-PR. deepens DAST integration; baseline is scheduled staging scans.

### 4. SBOM (Software Bill of Materials)

A complete list of components in the artifact. Per `containerization` skill, generated at build time:

```bash
# CycloneDX format (default)
syft <image-ref> -o cyclonedx-json > sbom.cdx.json

# SPDX format (alternative)
syft <image-ref> -o spdx-json > sbom.spdx.json
```

The SBOM:
- Captures dependency tree (direct + transitive).
- Attached as an attestation to the published image (per `cicd-pipeline`).
- Verified at deploy time (per `deploy-release`).

### 5. SLSA Build provenance

Per `containerization` and `cicd-pipeline`, every published image has a SLSA-Build-L3 provenance attestation:

- Which commit was the build from?
- Which builder built it?
- What dependencies were resolved?
- What build parameters were used?

The attestation is signed (cosign keyless via OIDC); deploy-time verification confirms the image came from the expected builder + commit.

### 6. Signing and verification

Per `cicd-pipeline`'s sign-and-attest stage, every published artifact:

- Signed via `cosign sign` (keyless OIDC flow).
- SBOM and provenance attached as attestations.
- Verified at deploy-time:

```bash
cosign verify --certificate-identity-regexp '^https://github\.com/myorg/.*$' \
 --certificate-oidc-issuer-regexp '^https://token\.actions\.githubusercontent\.com$' \
 <registry>/<image>:<tag>
```

Unsigned images are rejected at deploy time.

### 7. Dependency policy

Project-level policy (in `.project/procedural/dependency-policy.md`):

| Rule | Threshold |
|---|---|
| License allowlist | Allowed: MIT, Apache-2.0, BSD-2/3, ISC, MPL-2.0. Denied: GPL/AGPL (project-specific); unlicensed. |
| Version pinning | All direct deps pinned to exact versions in lock file. |
| Transitive deps | Pinned via lock file; managed by lock-file-only updates. |
| Update cadence | Dependabot / Renovate PRs reviewed within 7 days. Security updates within 24h. |
| Vendor allowlist | Internal mirror / proxy if using one; explicit allowlist of registries. |
| Pre-release / RC dependencies | Forbidden in production paths unless ADR. |
| Maintenance signal | Dependencies with no commits > 1 year flagged for replacement consideration. |

### 8. Vulnerability response plan

When a new CVE affects a dependency:

| Severity | Response time | Action |
|---|---|---|
| Critical | 24h | Patch immediately; emergency change ADR; deploy through accelerated path. |
| High | 7 days | Patch in next slice; if patch unavailable, mitigate (WAF rule, config change). |
| Medium | 30 days | Patch in normal cadence; track. |
| Low | 90 days | Patch in normal cadence; may be batched. |

For unpatched dependencies (no fix available upstream):
- Document in `.project/operational/risk-acceptances/`.
- Implement compensating controls.
- Monitor for fix availability.
- If business-critical: consider replacing the dependency.

### 9. License compliance

Every dependency's license is captured (SBOM does this). Project policy specifies allowed licenses; violations fail the build.

Common categories:
- **Permissive** (MIT, Apache-2.0, BSD): broadly safe.
- **Weak copyleft** (MPL-2.0, LGPL): allowed in many projects.
- **Strong copyleft** (GPL, AGPL): often forbidden in commercial closed-source; allowed in open-source.

The policy is project-specific. Lawyers / legal team should bless the allowlist if any commercial implications.

### 10. Base image discipline (from `containerization`)

Base images are dependencies too:

- **Pinned by SHA**, not by tag.
- **Re-scanned in registry** on a schedule (Trivy registry scan; cloud-native registry vulnerability scanning).
- **Updated** via Dependabot / Renovate (base-image bumps treated like dependency updates).

A vulnerable base image affects every image built on it; the response plan applies.

## Outputs

| Output | Location |
|---|---|
| SBOM (per build) | published as image attestation; archived in `.project/operational/sbom/` for releases |
| Provenance attestation | published with image; verified at deploy |
| SCA reports | CI artifact per build; latest summary in `.project/operational/sca-summary.md` |
| SAST reports | CI artifact per build |
| DAST reports | scheduled CI artifact; summary in `.project/operational/dast-summary.md` |
| Dependency policy | `.project/procedural/dependency-policy.md` |
| Vulnerability response plan | `.project/procedural/vuln-response.md` |
| Unpatched-CVE acceptances | `.project/operational/risk-acceptances/` |

## Mode handling (G/B)

**Greenfield.** Wire all scans from day one; the build never publishes without SBOM + provenance.

**Brownfield.** Audit existing dependencies; expect a backlog of CVEs. Triage by severity; prioritize by exploitability + reach. The first scan is a snapshot; the discipline is what matters going forward.

## What this skill does not do

- Threat modeling for the application's own code — that's `threat-modeling`.
- Secure-coding application — that's `secure-coding`.
- Penetration testing — separate practice.
- Implement the patches — developers do that; this skill surfaces and prioritizes the work.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Our deps are popular; they're safe." | Popular doesn't mean reviewed. event-stream, ua-parser-js, colors — all popular, all compromised. SBOM + provenance regardless. |
| "SBOM is paperwork." | SBOM is what enables fast response to disclosed CVEs. Without it, you don't know if you're vulnerable. |
| "Provenance signing is for big projects." | Sigstore + cosign are free + easy. The cost of supply-chain attacks is the justification. |
| "We pin versions; that's enough." | Pinning prevents drift but doesn't address compromised packages. Verification (signatures, SBOMs) is the next layer. |
| "Internal packages don't need this." | Internal compromise is faster lateral movement. Treat internal artifacts with the same discipline. |
| "Dependabot handles it." | Dependabot surfaces updates; doesn't decide priority or test compatibility. Pair with policy + CI. |

## Verification

You are done when:

- [ ] SBOM generated per build artifact (SPDX or CycloneDX).
- [ ] Provenance attestation generated per `supply-chain-security` policy (SLSA level documented).
- [ ] Signing: artifacts signed via cosign / equivalent; signatures verified at deploy.
- [ ] CVE scan in CI; severity threshold blocks merge.
- [ ] Dependency-update policy documented (cadence, criteria, ownership).
- [ ] Allowlist of approved registries; pulls from elsewhere blocked.
- [ ] Container image base images pinned to digests, not tags.
- [ ] Lock files committed and verified in CI.

Evidence to check:
- A deployed artifact's SBOM is retrievable and matches the build.
- A signature verification can be reproduced from a clean machine.

## Anti-patterns

- Images shipped without SBOM + provenance.
- SCA findings ignored "because they're transitive" (transitive CVEs still execute in your image).
- Unsigned artifacts pulled in production.
- Dependencies pinned to ranges (`^1.2.3`) instead of exact versions.
- License compliance check skipped (commercial-impact surprises later).
- Vulnerability response plan undefined (everything becomes "fix it next sprint" → never).
- Dependencies never updated (security debt accumulates).
- Base images by tag, not SHA (silent updates with surprise CVEs).
- Internal mirror / proxy without integrity checks (defeats the supply chain protection).
- DAST never run (only static scanning misses runtime issues).
