# Engineering Standards — Node / TypeScript

Stack-specific expression of the principles in `SKILL.md` for Node 20+ with TypeScript 5.x. Backend services (NestJS / Express / Fastify) and full-stack runtimes.

## Project layout

Bounded contexts as top-level directories, not technical layers:

```
src/
├── billing/
│   ├── domain/             entities, value objects, domain events
│   ├── application/        use cases, services, ports
│   ├── infrastructure/     adapters (repos, external clients)
│   └── presentation/       controllers (NestJS) or route handlers (Express/Fastify)
├── auth/
│   ├── domain/
│   ├── application/
│   ├── infrastructure/
│   └── presentation/
└── shared/                 cross-cutting only; default empty
    ├── common/
    └── events/
```

A `controllers/` + `services/` + `repos/` flat structure at top level is a violation.

## TypeScript settings

`tsconfig.json` baseline (non-negotiable for new projects):

```jsonc
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitReturns": true,
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "esModuleInterop": true,
    "skipLibCheck": true,
    "isolatedModules": true
  }
}
```

`strict: true` is a hard requirement. Disabling `strictNullChecks` or `noImplicitAny` to ship faster creates debt that compounds. Either type properly or use `unknown` and narrow.

## Naming

- Files: `kebab-case.ts`. `user-service.ts`, not `UserService.ts`.
- Types and classes: `PascalCase`.
- Variables and functions: `camelCase`.
- Constants: `SCREAMING_SNAKE_CASE` if truly constant; `camelCase` if just config.
- Booleans: `isActive`, `hasPermission`, `canRetry`.
- Interfaces drop the `I` prefix (TypeScript convention since 2016): `OrderRepository`, not `IOrderRepository`.

## SOLID applied

**S — Single responsibility.** A module/class has one reason to change. NestJS makes this easy via providers; Express/Fastify projects need discipline to avoid god-handlers that talk to DB + render + send emails.

**O — Open/closed.** Discriminated unions + exhaustive `switch` for variation points. Plug-in registries (NestJS dynamic modules; in Express, hand-rolled registries) for extension.

**L — Liskov.** Subtypes honor parent contracts. The async/sync trap: a synchronous interface method overridden by an async impl is a violation in TypeScript even if the type system allows it via `Promise<T>` widening.

**I — Interface segregation.** Don't export 30-method interfaces. Split by use case. TypeScript's structural typing makes ad-hoc small interfaces cheap.

**D — Dependency inversion.** Ports as TypeScript interfaces in `domain/`; adapters in `infrastructure/`. NestJS injects via tokens; Express/Fastify hand-wires via a small composition root.

## Type discipline

- `unknown` over `any`. `any` defeats the type system; use it only at JSON boundaries with immediate validation.
- Use `zod` (or `valibot`) at every external boundary — request bodies, env vars, config files, third-party API responses. Validate at the boundary; trust types within.
- Discriminated unions for finite domains: `type OrderStatus = { kind: 'pending' } | { kind: 'paid', paidAt: Date } | { kind: 'refunded', refundedAt: Date, reason: string };`
- `readonly` on domain types whenever possible. Mutability is the exception, not the default.
- Prefer `type` for unions and intersections; `interface` for extensible object contracts.

## Error handling

- Domain errors are typed. Either typed `Error` subclasses with discriminators, or a `Result<T, E>` pattern (e.g., `neverthrow`). Pick one per project.
- Never throw a bare `Error`. Throw a domain-typed error with structured payload.
- At the API boundary (controller, route handler), translate domain errors to HTTP responses centrally — NestJS exception filters, Express error-handling middleware.
- `async` functions that can fail are typed `Promise<Result<T, E>>` or document their thrown errors. Unhandled promise rejections are blocker violations.

## Validation

- `zod` schemas as the single source of truth for shape — derive TypeScript types from the schema (`z.infer<typeof Schema>`), never duplicate.
- Validate at the boundary; trust within. Re-validating internally is a smell.

## Concurrency & async

- Always `await` promises in `async` functions. Floating promises are violations (TypeScript lint flags them).
- `Promise.all` for independent parallel work; `Promise.allSettled` when failure of one shouldn't abort others.
- Cancellation via `AbortController` for long-running operations. Express/Fastify pass `req.signal`-equivalents that should propagate downstream.
- No `setTimeout` for "throttling" or "wait for state" — use proper synchronization primitives.

## Persistence

- ORMs: Prisma or Drizzle for type-safe SQL; TypeORM only if the team has prior expertise and the project's complexity justifies it.
- Migrations checked into the repo. No auto-sync schema changes in production.
- Repository pattern in `infrastructure/persistence/`. Domain entities are POTOs (plain old TS objects); persistence entities are separate or use ORM annotations contained to the infrastructure layer.

## Logging

- `pino` for structured JSON logging (fast and structured-first). `winston` only when an existing project standardized on it.
- Correlation ID via async-local-storage (`AsyncLocalStorage`) — set at request boundary, propagated automatically to all downstream calls.
- Never log raw request/response bodies that may carry PII.
- Log levels: `trace` (dev only) / `debug` / `info` / `warn` / `error` / `fatal`. Use them as documented.

## Build & packaging

- ESM modules (`"type": "module"` in package.json) for new projects.
- `tsx` or `tsc --watch` for dev; `tsc` for build; `esbuild` or `tsup` for bundling when needed (typically not for backend services — ship the compiled `dist/`).
- Pin Node version via `.nvmrc` and `engines` in package.json.
- `npm`, `pnpm`, or `yarn` — choose one and stick with it; lock file checked in.
- Production Dockerfile: multi-stage, non-root user, distroless or `node:slim` base.

## Testing

- `vitest` or `jest`. New projects: vitest (faster, better ESM, native TypeScript).
- `supertest` for HTTP integration tests.
- Testcontainers (`testcontainers` npm package) for real Postgres / Redis in integration tests.
- Test files colocate with source: `user-service.test.ts` next to `user-service.ts`. Or `__tests__/` per directory if the team prefers separation.
- Test names: full-sentence behavior. `it('charges the tenant when credit is sufficient')`.

## Common violations to flag in review

- `as` type assertions without runtime validation (`response as User` is a violation; `userSchema.parse(response)` is correct).
- Floating promises (`asyncFn()` without `await` or `void`).
- `any` outside of explicit boundary-handling code.
- `console.log` in production code paths.
- Re-validating data that's already been validated at the boundary.
- Mutating function parameters.
- Circular imports between domain and infrastructure (dependency-inversion violation).
- Default exports for anything other than React components or whole-module config (named exports are clearer).

## Tooling

Recommended baseline:

- **Build:** `tsc` + `tsx` (dev), `tsup` (bundling when needed).
- **Test:** vitest, supertest, Testcontainers, MSW for HTTP mocking.
- **Lint:** ESLint with `@typescript-eslint`, `eslint-plugin-import`, `eslint-plugin-promise`.
- **Format:** Prettier.
- **Type checking in CI:** `tsc --noEmit` as a build step.
- **Dependency hygiene:** `npm audit` + Renovate; `snyk` or `socket.dev` for richer signal.
