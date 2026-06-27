---
name: wireframing-prototyping
description: "Translate user journeys into low/mid-fidelity wireframes and interactive prototypes. Validate the interaction model BEFORE pixel polish — the wireframe is the design's contract; the prototype is its validation."
---

# Wireframing & Prototyping


<!-- praxis:description:full -->
## Full description

Translate user journeys into low/mid-fidelity wireframes and interactive prototypes. Validate the interaction model BEFORE pixel polish — the wireframe is the design's contract; the prototype is its validation. Lives downstream of `ux-journey-mapping` (which provides the friction inventory and opportunity hotspots to wireframe first) and upstream of `design-system` (which provides the tokens and components the wireframes resolve to). The UX Designer runs this. Use whenever a slice's UI is being designed before implementation begins.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: ux-and-design
domain: frontend
state: active
dependencies:
 - ux-journey-mapping
 - design-system
 - requirements-elicitation
triggers:
 - "designing screens for a new slice"
 - "validating the interaction model before pixel design"
 - "iterating on a prototype with user feedback"
 - "preparing the handoff package for the Frontend Developer"
outputs:
 - wireframe set per significant flow
 - interaction notes (state transitions, error states, edge cases)
 - clickable prototype (linked screens that can be walked through)
 - design-review notes
consumers:
 - ux-designer (primary author)
 - frontend-developer (consumes wireframes + prototype + interaction notes)
 - accessibility (consumes designs for a11y review)
 - product-manager (consumes for validation against requirements)
 - architecture-challenger (security/operations sub-personas review flows for hidden complexity)
