---
name: product-discovery
description: Turn business intent into validated product opportunities *before* requirements get written. Vision framing, jobs-to-be-done (JTBD) articulation, opportunity sizing, hypothesis-driven solution candidates, problem/solution fit, MVP scope hypothesis. Without product discovery, teams build the wrong thing efficiently — every other phase that follows is wasted effort if the underlying opportunity is misjudged. Use whenever a new project begins or a substantial new feature is being considered. Pushy trigger because skipping discovery is the most expensive form of waste.
capability: discovery
domain: cross-cutting
state: active
dependencies: []
triggers:
 - "new project starting"
 - "evaluating a substantial new feature"
 - "validating an opportunity before requirements get written"
 - "reframing a project whose original assumptions were wrong"
 - "jobs-to-be-done analysis"
 - "MVP scoping"
outputs:
 - opportunity brief
 - JTBD statements
 - hypothesis list (problem hypotheses + solution hypotheses)
 - success metrics tied to business outcomes
 - MVP scope hypothesis
 - validated / invalidated assumptions log
consumers:
 - product-manager (primary)
 - solution-architect (consumes opportunity + JTBD as architectural drivers)
 - requirements-elicitation (consumes the validated scope hypothesis)
 - delivery-planner (uses opportunity sizing to calibrate workflow)
references: []
---

# Product Discovery

The most leveraged single phase in the lifecycle. Forty-five minutes of disciplined discovery prevents weeks of building the wrong thing. This skill runs *before* requirements — its job is to figure out **what's worth building** and **how we'll know if it worked**, not how to build it.

## When this skill fires

- A new project is being considered. PM invokes this skill before anything else.
- A substantial new feature is on the table within an existing product. PM runs discovery against the specific opportunity.
- A project's original assumptions appear wrong mid-flight and the team needs to re-validate the underlying opportunity (not just re-elicit requirements).

## The discovery procedure

Run the steps in order. Each step has a defined exit criterion. Stop at any step whose exit criterion can't be met — that's a signal the project needs reframing, not requirements.

### 1. Vision

A one-paragraph statement of the change being attempted. Concrete, not abstract.

- *Concrete:* "Enable our SMB customers to reconcile their bank transactions in under 5 minutes per week, replacing the current 90-minute manual process."
- *Abstract (insufficient):* "Improve accounting workflows."

**Exit criterion:** the vision names a specific user/customer, a specific outcome change, and rough magnitude.

### 2. Jobs to be done

For each affected user persona, state the JTBD using the canonical structure:

> When **[situation]**, I want to **[motivation]**, so I can **[expected outcome]**.

Example: "When my month-end close arrives, I want to reconcile bank transactions in bulk, so I can finish books in one sitting rather than across a week."

**Exit criterion:** at least one JTBD per primary persona, each tied to a measurable outcome.

### 3. Opportunity sizing

Concrete numbers. Not exact — rough — but explicitly stated:

- How many users / customers have this job?
- How frequently does this job arise per user?
- What's the current cost of doing the job badly (time, errors, churn risk)?
- What's the expected value of solving it (revenue, retention, NPS, cost saved)?

**Exit criterion:** sizing is captured even if approximate. The orchestrator and `delivery-planner` later consume these numbers to calibrate gate intensity and parallelism. Missing sizing is a yellow flag — projects without sized opportunities tend to over-invest.

### 4. Problem hypotheses

What do we *believe* is true about the user / market / behavior that, if false, would invalidate this project? Each hypothesis is testable.

- "We believe SMB owners spend more than 60 minutes per month on bank reconciliation."
- "We believe the friction is in matching deposits to invoices, not in data entry."
- "We believe users will accept a 5-minute automated workflow if it requires only one manual confirmation step."

**Exit criterion:** at least three problem hypotheses, each with an explicit test (user research signal, behavioral data, A/B prerequisite).

### 5. Solution hypotheses

Three to five candidate solution shapes, each tied to the problem hypotheses they address:

- "A passive ingestion pipeline (Plaid + ML categorization) gets us to 90% auto-match; the remaining 10% needs human review."
- "An active-confirmation UI that the user runs weekly catches edge cases without requiring full review."

Note: these are *hypotheses*, not designs. Their job is to bound the design space the SA explores later.

**Exit criterion:** at least three solution hypotheses; rejected alternatives noted briefly.

### 6. Success metrics

Tied to the JTBD and the opportunity sizing. These are the metrics by which the project is later judged:

- Primary: % reduction in time-to-reconcile per customer per month.
- Secondary: % of customers completing reconciliation each month (engagement); error-rate in auto-matching; NPS delta.
- Counter-metrics (things that should *not* get worse): support ticket volume, transaction-categorization accuracy on existing flows.

**Exit criterion:** primary metric named and measurable; secondary and counter-metrics noted.

### 7. MVP scope hypothesis

