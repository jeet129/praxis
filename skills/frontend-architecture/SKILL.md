---
name: frontend-architecture
description: Frontend macro-decisions — component model, state-management choice (local / server / global / signals), data-fetching strategy (REST / GraphQL / RSC / cache-and-mutate), rendering strategy (SSR / SSG / ISR / CSR / streaming), routing model, micro-frontends (only if justified). The FE analog of `architecture-pattern-selection`. Solution Architect runs this for any web product; defaults to KISS — the simplest FE architecture that meets the NFRs. Use whenever a new web product is being designed or a slice introduces FE patterns not yet established.
---

# Frontend Architecture


<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: frontend
state: active
dependencies:
 - architecture-pattern-selection
 - nfr-definition
 - design-system
triggers:
 - "designing the FE architecture for a new product"
 - "choosing state management for a new slice"
 - "deciding rendering strategy (SSR / SSG / CSR / streaming / RSC)"
 - "evaluating whether micro-frontends are warranted"
 - "establishing routing model"
outputs:
 - FE architecture decision + ADR
 - component hierarchy / layout map
 - data-flow diagram
 - state-management strategy
 - rendering-strategy decision (per route or per app)
 - routing model
consumers:
 - solution-architect (primary author)
 - frontend-developer (consumes for implementation)
 - architecture-challenger (attacks FE decisions in scale/perf/security passes)
 - stack-web-frontend (consumes for framework-specific implementation)
