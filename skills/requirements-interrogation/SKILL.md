---
name: requirements-interrogation
description: The AOP Clarify-step skill that every agent invokes at every phase boundary. Produces a standardized Knowns / Unknowns / Assumptions / Conflicts / Questions (KUACQ) block from whatever inputs the agent has, surfacing ambiguity *before* execution begins. The single most leveraged defense against "starts coding too early." Distinct from `requirements-elicitation` (broader product-discovery-to-requirements activity owned by PM) — this is the focused, per-agent, per-phase interrogation that every developer/reviewer/architect agent runs. Pushy trigger because clarification is the failure mode most agents skip.
---

# Requirements Interrogation


<!-- praxis:metadata:begin -->
```yaml
capability: discovery
domain: cross-cutting
state: active
dependencies:
  - project-memory
  - memory-management
triggers:
  - "any agent entering a phase (AOP Clarify step)"
  - "developer about to start coding a slice"
  - "reviewer about to start a review"
  - "architect about to make a design decision"
  - "surfacing ambiguity before action"
outputs:
  - KUACQ block (Knowns / Unknowns / Assumptions / Conflicts / Questions)
  - escalation flag (if conflicts or unanswerable questions block progress)
consumers:
  - all role agents (every agent invokes this at every phase entry)
  - using-praxis (reads escalation flags)
  - project-memory (persists KUACQ blocks to .project/working/)
references: []
```
<!-- praxis:metadata:end -->

The discipline that turns the AOP's Clarify step from a vague instruction into a structured, evaluable, improvable procedure. Every agent at every phase entry runs this skill — the same block format, the same five categories, the same escalation rules.

The procedure is small and the output is small. That's the point. KUACQ is meant to be lightweight enough that agents actually do it.

## When this skill fires

Every time an agent enters a phase under the AOP lifecycle. Specifically:

- Developer agent receiving an implementation packet — runs KUACQ on the packet contents.
- Reviewer agent receiving a PR for review — runs KUACQ on the change scope.
- Solution Architect entering the design phase — runs KUACQ on the requirements + NFRs.
- Architecture Challenger about to challenge a design — runs KUACQ on the design artifact.
- PM entering elicitation — runs KUACQ on the discovery output.
- Platform/SRE entering deployment design — runs KUACQ on the architecture + capacity model.

Trivial actions (typo fix, comment edit) skip KUACQ — the AOP allows compression. But any substantive change runs it.

## The KUACQ block

Five categories. Each agent produces this block at phase entry and writes it to `.project/working/kuacq-{agent}-{slice}.md`.

```markdown
---
type: working
title: KUACQ — <agent> — <slice or phase>
agent: <agent-name>
slice: <slice-id-if-applicable>
phase: <phase-name>
date: YYYY-MM-DD
---

# KUACQ

## Knowns

Facts I have, sourced. Each known carries its source (artifact path).

- The user is authenticated by the time this flow begins.
  Source: `.project/working/requirements-brief.md`, story #3.
- The API contract is OpenAPI 3.1 at `.project/working/api-contract.yaml`.
  Source: SA architecture output.
- p99 latency target is 200ms.
  Source: `.project/working/nfr-register.md`.

## Unknowns

Things I don't know that I need to know before executing. Each unknown is
specific and bounded.

- The retention policy for transaction data (30 days? 7 years?).
- Whether the user expects email confirmation on completion.
- How the system handles concurrent edits from multiple sessions.

## Assumptions

Things I'm taking as true *in the absence of confirmation*, with the
risk if wrong stated.

- ASSUMING: Transactions are immutable once posted. RISK if wrong:
  rework of the reconciliation logic.
- ASSUMING: The bank API returns deterministic transaction IDs.
  RISK if wrong: matching algorithm needs redesign.
- ASSUMING: I have permission to modify the persistence schema for
  this slice. RISK if wrong: must coordinate with another team.

## Conflicts

Contradictions between sources, requirements, or constraints. Each conflict
names the contradicting parties and the agent's proposed resolution.

- Requirements story #3 says "instant confirmation"; NFR register
  says "p99 confirmation within 30 seconds." Resolution: clarify with
  PM whether "instant" means perceived (UI-level optimistic update)
  or actual.
- ADR-0007 says "no PII in logs"; the proposed structured logging
  scheme includes user email. Resolution: redact email at the log
  boundary; flag ADR-0007 if redaction is insufficient.

## Questions

Concrete questions the agent needs answered before completing the phase.
Each question is addressed to a specific responder and gated against a
specific exit criterion.

- For PM: What's the retention policy for transaction data?
  Blocks: implementation-packet completion.
- For SA: Should the reconciliation engine be a separate bounded
  context or part of billing?
  Blocks: architecture sign-off.
- For Platform/SRE: What's the existing logging redaction policy?
  Blocks: secure-coding review.
```

## The escalation flag

Beyond the KUACQ block itself, the skill emits a flag:

