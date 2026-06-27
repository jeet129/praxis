---
name: stack-web-frontend
description: Idiomatic web frontend implementation pack — project layout, state management, data fetching, routing, rendering strategy implementation, build tooling, framework-specific test idioms. Per the agnostic-everywhere decision, ships with framework-specific references for React+Next.js, Angular, and Vue+Nuxt.
---

# Stack — Web Frontend


<!-- praxis:description:full -->
## Full description

Idiomatic web frontend implementation pack — project layout, state management, data fetching, routing, rendering strategy implementation, build tooling, framework-specific test idioms. Per the agnostic-everywhere decision, ships with framework-specific references for React+Next.js, Angular, and Vue+Nuxt. Complements `frontend-architecture` (which makes the macro decisions) with the implementation-side idioms (the playbook). Frontend Developer consumes this for any UI implementation work.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: stack
domain: frontend
state: active
dependencies:
 - engineering-standards
 - frontend-architecture
 - design-system
triggers:
 - "implementing a frontend feature"
 - "scaffolding a new frontend app"
 - "choosing components from the design system in code"
 - "configuring framework-specific test idioms"
 - "wiring data fetching, state, and routing"
outputs:
 - scaffolded module/feature conforming to the layout
 - code conforming to standards + framework idioms
 - configuration (tsconfig, build, lint, format)
 - test scaffolds (framework-specific)
consumers:
 - frontend-developer
 - code-review (uses for FE idiom checks)
 - testing-strategy (uses for FE test patterns)
references:
 - react-next.md
 - angular.md
 - vue-nuxt.md
