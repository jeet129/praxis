---
name: architecture-documentation
description: 'Keep architecture documentation alive — not a snapshot that ages into archaeology. C4 model at four levels (context / container / component / code) at the right level of fidelity per level; ADR archive maintained as the immutable decision trail; system-context maps; trust boundaries; data flows; "you-are-here" diagrams that match the deployed reality. Owned by Solution Architect with monthly reconciliation cadence; consumed by every new joiner, every brownfield audit, every change scoped via `impact-analysis`. Distinct from `technical-documentation` (operational + developer docs). Use when establishing initial architecture documentation, when significant architecture changes ship, when a new joiner needs to onboard, when discovering documentation drift, or in the monthly reconciliation cadence.'
---

# Architecture Documentation

<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: active
dependencies:
  - architecture-pattern-selection
  - adr-decision-records
  - codebase-comprehension
  - api-design
  - data-modeling
triggers:
  - "establishing initial architecture documentation for a new project"
  - "significant architecture change shipping (new service, new boundary, new pattern)"
  - "new joiner onboarding (architecture-docs is their first read)"
  - "discovering documentation drift (docs disagree with reality)"
  - "monthly reconciliation cadence"
  - "preparing architecture review or audit"
outputs:
  - C4 context diagram (Level 1)
  - C4 container diagram (Level 2)
  - C4 component diagrams (Level 3; per container as needed)
  - ADR archive (chronological)
  - architecture overview document (the human-readable narrative)
  - trust-boundary + data-flow diagrams
  - decision log index (ADR titles + dates + status)
consumers:
  - solution-architect (primary author + reconciler)
  - lead-developer (consumes when planning slices)
  - architecture-challenger (reads to challenge from a current view)
  - new-joiner onboarding (their starting point)
  - impact-analysis (consumes the system map)
  - tech-writer (assists with prose; integrates with `technical-documentation`)
references: []
```
<!-- praxis:metadata:end -->

The discipline that keeps architecture *knowable*. Documentation that has drifted from the deployed system is worse than no documentation — it confidently misleads. This skill is the practice of maintaining a small set of high-leverage architecture artifacts so they reflect what's actually built, today.

The principle: **architecture docs are a living artifact. The cadence of reconciliation determines whether they're an asset or a liability.**

## When this skill fires

- Establishing initial architecture documentation for a new project.
- Significant architecture change shipping — new service, new boundary, new pattern.
- New joiner onboarding — architecture docs are their starting read.
- Documentation drift discovered (docs disagree with reality).
- Monthly reconciliation cadence.
- Preparing for architecture review or audit.

## The C4 model — levels and what they contain

C4 is the discipline. Four levels; each answers a different question.

### Level 1 — System Context

Who uses the system; what external systems it connects to.

- The system is one box.
- Around it: users (personas), other systems (databases not shown; just "Payment Gateway", "Identity Provider", "CRM").
- One diagram for the whole system.

Updated when external connectivity changes.

### Level 2 — Container

The deployable units inside the system.

- Each major deployable: web frontend, mobile apps, backend services, databases, message buses, caches.
- Technologies labeled on each container (Java/Spring, React, Postgres, Kafka).
- Communication between containers (HTTP, message bus, file).

One diagram per system. Updated when containers added / removed / split.

### Level 3 — Component

Inside a single container, the major components.

- Modules / packages / hexagonal-architecture ports + adapters.
- Per container that's complex enough to warrant it (typically backend services); skip for simple ones.

Updated when major component-level refactors ship.

### Level 4 — Code

Class / file structure. Rarely maintained as diagrams — kept in code only. Don't draw these unless there's a specific reason.

**Fidelity per level**: Level 1 and 2 are the high-leverage diagrams; maintain them rigorously. Level 3 selectively. Level 4 typically never.

## ADRs — the immutable decision trail

ADRs are the **decision** plane; C4 diagrams are the **state** plane. Each ADR records:

- Context (what problem prompted the decision).
- Options considered.
- Decision (chosen option + rationale).
- Consequences (positive + negative).
- Status (proposed / accepted / superseded by ADR-NNN / rejected).

ADRs are immutable. Decisions that change → write a new ADR that supersedes the old one; don't edit the old one.

Per `adr-decision-records`, every significant decision warrants an ADR. The archive grows monotonically; superseded ADRs stay readable for the trail.

ADR-archive index: `.project/decision/INDEX.md` — chronological list with status. Maintained by Solution Architect at each ADR addition.

## The architecture overview document

A single human-readable Markdown document. Sits at `.project/working/architecture/overview.md` (or equivalent). Sections:

```markdown
# Architecture Overview

