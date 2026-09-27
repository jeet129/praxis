# Reference — GDPR

Loaded by `compliance-privacy` when GDPR (or UK GDPR) applies — i.e., any product processing personal data of EU/UK residents.

## What GDPR is

The General Data Protection Regulation (GDPR; EU 2016/679, effective May 2018) regulates the processing of personal data of individuals in the EU. The UK retains a near-identical UK GDPR post-Brexit.

Applies if:
- You're established in the EU/UK AND process personal data, OR
- You offer goods/services to EU/UK individuals, OR
- You monitor EU/UK individuals' behavior.

Geography of the customer matters, not yours. A US company with EU customers is in scope.

## Roles

| Role | Definition |
|---|---|
| **Data Subject** | The individual whose data is processed. |
| **Controller** | The party that determines purpose + means of processing. (Usually: your company.) |
| **Processor** | The party that processes on the controller's behalf. (Often: vendors like AWS, Stripe, OpenAI.) |
| **Sub-processor** | A processor's processor. |
| **DPO** (Data Protection Officer) | Required if you do large-scale monitoring or process special-category data. |

You may be a Controller for your customers and a Processor for B2B customers using your platform.

## Lawful bases

Every processing operation must have a lawful basis. Six options:

1. **Consent** — explicit, specific, freely given, withdrawable.
2. **Contract** — necessary to perform a contract with the data subject.
3. **Legal obligation** — required by law (tax records, etc.).
4. **Vital interests** — life-or-death scenarios.
5. **Public task** — for public authorities.
6. **Legitimate interests** — your interests, balanced against the data subject's rights. Must be documented (legitimate-interest assessment).

Most product features rely on **Contract** (the user signed up; you process to deliver the service) or **Legitimate interests** (analytics, fraud prevention). Marketing usually needs **Consent**.

## Data subject rights

GDPR Articles 15-22:

| Right | What it means | Response SLA |
|---|---|---|
| **Access** (Art 15) | Provide copy of personal data processed. | 1 month (extendable to 3) |
| **Rectification** (Art 16) | Correct inaccurate data. | 1 month |
| **Erasure** ("right to be forgotten") (Art 17) | Delete data (with exceptions). | 1 month |
| **Restrict processing** (Art 18) | Halt processing while a dispute is resolved. | 1 month |
| **Portability** (Art 20) | Provide structured machine-readable export. | 1 month |
| **Object** (Art 21) | Stop processing for direct marketing. | Without delay |
| **Automated decision-making** (Art 22) | Right not to be subject to automated decisions with significant effects. | Per request |

Engineering must build these — they don't happen by hand at any scale.

## Engineering requirements

### Data inventory

Per `data-governance` SKILL — know what personal data you process, where it lives, how it flows:

- Catalog of all data assets containing personal data.
- Lineage from collection point to storage, processing, deletion.
- Classification by sensitivity (regular vs special-category like health, biometric, race).
- Retention period per data class.

### Lawful basis tracking

Every processing operation records its lawful basis. When consent is the basis, the consent record must include:
- What was consented to (purpose).
- When consent was given.
- How (UI flow, signature, etc.).
- Withdrawal mechanism.

### Data subject request (DSR) procedure

Per `compliance-privacy` and `data-governance`:

1. **Identity verification** — confirm the requester is who they claim.
2. **Request routing** — to the right team / automated system.
3. **Execution** — gather/correct/delete across all systems where the data lives.
4. **Response** — provide the result within SLA.
5. **Audit trail** — record what was done.

For erasure specifically:
- Delete from primary store.
- Delete from backups (or document why retained — backup-based recovery is allowed for limited time).
- Delete from analytics + warehouse.
- Delete from logs (or pseudonymize).
- Delete from search indexes.
- Delete from message queues, caches, CDN.
- Notify processors who got the data.

This is non-trivial. Build the procedure; test it.

### Cross-border transfers

GDPR restricts transfers of personal data outside the EEA:

- **Adequacy decision** — transfers to "adequate" countries (UK, Japan, Canada, etc. — current list maintained by EU Commission).
- **Standard Contractual Clauses (SCCs)** — for transfers to non-adequate countries (most common mechanism after Schrems II ruling).
- **Binding Corporate Rules (BCRs)** — for intra-corporate transfers.
- **Derogations** — narrow exceptions (consent, contract necessity, etc.).

If you use US-based services (AWS, GCP, Azure, Stripe, OpenAI, etc.), you typically rely on the EU-US Data Privacy Framework or SCCs.