```
<!-- praxis:metadata:end -->

The implementation playbook for the frontend. Three framework variants are supported (per the agnostic-everywhere decision): React + Next.js, Angular, Vue + Nuxt. The shared workflow body (this file) is framework-neutral; the framework-specific idioms live in references.

When implementing a frontend slice, the Frontend Developer reads:
- `engineering-standards/SKILL.md` (the universal bar).
- This file (the shared FE workflow).
- The specific framework reference (`references/react-next.md`, `references/angular.md`, or `references/vue-nuxt.md`) for the active framework.

The framework choice is set by `frontend-architecture` per project.

## Project layout (framework-neutral)

Feature-folder structure mirroring the bounded contexts:

```
src/
├── app/ framework's app root (routes, layouts, providers)
├── routes/ or pages/ URL-mapped routes (file-based in modern frameworks)
├── features/ one feature folder per bounded-context UI surface
│ ├── orders/
│ │ ├── components/
│ │ ├── hooks/ or composables/ or services/
│ │ ├── api/
│ │ ├── types/
│ │ └── routes/
│ └── billing/
├── design-system/ shared components (the `design-system` skill's output)
├── lib/ shared utilities — small, no UI
├── locales/ i18n catalogs (expansion via i18n-l10n)
├── styles/ global styles, theme bridges
└── tests/ mirrors features/
```

A flat `components/` + `services/` + `pages/` structure at the top level is a violation. Feature folders compose with the bounded contexts identified in `domain-discovery`.

## Universal disciplines

These apply regardless of framework:

### TypeScript strict

`strict: true`. `noUncheckedIndexedAccess: true`. `exactOptionalPropertyTypes: true`. Same baseline as `stack-node-ts`.

### Boundary validation

Every external input is validated at the boundary with zod (or framework-specific equivalent — Angular's reactive forms validators, Vue's vee-validate). Types are *derived* from schemas, never declared separately.

### State management

Per `frontend-architecture`'s decisions:

- **Server state** — TanStack Query (React, Vue), `@tanstack/angular-query` (Angular), or framework-native data layer (RSC, Nuxt's `useFetch`, Angular's resource API).
- **URL state** — query params and path segments. Frameworks have idioms (Next.js `searchParams`, Vue Router, Angular Router).
- **Local state** — framework hooks/signals/composables. Component-local.
- **Form state** — form library (React Hook Form, vee-validate, Angular Reactive Forms).
- **Cross-component client state** — Context (React), provide/inject (Vue), DI (Angular), or a small global store (Zustand / Pinia / NgRx Signal Store) only when justified.

### Data fetching

Per `frontend-architecture` and `api-design`:

- TanStack Query / SWR / framework-native for cache + invalidate + mutate.
- Use the OpenAPI spec to generate types and (optionally) clients — orval, openapi-typescript, NSwag, etc.
- Never hand-roll fetch in components; centralize per-feature in `api/`.

### Forms

- Form library at the boundary; never roll your own.
- Zod (or framework equivalent) schemas as the source of truth for validation.
- Inline errors per field; form-level error summary for screen reader announcement (per `accessibility`).

### Error handling

- Error boundaries (React `ErrorBoundary`, Vue `errorCaptured`, Angular `ErrorHandler`) at the feature root.
- Per-route error UI (frameworks have declarative slots for this).
- Errors logged to the error-tracking backend (Sentry, etc.) — per `observability`.

### Observability hooks

Per `observability` skill applied to FE:

- **RUM (Real User Monitoring)** — Sentry, DataDog RUM, Cloudflare RUM, or open-source alternatives. Tracks Core Web Vitals + custom marks.
- **Error tracking** — every unhandled exception captured with stack trace + breadcrumbs + user identifier (anonymized).
- **Correlation ID propagation** — every API call carries the correlation ID; the FE generates one per session/page.
- **Custom event tracking** — meaningful user actions (sign-up completed, checkout initiated) for product analytics. Distinct from observability metrics.

### Performance

Per `frontend-performance` (deepening; baseline here):

- **Code splitting** — per route by default; per feature when feature payloads are large.
- **Image optimization** — framework's image component (Next/Image, Nuxt Image, NgOptimizedImage).
- **Bundle size monitoring** — bundle analyzer in CI; budgets per route.
- **Lighthouse CI** — Web Vitals targets per release.

### Accessibility

Per `accessibility` skill applied during implementation:

- Semantic HTML primary.
- ARIA only when needed.
- Keyboard interaction for every interactive element.
- Focus management for dynamic content.
- axe in dev (via the framework's a11y addon) and in CI.

### Internationalization (expansion via i18n-l10n)

Baseline:
- Locale routing scaffolded (or planned for) even if only one locale ships initially.
- All user-facing strings via the i18n library; no hardcoded text in components.

## Testing

Per `testing-strategy` applied to FE:

- **Unit tests** — pure component logic (hooks, composables, services) and utility functions. Fast.
- **Component tests** — render-and-interact tests. React Testing Library, Vue Test Utils, Angular's TestBed.
- **Visual regression** — per `design-system` (Storybook + Chromatic / Playwright Visual).
- **E2E tests** — Playwright (preferred) or Cypress for the critical user journeys.
- **A11y tests** — axe per story and per E2E.

## Build and tooling

Framework-specific (see references). Universal:

- **Lint** — ESLint with framework-appropriate plugins; the project pins a config.
- **Format** — Prettier (or Biome).
- **Type check** — `tsc --noEmit` in CI.
- **Bundle analysis** — bundle-analyzer in CI; budgets in `lighthouse-budget.json` or equivalent.

## Framework references

Pick the one for the active framework:

- **React + Next.js** — `references/react-next.md`
- **Angular** — `references/angular.md`
- **Vue + Nuxt** — `references/vue-nuxt.md`

Only the relevant reference loads (progressive disclosure). Each reference covers framework-specific layouts, hooks/composables/services, data fetching idioms, routing patterns, testing tools, and common violations to flag in review.

## Mode handling (G/B)

**Greenfield.** Scaffold via the framework's CLI; apply the layout + disciplines above.

**Brownfield.** Read `.repo-intel/conventions.md` for the existing FE conventions; match for new code; flag drift in ADR.

## What this skill does not do

- Choose the framework — that's `frontend-architecture`.
- Design the components — that's `design-system`.
- Design the screens — that's `wireframing-prototyping`.
- Verify a11y deeply — that's `accessibility` (this skill applies the disciplines; that skill audits).
- Tune performance — that's `frontend-performance`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Newest framework is best." | Framework choice is about ecosystem maturity + team familiarity + product needs. Newness alone is a tax. |
| "Tailwind everywhere — fast to write." | Fast initially; ages poorly without design tokens. Use Tailwind alongside a design-system, not instead of one. |
| "We need a state management library." | Local state + URL state + server state (TanStack Query, SWR) usually suffices. Reach for Redux / Zustand only when actually needed. |
| "RSC / SSR / streaming because that's the new hot thing." | The right rendering strategy depends on TTI + SEO + interactivity needs. Decide deliberately. |
| "CSS-in-JS is best." | Runtime CSS-in-JS has cost. Compile-time variants (linaria, panda) or plain CSS + tokens are usually better. |
| "Bundlers are an abstraction we don't need to think about." | Bundle splitting / lazy loading / treeshaking are real perf levers. Know what your bundler does. |
| "Accessibility is a checklist we do at the end." | A11y is a property of components, not an audit. Ship it from component creation. |

## Verification

You are done when:

- [ ] Framework + meta-framework choice documented (React + Next.js / Vue + Nuxt / Svelte + SvelteKit / Angular).
- [ ] Component model + state-management approach documented per `frontend-architecture`.
- [ ] Design system applied; no orphan styles.
- [ ] Bundler config produces tree-shaken, code-split output.
- [ ] Routing strategy + data-fetching pattern decided.
- [ ] Accessibility checks built into component story / unit tests (per `accessibility`).
- [ ] Frontend performance budget set (per `frontend-performance`).
- [ ] Browser/devices supported documented.

Evidence to check:
- Lighthouse scores meet the project's targets.
- Initial bundle size within budget.
- a11y scan (axe / Pa11y) runs in CI.

## Anti-patterns (universal across frameworks)

- One-off styles instead of design-system components.
- Server state in a global client store.
- Form validation hand-rolled instead of using a form library.
- Components that import deeply from infrastructure (breaking dependency inversion in FE too).
- Bundle size growing without per-route awareness.
- Hardcoded user-facing strings (no i18n hook).
- `any` outside boundary code.
- Imperative DOM manipulation outside the framework's reactive model.
