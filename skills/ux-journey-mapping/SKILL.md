---
name: ux-journey-mapping
description: Map end-to-end user journeys per persona BEFORE any screen design. Actors, goals, touchpoints, emotional states, friction inventory, opportunity hotspots. Ground design decisions in actual flows rather than isolated screens. The UX Designer runs this for any product with non-trivial user flows, in close collaboration with the PM whose discovery output feeds it.
---

# UX Journey Mapping


<!-- praxis:description:full -->
## Full description

Map end-to-end user journeys per persona BEFORE any screen design. Actors, goals, touchpoints, emotional states, friction inventory, opportunity hotspots. Ground design decisions in actual flows rather than isolated screens. The UX Designer runs this for any product with non-trivial user flows, in close collaboration with the PM whose discovery output feeds it. Use whenever a new product is being designed, when a new significant user flow is being added, or when the team is debating screens before agreeing on the underlying journey.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: ux-and-design
domain: frontend
state: active
dependencies:
  - product-discovery
  - requirements-elicitation
triggers:
  - "designing a new product's user experience"
  - "adding a new significant user flow"
  - "evaluating an existing flow for friction"
  - "grounding screen design in the underlying journey"
outputs:
  - user journey map per primary persona
  - friction inventory (ranked pain points across the journey)
  - opportunity hotspots (where design intervention adds the most value)
consumers:
  - ux-designer (primary author)
  - product-manager (consumes for prioritization)
  - solution-architect (consumes for system touchpoint identification)
  - frontend-developer (consumes for context when building screens)
  - wireframing-prototyping (consumes journeys for wireframe scoping)
references: []
```
<!-- praxis:metadata:end -->

Screens without journeys produce disconnected experiences. The journey map is the *narrative* that explains why each screen exists, what the user is doing before and after, and where the friction in the current flow lives. Wireframes and prototypes are downstream of journeys, not parallel to them.

This is *not* a heavyweight CX exercise. It's a focused 60–90 minute activity per primary persona on a new product (or per significant new flow on an existing one).

## When this skill fires

- A new product is in design. UX Designer runs this for each primary persona identified by `product-discovery`.
- A new significant user flow is being introduced (e.g., a new payment method, a new account-recovery flow).
- An existing flow is being redesigned because user feedback or behavioral data shows friction.
- The team is arguing about screens before agreeing on the underlying journey — symptom of skipping this step.

## The procedure

### 1. Identify the persona

From `product-discovery`'s JTBD work, pick the persona this journey is for. The journey is *per persona* — multi-persona maps are usually two journeys badly conflated.

The persona has:
- A name (descriptive, not stereotyping).
- A primary JTBD (from `product-discovery`).
- Relevant context (familiarity with the domain, technical fluency, motivation level).

### 2. Define journey boundaries

Where does the journey *start* and *end*? Be explicit:

- **Trigger** — what causes the persona to engage? Time, external event, internal need.
- **Outcome** — what does the persona consider success? What state are they in after?

The boundaries are usually broader than the product. The journey might start before the persona thinks about your product and end after they've finished. The product's touchpoints are *within* the journey, not the whole thing.

### 3. Map the phases

Decompose the journey into 4–8 phases. Each phase is a coherent step toward the outcome:

For "User completes monthly bank reconciliation":

```
1. Aware     — User realizes month-end is coming; reconciliation is needed.
2. Prepare   — User gathers statements, opens accounting software.
3. Connect   — User links bank account to the tool (first time) or re-auths.
4. Review    — User reviews auto-matched transactions; addresses unmatched.
5. Confirm   — User accepts the match results; reconciliation is complete.
6. Reflect   — User has a moment of "it's done"; prepares for month-end close.
```

Phases are descriptive ("Connect"), not feature names ("Bank linking page"). The phases stay stable; the features within them change.

### 4. For each phase, capture five dimensions

The canonical journey-map columns:

| Dimension | What goes here |
|---|---|
| **Actions** | What is the persona physically doing? |
| **Touchpoints** | What systems/UIs are they interacting with? |
| **Thoughts** | What's running through their mind? |
| **Emotions** | High-level emotional state (curious, anxious, frustrated, satisfied). |
| **Pain points** | Specific friction in this phase. |

Capture in present tense, in the persona's voice when possible:

```
Phase: Review
Actions: Scrolls through 200 transactions; clicks each unmatched one;
         tries to remember which deposit went with which invoice.
Touchpoints: Our app's reconciliation table; their old paper notes; their email.
Thoughts: "Why can't this just figure it out?" "I know I sent that invoice
          in March." "Wait, did I deposit two checks together that day?"
Emotions: Anxious → Frustrated → Resigned
Pain points:
  - Deposits combining multiple invoices aren't matchable in the UI.
  - No way to add a note explaining a match for later auditing.
  - The "skip" button doesn't make clear what happens to skipped items.
