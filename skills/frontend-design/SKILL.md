---
name: frontend-design
description: "Visual design craft for UI that reads as designed, not generated: deliberate aesthetic direction grounded in the product's subject, a token system chosen for THIS brief, one justified signature element, typography that carries personality, and interface copy written as design material. Use when implementing or reviewing any user-facing surface — new screens, redesigns, marketing/landing pages, dashboards — and whenever generated UI looks templated or generic. Distinct from `design-system` (maintains the token/component system; this skill decides what the system should express), `stack-web-frontend` (framework engineering idioms), and `wireframing-prototyping` (interaction structure; this skill owns the visual treatment of that structure). Works on every harness — no tool dependency; pairs with design tools when available per references/design-tooling.md."
---

# Frontend Design

<!-- praxis:metadata:begin -->
```yaml
capability: design
domain: frontend
state: experimental
dependencies:
  - design-system
  - stack-web-frontend
  - wireframing-prototyping
  - accessibility
triggers:
  - "the generated UI looks generic / templated / not professional"
  - "designing a new screen, landing page, or dashboard"
  - "choosing palette, typography, or visual direction"
  - "reviewing whether a UI reads as designed vs AI-default"
  - "writing interface copy, empty states, error messages"
outputs:
  - design plan (palette, type roles, layout concept, signature element) before any UI code
  - anti-generic self-critique record (what was revised and why)
  - interface copy conforming to the writing rules
consumers:
  - frontend-developer (applies during implementation)
  - mobile-developer (same discipline, mobile idioms)
  - ux-designer (applies during design-system extension and hand-off)
  - code-reviewer (visual-craft dimension when screenshots are in evidence)
references:
  - design-craft.md
  - design-tooling.md
```
<!-- praxis:metadata:end -->

Adapted for Praxis from Anthropic's open [`frontend-design`](https://github.com/anthropics/skills/tree/main/skills/frontend-design) skill (see that repo's LICENSE for upstream terms); restructured to the Praxis template, wired to the design brief / token / review flow, and made harness-agnostic.

The core stance: approach every UI as the design lead at a studio known for giving each client a visual identity that could not be mistaken for anyone else's. The client has already rejected templated proposals. Make deliberate, opinionated choices about palette, typography, and layout that are specific to *this* brief — and take one real aesthetic risk you can justify.

## When this fires

Any task that produces or changes user-facing pixels: FE/mobile slice tasks, design-system extension, landing pages, dashboards, empty/error states. Also fires as a review lens whenever screenshots are part of gate evidence.

## Ground it in the subject

If the brief doesn't pin down the product's subject, pin it yourself before designing: name one concrete subject, its audience, and the page's single job — then state your choice. Distinctive choices come from the subject's own world: its materials, instruments, artifacts, vernacular. Use the project's design brief (`.project/semantic/design-brief.md` when discovery produced one), prior screens in this codebase, and the existing design tokens as the grounding inputs. Build with real content, not lorem-ipsum placeholders that hide layout problems.

## The two-pass process

**Pass 1 — plan before code.** Produce a compact design plan:

- **Color:** 4–6 named hex values chosen for this brief (these become or extend `design-tokens.json`).
- **Type:** faces for 2+ roles — a characterful display face used with restraint, a complementary body face, a utility face for captions/data if needed. Typography carries the personality of the page; it is not a neutral delivery vehicle.
- **Layout:** a one-sentence concept + ASCII wireframe to compare alternatives.
- **Signature:** the single element this page will be remembered by. Spend your boldness there; keep everything around it quiet.

**Pass 2 — critique against the generic default, then build.** Before writing code, ask: would I have produced this same plan for any similar prompt? If any part reads as the default (see the calibration list of known AI-default looks in `references/design-craft.md`), revise it and record what changed and why. Only then write the code, following the revised plan exactly — every color and type decision derives from the plan, not improvisation.

