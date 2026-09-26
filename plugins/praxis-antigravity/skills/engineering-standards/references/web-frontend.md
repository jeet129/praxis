# Engineering Standards — Web Frontend

Stack-specific expression of the principles in `SKILL.md` for frontend codebases (React/Next.js, Angular, Vue/Nuxt — framework idioms live in `stack-web-frontend/references/*`; this file is the cross-framework engineering bar). Applies to `code-review`, `secure-coding`, and `testing-strategy` whenever the diff touches frontend code.

## Project layout

Feature-based (bounded-context) directories, not type-based buckets:

```
src/
├── features/
│   ├── checkout/
│   │   ├── components/        presentational + container components
│   │   ├── hooks/              feature-scoped hooks / composables
│   │   ├── api/                data-fetching layer for this feature
│   │   ├── state/               feature-scoped store slice
│   │   └── types.ts
│   ├── catalog/
│   │   └── ...
│   └── shared/                 cross-cutting only; default small
│       ├── components/          truly generic (Button, Modal, Input)
│       ├── hooks/
│       └── lib/
└── app/                         routing / app shell / providers
```

A top-level `components/` + `hooks/` + `utils/` split with hundreds of files and no feature grouping is a violation past a handful of screens — it's the frontend equivalent of the `controllers/`+`services/`+`repositories/` anti-pattern.

## TypeScript strict mode (non-negotiable)

```jsonc
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitReturns": true,
    "jsx": "react-jsx"
  }
}
```

`any` in application code is a violation; `unknown` + narrowing is the escape hatch when a type genuinely can't be known ahead of time. Component props are always typed — no untyped `props` objects, no `React.FC` without a props generic.

## Component boundaries

- **Presentational vs container split**: presentational components receive data and callbacks via props only — no direct data-fetching, no direct store access. Container components own data-fetching/state and pass it down. This keeps presentational components trivially testable and reusable.
- **One component, one responsibility.** A component that fetches data, manages three pieces of local state, and renders a complex layout is a signal to split into a container + one or more presentational children.
- **Props are the API.** Treat a shared component's prop interface with the same discipline as a backend service's REST contract — breaking a shared component's props is a breaking change, reviewed accordingly.
- **Composition over configuration.** Prefer children/slots and composable sub-components over a single component with a dozen boolean/enum props controlling its rendering (`variant`, `size`, `showX`, `showY`, ...) — the boolean-prop-explosion pattern is a KISS/SOLID violation in frontend form.

## State discipline

Not all state belongs in the same place — misplaced state is the most common frontend architecture smell.

| State kind | Where it lives | Example |
|---|---|---|
| Local UI state | Component-local (`useState`/`ref`) | Is a dropdown open, form input value before submit |
| Cross-component, feature-scoped | Feature state slice (Zustand/Redux slice/Pinia store/Context) | Checkout cart contents, wizard step |
| Server/cache state | A data-fetching library (TanStack Query, SWR, Apollo, RTK Query) — never hand-rolled `useEffect` + `useState` fetch | API responses, anything with staleness/caching semantics |
| Global app state | App-level store, used sparingly | Authenticated user, theme, feature flags |
| URL state | Router (query params / path segments) | Filters, pagination, tab selection — anything that should survive a refresh or be shareable via link |

**Server state and client state are different problems** — the single most common violation is managing fetched API data with the same local-state tools used for UI state, hand-rolling loading/error/retry/cache-invalidation logic that a data-fetching library already solves correctly. `useEffect` for data fetching (outside of a data-fetching library's internals) is a code-review flag.

## Accessibility bar (a11y)

Non-negotiable baseline — WCAG 2.1 AA is the target, checked at review, not bolted on later:

- Semantic HTML first: `<button>` for actions, `<a>` for navigation, native form elements over div-based re-implementations. ARIA roles are a fallback for what semantic HTML can't express, not a first resort.
- Every interactive element is keyboard-reachable and keyboard-operable (tab order, Enter/Space activation, Escape to dismiss modals/menus).
- Every image has meaningful `alt` text (or `alt=""` when explicitly decorative — never omitted).
- Form inputs have associated `<label>`s (visible or `aria-label`), and validation errors are announced to assistive tech (`aria-describedby` + `role="alert"` or a live region).
- Color is never the sole signal (status, errors, required fields) — pair with text/icon.
- Focus management on route change and modal open/close — focus moves to the new context, and is trapped inside modals while open.
- Automated checks (`axe-core`, `eslint-plugin-jsx-a11y`) run in CI as a floor, not a ceiling — automated tools catch roughly a third of WCAG issues; manual keyboard/screen-reader spot checks are part of the review for significant UI changes. See `accessibility` skill for the full discipline.

## Testing layers (frontend expression of the pyramid)

Full test-pyramid rationale lives in `testing-strategy`; this is the frontend-specific application:

- **Unit** — pure functions, hooks in isolation (`renderHook`), reducers/selectors. Fast, no DOM rendering needed where avoidable.
- **Component tests** — render a component with Testing Library, assert on rendered output and behavior from a user's perspective (`getByRole`, not `getByTestId` as a first resort — querying by role/label doubles as an accessibility check). Never assert on implementation details (internal state, private methods, CSS class names as the primary assertion).
- **Integration** — a feature's components + real (or MSW-mocked at the network layer, not component-mocked) data-fetching working together — verifies the container/presentational wiring and state flow actually work, not just each piece in isolation.
- **E2E** — Playwright/Cypress, critical user journeys only (login, checkout, primary conversion flow) per the pyramid's "few at the top" discipline.
- **Visual regression** (optional, high-value for design-system components) — Chromatic/Percy catches unintended visual diffs that functional tests don't.

`render()` + `fireEvent`/`userEvent` + assert-on-DOM-output is the default pattern; testing a component by reaching into its internal hooks/state is a violation — it breaks on refactors that don't change behavior.

## Common violations to flag in review

- `any` types, or `@ts-ignore` without a comment explaining why and a linked issue.
- Data fetching inside `useEffect` where a data-fetching library (TanStack Query/SWR/RTK Query/Apollo) is already in the stack.
- Boolean-prop-explosion on shared components instead of composition.
- Missing `alt` text, unlabeled form inputs, non-keyboard-operable custom interactive elements (a `<div onClick>` masquerading as a button).
- Business logic embedded in presentational components (API calls, complex derived-state calculations) instead of extracted to hooks/services.
- Global state used for feature-scoped or local concerns — state placed at a broader scope than it needs, causing unnecessary re-renders and coupling.
- Components over ~200-300 lines doing multiple unrelated things — split signal, same as backend SRP violations.
- Tests asserting on CSS classes or internal component state instead of rendered, user-visible behavior.
- Uncontrolled bundle growth — no code-splitting on route boundaries for a large app (see `frontend-performance` for the full discipline).
