---
name: accessibility
description: "WCAG/ARIA conformance as a cross-cutting practice spanning design and code. Semantic structure, focus management, color contrast, keyboard navigation, screen-reader expectations, automated checks (axe), manual testing protocol, CI gate on regressions. Applied at design time (UX Designer), at code time (FE Developer), and at review time (a11y aspect of code-review + dedicated audits). Use whenever new UI is being designed or implemented, when auditing existing surfaces, or when establishing the project's WCAG conformance target."
---

# Accessibility

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: frontend
state: active
dependencies:
  - engineering-standards
  - design-system
  - nfr-definition
triggers:
  - "designing new screens or components"
  - "implementing new UI components"
  - "auditing existing UI for a11y compliance"
  - "setting up axe in CI"
  - "establishing WCAG conformance target"
  - "reviewing a PR that touches UI"
outputs:
  - a11y checklist per component/flow
  - axe rules configuration + CI integration
  - severity-tagged a11y findings (during review/audit)
  - manual testing protocol for keyboard / screen reader
  - WCAG conformance attestation (per release)
consumers:
  - ux-designer (applies at design time)
  - frontend-developer (applies at code time)
  - code-review (a11y aspect of reviews)
  - qa-engineer (manual a11y testing)
  - compliance-privacy (feeds into regulatory attestation)