references: []
```
<!-- praxis:metadata:end -->

The FE analog of `architecture-pattern-selection`. Most FE projects don't need exotic architectures; the right default is "boring works." Single-page application with conventional routing, server-side rendering where SEO or first-paint matters, and a state model that matches the actual data lifetimes. Over-engineered FE is one of the most expensive forms of YAGNI violation.

This skill produces the macro-decisions; `stack-web-frontend` translates them into idiomatic framework code; `design-system` provides the components implemented under those decisions.

## When this skill fires

- A new web product is being designed; the FE architecture is being chosen.
- A slice introduces FE patterns the existing architecture doesn't accommodate (e.g., adding real-time updates to a previously request/response app).
- An NFR change forces re-evaluation (e.g., a new SEO requirement triggers SSR consideration).

## The decisions

### 1. Rendering strategy

The fundamental decision. Each route or each app picks one:

| Strategy | Use when |
|---|---|
| **CSR (client-side rendering)** | Internal apps; behind-login dashboards; SEO doesn't matter; rich interactivity dominates. **Default for SaaS apps.** |
| **SSR (server-side rendering)** | First-paint matters (e-commerce, content); SEO matters; the app needs cookies/auth at render time. Adds server cost. |
| **SSG (static site generation)** | Content rarely changes; first paint must be instant; CDN-delivered. Marketing sites, docs. |
| **ISR (incremental static regeneration)** | Content changes occasionally but most page views are stale-tolerant. Hybrid SSG/SSR. |
| **Streaming + RSC (React Server Components / Suspense)** | Modern React-first; per-component server/client split; partial hydration. Powerful but adds mental complexity. |

Most SaaS products: CSR for the authenticated app; SSG or SSR for the marketing site. Mixed within one Next.js / Nuxt / Angular Universal codebase is fine.

### 2. State management

Categorize state by lifetime and ownership:

- **Server state** — data owned by the backend (user data, business records). **Lives in a server-state library** (TanStack Query, SWR, Apollo Client, Relay). Don't put server data in a global client store — it diverges from server reality and creates synchronization bugs.
- **URL state** — data that should survive page reload and be shareable (current filter, page number, selected tab). Lives in the URL via query params or path segments.
- **Local component state** — UI state that doesn't outlive the component (input value while editing, open/closed of a panel). Component-local hooks (`useState`, `signal`, etc.).
- **Form state** — multi-field forms with validation, transient editing. Form library (React Hook Form, TanStack Form, Vee Validate).
- **Cross-component client state** — shared across components, doesn't fit server/URL/local. Use Context with care; a global client store (Zustand / Pinia / Redux Toolkit) only when Context doesn't fit.

**KISS bias:** don't reach for global client state by default. Most "global state" is actually server state (use TanStack Query) or URL state (put it in the URL). True global *client* state is rare — theme, locale, authenticated-user identity. That's it.

### 3. Data fetching

Aligned with the rendering strategy and state management:

- **REST + TanStack Query / SWR** — most common for CSR apps. Cache + invalidate + mutate pattern.
- **GraphQL + Apollo / urql / Relay** — when clients have varied data needs and the cost of GraphQL infrastructure is worth it. Not the default; adds operational complexity.
- **Server Components + fetch on server** — Next.js / RSC pattern. Eliminates much of the client-fetching machinery for SSR routes.
- **WebSockets / SSE** — when real-time updates are required. Layered on top of the request-response pattern, not replacing it.

The decision is mostly downstream of the backend's `api-design` style — REST API → REST FE; GraphQL API → GraphQL FE.

### 4. Routing model

For web stacks, file-based routing is the default in modern frameworks (Next.js, Nuxt, Remix, SvelteKit). Conventional routing in Angular and React Router is fine when file-based isn't a fit.

Routing decisions:

- **Nested routes** for parent-child UI relationships (layout + content). Standard.
- **Dynamic segments** for resource pages (`/orders/[id]`).
- **Catch-all routes** for content like docs (`/docs/[...slug]`).
- **Auth boundaries** — protected routes have a layout-level auth check, not per-page.
- **Loading and error boundaries** — every route segment has loading and error UI (frameworks make this declarative).

### 5. Component hierarchy

A standard hierarchy that matches the design system:

```
src/
├── app/ framework's app root (routes, layouts, providers)
├── pages/ or routes/ routes mapped to URLs
├── features/ feature folders, one per bounded-context UI surface
│ ├── orders/
│ │ ├── components/ feature-specific components
│ │ ├── hooks/ feature-specific hooks
│ │ ├── api/ feature-specific server-state queries
│ │ └── routes/ feature's pages (if not in top-level routes/)
│ └── billing/
├── design-system/ shared components (from design-system skill)
├── lib/ shared utilities (no UI; small)
└── tests/
```

**Feature folders > "all components in one big folder."** Feature folders match bounded contexts; components used only within a feature live there.

### 6. Micro-frontends (rarely justified)

The default answer is **no**. Micro-frontends solve a specific problem: independent deployment of UI surfaces by independent teams, with technology heterogeneity tolerated. Real cost:

- Bundle size grows (multiple framework runtimes).
- Auth / session sharing becomes hard.
- Design consistency degrades (multiple design systems unless heavily disciplined).
- Cross-MFE state is awkward.

Use micro-frontends only when:
- Multiple teams own independent product surfaces *and*
- Independent deployment per surface is a real requirement *and*
- The team has the operational maturity to handle the complexity.

For solo development: never.

### 7. Performance budgets

From `nfr-definition`, the performance NFRs translate into FE budgets:

- **Bundle size budget** — kilobytes per route (~100 KB initial JS for SaaS apps is a reasonable target).
- **Core Web Vitals targets** — LCP < 2.5s, INP < 200ms, CLS < 0.1 (the "good" thresholds from CrUX).
- **Time to first interactive** — when does the user have a working app?
- **API call budget per route** — how many requests fire during initial render?

Budgets enforced in CI via `frontend-performance` skill .

## The ADR

After running this skill, write the FE architecture ADR via `adr-decision-records`:

- **Context** — the NFRs and product shape driving the FE decisions.
- **Decisions made** — rendering strategy per route (or "all CSR"), state management approach, data fetching pattern, routing model, micro-frontend stance.
- **Rejected alternatives** — what was considered and why rejected.
- **Consequences** — positive, negative, neutral.

## Outputs

| Output | Location |
|---|---|
| FE architecture decision + ADR | `.project/decision/` via `adr-decision-records` |
| Component hierarchy / layout map | `.project/semantic/frontend-architecture.md` |
| Data-flow diagram (where applicable) | inline in the same file or as a diagram |
| State-management strategy summary | inline |

## Mode handling (G/B)

**Greenfield.** Standard decision flow.

**Brownfield.** The existing FE architecture is the strong default. The SA decides whether the slice fits or warrants divergence. Divergence is rare — FE architecture divergence almost always means starting a new app, not modifying the existing one.

## What this skill does not do

- Choose the framework (React/Angular/Vue) — that's `stack-web-frontend` (which is downstream of this skill's macro decisions).
- Design specific screens — that's `wireframing-prototyping`.
- Implement components — that's the Frontend Developer with the stack pack.
- Define the visual style — that's `design-system`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Micro-frontends because we'll scale." | Micro-frontends solve org-scale (independent team deploys), not technical scale. Without that pain, they add cost. |
| "Global state because components need shared data." | Most "shared" data is server state or URL state. Global state is rarely the right shape. |
| "SSR for SEO." | SSR helps SEO when crawlers can't render JS. For most modern apps, prerendering or SSG is sufficient. |
| "Latest framework version because security." | Major versions can break ecosystem. Update deliberately, with codemods + tests. |
| "Single bundle is simpler." | Initial load time matters; code-splitting per route is the cheap win. |
| "We don't need a design system yet." | Without one, components diverge from PR 1. Establish even a minimal one before the team grows. |

## Verification

You are done when:

- [ ] Component model decided (atomic / feature-based / domain-driven) and documented.
- [ ] State management approach documented (local + server-cache + URL + global, with criteria).
- [ ] Data fetching strategy documented (REST + cache / GraphQL / RSC / streaming).
- [ ] Rendering strategy decided (SSR / SSG / ISR / CSR / streaming) with rationale per NFR.
- [ ] Routing model decided.
- [ ] Bundle strategy documented (single / split / lazy boundaries).
- [ ] Micro-frontends decision: explicit no, or explicit yes with team-deploy justification.
- [ ] Design-system integration documented (per `design-system`).

Evidence to check:
- A senior FE engineer can read the architecture doc and produce a component without re-deciding any macro decision.
- Architecture Challenger has reviewed against scale + ops sub-personas.

## Anti-patterns

- "Microservices for the frontend" because microservices are popular on the backend. Not the same problem.
- Global client state for everything. Most state has a more specific home.
- One rendering strategy forced on every route. Mix where it pays off.
- Bundle size growing unchecked. Set a budget; enforce it in CI.
- Skipping the architecture decision and letting "patterns emerge" from the first slice. The first slice's patterns will rule the codebase; pick them deliberately.

## KISS bias for FE architecture

The default modern stack — Next.js or Nuxt with file-based routing, TanStack Query for server state, URL state for filters, local state for UI, design-system components, CSS-in-JS or Tailwind — solves 90% of SaaS-frontend problems. Reach for more exotic patterns only when an NFR demands it.
