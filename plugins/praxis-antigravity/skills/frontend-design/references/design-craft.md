# Design craft — calibration, principles detail, and writing rules

Companion to `frontend-design/SKILL.md`. Adapted from Anthropic's open
[`frontend-design`](https://github.com/anthropics/skills/tree/main/skills/frontend-design)
skill (see that repo's LICENSE for upstream terms).

## Calibration: the three AI-default looks

AI-generated design currently clusters around three looks. All three are
legitimate for *some* briefs — but they are defaults, not choices, and they
appear regardless of subject:

1. **Warm cream** — near-`#F4F1EA` background, high-contrast serif display,
   terracotta accent.
2. **Dark + acid accent** — near-black background with a single bright
   acid-green or vermilion accent.
3. **Broadsheet** — hairline rules, zero border-radius, dense
   newspaper-style columns.

Rule: where the brief pins a visual direction, follow it exactly — the
brief's words always win, including when it asks for one of these looks.
Where the brief leaves an axis free, don't spend that freedom on a default.
Test yourself: work through a *similar* prompt mentally — if you arrive at
the same plan, it's a default, not a decision.

## Design principles, expanded

**The hero is a thesis.** Open with the most characteristic thing in the
subject's world — a headline, an image, an animation, a live demo, an
interactive moment. "Big number + small label + supporting stats + gradient
accent" is the template answer; use it only if it is truly the best option.

**Typography carries the personality.** Pair display and body faces
deliberately — not the families you'd reach for on any other project. Set a
clear type scale with intentional weights, widths, and spacing. The type
treatment should be a memorable part of the design.

**Structure is information.** Numbering (01/02/03), eyebrows, dividers, and
labels must encode something true about the content — a real sequence, a
real hierarchy. Decorative structure is noise.

**Motion is deliberate.** Consider a page-load sequence, a scroll-triggered
reveal, hover micro-interactions, ambient atmosphere — then choose what the
direction calls for. One orchestrated moment usually lands harder than
scattered effects. Excess animation is itself an AI-generated tell. Always
respect `prefers-reduced-motion`.

**Match complexity to the vision.** Maximalist directions need elaborate
execution; minimal directions need precision in spacing, type, and detail.
Elegance is executing the chosen vision well — and restraint can be the
risk: apply the removal test (take one thing away) before shipping.

**CSS discipline.** Watch selector specificity — type-based selectors
(`.section`) and element-scoped ones (`.cta`) cancelling each other out is
the classic generated-CSS failure, especially for section padding/margins.
Deriving every value from the token system avoids most of it.

## Writing in design — the full rules

Words appear in a design for one reason: to make it easier to understand
and therefore easier to use. They are design material, not decoration.

- **Write from the user's side of the screen.** Name things by what people
  control and recognize, never by how the system is built: a person manages
  *notifications*, not *webhook config*. Describe what something does in
  plain terms rather than selling it. Specific beats clever.
- **Active voice, exact actions.** A control says exactly what happens:
  "Save changes," not "Submit." An action keeps its name through the whole
  flow — the button that says "Publish" produces a toast that says
  "Published." Interface vocabulary is signposting; cohesion is how people
  learn their way around.
- **Failure and emptiness are moments for direction, not mood.** Explain
  what went wrong and how to fix it, in the interface's voice. Errors don't
  apologize and are never vague. An empty screen is an invitation to act.
- **Register:** conversational and tuned — plain verbs, sentence case, no
  filler, tone matched to brand and audience. Each element does exactly one
  job: a label labels, an example demonstrates, nothing quietly does double
  duty.

## Working notes across passes

Human designers have memory and try something new each time. Keep short
notes in the slice working files about directions tried and rejected — the
next pass (or the next drive iteration, which starts with fresh context)
should not rediscover the same dead ends.
