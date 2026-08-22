---
name: stack-node-ts
description: "Idiomatic Node.js / TypeScript backend implementation pack — project layout, framework idioms (NestJS / Express / Fastify), strict TypeScript configuration, dependency injection, runtime validation with zod, persistence (Prisma / Drizzle), structured logging with pino, async/concurrency discipline, build (tsc / tsup), packaging (multi-stage Docker), and test idioms (vitest / supertest / Testcontainers). Complements `engineering-standards/references/node-ts.md` (the bar) with the implementation-side idioms (the playbook). Use whenever a developer is implementing a Node/TS backend slice, scaffolding a new service, or choosing between framework patterns."
---

# Stack — Node / TypeScript

<!-- praxis:metadata:begin -->
```yaml
capability: stack
domain: backend
state: active
dependencies:
 - engineering-standards
triggers:
 - "implementing a feature on Node/TypeScript"
 - "scaffolding a new Node/TS service"
 - "choosing between NestJS / Express / Fastify"
 - "configuring TypeScript strict settings"
 - "configuring Node testing"
outputs:
 - scaffolded module conforming to the layout
 - code conforming to standards + framework idioms
 - tsconfig.json + package.json + lock file
 - test scaffolds (vitest + supertest + Testcontainers)
consumers:
 - backend-developer
 - code-review
 - testing-strategy
references:
 - nestjs.md
 - fastify.md
 - express.md
 - architecture.md
```
<!-- praxis:metadata:end -->

Implementation idioms for Node 20+ and TypeScript 5.x backend services. Complements `engineering-standards/references/node-ts.md` — that file is the *bar*; this file is the *playbook*.

## Framework choice

The three mainstream Node backend frameworks have different sweet spots. Pick at project start; don't mix.

| Framework | Sweet spot | Reference |
|---|---|---|
| **NestJS** | Opinionated, batteries-included, decorator-driven. DI built-in. Best for teams that want structure, especially coming from Java/Spring or Angular. Heavier. | `references/nestjs.md` |
| **Fastify** | Performance-first, plugin architecture, less ceremony than Nest. Good middle ground. | `references/fastify.md` |
| **Express** | Minimalist, mature, ubiquitous. Best when team has Express experience and the project is small. Most "DIY" — you wire DI yourself. | `references/express.md` |

If unsure: **NestJS** for non-trivial projects with > 2 engineers; **Fastify** for performance-sensitive services; **Express** for small/legacy compatibility.

## Project layout

Bounded-context-first, mirrored from `engineering-standards`. `controllers/` + `services/` + `repos/` at the top level is a violation. Load `references/architecture.md` for the full directory tree.

## TypeScript configuration

`strict: true` is hard-required. Disabling `strictNullChecks` to ship faster is a debt that compounds. Load `references/architecture.md` for the non-negotiable `tsconfig.json` baseline.

## Boundary validation with zod

Every external input is validated at the boundary; the request type is *derived* from the schema — never declared separately. Single source of truth. Load `references/architecture.md` for the schema pattern, or `references/fastify.md` / `references/express.md` for framework-specific schema wiring.

## Dependency injection

Pattern depends on framework:

- **NestJS** — built-in DI via decorators and modules. Use it.
- **Fastify / Express** — hand-wire a composition root in `src/app.ts` or use a lightweight DI container (`tsyringe`, `awilix`). Avoid building a custom container.

## Application service (framework-neutral)

`readonly` on injected dependencies. `async` is the default for I/O-bound work. Load `references/architecture.md` for the full use-case template.

## Persistence

**Prisma** (preferred) or **Drizzle** for type-safe SQL. TypeORM only if the team has prior expertise and the project's complexity justifies it. Migrations checked in (`prisma/migrations/`). No `prisma db push` in production. Load `references/architecture.md` for the schema + repository template.

## Error handling

Typed domain errors with discriminators. Central error translation in framework-specific filter / middleware (NestJS exception filter; Fastify `setErrorHandler`; Express error-handling middleware). Never throw bare `Error`; never `catch (e: any)` and swallow. Load `references/architecture.md` for the domain-error template.

