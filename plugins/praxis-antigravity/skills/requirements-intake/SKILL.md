---
name: requirements-intake
description: "The steady-state intake discipline for brownfield projects — how the team handles the continuous arrival of new requirements after the initial /audit + /discover + /architect rounds are complete. Captures each incoming ask into `.project/working/inbox.md`, runs lightweight triage (size + impact + owner), sequences by dependency + risk score, groups related items into mini-phases, and routes whole groups (not individual items) into `/discover`. Prevents two common failure modes: FIFO churn (every small ask gets full ceremony, team burns out) and impulse coding (small asks skip impact-analysis and detonate load-bearing modules). Use whenever a new requirement arrives at a brownfield project past initial discovery. Distinct from `requirements-elicitation` and `product-discovery`."
---

# Requirements Intake

<!-- praxis:metadata:begin -->
```yaml
capability: discovery
domain: cross-cutting
state: experimental
dependencies:
  - product-discovery
  - requirements-elicitation
  - impact-analysis
  - project-memory
  - codebase-comprehension
triggers:
  - "new requirement arrives at an ongoing brownfield project"
  - "PM dumps a batch of stories or asks into the project"
  - "stakeholder requests a change mid-flight"
  - "discovering an inbox backlog that hasn't been triaged"
  - "deciding whether the next requirement is one slice, several slices, or needs architecture"
  - "deciding whether to refresh codebase-comprehension before scoping a new ask"
outputs:
  - .project/working/inbox.md (the triage queue, append-only)
  - .project/working/inbox-decisions.md (sequencing + grouping decisions per cycle)
  - one or more grouped intake briefs handed to /discover
  - impact-analysis refresh decisions (which modules to re-comprehend)
consumers:
  - product-manager (primary author)
  - delivery-lead (uses the sequencing decision to route work)
  - solution-architect (consumes the grouped brief for any architectural impact check)
  - all developer agents (consume the per-group requirements via the implementation packet)
references: []
```
<!-- praxis:metadata:end -->

The first months of a brownfield engagement are bounded: one `/audit`, one `/discover`, one `/architect`, then slices. After that — for the rest of the project's life — requirements keep arriving. This skill is what you do every time one shows up.

The two failure modes this skill prevents are not theoretical:

- **FIFO churn.** Every small ask is treated like a new project: full discovery, full architect pass, full slice. The team burns out. By month three the principal is reviewing six PRs a day with no thread to follow.
- **Impulse coding.** Small asks skip `impact-analysis` because they "look obvious," ship straight into the codebase, and the third one detonates a load-bearing module. The cleanup costs more than the asks would have if triaged properly.

Both are common. Both are avoidable. The intake discipline is the avoidance.

## When this skill fires

- Any time a new requirement, ticket, story, stakeholder ask, bug-disguised-as-feature, or change request arrives at the project — once the initial discovery + architecture pass is complete.
- When you notice an untouched inbox of requests has accumulated.
- When you're tempted to skip triage and "just do this one quickly." That is exactly when this skill fires.
- Before deciding whether to refresh codebase-comprehension (a partial re-run on affected modules is usually right).

This skill does NOT fire during the initial engagement — that's `/discover` running on the original principal_intent. This is for steady-state.

## The intake procedure

### Step 1 — Capture the ask in `.project/working/inbox.md`

This is a single append-only markdown file. Each new ask gets ~5 minutes of writing and these fields:

```markdown
## R-{N}: {short-name}     [arrived YYYY-MM-DD, from <stakeholder>]

- **The ask:** {one sentence — what the requester literally asked for}
- **The intent:** {what they actually need — often different from the ask}
- **Business outcome:** {what success looks like for the requester}
- **Deadline / urgency:** {if any — date, event, or 'whenever'}
- **Suspected impact areas:** {modules / domains likely affected — your guess, not validated yet}
- **Status:** intake | triaged | grouped:<group-name> | in-discover | shipped | rejected
```

The point of the inbox file is **provenance**. Three months later when a stakeholder says "what happened to that thing I asked about?" — you can find it. The inbox is not the work itself; it's the audit trail.