### Privacy by design (Art 25)

Build privacy into systems from the start:

- Minimize data collected (per `data-governance` minimization principle).
- Apply default settings that are privacy-respecting (don't default to "share with everyone").
- Encrypt at rest + in transit (per `secure-coding`).
- Pseudonymize where possible.
- Document the design decision in an ADR.

### Data Protection Impact Assessment (DPIA)

Required for high-risk processing (large-scale profiling, special categories, public area monitoring, etc.). The DPIA documents:

- Nature, scope, context of processing.
- Necessity + proportionality.
- Risks to data subjects.
- Mitigations.

DPIAs aren't just paperwork — they're engineering input. The mitigations end up in code.

### Breach notification

If a breach is likely to result in risk to data subjects:
- Notify the supervisory authority **within 72 hours** of becoming aware.
- Notify affected individuals if high risk (Art 34).

Engineering must support:
- Fast detection (`observability` + security monitoring).
- Fast investigation (sufficient audit logs).
- Fast scope determination (data inventory + lineage).

The 72-hour clock is real. Practice this in chaos drills.

## Special categories of personal data (Art 9)

These need additional safeguards + explicit consent (or other narrow basis):

- Racial/ethnic origin
- Political opinions
- Religious/philosophical beliefs
- Trade union membership
- Genetic data
- Biometric data (for identification)
- Health data
- Sex life or sexual orientation

If your product processes any of these (health apps, biometric auth, dating apps, etc.), the bar is much higher.

## Penalties

- Up to €20M or 4% of global annual turnover (whichever is higher) for the most serious infringements.
- Up to €10M or 2% for less severe infringements.

Not just theoretical — fines in 2024-2025 included Meta (€1.2B), Amazon (€746M), TikTok (€345M), Clearview AI (€20M+ in multiple jurisdictions).

## Common engineering checklist

- [ ] Personal data inventory + classification complete.
- [ ] Lawful basis recorded for every processing operation.
- [ ] Privacy notice published, accurate, accessible from product.
- [ ] Consent mechanism (where applicable) captures + tracks consent.
- [ ] DSR procedure documented + exercised end-to-end within last 12 months.
- [ ] Retention policies enforced (automated deletion or archival).
- [ ] Cross-border transfer mechanism documented per processor.
- [ ] Sub-processor list maintained + customers notified of changes.
- [ ] DPIA completed for high-risk processing.
- [ ] Breach detection + 72-hour notification procedure documented + drilled.
- [ ] Encryption at rest + in transit for personal data.
- [ ] Audit log for personal-data access (who/what/when).
- [ ] Data Processing Agreement (DPA) in place with each processor.

## Common rationalizations

| Thought | Counter |
|---|---|
| "We're a US company; GDPR doesn't apply." | If you have EU/UK users, it does. Geography of the user. |
| "We don't store PII." | Email is PII. IP address is PII. Cookies can be PII. Most products process some PII. |
| "Cookie banner = GDPR done." | Cookies are one slice. Lawful basis, data inventory, DSRs, retention, transfers — all separate. |
| "We'll do DSR manually." | Works at 1 DSR/year. Breaks at 10. Legally hazardous at 100. Build the procedure. |
| "Erasure means deletion from prod DB." | Erasure means deletion from ALL systems where the data lives. Build the inventory. |
| "Schrems II — we're using AWS US-East." | You need SCCs or the Data Privacy Framework. Document the transfer mechanism. |

## Verification checkpoints (per `compliance-privacy` SKILL)

- [ ] Lawful basis catalog complete + reviewed annually.
- [ ] Data inventory + classification current.
- [ ] DSR procedure functional + tested within target SLA.
- [ ] Cross-border transfers documented per processor.
- [ ] Privacy notice current + linked from all entry points.
- [ ] Consent mechanism implemented where relied upon.
- [ ] Breach response procedure documented + drilled.
- [ ] DPIA on file for high-risk processing.
- [ ] DPO appointed if required.
- [ ] Sub-processor list maintained.
- [ ] DPA signed with all processors.

## Official sources

- GDPR full text: https://gdpr-info.eu
- European Data Protection Board (EDPB) guidelines: https://edpb.europa.eu/our-work-tools/general-guidance_en
- ICO (UK) practical guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/
- IAPP (privacy professionals' association): https://iapp.org
- EU-US Data Privacy Framework: https://www.dataprivacyframework.gov
