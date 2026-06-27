---
name: adr-decision-records
description: Standardize how every significant architectural and engineering decision is recorded as an Architecture Decision Record (ADR) — context, options considered, decision taken, consequences, rejected alternatives. Use whenever a non-trivial decision is being made that future readers will need to understand (architecture choices, technology selections, risk acceptances, policy waivers, deprecations, supersessions). ADRs live in `.project/decision/` and are indexed by `memory-management`. The team's decision memory; every design and review skill defers to this format. Pushy trigger because undocumented decisions are the most common operational failure.
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - project-memory
triggers:
  - "making an architecture decision"
  - "choosing between technology options"
  - "accepting a risk explicitly"
  - "waiving a security finding"
  - "deprecating a skill, library, or pattern"
  - "superseding a prior decision"
  - "documenting a Challenger objection override (governance)"
outputs:
  - ADR file (.project/decision/adr-NNNN-{slug}.md)
  - INDEX entry (added via project-memory + memory-management)
consumers:
  - solution-architect
  - architecture-challenger
  - all role agents (any agent can author an ADR)
  - memory-management (indexes ADRs)
references: []
---

# ADR — Architecture Decision Records

The standard format and lifecycle for the team's decision memory. Every significant decision becomes an ADR. The format is small, opinionated, and the *only* sanctioned way to record decisions — no scattered Slack messages, no design-doc-then-forgotten, no folklore.

## When to write an ADR

An ADR is required for any decision that:

- **Changes the architecture** — chosen pattern, new bounded context, new integration, new persistence store.
- **Selects a technology or vendor** — framework, library, managed service, cloud region.
- **Accepts a risk or waives a control** — Challenger objection override, security finding waiver, NFR target relaxation.
- **Deprecates or supersedes** — sunsetting a library, retiring a pattern, replacing a service.
- **Establishes a project-local convention** — overrides to `engineering-standards`, naming or layout rules specific to this codebase.

An ADR is *not* required for trivial decisions (choice of variable name, ordering of arguments, etc.). Test: would a future engineer asking "why did we do this?" benefit from an explanation? If yes, ADR.

## The template

ADRs are short. Aim for under 250 lines. Filenames are `adr-NNNN-{kebab-case-slug}.md` with sequential numbering across the project.

```markdown
---
type: decision
title: <short title>
adr_id: adr-NNNN-{slug}
date: YYYY-MM-DD
status: proposed | accepted | superseded | rejected | deprecated
author: <agent or human name>
tags: [tag1, tag2, ...]
impacted_domains: [billing, auth, ...]
confidence: high | medium | low
supersedes: <adr-id-if-applicable>
superseded_by: <adr-id-if-applicable>
related: [<adr-id>, ...]
---

# ADR-NNNN: <Title>

## Status

<one of: proposed, accepted, superseded by adr-MMMM, rejected, deprecated>

## Context

What is the problem or question this decision addresses? What forces are at play
— NFRs, constraints, prior decisions, business drivers? Keep this concrete.
Reference the relevant `.project/semantic/` entries, NFR register entries,
or prior ADRs.

## Options considered

Enumerate the realistic options. For each:

- **Option A: <name>** — short description; pros; cons.
- **Option B: <name>** — short description; pros; cons.
- **Option C: <name>** — short description; pros; cons.

Three options is typical; two is fine; one is a yellow flag — if there's really
only one option, this is probably not a decision worth an ADR.

## Decision

We chose <Option X> because <primary reasons tied to the context>.

State the decision crisply. One sentence ideally; one paragraph at most.

## Consequences

What follows from this decision — positive, negative, and neutral:

- **Positive.** Things this enables or simplifies.
- **Negative.** Costs accepted, debts taken on, future work this commits to.
- **Neutral.** Side effects that are neither good nor bad but worth flagging.

Be honest about negatives. ADRs that only list positives are the ones future
readers regret most.

## Rejected alternatives

Brief paragraph per rejected option — *why* it was rejected. Future readers
sometimes find the rejection rationale more useful than the chosen path.

## Related decisions

- supersedes: adr-NNNN (link, with one-line summary of what changed)
- superseded by: adr-NNNN
- related: adr-NNNN, adr-NNNN
```

## Lifecycle

ADRs move through five status states:

```
proposed → accepted → (superseded | deprecated)
            ↓
         rejected
```

- **proposed** — drafted but not yet approved per the governance matrix.
- **accepted** — approved; this is the current decision.
- **superseded** — a later ADR has replaced this one; this ADR carries `superseded_by: adr-MMMM`.
- **rejected** — the proposal was not adopted; the ADR is kept for context (the reasoning still has value).
- **deprecated** — the decision still stands but the underlying choice is being phased out (e.g., the library this ADR adopted is being migrated away from).

