# Reference — Architecture, persistence, logging, testing & packaging (Node/TypeScript)

Loaded by `stack-node-ts` for the framework-neutral implementation templates that apply regardless of which of NestJS / Fastify / Express was chosen. Framework-specific idioms live in `nestjs.md`, `fastify.md`, `express.md`.

## Project layout

Bounded-context-first, mirrored from `engineering-standards`:

```
src/
├── billing/
│   ├── domain/
│   │   ├── order.ts                   aggregate
│   │   ├── order-id.ts                value object
│   │   ├── order-repository.ts        port (interface)
│   │   └── events/order-placed.ts     domain event
│   ├── application/
│   │   ├── place-order.use-case.ts
│   │   └── ports/payment-gateway.ts   port
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── prisma-order-repository.ts   adapter
│   │   │   └── order.prisma.ts              persistence shape
│   │   └── external/stripe-payment-gateway.ts
│   └── presentation/
│       ├── orders.controller.ts (or routes.ts for Fastify/Express)
│       ├── order.request.ts       DTO + zod schema
│       └── order.response.ts      DTO
├── auth/
│   └── ...
└── shared/                        default empty
```

`controllers/` + `services/` + `repos/` at the top level is a violation.

## TypeScript configuration

`strict: true` is hard-required. Disabling `strictNullChecks` to ship faster is a debt that compounds.

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

## Boundary validation with zod

Every external input is validated at the boundary; types are *derived* from the schema — never declared separately. Single source of truth.

```typescript
// orders/presentation/order.request.ts
import { z } from 'zod';

export const OrderRequestSchema = z.object({
  customerId: z.string().min(1).max(100),
  amount: z.number().positive(),
  items: z.array(z.object({
    sku: z.string(),
    quantity: z.number().int().positive(),
  })).nonempty(),
});

export type OrderRequest = z.infer<typeof OrderRequestSchema>;
```

## Application service (framework-neutral)

`readonly` on injected dependencies. `async` is the default for I/O-bound work.

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

## Persistence

**Prisma** (preferred) or **Drizzle** for type-safe SQL. TypeORM only if the team has prior expertise and the project's complexity justifies it. Migrations checked in (`prisma/migrations/`). No `prisma db push` in production.

```prisma
// schema.prisma
model Order {
  id         String   @id @default(uuid())
  customerId String
  amount     Decimal  @db.Decimal(10, 2)
  status     String
  createdAt  DateTime @default(now())

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

## Error handling

Typed domain errors with discriminators. Central error translation in framework-specific filter / middleware (NestJS exception filter; Fastify `setErrorHandler`; Express error-handling middleware). Never throw bare `Error`; never `catch (e: any)` and swallow.

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

## Logging

`pino` for structured JSON logging. `AsyncLocalStorage` for correlation-ID propagation through async chains.

```typescript
import pino from 'pino';
import { AsyncLocalStorage } from 'node:async_hooks';

const correlationStore = new AsyncLocalStorage<{ correlationId: string }>();

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  formatters: {
    log(obj) {
      const store = correlationStore.getStore();
      return { ...obj, correlationId: store?.correlationId };
    },
  },
});
```

## Testing

**Vitest** (preferred for new projects — fast, ESM-native, TS-native) or **Jest**.

```typescript
// billing/application/place-order.use-case.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { PlaceOrderUseCase } from './place-order.use-case.js';
import { InMemoryOrderRepository } from '../../../test/in-memory-order-repository.js';

describe('PlaceOrderUseCase', () => {
  let orders: InMemoryOrderRepository;
  let useCase: PlaceOrderUseCase;

  beforeEach(() => {
    orders = new InMemoryOrderRepository();
    useCase = new PlaceOrderUseCase(orders, stubPaymentGateway, stubEventBus);
  });

  it('persists the order and returns its id when payment succeeds', async () => {
    const id = await useCase.execute(samplePlaceOrderCommand);
    expect(id).toBeDefined();
    expect(await orders.find(id)).not.toBeNull();
  });
});
```

Integration tests with Testcontainers for real Postgres:

```typescript
import { PostgreSqlContainer } from '@testcontainers/postgresql';

const postgres = await new PostgreSqlContainer('postgres:16-alpine').start();
const prisma = new PrismaClient({ datasources: { db: { url: postgres.getConnectionUri() } } });
```

## Build and packaging

For backend services, ship compiled JS (no bundler needed in most cases). `npm`, `pnpm`, or `yarn` — choose one per project; lockfile checked in.

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