### Step 2 — Triage (lightweight, 10 minutes per item max)

For each new item, decide three things:

1. **Rough size:** XS (one slice, <2 days) / S (one slice, ~1 week) / M (2–4 slices) / L (architecture impact, may trigger /architect) / XL (genuinely new sub-product, run full /discover).
2. **Risk score (1–5):** Based on impact-analysis quick read — how many modules touched, are any of them in `.repo-intel/hotspot-analysis.md`, does it cross trust boundaries, does it touch the data plane?
3. **Owner:** Which existing agent does this fall to? PM for ambiguous, Lead Dev for narrow tech, BE/FE/Data/ML for stack-specific.

Write the decision back into the inbox entry as a one-liner: `Triage: M, risk 3, owner PM`.

**Do not** elaborate the requirement at this stage. Triage is about routing, not writing specs. Specs come in `/discover` when this item enters a group.

### Step 3 — Sequence (every triage cycle, ~weekly)

You'll have a stack of triaged items. Sequence them by two cuts:

- **Dependency:** Item B builds on Item A → A goes first. Item C is independent → it can interleave.
- **Risk-weighted urgency:** `urgency × (6 - risk)`. Higher = sooner. This rewards low-risk + high-urgency (do now) and demotes high-risk + low-urgency (do later, with care).

Write the sequenced list at the bottom of `.project/working/inbox-decisions.md` with the date and reasoning. This is the artifact the delivery-lead reads when routing next.

### Step 4 — Group into mini-phases

Look at the sequenced top of the queue. Items that touch the same module, the same data model, the same user surface, or the same NFR cluster should be **grouped**. A group becomes one `/discover` pass, one architecture-impact check, one implementation packet.

| Item alone | Item in a group |
|---|---|
| 4 separate `/discover` runs | 1 `/discover` run on the bundle |
| 4 implementation packets | 1 grouped packet, slices fanned out |
| 4 review cycles | 1 review with shared context |
| Stakeholder confusion ("which one shipped?") | Single phased release |

Grouping is the single most under-used discipline in steady-state brownfield. The triage is cheap; the savings are large.

A group gets a name, an owner, an estimated horizon (1 sprint? 2?), and a list of inbox items. Write it at the top of `.project/working/inbox-decisions.md`.

### Step 5 — Decide on `.repo-intel/` freshness

For each group, before handing to `/discover`, check whether the relevant `.repo-intel/` maps are stale:

- If `.repo-intel/` is < 30 days old AND no major merges touched the relevant modules → fresh, skip re-comp.
- If `.repo-intel/` is 30–90 days old OR there have been significant merges → **partial re-comprehension** on the affected modules. Don't re-comp the whole repo.
- If `.repo-intel/` is > 90 days old or the codebase has shifted significantly → full re-comprehension. This is rare in steady-state.

Record the decision in the inbox-decisions file.

### Step 6 — Hand the group to `/discover`

`/discover` runs scoped to the GROUP, not to the project. Inputs:

- The principal_intent for the group (synthesized from the items)
- The existing opportunity doc (read-only)
- The (now-fresh) `.repo-intel/`
- The items themselves, with their original asks and inferred intents

From here the standard fork: `/architect` if architecture touched, otherwise straight to `/slice`. Each item from the group may become one slice, multiple slices, or — if the discover process reveals it's no longer needed — get marked `rejected` in the inbox with reasoning.

## Anti-rationalization

The reason this discipline holds is that the alternatives are seductive in the moment and expensive over time. Each row is a real failure mode.