references: []
```
<!-- praxis:metadata:end -->

Accessibility is *not* a checklist to satisfy regulation; it's a discipline that makes the product work for everyone, including the team's own users when they're tired, on a low-bandwidth connection, using one hand, or relying on a screen reader. Built in from the start; nearly free. Retrofitted later; expensive.

This skill spans design and code. The UX Designer applies it during wireframing (color contrast, semantic structure, focus order). The Frontend Developer applies it during implementation (ARIA, keyboard interaction, focus management). The Code Reviewer audits it during review. QA runs manual checks before release.

## When this skill fires

- A new screen or component is being designed — UX Designer applies the design-time checks.
- A new component is being implemented — FE Dev applies the code-time checks.
- A PR touches UI — Code Reviewer runs the a11y dimension of `code-review`.
- A release is being prepared — QA runs the manual testing protocol.
- An a11y audit is being scheduled — auditor uses the full checklist.

## WCAG conformance target

The project's target is set in the NFR register. Defaults:

- **WCAG 2.2 AA** — the standard target for B2B SaaS and consumer products.
- **WCAG 2.2 AAA** for specific regulated contexts (government, healthcare in some regimes).
- **WCAG 2.0 AA** acceptable only when an older regulatory regime requires it specifically.

This skill assumes WCAG 2.2 AA unless the NFR register says otherwise.

## The four principles (POUR)

Every check ties to one of these:

- **Perceivable** — users can see / hear / interpret the content.
- **Operable** — users can interact via any input method.
- **Understandable** — content and operation are predictable.
- **Robust** — works across browsers, assistive tech, and over time.

## Design-time discipline

Applied during `wireframing-prototyping`:

### Color and contrast

- **Text contrast** — 4.5:1 for body text, 3:1 for large text (18pt+ or 14pt+ bold) against background.
- **Non-text contrast** — 3:1 for UI components (borders, icons) and graphical objects.
- **Never color-only signal** — if a state is communicated by color (error red, success green), it's *also* communicated by icon, label, or position. Color-blind users cannot rely on color alone.
- Tools: Stark, axe DevTools, design-tool plugins that flag contrast issues in real time.

### Semantic structure

- Heading hierarchy is logical (h1 → h2 → h3, no skipping). One h1 per page typically (the page's primary title).
- Landmarks (main, nav, header, footer, aside) are present.
- Content order makes sense when CSS is stripped.

### Reading and focus order

- Reading order matches visual order. RTL languages flip the visual; reading order must follow.
- Focus order is logical — tabbing through interactive elements moves through them in the order the user expects.

### Touch targets

- Minimum 44×44 CSS pixels for touch targets (WCAG 2.5.5; AAA for 2.1, AA for 2.2 with exceptions).
- Spacing between targets prevents adjacent activation.

## Code-time discipline

Applied during implementation:

### Semantic HTML

- Use the right element for the meaning. `<button>` for buttons (not `<div onclick>`). `<a>` for navigation (not `<button onclick={navigate}>`).
- Form fields have associated `<label>` elements (via `for`/`id` or wrapping).
- Lists are `<ul>` / `<ol>`. Tables are `<table>` with `<th scope>` for headers.

### Keyboard interaction

- Every interactive element is keyboard-accessible. Tab to focus; Enter or Space to activate; Esc to dismiss overlays; arrow keys for composite widgets (tabs, menus, grids).
- Focus is visible — never hide focus indicators globally; design them deliberately.
- Focus management on dynamic content — when a modal opens, focus moves into it; when it closes, focus returns to the trigger.
- Skip-link at the top — "Skip to main content" for keyboard users who don't want to tab through nav on every page.

### ARIA — only when needed

The first rule of ARIA: don't use ARIA when native HTML works. A `<button>` doesn't need `role="button"`. `<input type="checkbox">` doesn't need ARIA state attributes.

When ARIA is genuinely needed:

- **Roles** for components without native HTML equivalent (tablist, menu, dialog, alert).
- **States** for dynamic widgets (`aria-expanded`, `aria-selected`, `aria-checked`).
- **Properties** for relationships (`aria-labelledby`, `aria-describedby`, `aria-controls`).
- **Live regions** (`aria-live="polite"` / `assertive`) for dynamic announcements (toasts, error summaries).

ARIA patterns (tabs, menus, listboxes, comboboxes, dialogs) follow the WAI-ARIA Authoring Practices Guide patterns exactly. Hand-rolled ARIA is a violation source.

### Forms

- Every input has a visible label (or `aria-label` if visual context provides it — but visible labels are preferred).
- Required fields marked clearly (not only by color).
- Errors are announced (via `aria-live` or `aria-describedby`).
- Inline validation provides text, not just color cues.
- Auto-complete attributes set correctly (`autocomplete="email"`, etc.) for password managers and screen readers.

### Images and media

- Meaningful images have `alt` text describing the content's *purpose*.
- Decorative images have `alt=""` (empty, not missing) so screen readers skip them.
- Videos have captions and transcripts.
- Audio has transcripts.

### Internationalization-aware

- `<html lang="...">` set correctly per page/component locale.
- Direction (LTR/RTL) set explicitly when relevant.

## Testing protocol

### Automated (CI)

axe (or equivalent) runs as part of the build:

- **Per Storybook story** (via @storybook/addon-a11y) — every component variant is axe-tested in isolation.
- **Per E2E test** (via @axe-core/playwright or cypress-axe) — full pages are tested as users see them.
- **CI gate** — new a11y violations fail the build. Existing violations (legacy) are tracked separately in `.project/working/a11y-debt.md`.

axe is fast and catches ~30% of issues. The other 70% need manual testing.

### Manual (per release; per significant change)

- **Keyboard-only navigation** — unplug the mouse; complete the primary user flows using only the keyboard. Note any unreachable elements, lost focus, illogical order.
- **Screen reader** — VoiceOver (macOS/iOS), NVDA or JAWS (Windows), TalkBack (Android). Listen through the primary flows. Note unannounced content, confusing announcements, role mismatches.
- **Zoom test** — zoom browser to 200% and 400%. Content should reflow, not require horizontal scrolling at 200% (WCAG 1.4.10).
- **Color check** — view the UI in grayscale; ensure information is preserved.

QA Engineer runs the manual protocol pre-release; results go into `.project/working/a11y-manual-{release}.md`.

## Severity tagging (for review/audit)

| Severity | Definition |
|---|---|
| **blocker** | Violation of WCAG conformance level (e.g., AA violation when the target is AA). Examples: contrast failures, missing labels, keyboard traps, missing alt on meaningful images. |
| **major** | Conformance is technically met but the experience is significantly worse for assistive-tech users. Examples: confusing focus order, inadequate ARIA on custom widgets. |
| **minor** | Edge-case issues; small improvements. |
| **nit** | Stylistic improvement. |

Any blocker fails the gate. Existing legacy blockers are tracked into `tech-debt-management` with a remediation plan.

## Outputs

| Output | Location |
|---|---|
| A11y checklist per component | inline in component's Storybook (`docs` story or a11y addon panel) |
| axe configuration | `axe.config.json` or equivalent in the FE project |
| CI integration | `.github/workflows/` or CI equivalent |
| Findings per audit/review | `.project/working/a11y-findings-{date}.md` |
| Manual testing protocol results | `.project/working/a11y-manual-{release}.md` |
| WCAG conformance attestation | `.project/operational/a11y-attestation-{release}.md` |

## Mode handling (G/B)

**Greenfield.** Build a11y in from day one. The design system is a11y-tested as components land.

**Brownfield.** Audit the existing surface; categorize findings (blockers / major / minor / nit). Backlog the blockers into `tech-debt-management` with a remediation plan. New slices meet the bar; existing surfaces are improved opportunistically until parity is reached.

## What this skill does not do

- Replace user research with disabled users — real-user testing surfaces issues automated checks and protocol-driven testing miss.
- Approve regulatory compliance — that's `compliance-privacy` consuming this skill's attestations.
- Make the product fast — that's `frontend-performance` (a11y and perf are related but distinct).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We'll add a11y in v2." | Retrofit cost is 5-10x the build-in cost. A11y from day one or never. |
| "Our users don't use screen readers." | You don't know that. And even if true, keyboard nav, contrast, focus management help every user. |
| "Auto-tests catch a11y bugs." | Auto-tests catch ~30%. The other 70% require human + assistive-tech testing. Both are needed. |
| "Color choices are designer's, not engineer's." | Color contrast is testable. Engineers can — and should — catch low-contrast components in code review. |
| "WCAG is a guideline." | For most regulated regions in 2026 it's a legal requirement. Treat as binding. |
| "Tab order is automatic." | DOM order ≠ visual order ≠ logical order. Tab order needs deliberate management for complex UIs. |
| "Aria does the work." | ARIA tells assistive tech what your custom element pretends to be. Used wrong, it makes things worse. Prefer semantic HTML. |

## Verification

You are done when:

- [ ] WCAG conformance target met (typically AA) per `nfr-definition`.
- [ ] Automated a11y scan (axe / Pa11y) integrated in CI; zero violations on changed pages.
- [ ] Keyboard navigation tested for every interactive flow.
- [ ] Screen reader sample test on top-3 user flows (VoiceOver, NVDA, JAWS as applicable).
- [ ] Color contrast tested; minimum 4.5:1 for normal text, 3:1 for large text + UI components.
- [ ] Focus management verified for modals, drawers, dialogs, page transitions.
- [ ] Form errors announced + linked via aria-describedby.
- [ ] Skip-links + landmark regions + heading hierarchy correct.

Evidence to check:
- Sample SR pass produces a usable experience (recorded run).
- Axe CI gate enforces the rule.

## Anti-patterns

- "We'll add a11y in v2." Retrofit cost is 5–10x the build-in cost. Never.
- Relying only on automated checks. axe catches ~30% of issues.
- Hand-rolled ARIA roles and states. Follow WAI-ARIA patterns exactly; don't improvise.
- Hiding focus indicators because they "look bad." Design them deliberately; don't remove them.
- Using `aria-label` when a visible label would work. Visible labels help everyone; hidden labels help only screen-reader users.
- Treating a11y as a checklist to complete once. It's a continuous practice; new code can regress it.