The thinnest end-to-end slice that, if shipped, lets us measure the primary success metric. Often dramatically smaller than the eventual product.

- "MVP: connect one bank, auto-match deposits, ask user to confirm three sample matches, measure time-to-complete." — not all features, not all banks, not all transaction types.

**Exit criterion:** MVP fits in 2–4 weeks of build *and* moves the primary metric.

### 8. Validated / invalidated assumptions log

After running user research (if applicable) or after the first hypothesis-testing pass, every assumption from steps 4–5 is marked validated, invalidated, or still-open. This log persists into `.project/episodic/` and `.project/semantic/` — future discovery rounds for related features start from here, not from scratch.

## Outputs

Each output goes to a specific location in `.project/`:

| Output | Location | Lifecycle |
|---|---|---|
| Vision + JTBDs + opportunity sizing | `.project/semantic/opportunity.md` | Stable; updated when fundamentally reframed |
| Problem + solution hypotheses | `.project/working/discovery-hypotheses.md` | Working artifact; promoted to episodic on close |
| Success metrics | `.project/semantic/success-metrics.md` | Stable; referenced throughout the project |
| MVP scope hypothesis | `.project/working/mvp-scope.md` → handed to `requirements-elicitation` | Working |
| Validated/invalidated assumptions | `.project/episodic/discovery-{date}.md` | Append-only history |

## Lightweight user research

When discovery requires user input the PM doesn't already have, this skill triggers `user-research` . For solo dev, user research is often replaced with the principal's domain expertise + behavioral data already available — but flagging "we acted on assumption X without testing" is mandatory; that gets written into the assumptions log.

## Mode handling (G/B)

**Greenfield.** Full discovery procedure as above.

**Brownfield.** Discovery is scoped to the specific feature or enhancement; the broader vision is read from `.project/semantic/opportunity.md` (which already exists from the project's original discovery). Re-validation of the existing vision is required only when the new feature contradicts it.

## What this skill does not do

- Write requirements — that's `requirements-elicitation`, which consumes the MVP scope hypothesis.
- Design the architecture — that's `architecture-pattern-selection`, which consumes the JTBD + opportunity sizing.
- Build prototypes — that's `wireframing-prototyping` .
- Validate hypotheses experimentally — that's `evaluation-engineering` for agentic systems or general experimentation discipline.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We already know what to build." | If certainty is high, discovery is a fast pass + a written record. If certainty is *falsely* high, discovery surfaces it cheaply. Worth doing either way. |
| "Discovery is product's job, not engineering's." | Engineering owns "is this technically right?" Discovery surfaces what we'd otherwise rediscover at deploy time. Worth the cross-functional pass. |
| "We'll do a fast lap and write up later." | Later means never. The artifacts ARE the discovery — without them, the JTBD lives in someone's head. |
| "MVP scope is obvious from the request." | The request is one of many possible scopes for one of many possible JTBDs. Make the choices explicit. |
| "The user is the persona; we don't need personas." | Single-persona projects do exist, but most "one user" assumptions break under actual usage. Name them deliberately. |
| "JTBD is just a vague header for the doc." | JTBD is the only invariant — features change, users change, but the job-to-be-done is what's measured. Get it right. |

## Verification

You are done when:

- [ ] Opportunity brief at `.project/semantic/opportunity-brief.md` exists.
- [ ] At least one named persona with a clear job-to-be-done.
- [ ] Value hypothesis stated as "if we ship X, we expect Y measurable outcome within Z time."
- [ ] MVP scope hypothesis: smallest thing that tests the value hypothesis.
- [ ] Non-goals documented (what we're explicitly NOT building this round).
- [ ] Alternatives considered (at least 2 other shapes the same opportunity could take).
- [ ] Open questions logged for `requirements-elicitation` to resolve.

Evidence to check:
- A reader can answer "who is this for, what job does it do, why now?" from the brief alone.
- The MVP scope is small enough that "build it" is bounded; not "build the whole product."
- Value hypothesis is measurable, not aspirational ("delight users" is not measurable).

If any item is missing, discovery is incomplete; do not advance to `requirements-elicitation`.

## Anti-patterns

- Skipping discovery because "we already know what to build." If the team's certainty is high, discovery is a fast pass and a written record. If certainty is *false* high, discovery surfaces it cheaply. Either way, it's worth the time.
- Solution-first discovery (starting from the proposed feature and reverse-engineering a JTBD). The JTBD should make the solution shape obvious; if you have to bend the JTBD to fit the solution, the solution is wrong.
- Discovery that produces an opportunity brief but no MVP scope hypothesis. Without MVP, requirements elicitation has no boundary.

## Sign-off

Discovery output requires the **requirements_freeze** gate per the governance matrix. The PM owns the output; the principal (or designated approver) reviews and approves before the project advances to `requirements-elicitation`.