## Logging

`pino` for structured JSON logging; `AsyncLocalStorage` for correlation-ID propagation through async chains. Load `references/architecture.md` for the configuration snippet.

## Async discipline

- Every promise is `await`ed or explicitly `void`. Floating promises are blocker violations.
- `Promise.all` for independent parallel work; `Promise.allSettled` when partial failure is acceptable.
- `AbortController` for cancellation propagation.
- No `setTimeout` for synchronization.

## Testing

**Vitest** (preferred for new projects — fast, ESM-native, TS-native) or **Jest**. Load `references/architecture.md` for the unit-test and Testcontainers templates.

## Build and packaging

For backend services, ship compiled JS (no bundler needed in most cases). `npm`, `pnpm`, or `yarn` — choose one per project; lockfile checked in. Load `references/architecture.md` for the `package.json` fragments and Dockerfile.

## Observability hooks

- `pino-http` for request logging with correlation ID.
- `prom-client` for Prometheus metrics; `/metrics` endpoint.
- OpenTelemetry instrumentation per the `observability` skill; leaves the hooks ready for the collector wiring.

## Sub-variant references

- `references/nestjs.md` — NestJS-specific module/provider/decorator patterns.
- `references/fastify.md` — Fastify plugin architecture, schema-driven validation.
- `references/express.md` — Express patterns, hand-rolled DI, middleware discipline.
- `references/architecture.md` — framework-neutral templates: project layout, tsconfig, zod schemas, application service, Prisma persistence, error types, pino logging, vitest/Testcontainers, package.json + Dockerfile.

## Mode handling (G/B)

**Greenfield.** Scaffold via the chosen framework's CLI (`nest new`, `fastify-cli`, or hand-rolled for Express). Replace the default flat layout with the bounded-context-first layout.

**Brownfield.** Read `.repo-intel/conventions.md`. Match existing layout and patterns for new code; flag drift in an ADR.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "`any` is fine for boundaries." | At boundaries, use `unknown` + a runtime validator (zod / valibot). `any` removes type checking, not just delays it. |
| "TypeScript with strict-mode-off is faster to write." | The bugs strict mode catches will catch you later, at higher cost. Strict-on from day one. |
| "Async/await everywhere makes code clean." | True; but unhandled rejections + nested awaits in loops are subtle hazards. Type Promise<T> explicitly when returning. |
| "ESM vs CJS doesn't matter for the app." | It does — for bundle output, tree-shaking, and dependency compat. Pick one (ESM, by default in 2026) and configure it consistently. |
| "Node has good built-in tools; no need for a framework." | True for simple services; not true for HTTP-routing / validation / DI / config / lifecycle / observability. Pick (Fastify, Express, Nest, Hono) deliberately. |
| "tsx / ts-node for production." | For dev. Production runs compiled JS. Mixing means slow startup + dev/prod skew. |

## Verification

You are done when:

- [ ] `tsconfig.json` has `strict: true`; no per-file `// @ts-nocheck`.
- [ ] Runtime validation library (zod / valibot / yup) guards every external boundary.
- [ ] Error types are explicit; not `Error` everywhere.
- [ ] No `any` outside documented boundary code.
- [ ] Logger is structured (pino / winston) with correlation IDs.
- [ ] Async work has timeouts; unhandled rejection handler installed.
- [ ] Build produces JS for prod; tsx/ts-node confined to dev.
- [ ] `package.json` engines field pins Node version.
- [ ] Brownfield: existing conventions matched; divergence captured in ADR.

Evidence to check:
- `tsc --noEmit` runs clean.
- ESLint rules enforce stylistic + correctness checks; no overrides.

## Anti-patterns

- `any` outside of explicit boundary-handling.
- Floating promises.
- Re-validating data already validated at the boundary.
- Mutating function parameters.
- Default exports (use named exports).
- `console.log` in production code.
- N+1 queries in ORM mappings (Prisma's `include` vs explicit `select`).
- `eval`, `new Function`, or any dynamic code execution.
