---
name: requirements-elicitation
description: "Convert validated product-discovery outputs into structured, testable requirements with explicit acceptance criteria, assumptions, open questions, and scope boundaries. Runs a clarifying-question loop before any design work begins — the discipline that prevents architecture and implementation from running on ambiguous foundations. Use whenever discovery has produced an opportunity brief + MVP scope hypothesis and the project is ready to enter design. Distinct from `requirements-interrogation` (which is the per-agent phase-entry KUACQ procedure) — this is the structured front-end discovery-to-requirements activity owned by the PM."
---

# Requirements Elicitation

<!-- praxis:metadata:begin -->
```yaml
capability: discovery
domain: cross-cutting
state: active
dependencies:
  - product-discovery
triggers:
  - "converting discovery output to formal requirements"
  - "writing user stories with acceptance criteria"
  - "scoping the requirements freeze"
  - "running a clarification loop on ambiguous requests"
  - "surfacing assumptions and open questions before architecture"
outputs:
  - requirements brief
  - user stories with acceptance criteria
  - assumptions register
  - open questions log
  - scope boundary (in/out of MVP)
consumers:
  - product-manager (primary author)
  - solution-architect (consumes requirements as the design input)
  - delivery-planner (consumes scope to instantiate the workflow)
  - architecture-challenger (reads requirements to attack assumptions)
  - all developer agents (consume per-slice requirements via the implementation packet)
references: []
```
<!-- praxis:metadata:end -->

Discovery told us *what's worth building*; this skill produces the structured, testable artifact that downstream phases can build against. The PM owns this skill; its output is the input to architecture and the foundation for every implementation packet.

## When this skill fires

- After `product-discovery` produces an MVP scope hypothesis and the requirements_freeze gate is approaching.
- When a new slice within an existing project needs its specific requirements articulated (smaller version of the same loop).
- When ambiguity surfaces mid-project and requirements need to be re-articulated for a slice.

## The elicitation procedure

### 1. Read the discovery output

From `.project/semantic/opportunity.md` and `.project/working/mvp-scope.md`. The MVP scope hypothesis is the input; requirements elicitation makes it concrete and testable.

### 2. Clarifying-question loop

Discovery produces *intent*; this step extracts the *specifics* by asking — explicitly — every question that needs to be answered before architecture can begin. The clarifying-question loop is the most important part of this skill.

Standard question categories (run each):

| Category | Sample questions |
|---|---|
| **Users** | Who exactly is the user? Are there multiple personas? What's their context of use? |
| **Trigger** | What initiates the user journey? Time, action, state change, external event? |
| **Inputs** | What does the user bring to this interaction? What does the system already know? |
| **Behavior** | What does the system do? What's the happy path? Branches? |
| **Outputs** | What does the user receive? What artifacts persist? Who else is notified? |
| **Edges** | What about empty state, error state, concurrent edits, offline, rate-limited? |
| **Quality** | How fast should it be? How reliable? How accurate? (Pointer to `nfr-definition`.) |
| **Constraints** | Regulatory? Internal policy? Existing-system contract? |
| **Out-of-scope** | What explicitly will NOT be built in MVP, even though related? |

The agent asks these questions of the human (PM running solo) or routes them to the requester. Each answer becomes part of the requirements brief. Each non-answer becomes an open question or an assumption.

### 3. Write user stories with acceptance criteria

Each story follows the standard form:

```
As a <persona>,
I want to <action>,
so that <outcome>.

Acceptance criteria:
- Given <precondition>, when <action>, then <expected outcome>.
- Given <precondition>, when <action>, then <expected outcome>.
- ...
```

Acceptance criteria are *testable* — written so QA and the developer can both verify they're met. Vague criteria ("system should be fast") are violations; "p99 response time under 200ms for the GET /orders endpoint" is the bar.

For MVP, stories are minimal — the thinnest set that delivers the validated outcome. Each story carries a `slice` tag identifying which delivery slice it belongs to (set later by `project-phasing`).

### 4. Surface assumptions

Every assumption that's been made — explicitly or implicitly — gets logged. Examples:

- "We assume the user is authenticated when reaching this flow."
- "We assume bank transaction data arrives within 24 hours of posting."
- "We assume user tolerance for false-positive matches is < 5%."

Assumptions go to `.project/working/assumptions.md` and become candidates for testing during architecture and implementation.