```

### 5. Build the friction inventory

Across all phases, list the pain points. Rank them by:
- **Frequency** — how often does this hit users?
- **Severity** — how badly does it derail the journey?
- **Recoverability** — can the user recover, or do they abandon?

Top 5–10 pain points become the **friction inventory**. This is the actionable output — every screen design or feature decision later references it.

### 6. Identify opportunity hotspots

Hotspots are phases or transitions where design intervention adds the most value. Often these are:
- The first time a persona uses something (onboarding friction lands here).
- Transitions between systems or contexts (the persona's mental model breaks here).
- Recovery from failure or error.
- Decision moments (the persona pauses; clarity here pays off).

Mark hotspots on the map. Wireframing and prototyping focus here first.

## Outputs

| Output | Location | Audience |
|---|---|---|
| Journey map | `.project/semantic/journey-map-{persona-slug}.md` | UX Designer, FE Dev, PM, SA |
| Friction inventory (ranked) | `.project/semantic/friction-inventory.md` | All design + dev work |
| Opportunity hotspots | `.project/working/opportunity-hotspots.md` | UX Designer (input to wireframing) |

The journey map lives in `.project/semantic/` because it's stable — the journey doesn't change as the product evolves; the touchpoints within it might.

## Format example

A journey map can be a markdown table with columns per phase, or a more visual representation (the choice depends on team preference). Both are valid; the markdown table is more portable across coding assistants.

```markdown
# Journey: SMB Owner Reconciles Bank Transactions

**Persona:** SMB Owner (Sarah)
**JTBD:** When month-end arrives, reconcile bank transactions, so I can close the books quickly.
**Trigger:** Month-end approaches.
**Outcome:** Reconciliation complete; ready for month-end close.

| | Aware | Prepare | Connect | Review | Confirm | Reflect |
|---|---|---|---|---|---|---|
| **Actions** | ... | ... | ... | ... | ... | ... |
| **Touchpoints** | ... | ... | ... | ... | ... | ... |
| **Thoughts** | ... | ... | ... | ... | ... | ... |
| **Emotions** | ... | ... | ... | ... | ... | ... |
| **Pain points** | ... | ... | ... | ... | ... | ... |

## Friction inventory (ranked)

1. [Review/Severe] Deposits combining multiple invoices aren't matchable.
2. [Connect/Moderate] Re-auth flow re-triggers monthly without explanation.
3. [Prepare/Moderate] No reminder to start reconciliation; users discover it late.
...

## Opportunity hotspots

- **Onboarding (Aware → Prepare):** the moment a new user discovers the tool.
- **Match failures (Review):** the deposits-combining-invoices pain is the #1 friction.
- **Confirm → Reflect:** acknowledge completion explicitly; users feel uncertain.
```

## Working with the map

Subsequent work consumes the journey:

- `wireframing-prototyping` builds wireframes for the screens at the hotspots first.
- `architecture-pattern-selection` identifies which system touchpoints are required and how they integrate.
- `data-modeling` ensures the entities exist to support the journey's data needs.
- `frontend-developer` reads the relevant phase's context when building each screen.

## Mode handling (G/B)

**Greenfield.** Build the journey from PM's discovery output and any user research that's been done.

**Brownfield.** A journey often already exists implicitly in the product. The UX Designer reverse-engineers it from the product's current behavior + behavioral data + any user research that's been logged. The map is then *current state*; the redesign target is a parallel *future state* journey.

## What this skill does not do

- Design screens — that's `wireframing-prototyping`.
- Define the visual style — that's `design-system`.
- Validate the journey with users — that's `user-research`.
- Implement the screens — that's the Frontend Developer.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Engineers don't need journey maps." | Engineers building flows need to see them end-to-end. Otherwise they build screen-by-screen and the seams show. |
| "Journey maps are for the discovery doc." | They're for the slice decomposition too — slice ≈ steps in a journey, not "screens in a sitemap." |
| "Personas are stereotypes." | Done poorly, yes. Done well, they're shorthand for "for this user with these goals." Skip the demographics; keep the goals. |
| "Map per screen because it's faster." | Per-screen produces a sitemap, not a journey. Wrong abstraction; rebuild per-persona. |
| "Happy path is enough." | The interesting design work is on the unhappy paths (error, abandon, retry, return). Map them. |
| "We'll just user-test later." | User testing without a journey hypothesis is unfocused. Map first; test specific moments. |

## Verification

You are done when:

- [ ] Journey maps per persona at `.project/working/ux/journeys/`.
- [ ] Each journey covers: trigger → action stages → emotions/blockers → outcomes.
- [ ] At least one happy path + one unhappy path mapped per persona.
- [ ] Specific touchpoints identified (where the system intervenes).
- [ ] Critical moments highlighted (where retention / churn / conversion is decided).
- [ ] Open questions logged for `requirements-elicitation` or future user research.

Evidence to check:
- Engineering can use the journey to sequence slices (each slice = a journey step).
- A new joiner can read the journey and answer "what does the user feel here?"

## Anti-patterns

- Journey maps built per-screen rather than per-persona. Wrong abstraction.
- Mapping the desired future state without first capturing the current state. Without a current-state baseline, you can't tell what improved.
- Including the system's internal flow (what the backend does) in the journey map. The journey is about the user's experience; backend flow is a separate concern.
- Decorative journey maps that look beautiful but aren't actionable. The friction inventory is the deliverable; the map is the structure that produces it.

## Time budget

- Greenfield: 60–90 minutes per primary persona, with the PM in the room.
- Slice-level extension: 20–30 minutes to extend an existing journey or add a sub-journey.

The map is meant to be created quickly and revisited often — not a one-shot artifact.
