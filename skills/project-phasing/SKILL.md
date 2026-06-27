---
name: project-phasing
description: Convert validated requirements + chosen architecture into a phased, dependency-ordered roadmap of vertical slices. MVP/walking-skeleton first, then prioritized increments. Each slice is the *thinnest* user-visible value that flows through every layer (DB → service → API → UI if applicable).
---

# Project Phasing


<!-- praxis:description:full -->
## Full description

Convert validated requirements + chosen architecture into a phased, dependency-ordered roadmap of vertical slices. MVP/walking-skeleton first, then prioritized increments. Each slice is the *thinnest* user-visible value that flows through every layer (DB → service → API → UI if applicable). Phasing is the spine that turns "build the thing" into "build it slice by slice with discipline." Use whenever a project transitions from architecture to execution, or when re-planning mid-project.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: lifecycle
domain: cross-cutting
state: active
dependencies:
  - requirements-elicitation
  - architecture-pattern-selection
  - nfr-definition
  - product-discovery
triggers:
  - "transitioning from architecture to execution"
  - "planning the slice sequence"
  - "scoping the walking skeleton"
  - "re-prioritizing mid-project"
  - "estimating delivery milestones"
outputs:
  - phased roadmap (slice list with dependency ordering)
  - walking-skeleton slice definition
  - milestone plan
  - dependency graph between slices
consumers:
  - delivery-lead (executes the roadmap)
  - delivery-planner (parameterizes workflow from slice characteristics)
  - product-manager (validates slice ordering against priority)
  - solution-architect (validates slice feasibility against architecture)
  - all developer agents (work per slice)
references: []
```
<!-- praxis:metadata:end -->

Phasing is what turns a project from "we'll figure out what to build next when we get there" into "here's the sequence, here's the dependency graph, here's where each slice produces measurable value." It's the most-leveraged planning artifact for incremental delivery.

The key principle: **every slice is end-to-end**. A slice is not "the database schema for the order subsystem"; a slice is "user can create an order, see it persisted, and view it in the UI — with one item, one customer, one product." Slices are vertical, not horizontal.

## When this skill fires

- The architecture is approved and the project is ready to enter execution. PM runs this with input from SA.
- Mid-project, when re-prioritization is needed (new information, changed business priority, slice slipped).
- After factory-evaluation surfaces that the current slice plan isn't producing learning fast enough.

## The phasing procedure

### 1. Define the walking skeleton

The first slice is special. It is the **smallest end-to-end vertical that exercises every layer** of the chosen architecture and ships through the real pipeline into the real environment ladder.

For a modular monolith with a Postgres DB and a React frontend, the walking skeleton might be: "user can submit a contact form; submission persists to DB; user sees confirmation." That's it. One endpoint, one table, one component — but it goes through CI/CD, runs in a real environment, and is observable.

The walking skeleton's job is *not feature value* — it's to **shake out the plumbing** before any complexity lands on top. Stage 4 (environments + pipeline) ships before Stage 5 (develop) precisely so the walking skeleton runs through the real machinery from day one.

### 2. Decompose into vertical slices

For each story or capability beyond the walking skeleton:

- Slice into the smallest piece that delivers measurable user value.
- Each slice touches every relevant layer (data + service + API + UI if applicable).
- Slices are 2–10 days of effort each. Larger means it should be split further.
- Slices have explicit acceptance criteria (from `requirements-elicitation`).

### 3. Identify dependencies

Each slice's dependencies on prior slices are explicit:

```
slice-0: walking skeleton
slice-1: user can register an account (depends on: slice-0)
slice-2: user can log in (depends on: slice-1)
slice-3: user can create an order (depends on: slice-2, infrastructure: order persistence)
slice-4: user can view their orders (depends on: slice-3)
slice-5: payment integration (depends on: slice-3, external: payment provider sandbox)
slice-6: order cancellation (depends on: slice-3, slice-5 if refund)
```

The dependency graph is a DAG. Slices without dependencies on each other can run in parallel (if the team has the capacity per `delivery-planner`'s parallelism strategy).

### 4. Order by priority within constraint

Within the dependency graph, order by:

- **Business value** — high-value slices early.
- **Risk reduction** — uncertain slices (technical risk, integration risk, user-validation risk) earlier rather than later, so failures surface cheaply.
- **Learning velocity** — slices that produce learning (signal on a hypothesis from `product-discovery`) earlier.
- **Cost of delay** — slices that unlock other slices have higher implicit priority.

The order isn't a strict ranking — it's a sequence the team will execute, revisable per slice.

### 5. Milestone-tag the roadmap

Milestones are the human-facing checkpoints:

- **M1 — Walking skeleton live in staging.**
- **M2 — First user journey end-to-end (slices 1–3 done).**
- **M3 — Payment integration shipped (slice 5 done).**
- **M4 — MVP launch (all in-scope slices done, NFRs verified).**

Milestones are *outcomes*, not arbitrary dates. A date is attached only after estimation against the team's actual velocity (calibrated by `factory-evaluation` over time).

### 6. Identify slice-level risk

For each slice, briefly note:

- **What could go wrong technically?** (Integration risk, performance risk, edge cases.)
- **What could invalidate the slice's value?** (Pointers to the assumptions from `product-discovery`.)
- **What's the rollback?** (How do we undo this slice if it shipped wrong?)

These notes feed into `risk-assessment` and the per-slice KUACQ blocks.

## Output format

The phased roadmap lives in `.project/semantic/roadmap.md`:

```markdown
---
type: semantic
title: Phased Roadmap
date: YYYY-MM-DD
author: product-manager
tags: [planning, phasing, mvp]
confidence: medium
---