references: []
```
<!-- praxis:metadata:end -->

The bridge between the journey and the code. Low or mid-fidelity wireframes show *what's on screen and what it does*; the prototype links them into a walkable flow. Pixel polish and brand styling come later — they're cheap to add once the structure is right, and expensive to change after they're applied.

## When this skill fires

- A slice's UI is being designed before implementation. UX Designer runs this once the journey map exists and the design-system tokens are available.
- An existing screen is being redesigned because a hotspot in the friction inventory points there.
- A prototype is being iterated based on internal review or user feedback.

## The procedure

### 1. Identify the screens needed

From the journey map (`ux-journey-mapping`), each opportunity hotspot maps to one or more screens. Some phases are non-screen interactions (an email confirmation, a passive notification); some are heavy-screen phases (a checkout flow with 4–5 steps).

Don't wireframe every possible screen — focus on:
- The hotspot screens (where friction lives or where the design must shine).
- The decision-point screens (where the user makes a non-trivial choice).
- The state-transition screens (success, error, empty, loading).

### 2. Fidelity choice

Pick the right fidelity for the goal:

| Fidelity | When | What it shows |
|---|---|---|
| **Low (paper / sketch)** | Initial layout exploration; rapid divergent thinking. | Boxes labeled with content type and rough proportion. |
| **Mid (wireframe tools)** | Validating structure and interaction model. | Real layout with placeholder content, no brand styling. |
| **High (pixel-perfect)** | Final hand-off package; brand and polish applied. | The actual visual design ready for development. |

's bias: **mid-fidelity by default**. Low fidelity is a sketchbook activity; high fidelity is downstream and slower. Mid-fidelity is the sweet spot for the team's iteration speed.

### 3. Wireframe the screen

For each screen, capture:

- **Layout** — what goes where. Header, primary content area, secondary content, actions. Use real proportions.
- **Content types** — what kind of content lives in each region (heading, body text, table, form, image, action). Don't draft real copy yet; use representative placeholders.
- **Primary action** — what's the *one* thing this screen wants the user to do? Marked visually.
- **Secondary actions** — what other actions are available; clearly subordinate to the primary.
- **Information density** — how much is on screen at once? Dense screens for power-user contexts; sparse for unfamiliar users.

Wireframes use the design-system tokens and components where they exist. Custom components in wireframes are a flag for the design system to grow (a new component candidate goes to `library-backlog/proposed-patterns/`).

### 4. Capture interaction notes per screen

Wireframes show *state*; interaction notes show *transitions*:

- **Entry** — how does the user arrive at this screen? From which other screens?
- **Exit** — where does each action take them?
- **Loading state** — what does the screen show while waiting for data?
- **Empty state** — what does the screen show when there's no data yet (e.g., new user, empty list)?
- **Error state** — what does the screen show on failure (network, validation, server error)?
- **Edge cases** — keyboard navigation order, long-content overflow, very-short-content centering, RTL layout if i18n applies.

Interaction notes live alongside the wireframes in the same file or directory.

### 5. Stitch into a clickable prototype

The prototype connects the wireframes via clickable hotspots, representing the user's path through the journey. The prototype is **walkable** — the UX Designer or PM can click through end-to-end and feel the flow.

Tools (any of):
- Figma (prototype mode) — most teams' default.
- Excalidraw + interactive PDFs — lighter.
- HTML/CSS prototype — when the design is simple and you want it to actually run in a browser.

The prototype's purpose is **internal validation** — does the flow make sense? Does the team agree on the interaction model? It's not the production code.

### 6. Design review

Before handing to the Frontend Developer:

- **PM review** — do the wireframes accurately reflect the requirements?
- **SA review** — do any screens imply system capabilities that aren't designed yet? (E.g., a screen showing "real-time matches" implies a real-time backend.)
- **Accessibility review** — does the design support the a11y requirements? (Reading order, focus order, sufficient contrast even at low fidelity, alt-text candidates noted.)
- **Frontend Developer review** — is the design implementable with the chosen frontend stack and the available design-system components?

Findings from these reviews iterate the wireframes before hand-off. The hand-off package is the gate to FE Dev; it doesn't ship until the four reviewers sign off (or non-blocker findings are explicitly tracked).

## Outputs

| Output | Location | Audience |
|---|---|---|
| Wireframes (per flow) | `.project/working/wireframes/{flow-name}/` | All reviewers; FE Dev |
| Interaction notes | inline with wireframes; one note file per screen | FE Dev (implementation reference) |
| Clickable prototype | wireframes + linked navigation; living in the design tool | All reviewers; PM (for stakeholder review) |
| Design review notes | `.project/working/design-review-{flow}.md` | UX Designer (input for iteration) |

The wireframe directory becomes part of the implementation packet (Section 9 of the blueprint) handed to the Frontend Developer for the slice.

## The handoff package

For each slice involving UI work, the UX Designer hands FE Dev:

1. The **journey map** (`.project/semantic/journey-map-{persona}.md`) for context.
2. The **wireframes for this slice's screens** with interaction notes.
3. The **design-system tokens + components** to use (from `design-system`).
4. The **a11y expectations** (from `accessibility`).
5. The **i18n requirements** (which strings need translation hooks).
6. The **performance budget** (from `frontend-performance` deepening; sets the baseline).

The hand-off package is the input to the FE Dev's KUACQ — they read it, surface any clarifications needed, and start implementation.

## Mode handling (G/B)

**Greenfield.** Build wireframes from scratch using the design system's existing components.

**Brownfield.** The existing product has existing screens. Wireframe the *delta* — what's changing — not the whole screen. Show the current state alongside the proposed state when changes are non-trivial. The handoff package highlights what's existing vs. new so the FE Dev knows what's being replaced.

## What this skill does not do

- Define the visual style — that's `design-system`.
- Validate with real users — that's `user-research`.
- Implement the screens — that's the Frontend Developer.
- Ensure technical feasibility — that's the FE Dev review and the SA's input.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Low-fidelity wireframes don't help engineers." | They do — they show structure without prejudicing aesthetics, accelerating "where does the data go" decisions. |
| "Let's go straight to high-fidelity." | Pixel-perfect early = expensive iteration. Stay low-fidelity until the structure is right. |
| "Wireframes are designer territory." | Engineers contribute layout + interaction feedback; PM contributes flow validation. Cross-functional from start. |
| "Prototypes are nice-to-have." | For non-trivial flows, prototypes catch usability bugs no document can. Cheap insurance. |
| "Mobile and desktop are the same thing scaled." | They are not. Touch targets, thumb zones, viewport behavior — design specifically. |
| "Let's prototype every screen." | Prototype the risk — flows where usability is uncertain. Standard CRUD doesn't need a prototype. |

## Verification

You are done when:

- [ ] Wireframes for each significant screen at `.project/working/ux/wireframes/`.
- [ ] Low-fidelity (boxes + arrows) until structure validated, then upgrade to mid-fi.
- [ ] Mobile + desktop variants for responsive UIs.
- [ ] Clickable prototype for at least the top-3 risky flows.
- [ ] Annotations capture data sources + state changes per interaction.
- [ ] Engineering feedback round completed.
- [ ] Open questions logged.

Evidence to check:
- Engineering can implement directly from the wireframes without ambiguity.
- Prototype lets stakeholders verify the flow before code.

## Anti-patterns

- Wireframes that are actually mockups (pixel-perfect, branded) too early. Slows iteration; adds cost to changes.
- Skipping interaction notes ("the dev will figure it out"). The FE Dev shouldn't have to invent state transitions; that's design work.
- Wireframing every conceivable screen. Focus on the hotspots from the journey map.
- Prototypes that don't actually walk end-to-end. A static set of screens isn't a prototype; it's slides.
- Wireframes that bypass the design system (custom components everywhere). Either extend the system explicitly or use what's there.

## Iteration cadence

Wireframes are *meant* to change. The first version is rarely the last. Plan for 2–3 iteration rounds per significant flow before hand-off; treat the first as a draft, not a deliverable.
