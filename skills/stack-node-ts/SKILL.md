---
name: stack-node-ts
description: Idiomatic Node.js / TypeScript backend implementation pack — project layout, framework idioms (NestJS / Express / Fastify), strict TypeScript configuration, dependency injection, runtime validation with zod, persistence (Prisma / Drizzle), structured logging with pino, async/concurrency discipline, build (tsc / tsup), packaging (multi-stage Docker), and test idioms (vitest / supertest / Testcontainers). Complements `engineering-standards/references/node-ts.md` (the bar) with the implementation-side idioms (the playbook). Use whenever a developer is implementing a Node/TS backend slice, scaffolding a new service, or choosing between framework patterns.
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

Bounded-context-first, mirrored from `engineering-standards`:

```
src/
├── billing/
│ ├── domain/
│ │ ├── order.ts aggregate
│ │ ├── order-id.ts value object
│ │ ├── order-repository.ts port (interface)
│ │ └── events/order-placed.ts domain event
│ ├── application/
│ │ ├── place-order.use-case.ts
│ │ └── ports/payment-gateway.ts port
│ ├── infrastructure/
│ │ ├── persistence/
│ │ │ ├── prisma-order-repository.ts adapter
│ │ │ └── order.prisma.ts persistence shape
│ │ └── external/stripe-payment-gateway.ts
│ └── presentation/
│ ├── orders.controller.ts (or routes.ts for Fastify/Express)
│ ├── order.request.ts DTO + zod schema
│ └── order.response.ts DTO
├── auth/
│ └── ...
└── shared/ default empty
```

`controllers/` + `services/` + `repos/` at the top level is a violation.

## TypeScript configuration

Non-negotiable baseline:

```jsonc
// tsconfig.json
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
 "isolatedModules": true,
 "outDir": "./dist",
 "rootDir": "./src"
 },
 "include": ["src/**/*"],
 "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

`strict: true` is hard-required. Disabling `strictNullChecks` to ship faster is a debt that compounds.

## Boundary validation with zod

Every external input is validated at the boundary; types are *derived* from the schema:

```typescript
// orders/presentation/order.request.ts
import { z } from 'zod';

export const OrderRequestSchema = z.object({
 customerId: z.string.min(1).max(100),
 amount: z.number.positive,
 items: z.array(z.object({
 sku: z.string,
 quantity: z.number.int.positive,
 })).nonempty,
});

export type OrderRequest = z.infer<typeof OrderRequestSchema>;
```

The request type is *derived* from the schema — never declared separately. Single source of truth.

## Dependency injection

Pattern depends on framework:

- **NestJS** — built-in DI via decorators and modules. Use it.
- **Fastify / Express** — hand-wire a composition root in `src/app.ts` or use a lightweight DI container (`tsyringe`, `awilix`). Avoid building a custom container.

## Application service (framework-neutral)

```typescript
// billing/application/place-order.use-case.ts
import type { OrderRepository } from '../domain/order-repository.js';
import type { PaymentGateway } from './ports/payment-gateway.js';
import type { EventBus } from '../../shared/events/event-bus.js';
import { Order } from '../domain/order.js';
import type { PlaceOrderCommand } from './place-order.command.js';

export class PlaceOrderUseCase {
 constructor(
 private readonly orders: OrderRepository,
 private readonly payments: PaymentGateway,
 private readonly events: EventBus,
) {}

 async execute(cmd: PlaceOrderCommand): Promise<OrderId> {
 const order = Order.place(cmd);
 await this.orders.save(order);
 await this.payments.charge(order.id, cmd.amount);
 await this.events.publish(new OrderPlaced(order.id));
 return order.id;
 }
}
```

`readonly` on injected dependencies. `async` is the default for I/O-bound work.

## Persistence

**Prisma** (preferred) or **Drizzle** for type-safe SQL. TypeORM only if the team has prior expertise and the project's complexity justifies it.

Prisma example:

```prisma
// schema.prisma
model Order {
 id String @id @default(uuid)
 customerId String
 amount Decimal @db.Decimal(10, 2)
 status String
 createdAt DateTime @default(now)

 @@map("orders")
 @@index([customerId])
}
```

```typescript
// billing/infrastructure/persistence/prisma-order-repository.ts
import { PrismaClient } from '@prisma/client';
import type { Order } from '../../domain/order.js';
import type { OrderRepository } from '../../domain/order-repository.js';

export class PrismaOrderRepository implements OrderRepository {
 constructor(private readonly prisma: PrismaClient) {}