## Non-negotiable quality floor

Ship without announcing it: responsive down to mobile, visible keyboard focus, `prefers-reduced-motion` respected, WCAG contrast per `accessibility`. Structure encodes information — numbering, eyebrows, dividers only when the content genuinely is a sequence or hierarchy, never as decoration. Motion is deliberate: one orchestrated moment beats scattered effects; excess animation is itself an AI-generated tell.

## Interface copy is design material

Words exist to make the design easier to understand and use. Write from the user's side of the screen (people manage "notifications", not "webhook config"); active voice; a control says exactly what happens ("Save changes", not "Submit") and keeps its name through the whole flow; errors explain what went wrong and how to fix it without apologizing; an empty screen is an invitation to act. Full rules in `references/design-craft.md`.

## Self-critique loop

Critique your own work as you build. If the harness can capture screenshots (Playwright, browser tools), take one and look — a picture is worth a thousand tokens; apply the removal test: take one thing away before calling it done. Record what you tried in the slice notes so later passes don't rediscover the same dead ends. When the slice carries a visual-review step, your design plan and screenshots are its input evidence.

## Tool escalation

This skill is the zero-dependency floor and works on any harness. When design tools are available, use them in preference to designing in prose — the fallback chain (Figma MCP → community Figma context / Penpot → generation tools → this skill's text-only floor), including which tiers are free, lives in `references/design-tooling.md`.

## Mode handling (G/B)

- **Greenfield:** run the full two-pass process; the plan seeds `design-tokens.json` and the design system.
- **Brownfield:** the existing product's visual language is the brief. Match it faithfully; propose divergence as a design-system extension through `ux-designer`, never as a one-off. The anti-generic pass still applies to NEW surfaces (a bland admin screen in a distinctive product is still a miss).

## Common rationalizations

| Rationalization | Reality |
|---|---|
| "It's an internal tool, looks don't matter" | Internal users are users; hierarchy and copy quality are usability, not vanity |
| "The component library already looks fine" | Default-themed component libraries are the definition of templated; tokens exist to be chosen |
| "I'll polish it after it works" | Layout, type, and spacing decisions are structural; retrofitting them costs more than choosing them |
| "The brief didn't specify a style" | Then pinning the subject and direction is YOUR first deliverable, not a reason to default |
| "More animation = more polish" | Motion without purpose reads as AI-generated; one orchestrated moment beats ten effects |

## Verification

- [ ] A design plan (palette, type roles, layout, signature) exists BEFORE the UI code and the code derives from it.
- [ ] The anti-generic critique ran: at least one element was revised away from the default, recorded with rationale.
- [ ] No hardcoded colors/spacing outside the token system; type scale is intentional.
- [ ] Quality floor: responsive, keyboard focus visible, reduced-motion respected, contrast passes.
- [ ] Empty, loading, and error states designed — not left as afterthoughts.
- [ ] Interface copy follows the writing rules (user-side naming, active voice, consistent action names).
- [ ] If screenshots were possible, a self-critique pass happened against them.

## Anti-patterns

- Writing UI code before a design plan exists, then "styling it up" afterward.
- The three AI-default looks (see `references/design-craft.md`) chosen when the brief left the axis free.
- Boldness spent everywhere — five competing signature elements and no quiet ground.
- Numbered markers, gradient accents, or eyebrow labels that encode nothing about the content.
- Placeholder copy shipped to review; copy that names system internals instead of user concepts.
- Treating this skill as web-only — the discipline applies to mobile (`stack-flutter`) surfaces identically.

## What this SKILL does NOT do

- Maintain the token/component system over time — `design-system` owns that.
- Choose the FE framework or engineering idioms — `frontend-architecture` + `stack-web-frontend`.
- Define interaction structure and journeys — `ux-journey-mapping` + `wireframing-prototyping`.
- Replace the visual review gate — it makes the work reviewable; reviewers still judge it.
