---
name: compliance-privacy
description: Map regulatory regimes (SOC2 / GDPR / HIPAA / PCI-DSS / ISO 27001 / CCPA-CPRA / NIST CSF / FedRAMP) to concrete controls. Data classification, retention, audit logging, PII handling, data residency. Per the Resolved Decision (Section 14 of blueprint), eight regimes are encoded with shared workflow body and per-regime references.
---

# Compliance & Privacy


<!-- praxis:description:full -->
## Full description

Map regulatory regimes (SOC2 / GDPR / HIPAA / PCI-DSS / ISO 27001 / CCPA-CPRA / NIST CSF / FedRAMP) to concrete controls. Data classification, retention, audit logging, PII handling, data residency. Per the Resolved Decision (Section 14 of blueprint), eight regimes are encoded with shared workflow body and per-regime references. Solution Architect and Security Reviewer co-own this; Platform/SRE provisions the controls; tech-writer maintains the compliance evidence. Use whenever a project enters a regulated regime, when designing data handling, or when assembling compliance evidence for the production_go_live gate.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
  - secure-coding
  - threat-modeling
  - data-modeling
  - secrets-config
  - observability
triggers:
  - "project enters a regulated regime (SOC2 / GDPR / HIPAA / PCI / etc.)"
  - "designing data classification + retention policy"
  - "implementing audit logging for compliance"
  - "designing data residency / sovereignty"
  - "preparing compliance evidence for production_go_live"
  - "responding to data subject request (GDPR right to erasure / access)"
outputs:
  - data classification taxonomy + per-class controls
  - retention policy per data class
  - audit-logging requirements per regime
  - PII handling design (classification → flow → retention → erasure)
  - data residency policy (regions, cross-border restrictions)
  - control-coverage matrix per regime
  - data subject request runbook (GDPR / CCPA)
consumers:
  - solution-architect (designs data handling)
  - security-reviewer (audits compliance)
  - platform-sre (provisions infrastructure controls via iac)
  - tech-writer (maintains evidence documentation)
  - data-modeling (consumes classification for schema design)
  - production_go_live gate (consumes evidence for regulated releases)
references:
  - soc2.md
  - gdpr.md
  - hipaa.md
  - pci-dss.md
  - iso-27001.md
  - ccpa.md
  - nist-csf.md
  - fedramp.md