ADRs are **never deleted**. Even rejected ones stay — they prevent future re-litigation of the same question.

## Supersession discipline

When a new ADR supersedes an older one:

1. The new ADR carries `supersedes: adr-NNNN` and explains in its Context what changed since the original.
2. The old ADR is updated *in place* to `status: superseded` and `superseded_by: adr-MMMM`. Its body is **not modified** otherwise — the original reasoning stays intact.
3. `memory-management` updates the index to reflect both states.

Cascading supersession (A → B → C) is allowed but flagged for review — three ADRs on the same question in a year suggests the question itself is unstable and may need broader rethinking.

## Numbering

ADRs are sequentially numbered across the project, starting at 0001. No branches or sub-numbering. If two ADRs are written concurrently the orchestrator assigns numbers on write (single-writer discipline via `project-memory`).

## Authoring agents

Any agent can author an ADR. Most commonly:

- **Solution Architect** — the bulk of architecture decisions.
- **Architecture Challenger** — *override ADRs* when the SA rejects a Challenger finding (the rationale becomes an ADR per the governance matrix).
- **Security Reviewer** — security-finding waivers as ADRs.
- **PM** — requirements decisions worth preserving.
- **Platform/SRE** — operational and infrastructure decisions.
- **ML / AI Engineer** — model selection, framing, eval design.

The agent fills the template, invokes `project-memory` to write to `.project/decision/`, and `memory-management` updates the index.

## Approval routing

The governance matrix (Section 7) defines who approves what category of ADR. The orchestrator routes proposed ADRs to the right approver before flipping `status: proposed` → `status: accepted`.

## Mode handling (G/B)

**Greenfield.** ADR numbering starts at 0001; the first ADR typically captures the architecture-pattern selection.

**Brownfield.** Scan existing ADR-like documents on adoption — if the legacy codebase has design docs in a recognizable format, this skill bootstraps them as ADRs with their original dates and a `confidence: medium` tag (acknowledging the format conversion). New ADRs start at the next available number.

## What this skill does not do

- Decide what's worth deciding — that judgment lives in the agent invoking this skill.
- Approve ADRs — governance matrix does that; this skill captures the artifact.
- Index ADRs — `memory-management` does that; this skill writes, that one reads.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll write the ADR after we know it worked." | After-the-fact ADRs are retro-rationalization, not decisions. The ADR's value is in capturing the reasoning *before* the outcome is known. |
| "This decision is too small for an ADR." | Small decisions that shape architecture compound. Better to write a 10-line ADR than to lose the rationale. |
| "We already decided in the meeting; ADR is paperwork." | Meetings die; ADRs survive. The new joiner six months from now will read the ADR, not your meeting notes. |
| "Decision changed; I'll just edit the old ADR." | ADRs are immutable. Write a new one that supersedes; preserve the trail. |
| "Status doesn't matter; the decision is the decision." | Status (proposed/accepted/superseded) is what new readers use to know which ADR is current. Don't skip it. |
| "Alternatives section is busywork." | "What we didn't pick and why" is the most read section in 6 months — when someone wonders "why didn't we do X?" |

## Verification

You are done when:

- [ ] ADR file exists at `.project/decision/<NNN>-<title>.md` with monotonic numbering.
- [ ] All 5 required sections present: Context / Options / Decision / Consequences / Status.
- [ ] At least 2 alternatives considered (even if one is "do nothing").
- [ ] Consequences include both positive AND negative (no all-upside ADRs).
- [ ] Status is one of: `proposed`, `accepted`, `superseded by ADR-NNN`, `rejected`.
- [ ] `.project/decision/INDEX.md` updated with the new entry.
- [ ] Reviewer-listed (who approved) for `accepted` status.
- [ ] If superseding: the prior ADR's status updated to `superseded by ADR-<this>`.

Evidence to check:
- Reading just the Context + Decision sections, a new joiner can understand what changed and why.
- No edits to the ADR body after `accepted` status — only status field updates allowed.

## Anti-patterns

- ADRs written *after* the decision was made and the code shipped. ADRs are decisions; they precede or accompany implementation. Retroactive ADRs are warning signs.
- ADRs that document "we'll figure it out later." That's not a decision; that's an open question. Open questions live in `.project/working/in-flight-{topic}.md`, not as ADRs.
- ADRs longer than 500 lines. Long ADRs are usually two ADRs trying to be one.