## What this system does
- One paragraph; written for a new joiner.

## Quality attributes (the NFRs)
- Reference to NFR register; the top 3-5 NFRs called out by name.

## C4 context (Level 1)
- Embedded diagram + brief callouts of each external system.

## C4 containers (Level 2)
- Embedded diagram + per-container 1-paragraph description.

## Key architecture decisions
- Link to ADR archive index.
- Top 5 ADRs called out by name + 1-line summary each.

## Trust boundaries + data flows
- Per `threat-modeling` skill — boundaries between trust zones; data flows across them; auth at each boundary.

## Operational shape
- Deployment topology (link to `iac` artifacts + Layer-4 platform pack).
- SLOs (link to `observability`).
- Reliability posture (link to `reliability-dr`).

## How to navigate this codebase
- Top-level repo layout.
- Where to start for common tasks (add an endpoint, change a feature, debug an incident).

## What we deliberately are NOT
- Scope boundary; the "non-goals."
```

This document IS the architecture documentation. The C4 diagrams + ADRs are embedded references. A new joiner reads this front to back.

## Trust boundaries + data flows

Per `threat-modeling`, the trust-boundary diagram is its own artifact:

- Zones (DMZ, application tier, data tier, third-party).
- Boundaries between zones.
- Authentication enforcement at each boundary.
- Data flows crossing boundaries — what data, what protection (in-transit / at-rest), what authorization.

Updated when boundaries change (new trust zone, new boundary crossing).

## Reconciliation cadence

The thing that keeps docs from becoming archaeology.

**Monthly cadence** (Solution Architect responsibility):

- Walk Level 1 — are external systems current?
- Walk Level 2 — are containers + their tech stacks current? Are inter-container edges still as drawn?
- Walk top of architecture overview — does paragraph 1 still describe what we ship?
- Check the ADR index — any superseded decisions not marked as such?
- Diff: declared vs actual (read recent IaC changes; recent deploys).

Discrepancies → fix the docs (preferred) or open a `tech-debt-management` entry to fix the deployment (when the docs reflect the intended target).

**Triggered cadence** (any time):

- New service deployed → Level 2 updated.
- New external integration → Level 1 updated.
- New ADR accepted → index updated; overview's "key decisions" reviewed.
- Significant component refactor → Level 3 diagram for that container updated.
- New trust boundary → boundary diagram updated.

**Quarterly cadence**:

- Full re-read of architecture overview from a new-joiner's perspective. If it doesn't read smoothly, rewrite.
- Review ADRs for "decisions that should have been written but weren't" — backfill.

## "You are here" discipline

Architecture docs answer: *given the system as it actually is today, where are we?* They are NOT:

- A wishlist of where the architecture should go (that's roadmap / `project-phasing`).
- A historical record of every architecture iteration (the ADR archive does that).
- A snapshot frozen at project kickoff (that's the original ADR; reality has moved).

When docs and reality diverge: fix the docs. The architecture is whatever's deployed; the docs serve readers who need to understand the deployed reality.

## Diagrams as code

Diagrams maintained in code-first formats:

- **Mermaid** for C4 (in Markdown; renders in most viewers).
- **PlantUML / Structurizr** for richer C4 fidelity if needed.
- **draw.io / Excalidraw** for sketches that don't warrant code (kept SVG-source in repo).

Avoid: PNG-only diagrams (impossible to update); embedded screenshots; visio-only formats (vendor lock).

Diagrams in code = diagrams in version control = diagrams that don't drift silently.

## Outputs

| Output | Location |
|---|---|
| Architecture overview | `.project/working/architecture/overview.md` |
| C4 context diagram | `.project/working/architecture/c4-context.md` (Mermaid) |
| C4 container diagram | `.project/working/architecture/c4-container.md` (Mermaid) |
| C4 component diagrams | `.project/working/architecture/c4-component-{container}.md` |
| ADR archive | `.project/decision/` (per `adr-decision-records`) |
| ADR index | `.project/decision/INDEX.md` |
| Trust-boundary diagram | `.project/working/architecture/trust-boundaries.md` |
| Reconciliation log | `.project/operational/architecture-reconciliation.md` (date + walk findings) |

## Mode handling (G/B)

**Greenfield.** Diagrams written before the code is. Level 1 + 2 + overview in the project kickoff. Reconciliation cadence starts immediately.

**Brownfield.** First task is **discovery** (per `codebase-comprehension`) — extract what's actually there. Then write the docs the codebase deserves. Common finding: the existing diagrams are 6-24 months stale.

## Critical disciplines

**Reconcile monthly.** The cadence IS the discipline. Without it, docs drift.

**Diagrams as code.** PNG diagrams become abandoned within a year.

**ADRs for decisions; diagrams for state.** Don't conflate.

**Overview is for humans.** If reading it doesn't feel like reading prose, rewrite. Not bullet-list bingo.

**Fix docs OR fix reality.** When they disagree, one or the other moves. Open a debt entry if reality needs to move.

**Audit reads what new joiners would.** If an audit reads only the diagrams without the overview, you're missing the integrative narrative.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Diagrams are documentation enough." | Diagrams without narrative are inscrutable. The overview + the diagrams together are documentation. |
| "We'll reconcile when something changes." | Most projects "change something" weekly. Without cadence, reconciliation never happens. Monthly walk minimum. |
| "C4 Level 4 should be diagrammed." | Level 4 ages fastest; lives in code. Don't diagram it unless there's specific reason. |
| "ADRs are immutable; that's bureaucratic." | Immutability is what makes the trail trustworthy. Decisions change via new ADRs that supersede; preserve the trail. |
| "Visio/Lucidchart is fine for diagrams." | PNG diagrams become abandoned. Use code-first formats (Mermaid / PlantUML / Structurizr). |
| "Trust-boundary diagram is for the security review." | It's also for impact analysis, threat modeling, incident response. Keep it current. |
| "Overview is implicit in the diagrams." | The narrative is what synthesizes the diagrams + ADRs. Without it, readers can't put it together. |

## Verification

You are done when:

- [ ] Architecture overview at `.project/working/architecture/overview.md` reads as prose; not a bullet list.
- [ ] C4 Level 1 (context) + Level 2 (containers) exist as Mermaid/PlantUML, current within month.
- [ ] C4 Level 3 exists for complex containers.
- [ ] ADR archive + INDEX.md current; ADRs immutable.
- [ ] Trust-boundary diagram exists + current with security-review cycle.
- [ ] Reconciliation log shows monthly walk completed.
- [ ] No "stale" markers older than threshold.
- [ ] Discrepancies between docs + reality either fixed-the-docs OR opened-debt-entry-for-reality.

Evidence to check:
- A new joiner can navigate the docs in 30 minutes and explain the system.
- An audit can map deployed reality to documented architecture.

## Anti-patterns

- Diagram once at kickoff; never update.
- C4 Level 4 maintained as diagrams (impossible to keep current).
- ADRs deleted or edited (immutability broken).
- Overview document doesn't exist (only diagrams; no narrative).
- Trust boundary diagram absent (security review can't proceed).
- Reconciliation cadence skipped; quarterly readers find years of drift.
- Diagrams in formats only one person can edit.
- Architecture overview reads like an ADR summary (no narrative).
- "Sources of truth" plural (multiple disagreeing diagrams in the wiki).
- Documentation as an event ("we documented the architecture in Q2") rather than a practice.