| Shortcut you'll be tempted to take | Why it's tempting | What actually happens | Hold the line |
|---|---|---|---|
| "This is a small ask, skip triage" | Capturing the inbox entry feels like overhead | The ask gets forgotten or duplicated; provenance is lost; downstream impact-surprise costs days | 5 minutes of inbox writing is the cheapest insurance you'll buy |
| "Just go straight to a slice, the impact is obvious" | The visible code change is small | The invisible blast radius takes out a load-bearing module | `impact-analysis` is mandatory; it's 15 minutes and catches the case that costs the project |
| "FIFO is fair, work them in arrival order" | Feels fair to stakeholders | Real impact and risk get ignored; high-risk items get worked at the wrong time | Sequence by dependency + risk-weighted urgency, communicate the sequencing to stakeholders |
| "Group later — these don't look related" | Each item has its own requester | Two items touch the same module → you re-comp twice, design twice, review twice | Re-read groups after each new arrival; relatedness emerges from the inbox, not from requesters |
| "`.repo-intel/` is recent enough" | Re-comprehension feels like dead work | A merge from 3 weeks ago invalidates the dependency map; intake decisions are made on stale data | If unsure, partial re-comp on the affected modules. Cheap; defensive |
| "We'll triage later, just queue them up" | Today is busy | The backlog rots; later you face a 40-item triage day instead of 5 ten-minute ones | Triage on arrival or at most weekly. Never let the inbox get past ~10 untriaged items |
| "The requester said it's urgent, skip sequencing" | Urgency feels real | Real urgency vs. requester urgency are different things; the project gets whipsawed | Urgency is one input to the sequence formula, not the whole formula. Risk and dependencies still apply |
| "Don't write the intent, just the ask" | The ask seems clear | The ask and the intent diverge in 1 of 3 cases; teams build the wrong thing | Write both. The intent is what the implementation should serve |

## Red flags during intake

These signals tell you the discipline is breaking. Pause when you see them.

- **Inbox is "active" — no triage column.** Items are being added but never triaged. The inbox is rotting; do a triage sweep immediately.
- **Same module appearing in 3+ ungrouped items.** Should have been grouped two arrivals ago. Group now; the re-discovery cost has already started.
- **Stakeholder asks "where is this in the queue?"** and you can't answer. Inbox provenance is missing; you've drifted out of the discipline.
- **Items getting reordered weekly based on who shouted loudest.** Risk-weighted sequencing is being overridden by politics. Document the override reason explicitly so it's visible.
- **`/discover` running on single items repeatedly.** Either grouping is failing or items are genuinely independent — re-read your last 5 intake decisions to see which.
- **`impact-analysis` skipped because "the change is small."** This is the canonical bug. Re-run it before merging anything.
- **`.repo-intel/` hasn't been refreshed in > 90 days.** Your triage decisions are running on a stale map. Schedule a refresh next cycle.
- **Multiple slices ship without a release entry in `.project/operational/releases/`.** The shipping discipline is degrading too; it's a symptom of upstream intake erosion.

## Verification

Before treating an intake cycle as complete, verify all of:

- [ ] Every new ask has an inbox entry with ask + intent + outcome + suspected impact + status
- [ ] Every triaged item has size + risk + owner recorded
- [ ] The sequencing decision is written with explicit reasoning (not just a reordered list)
- [ ] Groups have name + owner + horizon + member items
- [ ] `.repo-intel/` freshness decision is recorded per group with the decision (skip / partial / full)
- [ ] The group(s) handed to `/discover` carry the synthesized principal_intent and the underlying items
- [ ] No item has been silently dropped (rejected items are explicitly marked with reasoning)
- [ ] The inbox-decisions.md entry is dated and signed (PM name or initials)

The intake artifact lives as long as the project; later steward review will read it to understand decision history. Write it like a future-you will need to defend it.

## Operating cadence

| Tempo | What runs |
|---|---|
| **On arrival of any item** | Step 1 (capture) — always. Steps 2–3 (triage + tentative sequence) — if the inbox has < 3 untriaged items, do it now |
| **Weekly (or per sprint)** | Steps 2–6 in one sitting; produces the next group(s) for `/discover` |
| **Monthly** | Review the rejected items; were any of them right and we missed it? Refresh `.repo-intel/` if not already done in a triage cycle |
| **Quarterly** | System Steward reads `.project/working/inbox-decisions.md` as part of factory-evaluation; surfaces patterns (chronic over/under-grouping, recurring stakeholder, common module getting hit) |