```yaml
escalation:
  required: true | false
  reason: <if true, the specific blocker>
  routes_to: <responder agent or human>
```

`required: true` happens when:

- A conflict cannot be resolved within the agent's authority.
- A question blocks the phase exit and has no responder available.
- An assumption's risk exceeds the agent's risk-acceptance threshold.

The orchestrator reads this flag. On `required: true`, the workflow pauses; the orchestrator routes per the question's `routes_to`.

## The 5–15 minute rule

KUACQ is meant to take 5–15 minutes of focused attention. If it takes more, the inputs to the phase are insufficient and the upstream phase needs to be revisited (the agent escalates rather than spending hours interrogating).

If KUACQ takes *less than 5 minutes*, the agent is probably skipping categories. The orchestrator can validate the output's shape (all five sections present, each with at least one entry or an explicit "none — checked" note) but cannot validate quality.

## Persistence and indexing

Every KUACQ block writes to `.project/working/kuacq-{agent}-{slice}.md` for the in-flight slice. On slice close, the working/ entries archive to `.project/episodic/`. `memory-management` indexes them so the System Steward can later analyze KUACQ patterns across phases — which agents surface the most unknowns, which assumptions most often turn out wrong, which questions repeat across slices.

## What this skill produces, structurally

The KUACQ block isn't just documentation; it's data:

- **factory-evaluation** reads KUACQ blocks to compute the `clarification depth` metric (how many unknowns/questions per phase entry).
- **architecture-challenger** consults KUACQ blocks to find under-examined assumptions.
- **system-steward** identifies patterns: "Agents repeatedly assume X across N slices — should X be a workflow precondition?"

Structured clarification at phase boundaries is what makes the platform measurable.

## Mode handling (G/B)

**Greenfield.** Standard KUACQ at phase entry.

**Brownfield.** The agent additionally consults `.repo-intel/` (from `codebase-comprehension`) and `.project/decision/` (prior ADRs) before listing Unknowns and Assumptions. Many things that would be Unknowns in greenfield are Knowns in brownfield — but only if the agent reads the existing memory. Skipping the brownfield context check is a Conflict that should be self-flagged.

## What this skill does not do

- Answer the questions it surfaces — that's the responsibility of the responder named in each question.
- Run the upstream phase (requirements elicitation, architecture design) — only interrogates the inputs available to *this* phase.
- Replace `requirements-elicitation` — the two are complementary; one runs once per project at the requirements-freeze gate, this one runs per agent per phase.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I have enough context; I'll skip the KUACQ block." | KUACQ is 5 minutes. The wrong assumption you'd otherwise carry forward is 5 days of rework. |
| "Unknowns and Assumptions are the same thing." | Unknowns are what you'd need to ask. Assumptions are what you've already decided without asking. Different categories, different actions. |
| "Conflicts haven't appeared yet; skip that section." | Conflicts hide in unread documents and unconsulted stakeholders. Surface them by looking. |
| "I'll just ask the user later if questions come up." | "Later" arrives mid-implementation when the cost of asking is "stop work." Batch questions now. |
| "Knowns is just restating the brief." | Restating in your own words is the proof of comprehension. If you can't summarize Knowns crisply, you don't yet understand the brief. |
| "Five empty sections is fine — there's nothing to add." | If KUACQ is genuinely empty, the agent has nothing to learn from the brief (almost never true) OR skipped the work. Both are signals. |

## Verification

You are done when:

- [ ] KUACQ block written for the current handoff (per agent, per phase entry).
- [ ] **K**nowns: ≥ 3 specific facts from the brief, in agent's own words.
- [ ] **U**nknowns: ≥ 2 questions the agent would need answered to proceed.
- [ ] **A**ssumptions: ≥ 2 decisions the agent is making without explicit input.
- [ ] **C**onflicts: ≥ 1 noted, or explicit "none found after checking X, Y, Z."
- [ ] **Q**uestions: structured list with WHO to ask, by WHEN, blocking WHAT.
- [ ] Block surfaced to the user (not just written to disk).

Evidence to check:
- Each Unknown has a documented Question, or is explicitly accepted as risk.
- Each Assumption is one the user has confirmed OR is explicitly "agent will proceed unless corrected by Y deadline."
- The block is short enough to read in 60 seconds; the work IS the categorization, not the prose.

If any category is empty without rationale, KUACQ is ceremony, not work; redo.

## Anti-patterns

- KUACQ as ceremony — five empty sections marked "none." Either the agent has no real input (escalate) or skipped the work (audit signal).
- Conflating Unknowns with Questions. Unknowns are *internal* to the agent (things the agent doesn't know); Questions are *external* (things requiring another responder). They drive different next steps.
- Single-source KUACQ. If every Known cites the same artifact, the agent didn't read broadly enough; KUACQ pulls from requirements + NFRs + ADRs + `.repo-intel/` + prior slice handoffs.