# Roadmap

## M0: Walking skeleton (1 week)

- slice-0: Submit contact form → persist → confirm.
  Acceptance: end-to-end through CI/CD, runs in staging,
  observable via dashboard.

## M1: First user journey (3 weeks)

- slice-1: User registration (depends: slice-0).
  Acceptance: <stories from requirements>.
  Risk: email verification flow integration with provider.
- slice-2: User login (depends: slice-1).
  ...
- slice-3: User creates an order (depends: slice-2).
  ...

## M2: Payment integration (2 weeks)

- slice-4: Single-payment flow (depends: slice-3,
  external: payment provider sandbox).
  Acceptance: ...
  Risk: webhook handling for async confirmations.
  Rollback: feature flag; revert to manual ops handling.
- slice-5: Refund flow (depends: slice-4).
  ...

## M3: MVP launch

- All in-scope slices done.
- NFR verification complete (load test, restore drill).
- Production go-live gate cleared.
```

## Updates mid-project

The roadmap is a working document. Updates are routine:

- A slice slips → either replan its dependents or accept the slip and update milestone dates.
- A new requirement arrives → slot a new slice into the dependency graph; check what it pushes back.
- A slice's risk materializes → re-order with the risky work earlier or de-scope it.

Each material update is captured in `.project/episodic/replan-{date}.md` so the project history is preserved.

## Walking skeleton discipline

The walking skeleton deserves special attention because it's the slice teams most often get wrong. Anti-patterns:

- **"Walking skeleton" that doesn't run end-to-end.** If the walking skeleton skips the DB or skips the pipeline, it isn't a skeleton — it's a feature stub.
- **"Walking skeleton" with feature value.** The skeleton's job is plumbing. Adding user-visible cleverness expands its scope; expanded scope means longer to ship; longer means the plumbing benefit arrives late.
- **No skeleton at all** ("we'll just start with slice-1"). Then the first real feature also has to fight every plumbing problem simultaneously.

## Mode handling (G/B)

**Greenfield.** Full phasing from scratch.

**Brownfield.** The walking skeleton concept changes — the existing system *is* the running plumbing. The first slice in brownfield is typically *the smallest meaningful change* that exercises the new behavior end-to-end against the existing system. Phasing also reads `.repo-intel/` to understand which existing components the slices touch and order around them.

## What this skill does not do

- Estimate dates — the roadmap names milestones as outcomes; date estimates come from team velocity calibration after the first slice or two.
- Reorder around hidden constraints — those need to be surfaced via `requirements-interrogation` first.
- Manage the slice execution itself — that's the Delivery Lead + the `using-praxis`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Phasing is over-planning; just start building." | The phasing IS the discovery of dependencies. Skipping phasing means discovering them at integration time. |
| "Each slice is independent." | Most slices have dependency on prior slices. Surface them in the phasing or hit them as surprises. |
| "Phasing should match team capacity." | Phasing matches the system's dependency graph; team capacity informs HOW MANY parallel tracks, not phasing itself. |
| "5-day slices are arbitrary." | They're an empirical sweet spot: small enough to verify, large enough to deliver. Wider variance has well-known costs. |
| "We can always re-phase later." | Re-phasing means rework. Get it right early; revisit at slice boundaries only. |
| "Phasing locks us in." | Phasing is a working hypothesis; revisits happen at gates. Locked-in is a misunderstanding of the artifact. |

## Verification

You are done when:

- [ ] Phased roadmap exists at `.project/working/architecture/phasing.md`.
- [ ] Each phase has a measurable outcome (not "more work done").
- [ ] Phase dependencies are explicit (Phase 2 needs Phase 1's X).
- [ ] Slices within each phase are 2-5 day work units.
- [ ] Each slice has acceptance criteria.
- [ ] At least one slice produces a deployable / shippable increment (no big-bang at the end).
- [ ] Risks per phase noted (what could derail this phase).
- [ ] Re-phasing triggers documented (what would cause us to re-plan).

Evidence to check:
- A reader can sequence the work just from the roadmap.
- Critical-path is identifiable; parallel-able work is identified.
- Slice estimates roll up to phase estimates; phase estimates roll up to project estimates.

## Sign-off

The phased roadmap is part of the **architecture_sign_off** gate evidence — the architecture and the phasing are signed off together.
