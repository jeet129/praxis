---
name: technical-documentation
description: "Operational and developer documentation — distinct from `architecture-documentation` (which is about the system shape). Runbooks per service / per incident class; README discipline at every level (repo / service / library / module); API reference (auto-generated + curated); developer onboarding; release notes; documentation-as-code with CI checks. Tech Writer drives; every role contributes (operators write runbooks, developers write READMEs and API ref, PM contributes release notes). Discoverability matters as much as content — docs that exist but can't be found don't exist. Use when establishing initial doc structure, when writing an incident runbook, when shipping a release (release notes), when onboarding a new joiner, when discovering documentation that no longer matches reality, or in the quarterly doc audit."
---

# Technical Documentation

<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: active
dependencies:
  - engineering-standards
  - architecture-documentation
  - incident-runbook
  - api-design
  - codebase-comprehension
triggers:
  - "establishing initial documentation structure"
  - "writing an incident runbook (per `incident-runbook`'s template)"
  - "shipping a release (release notes)"
  - "new joiner onboarding"
  - "discovering doc that no longer matches reality"
  - "quarterly documentation audit"
  - "API reference generation / curation"
outputs:
  - documentation site (or distributed README network)
  - per-service / per-module README
  - runbook catalog (per incident class)
  - API reference (auto-gen + curated)
  - developer onboarding guide
  - release notes (per release)
  - documentation audit findings
consumers:
  - tech-writer (primary driver)
  - every role agent (everyone contributes)
  - new-joiner (onboarding consumer)
  - platform-sre (runbooks for incidents)
  - incident-runbook (consumed by; runbooks live here)
  - api-design (consumes; API ref draws from API design)
references: []
```
<!-- praxis:metadata:end -->

The discipline that makes a system *operable*. Architecture docs (per `architecture-documentation`) answer "what is this system?" Technical docs answer "how do I work in it / run it / fix it / extend it?" Different audience, different artifacts, different cadence.

The principle: **documentation that exists but can't be found doesn't exist. Discoverability is half the work.**

## When this skill fires

- Establishing initial documentation structure for a project.
- Writing an incident runbook (per `incident-runbook`).
- Shipping a release — release notes.
- New joiner onboarding.
- Documentation that no longer matches reality discovered.
- Quarterly documentation audit.
- API reference being generated or curated.

## What this skill is NOT

- Architecture overview / C4 / ADRs (that's `architecture-documentation`).
- Code comments (that's `engineering-standards`).
- External marketing / customer-facing docs (that's a separate function; this skill provides primary technical content that may feed it).

## The documentation tiers

Five tiers; each has owner, audience, cadence.

### Tier 1 — Repo / project README

The first thing anyone sees. Lives at repo root.

Required content:

- **What is this** — one paragraph for someone who has never heard of it.
- **Status** — actively developed / maintenance / archived.
- **How to run it locally** — exact commands.
- **How to test it** — exact commands.
- **Where to read more** — links to architecture-docs, runbooks, API ref.
- **How to contribute** — link to contributing guide.
- **Who owns this** — team / individual.

Owner: Lead Developer. Cadence: reviewed at any significant change; quarterly audit minimum.

### Tier 2 — Per-service / per-module README

Inside any non-trivial module or service. Same pattern as Tier 1 but scoped.

Required content:

- What this service / module is responsible for.
- How it interacts with other services (link to architecture-docs Level 2).
- How to run it standalone (dev loop).
- Its key dependencies.
- Its operational properties (SLO, alerting, runbook link).
- Open questions / known limitations.

Owner: the service / module's primary developer. Cadence: reviewed at major changes.

### Tier 3 — Runbooks

Operational documents. One per incident class (per `incident-runbook`'s catalog). Lives at `.project/operational/runbooks/`.

Per `incident-runbook`, a runbook has:

- Symptoms (what the operator sees).
- Severity / impact.
- Diagnosis steps (specific tool commands).
- Mitigation steps.
- Permanent fix vs temporary fix distinction.
- Escalation path.
- Post-incident actions.

Owner: Platform/SRE for system-level runbooks; Lead Developer or ML/AI Engineer for service-specific. Cadence: tested in GameDay / chaos / drill (per `chaos-engineering`); updated post-incident.

### Tier 4 — API reference

For systems exposing APIs (internal or external).

Generated portion:

- Spec-driven (OpenAPI / GraphQL schema / gRPC proto / etc.) — auto-generated from source.
- Re-generated on each release.

Curated portion:

- Authentication setup.
- Rate limits + quotas.
- Error code catalog.
- Examples per endpoint (request + response + common error).
- Versioning + deprecation policy.

Owner: Backend Developer (generated) + Tech Writer (curated). Cadence: regenerated each release; curated parts reviewed monthly.

### Tier 5 — Developer onboarding guide

How a new joiner becomes productive. The journey from "git clone" to "shipped my first slice."

Required content:

- Setup checklist (accounts, machine config, dev tools).
- First-week reading: architecture-overview → repo README → one service README of choice.
- Where the Praxis lives (the skill library); how to invoke skills.
- Pair-up / shadow plan (who to ask).
- First-slice candidates (good warm-up tasks).
- Glossary (project-specific terms).
- "When stuck, ask in #channel" routing.

Owner: Tech Writer + Lead Developer. Cadence: refreshed quarterly + after onboarding feedback.

## Release notes

Per release. Format:

```markdown
# Release v4.7.0 — 2026-11-15

## Highlights
- [User-visible] New feature X.
- [Operations] Migration Y deployed (see runbook ABC).
- [Security] Auth library upgraded to patch CVE-2026-NNNN.

