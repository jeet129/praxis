# Reference — SOC 2

Loaded by `compliance-privacy` when SOC 2 is in the project's compliance regimes.

## What SOC 2 is

SOC 2 (Service Organization Control 2) is a voluntary attestation standard from the AICPA. It's not a regulation — it's an audit report you publish to demonstrate trustworthy operations. Customers (especially enterprise) increasingly require a SOC 2 report before signing.

Two report types:
- **Type I** — controls are designed appropriately at a point in time.
- **Type II** — controls are designed AND operating effectively over a period (3-12 months). Type II is what enterprise customers actually want.

## The Trust Services Criteria (TSC)

SOC 2 organizes controls under five TSC categories. **Security is mandatory; the others are optional based on what you commit to.**

| TSC | Mandatory? | Scope |
|---|---|---|
| **Security** | Yes | Protection against unauthorized access, both physical and logical. |
| **Availability** | Optional | System is available for operation as committed. |
| **Confidentiality** | Optional | Information designated as confidential is protected. |
| **Processing Integrity** | Optional | Processing is complete, valid, accurate, timely, authorized. |
| **Privacy** | Optional | Personal information handled per the entity's privacy notice. |

Most startups start with Security only. Add Availability when customer SLAs require it. Add Confidentiality for enterprise data handling. Privacy overlaps heavily with GDPR/CCPA — usually addressed separately.

## Common Criteria (CC)

The Security TSC is implemented via "Common Criteria" CC1-CC9:

| Code | Area | Examples |
|---|---|---|
| **CC1** | Control Environment | Board oversight, hiring, training, code of conduct. |
| **CC2** | Communication & Information | Internal/external comms, customer notification. |
| **CC3** | Risk Assessment | Risk identification, fraud risk, change impact analysis. |
| **CC4** | Monitoring | Ongoing evaluation, deficiency communication. |
| **CC5** | Control Activities | Policies + procedures + technology. |
| **CC6** | Logical & Physical Access | Authn, authz, key management, MFA. |
| **CC7** | System Operations | Monitoring, incident detection, BCDR. |
| **CC8** | Change Management | Reviews, approvals, deployment controls. |
| **CC9** | Risk Mitigation | Vendor risk, business continuity. |

## What this means in engineering terms

The auditor will sample evidence over the audit period. Engineering needs:

### CC6 — Logical access

- **MFA on all production accounts** (`authn-authz` configuration enforces this).
- **Least-privilege RBAC** for production resources (per `authn-authz` ABAC/RBAC).
- **Access review cadence** — quarterly review who has what.
- **Offboarding within target SLA** (often 24 hours) when a user leaves.
- **Audit logs for all production access** (per `secure-coding` + `observability`).
- **Service account credentials rotated** on a documented cadence.

### CC7 — System operations

- **Centralized monitoring + alerting** (`observability` SKILL).
- **Incident response runbook** (`incident-runbook` SKILL) with documented severity matrix.
- **Backup + restore procedure tested** within the audit period (`reliability-dr` SKILL).
- **DR plan documented + tested** (often annually minimum).

### CC8 — Change management

- **Code review required** for all changes (`code-review` gate).
- **Approvals captured** in tooling (PR approvals, ADR sign-offs).
- **Production deploys via documented pipeline** (`cicd-pipeline` SKILL).
- **Rollback procedure documented + rehearsed** (`deploy-release` SKILL).
- **Separation of duties** — the person who writes code can't be the only approver of its production deploy (small teams document compensating controls).

### CC2/CC4 — Vulnerability management

- **Dependency scanning in CI** (`supply-chain-security`) with documented severity thresholds.
- **CVE response timeline** — critical vulnerabilities patched within X days (define X).
- **Pen tests + security audits** on a cadence (often annually).

### Data protection

- **Encryption at rest** for production data (cloud-native services usually default; verify).
- **Encryption in transit** for all production traffic (TLS 1.2+ minimum).
- **Key management** documented; access controlled.

## Evidence engineering needs to produce

The auditor will ask:

- "Show me 3 random sample weeks where someone reviewed production access."
- "Show me the deploy log for change X — who approved it, who deployed it, what tested it."
- "Show me the last 3 incident postmortems — were action items closed?"
- "Show me the backup restoration test from the audit period."
- "Show me your vulnerability scan history; show me 3 sample critical vulns and their remediation timeline."
- "Show me terminated employees and the date their access was revoked."

Per `compliance-privacy` verification, the control coverage matrix maps each requirement to:
- The control implementation (link to code / runbook / policy).
- The evidence source (link to where the audit log lives).
- The owner (who maintains this).

## Common platform overlaps

| Platform area | Maps to |
|---|---|
| `cicd-pipeline` | CC8 change management evidence |
| `code-review` | CC8 change management — approval evidence |
| `secrets-config` | CC6 logical access — credential management |
| `authn-authz` | CC6 logical access — authentication, authorization |
| `observability` | CC7 system operations — monitoring, alerting |
| `incident-runbook` | CC7 system operations — incident response |
| `reliability-dr` | CC7 system operations — backup, DR |
| `supply-chain-security` | CC2/CC9 — vulnerability management |
| `secure-coding` + `threat-modeling` | CC3 risk assessment + CC6 controls |
| `data-governance` | All TSCs — access controls + classification |

## Common SOC 2 platforms

If you're going for SOC 2, automation platforms help collect evidence:

- **Vanta** — most popular for startups; ~$8-25K/year.
- **Drata** — strong workflow automation; ~$10-30K/year.
- **Secureframe** — similar tier.
- **Tugboat Logic / OneTrust GRC** — enterprise.
- **Manual (spreadsheets + Drive)** — possible for very small companies; doesn't scale.

These platforms automate evidence collection from AWS/GCP/Azure/GitHub/Jira/etc. but don't replace engineering controls — they observe and audit them.

## Audit timeline (typical)

| Stage | Duration | Engineering involvement |
|---|---|---|
| Readiness assessment | 4-8 weeks | Gap analysis; identify missing controls. |
| Remediation | 8-12 weeks | Implement missing controls; document policies. |
| Type I observation period | ~1 month | Controls live; evidence captured. |
| Type I audit | 2-4 weeks | Auditor interviews + sample. |
| Type II observation period | 3-12 months | Controls operate; evidence collected. |
| Type II audit | 4-6 weeks | Auditor sample over full period. |

Start ~12 months before you need the Type II report.

## Common rationalizations

| Thought | Counter |
|---|---|
| "SOC 2 is checkbox compliance." | The controls catch real failures: leaked credentials, missing backups, unreviewed deploys. The checkbox is the evidence trail. |
| "We'll add controls right before the audit." | Type II observes a real period; controls must operate during it. Last-minute = Type I only. |
| "Our cloud provider's SOC 2 covers us." | It covers their controls; not yours. You still need your own report for what runs on top. |
| "We can do this without engineering time." | Compliance platforms collect evidence; they don't implement controls. Engineering builds the controls. |
| "MFA on production is friction." | MFA is a CC6 requirement and prevents 95%+ of credential-based attacks. Non-negotiable. |
| "Tests are good enough as evidence." | Tests prove the code works once; evidence proves it kept working. Logs + audit trails over time. |

## Verification checkpoints (per `compliance-privacy` SKILL)

- [ ] Trust Services Criteria scope confirmed (Security mandatory + optional adds).
- [ ] Control coverage matrix maps every CC requirement to a control + evidence source.
- [ ] Audit log captures: who, what, when, where for all production access + changes.
- [ ] Quarterly access review scheduled + last performed within cadence.
- [ ] Backup restoration tested within audit period.
- [ ] DR plan tested annually minimum.
- [ ] Vulnerability scans run in CI; remediation timeline documented per severity.
- [ ] Incident response runbook + last incident postmortem available.
- [ ] Change management — every prod change has approval + deploy log.
- [ ] Compliance platform integrated (or manual evidence collection working).
- [ ] Annual audit booked; auditor selected.

## Official sources

- AICPA SOC 2 Trust Services Criteria: https://www.aicpa.org/interestareas/frc/assuranceadvisoryservices/aicpasoc2report.html
- AICPA Trust Services Criteria description: https://www.aicpa.org/resources/download/trust-services-criteria-2017-version-1
- Common Criteria mapping guides: published by each compliance automation platform.