 async save(order: Order): Promise<void> {
 await this.prisma.order.upsert({
 where: { id: order.id.value },
 create: this.toRow(order),
 update: this.toRow(order),
 });
 }

 async find(id: OrderId): Promise<Order | null> {
 const row = await this.prisma.order.findUnique({ where: { id: id.value } });
 return row ? this.toDomain(row) : null;
 }

 private toRow(order: Order) { /* ... */ }
 private toDomain(row: OrderRow): Order { /* ... */ }
}
```

Migrations checked in (`prisma/migrations/`). No `prisma db push` in production.

## Error handling

Typed domain errors with discriminators:

```typescript
export class DomainError extends Error {
 readonly kind: string;
 constructor(kind: string, message: string) {
 super(message);
 this.kind = kind;
 }
}

export class InsufficientFundsError extends DomainError {
 constructor(public readonly customerId: string) {
 super('insufficient-funds', `Customer ${customerId} has insufficient funds`);
 }
}
```

Central error translation in framework-specific filter / middleware (NestJS exception filter; Fastify `setErrorHandler`; Express error-handling middleware). Never throw bare `Error`; never `catch (e: any)` and swallow.

## Logging

`pino` for structured JSON logging:

```typescript
import pino from 'pino';
import { AsyncLocalStorage } from 'node:async_hooks';

const correlationStore = new AsyncLocalStorage<{ correlationId: string }>;

export const logger = pino({
 level: process.env.LOG_LEVEL ?? 'info',
 formatters: {
 log(obj) {
 const store = correlationStore.getStore;
 return { ...obj, correlationId: store?.correlationId };
 },
 },
});
```

`AsyncLocalStorage` for correlation-ID propagation through async chains.

## Async discipline

- Every promise is `await`ed or explicitly `void`. Floating promises are blocker violations.
- `Promise.all` for independent parallel work; `Promise.allSettled` when partial failure is acceptable.
- `AbortController` for cancellation propagation.
- No `setTimeout` for synchronization.

## Testing

**Vitest** (preferred for new projects — fast, ESM-native, TS-native) or **Jest**.

```typescript
// billing/application/place-order.use-case.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { PlaceOrderUseCase } from './place-order.use-case.js';
import { InMemoryOrderRepository } from '../../../test/in-memory-order-repository.js';

describe('PlaceOrderUseCase',  => {
 let orders: InMemoryOrderRepository;
 let useCase: PlaceOrderUseCase;

 beforeEach( => {
 orders = new InMemoryOrderRepository;
 useCase = new PlaceOrderUseCase(orders, stubPaymentGateway, stubEventBus);
 });

 it('persists the order and returns its id when payment succeeds', async  => {
 const id = await useCase.execute(samplePlaceOrderCommand);
 expect(id).toBeDefined;
 expect(await orders.find(id)).not.toBeNull;
 });
});
```

Integration tests with Testcontainers for real Postgres:

```typescript
import { PostgreSqlContainer } from '@testcontainers/postgresql';

const postgres = await new PostgreSqlContainer('postgres:16-alpine').start;
const prisma = new PrismaClient({ datasources: { db: { url: postgres.getConnectionUri } } });
```

## Build and packaging

For backend services, ship compiled JS (no bundler needed in most cases):

```json
// package.json (key fragments)
{
 "type": "module",
 "engines": { "node": ">=20.0.0" },
 "scripts": {
 "build": "tsc",
 "start": "node dist/main.js",
 "dev": "tsx src/main.ts",
 "test": "vitest run",
 "test:watch": "vitest"
 }
}
```

Multi-stage Dockerfile:

```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY tsconfig.json ./
COPY src ./src
RUN npm run build

FROM gcr.io/distroless/nodejs20-debian12:nonroot
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY package.json ./
USER nonroot
CMD ["dist/main.js"]
```

`npm`, `pnpm`, or `yarn` — choose one per project; lockfile checked in.

## Observability hooks 

- `pino-http` for request logging with correlation ID.
- `prom-client` for Prometheus metrics; `/metrics` endpoint.
- OpenTelemetry instrumentation per the `observability` skill; leaves the hooks ready for the collector wiring.

## Sub-variant references

- `references/nestjs.md` — NestJS-specific module/provider/decorator patterns.
- `references/fastify.md` — Fastify plugin architecture, schema-driven validation.
- `references/express.md` — Express patterns, hand-rolled DI, middleware discipline.

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