## Breaking changes
- API `GET /v1/foo` removes deprecated `legacy_id` field (deprecated 2026-09; sunset window expired).

## New
- {list}

## Changed
- {list}

## Deprecated
- {list}

## Fixed
- {list}

## Security
- {list}

## Operational notes
- Migration time estimated 15m; runs in pre-deploy window.
- Rollback procedure: revert to v4.6.x; no data migration to reverse.

## ADRs landed this release
- ADR-091 (state-machine for order lifecycle).
- ADR-092 (event bus partitioning by customer-tier).
```

Owner: PM (highlights) + Lead Developer (changes) + Platform/SRE (operational notes). Generated semi-automatically from PR titles + ADRs landed; curated for readability.

## Documentation as code

All technical documentation lives in version control. Even when published to a separate site (Docusaurus, Sphinx, Hugo, Mintlify), the source is in the repo.

CI checks:

- **Links** — broken-link detection on every PR.
- **Stale markers** — pages flagged with "needs review by 2027-Q1"; CI surfaces overdue.
- **API ref freshness** — generated docs match source spec; CI fails if mismatch.
- **README presence** — services without README fail a lint rule.

Documentation site built per release; preview deploys per PR.

## Discoverability

Documentation that exists but can't be found doesn't exist. Discoverability tactics:

- **Single index** — every doc links from one navigable map.
- **Search** — the doc site has working search.
- **Cross-linking** — runbook references architecture diagram; API reference links to architecture-doc Level 2; onboarding links to all of the above.
- **Standard naming** — `runbook-{service}-{class}.md`, `api-reference-{service}-{version}.md`, etc.
- **Stale flagging** — visible "last updated" date; warning if older than threshold.

The new-joiner test: a new hire can find what they need in < 5 minutes. If not, discoverability is broken.

## Quarterly documentation audit

A single quarterly walkthrough:

- Open every Tier-1 + Tier-2 README — does the first paragraph still describe what's true?
- Sample 5-10 runbooks — were they updated after their last incident?
- Open the API reference — does the spec match deployed?
- Re-read the onboarding guide as if new — does it work?
- Find docs without owners — assign.
- Find stale flags — refresh or archive.

Audit findings go in `.project/operational/doc-audit-{quarter}.md`. Action items get scheduled into upcoming cycles or filed in `tech-debt-management`.

## Outputs

| Output | Location |
|---|---|
| Repo README | `/README.md` |
| Per-service README | `services/{service}/README.md` |
| Runbooks | `.project/operational/runbooks/` |
| API reference | published site + source in repo (`/docs/api/`) |
| Developer onboarding guide | `/docs/onboarding.md` or `.project/semantic/onboarding.md` |
| Release notes | `/docs/release-notes/` + per-release tag |
| Documentation audit | `.project/operational/doc-audit-{quarter}.md` |

## Mode handling (G/B)

**Greenfield.** Documentation structure designed in the first week. Templates in place; CI checks enforced from PR 1.

**Brownfield.** Audit existing docs. Common findings: README outdated; runbooks missing; API ref stale; no onboarding; no quarterly cadence. Doc improvements often blocked by docs-not-treated-as-code (in random Confluence pages). Migration to docs-as-code is itself a multi-cycle effort.

## Critical disciplines

**Docs as code.** In repo. Version controlled. PRs.

**CI checks.** Broken links, stale flags, missing READMEs caught automatically.

**Audit quarterly.** The cadence makes the difference.

**Owners everywhere.** Doc without an owner has no one accountable for currency.

**New-joiner as the discoverability test.** The first new hire is also the first audit.

**Runbooks tested in GameDay.** Untested runbooks don't work in production incidents.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Docs are a wiki." | Wiki docs drift fastest; PR-less; un-reviewed. Docs-as-code in repo. |
| "READMEs are old-fashioned." | READMEs are the first touch; new joiners read them. Quality matters. |
| "API ref is generated; it's fine." | Generated covers syntax; not semantics, examples, auth, errors. Curate. |
| "Onboarding doc becomes stale anyway." | Then refresh it after each onboarding. The new joiner is the refresh trigger. |
| "Release notes are tedious." | They're the change record for ops + customers + downstream. Mandatory. |
| "Discoverability is solved by search." | Search finds what's well-tagged. Without taxonomy, search fails. |

## Verification

You are done when:

- [ ] Tier-1 README at every repo root with the required sections.
- [ ] Tier-2 per-service / per-module README.
- [ ] Tier-3 runbooks per incident class.
- [ ] Tier-4 API ref: generated + curated (auth, errors, examples).
- [ ] Tier-5 developer onboarding guide.
- [ ] Release notes per release (with breaking changes flagged).
- [ ] Docs-as-code: in repo; CI checks (links, stale markers, missing READMEs).
- [ ] Discoverability: single index; search works; cross-linked.
- [ ] Quarterly audit performed.

Evidence to check:
- A new hire becomes productive in target time.
- Runbooks tested in last GameDay actually worked.

## Anti-patterns

- Docs in Confluence / wiki only (drift; no PR review; no CI checks).
- README that says "TODO."
- Runbooks written once; never rehearsed.
- API ref hand-written; drifts from spec immediately.
- Onboarding guide last updated 18 months ago.
- Release notes generated from raw git log (unreadable).
- Single owner for ALL docs (Tech Writer can't be the only contributor).
- Discoverability ignored (docs exist; no one can find them).
- "We documented it" claimed in a slack message; never re-checked.
- Documentation audit skipped quarter after quarter.
- Auto-generated docs treated as complete (the curation IS the value).