```
<!-- praxis:metadata:end -->

The discipline of translating regulatory requirements into concrete engineering controls. Compliance is not paperwork — it's *evidence* that the engineering controls exist, work, and are documented. Done right, the controls are built in; the evidence is a query against the platform. Done wrong, compliance is a fire drill before each audit.

The principle: **encode the regulation as engineering controls; produce evidence as a side effect of normal operation.**

## When this skill fires

- A project enters a regulated regime — encode the regime's required controls.
- Data classification + retention is being designed (the foundation that most regimes build on).
- Audit logging is being implemented for compliance purposes.
- Data residency / sovereignty requirements need design.
- The production_go_live gate's compliance evidence is being assembled.
- A data subject request (GDPR access, GDPR erasure, CCPA opt-out) needs to be answered.

## The shared workflow body

The eight regimes share substantial common ground. The shared body covers the universal controls; per-regime references add what's specific.

### 1. Data classification taxonomy

Universal across regimes. Define data classes and the controls per class:

| Class | Examples | Controls |
|---|---|---|
| **Public** | Marketing content; public API docs | None special. |
| **Internal** | Employee data; internal metrics | Access controls; encrypted in transit. |
| **Confidential** | Business data; non-PII customer data | Access controls; encrypted at rest; audit access. |
| **Restricted (PII)** | Names, emails, addresses, phone | Strong access controls; encrypted at rest + in transit; audit access; retention policy; deletable. |
| **Highly Restricted (PHI / PCI / SSN)** | Medical data; payment card data; SSN; biometrics | All above + segmented network / scope; per-record audit; specific regime requirements. |

Per-field classification in `data-modeling`'s schema: each column tagged with its class. Application code consumes the classification (logs redact restricted classes; persistence enforces encryption).

### 2. Retention policy

Per data class:

| Class | Default retention |
|---|---|
| Public | Indefinite. |
| Internal | 3 years (operational); regime-specific overrides. |
| Confidential | Per business need + regime requirement. |
| Restricted (PII) | Per regime — GDPR purpose-limitation: no longer than necessary; HIPAA: 6+ years; SOC2: per policy (typically 1-7 years). |
| Highly Restricted | Per regime — PCI: cardholder data minimized (tokenize where possible); HIPAA PHI: 6 years; FedRAMP: 3+ years. |

Retention is enforced automatically — TTL fields, lifecycle policies, scheduled deletion jobs. Manual retention is not retention.

### 3. Audit logging

Per regime, certain events must be logged. Common requirements:

- **Who** — user / service identity.
- **What** — action performed (create, read, update, delete; admin action).
- **When** — timestamp.
- **Where** — source IP / network identity.
- **Outcome** — success / failure.
- **Reason** — for sensitive operations.

Per-regime specifics:

- **SOC2**: access to systems containing customer data; changes to access controls; security events.
- **HIPAA**: every access to PHI (logged for 6 years).
- **PCI-DSS**: every access to cardholder data environment; admin actions; firewall changes.
- **GDPR**: lawful basis for processing PII; data subject requests fulfilled; cross-border transfers.

Audit logs:
- **Immutable** — append-only storage; tamper-evident (signing, hashing).
- **Retained** per regime (HIPAA 6+ years; SOC2 typically 1+ year; PCI 1 year).
- **Reviewable** — auditor can query without breaking production access patterns.

### 4. PII handling

PII flows tracked end-to-end:

- **Collection** — lawful basis documented (GDPR); explicit consent where required.
- **Storage** — encrypted at rest; access-controlled; classified field-by-field.
- **Processing** — purpose-limited (GDPR Article 5(1)(b)); minimization (only what's needed).
- **Sharing** — only with documented third-party agreements (BAAs for HIPAA, DPAs for GDPR).
- **Retention** — automated deletion when purpose ends.
- **Erasure** — GDPR Article 17 right to erasure / CCPA right to delete; deletable per `data-modeling`'s no-PII-spread design.

PII flow diagrams in `.project/operational/pii-flows-{system}.md` for regulated systems.

### 5. Data residency

For regimes with geographic restrictions:

- **GDPR**: EU residents' data should ideally stay in EU; cross-border transfers require adequacy or SCCs.
- **Various national regulations**: Russia, China, India, Brazil — data localization requirements.
- **Customer contracts**: enterprise contracts often require regional data residency.

Implementation:
- IaC parameterized per region; tenant routing by region.
- Database replication topology respects region boundaries.
- Cross-region operations (analytics, ML training) handled with data-residency-preserving patterns (aggregation, anonymization, in-region processing).

### 6. Data subject requests

GDPR / CCPA / similar:

- **Right to access** — provide a copy of the data subject's personal data.
- **Right to erasure** — delete the data subject's personal data.
- **Right to portability** — provide data in a machine-readable format.
- **Right to opt-out / object** — stop processing for marketing, profiling, etc.

Each has a runbook:

```markdown
# Runbook — Data Subject Erasure Request (GDPR Article 17)

## Pre-requisites
- Request received via authorized channel (privacy portal / DPO email).
- Identity verified.
- No outstanding legal hold on this data subject.

## Steps
1. Identify the data subject's customer_id from the verified identity.
2. Run the erasure-eligibility check (some data must be retained per other regulations — financial records for tax).
3. Execute the erasure pipeline:
   a. Soft-delete in primary database (mark as erased; keep customer_id for foreign key integrity).
   b. Hard-delete PII fields (replace with `[ERASED]` markers).
   c. Cascade to derived data stores (search index, analytics warehouse, ML feature store).
   d. Erase from backups within next backup cycle (or wait for retention expiry; document choice).
4. Verify erasure via the verification script.
5. Notify the data subject of completion (with explanation of any retained data + lawful basis).
6. Record the request in `.project/operational/dsr-log.md`.

## SLA
- Confirmation within 1 month per GDPR; sooner if practical.
```

## Per-regime references

Per the Resolved Decision (R4 acceptance), eight regimes are encoded. Each reference adds regime-specific specifics:

- **`references/soc2.md`** — Trust Services Criteria; common audit-evidence patterns; type 2 vs type 1.
- **`references/gdpr.md`** — Lawful basis; DPA / DPO; cross-border transfers; data subject rights.
- **`references/hipaa.md`** — PHI scope; BAA requirements; encryption + access + audit.
- **`references/pci-dss.md`** — Cardholder data scope; SAQ levels; tokenization; segmentation.
- **`references/iso-27001.md`** — ISMS scope; control objectives; certification process.
- **`references/ccpa.md`** — California residents' rights; CCPA vs GDPR differences.
- **`references/nist-csf.md`** — Cybersecurity Framework functions (Identify / Protect / Detect / Respond / Recover).
- **`references/fedramp.md`** — Authorization levels (Low / Moderate / High); FedRAMP Marketplace.

References themselves will populate as projects engage each regime (per the Knowledge Growth Policy — references grow, skill bodies stay stable).

## Control-coverage matrix

Per active regime, a matrix maps regime requirements to engineering controls:

```markdown
# SOC2 Trust Services Criteria — Coverage Matrix