### 5. Capture open questions

What can't be answered yet? Each open question is tagged with:

- Who can answer it (stakeholder name or "research needed").
- When it must be answered (gate it blocks).
- What the temporary assumption is until then.

Open questions go to `.project/working/open-questions.md`.

### 6. Define scope boundary

What's *in* MVP, what's *deferred to later slices*, what's *explicitly out of scope*. Each story has a scope tag. The scope boundary is documented in a single artifact that the SA and Challenger read first when entering design.

## Outputs

| Output | Location | Audience |
|---|---|---|
| Requirements brief | `.project/working/requirements-brief.md` | All downstream phases |
| User stories with AC | `.project/working/user-stories.md` | SA, developers, QA |
| Assumptions register | `.project/working/assumptions.md` | SA (designs against assumptions), Challenger (attacks them) |
| Open questions | `.project/working/open-questions.md` | PM (tracks closure), orchestrator (gates progress) |
| Scope boundary | `.project/working/scope.md` | SA, planner, developers |

These flow into the implementation packet (Blueprint Section 9) which the developer agent receives per slice.

## The clarifying-question discipline

Most failure modes in delivery trace back to questions that should have been asked at this step but weren't. The PM's discipline is to ask the *uncomfortable* questions early — the ones that risk delaying the project — because the cost of asking them later is always higher.

If a question can't be answered before requirements freeze, it becomes either an open question (acknowledged risk) or an assumption (explicit risk). It never becomes a silent decision.

## Mode handling (G/B)

**Greenfield.** Standard elicitation against the discovery output.

**Brownfield.** Elicitation also reads `.repo-intel/` (from `codebase-comprehension`) to understand the existing system's behavior and constraints. Many requirements are about *changing* existing behavior rather than building new — those are framed against the current state explicitly. Brownfield user stories carry a `changes_existing_behavior: true` flag where applicable; QA uses this to write characterization tests against the prior behavior before the new behavior is implemented.

## What this skill does not do

- Discover *what* to build — that's `product-discovery`.
- Define quality targets — that's `nfr-definition` (parallel activity; both feed the SA).
- Design the solution — that's `architecture-pattern-selection`.
- Per-agent clarification at every phase entry — that's `requirements-interrogation` (which can call into this skill to produce a focused KUACQ block for a single agent).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "User stories are too granular; just write what to build." | Without stories, the team can't decompose into slices. The granularity IS the leverage. |
| "Acceptance criteria are obvious." | "Obvious" is what causes bugs at the boundary. Write them explicitly; the writing reveals the ambiguity. |
| "Scope boundary is rigid; we're being agile." | Agility means changing scope deliberately, not silently. The boundary is what makes scope changes visible. |
| "We'll add edge cases as they come up." | The interesting edge cases are at the boundary — they come up in production unless surfaced now. |
| "INVEST is just a mnemonic." | INVEST is checklist for "is this story shippable independently?" If any letter fails, the story needs work. |
| "Open questions can be resolved during implementation." | Most can; some can't (they affect architecture). Tag each open question with its blocking gate. |

## Verification

You are done when:

- [ ] Requirements brief at `.project/semantic/requirements-brief.md` exists.
- [ ] User stories list at `.project/semantic/user-stories.md` (INVEST-compliant; per-story acceptance criteria).
- [ ] Scope boundary at `.project/semantic/scope-boundary.md` (what's in, what's NOT in this round).
- [ ] Assumptions register at `.project/semantic/assumptions-register.md` (what we're betting on).
- [ ] Open questions log at `.project/semantic/open-questions.md` (each tagged with blocking gate).
- [ ] Every user story has at least one acceptance criterion that's testable.
- [ ] At least one "non-goal" explicitly listed.

Evidence to check:
- Each user story compiles (passes INVEST):
  - **I**ndependent — no story blocks another except by data dependency.
  - **N**egotiable — leaves room for design.
  - **V**aluable — to a named user, for a named outcome.
  - **E**stimable — sized rough but not "unknown."
  - **S**mall — fits a slice (2-5 days).
  - **T**estable — acceptance criteria exist.

If any item is missing, elicitation is incomplete; do not advance to `nfr-definition`.

## Sign-off

The requirements brief + user stories + scope boundary together gate the **requirements_freeze** approval. Open questions can remain open past requirements freeze if they're flagged as blocking *specific* later gates rather than the freeze itself.