| Criterion | Control | Implemented by | Evidence | Status |
|---|---|---|---|---|
| CC1.1 (control environment) | Code of conduct + training | HR (org-level) | Training records | Compliant |
| CC6.1 (logical access) | RBAC + MFA on identity provider | authn-authz + identity provider | IdP logs | Compliant |
| CC6.7 (data transmission) | TLS 1.2+ on all surfaces | secure-coding + platform-k8s | Cipher suite audit | Compliant |
| CC7.2 (anomaly detection) | SIEM alerting | observability + incident-runbook | Alert history | Compliant |
| ... | | | | |
```

The matrix is updated as controls are added or as the auditor evolves their criteria. Evidence references point to artifacts produced by normal operation (logs, IaC plans, ADRs) — not separate documents.

## Outputs

| Output | Location |
|---|---|
| Data classification taxonomy | `.project/semantic/data-classification.md` |
| Retention policy | `.project/procedural/retention-policy.md` |
| Audit logging requirements | `.project/procedural/audit-logging.md` (consumed by observability) |
| PII flow diagrams | `.project/operational/pii-flows-{system}.md` |
| Data residency policy | `.project/procedural/data-residency.md` |
| Per-regime control matrices | `.project/operational/compliance/{regime}-coverage.md` |
| DSR (data subject request) runbooks | `.project/operational/runbooks/dsr-{type}.md` |
| DSR log | `.project/operational/dsr-log.md` |

## Mode handling (G/B)

**Greenfield.** Encode regime requirements from day one; controls built in; evidence accumulates from normal operation.

**Brownfield.** Audit existing controls; common findings: PII flows undocumented; audit logging incomplete; retention not enforced. Prioritize the highest-severity gaps; the rest is multi-quarter work.

## Verification

You are done when:

- [ ] Applicable regimes confirmed (from `delivery-planner` charter); per-regime control matrix established.
- [ ] PII / PHI / regulated data classified; flow diagrams exist.
- [ ] Data residency / sovereignty requirements documented.
- [ ] Retention policy per data class; enforcement automated.
- [ ] DSR (data subject request) procedure documented + exercised end-to-end.
- [ ] Audit logging captures: who, what, when, where; retention per regime; immutability assured.
- [ ] Sub-processor / vendor inventory + DPA status documented.
- [ ] Incident response includes regulatory notification timelines.
- [ ] Annual or per-regime cadence for control attestation scheduled.

Evidence to check:
- A control reviewer can map every regime requirement to a specific control + evidence.
- DSR procedure was exercised within the last 12 months.
- Audit log query for a specific user surfaces all access events.

## What this skill does not do

- Legal advice — engage real lawyers for regulatory interpretation.
- Auditor engagement — handled by Security / Compliance team.
- Penetration testing — separate practice.
- Implement encryption itself — that's `secure-coding` + `secrets-config` + `platform-k8s`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We're not under regulation X yet." | The flag in the charter is the source of truth. If a regime applies, the controls apply. If it doesn't, document why not. |
| "Compliance is the lawyer's problem." | Compliance has lawyer artifacts; the controls themselves are engineering. Build them right; the lawyer's job becomes easy. |
| "We'll add the controls before audit." | "Before audit" is months of debt accumulation. The controls go in at design time; the audit is the verification. |
| "Audit log is just another log stream." | Audit log has integrity, retention, and access-control requirements that production logs don't. Different artifact. |
| "PII handling is on me to remember." | It's on the system to enforce. Tagging + access controls + redaction + retention. Memory doesn't scale. |
| "Encryption in transit is enough; data is safe." | At-rest, in-use, key management, key rotation. The threat model has more vectors than "the wire." |
| "DSR is one-time; we'll do it manually." | One-time works at 1 DSR/year; breaks at 10/year; legally dangerous at 100/year. Build the procedure; automate where possible. |

## Anti-patterns

- Compliance treated as paperwork (separate from engineering reality).
- Evidence assembled at audit time, not generated continuously.
- PII flows undocumented.
- Audit logs not immutable.
- Retention "policy" without automatic enforcement.
- DSR responses ad-hoc per request (no runbook).
- Data classification field-by-field skipped (some PII not tagged → not protected).
- Cross-border data transfers without documentation.
- Compliance regimes' requirements interpreted by engineers alone (need legal blessing for ambiguous cases).
- "We're GDPR-compliant" stated without per-control evidence.
