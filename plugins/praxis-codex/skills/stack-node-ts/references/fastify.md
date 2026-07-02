# Reference — Fastify (Node/TypeScript)

Loaded by `stack-node-ts` when Fastify is the chosen HTTP framework.

## When to use

Fastify is the recommended default for new Node/TS backend services when:
- High throughput matters (Fastify is ~2x faster than Express for typical workloads).
- You want first-class TypeScript + schema-driven validation/serialization.
- You're comfortable with a slightly smaller plugin ecosystem than Express.

Skip Fastify when:
- The team has deep Express muscle memory and the perf delta doesn't justify the switch.
- A specific dependency requires Express middleware that has no Fastify equivalent.

## Project layout

```
src/
├── server.ts                 wire-up; instantiates the Fastify instance
├── plugins/                  reusable plugins (auth, logger, error-handler, etc.)
│   ├── auth.ts
│   ├── error-handler.ts
│   └── observability.ts
├── routes/                   route registrations
│   ├── orders/
│   │   ├── index.ts          registers /orders/* routes
│   │   ├── schema.ts         JSON Schema for request/response
│   │   └── handler.ts        business handlers
│   └── users/
├── services/                 domain services (no Fastify dependency)
├── repositories/             persistence
└── lib/                      cross-cutting utilities
```

Routes register with explicit JSON Schemas — schemas are the contract.

## Schema-first request handling

Fastify's biggest leverage: JSON Schema does validation, serialization, and (with `@fastify/swagger`) OpenAPI generation. One spec drives three behaviors.

```ts
// routes/orders/schema.ts
export const createOrderSchema = {
  body: {
    type: 'object',
    required: ['customerId', 'items'],
    properties: {
      customerId: { type: 'string', format: 'uuid' },
      items: {
        type: 'array',
        minItems: 1,
        items: {
          type: 'object',
          required: ['sku', 'quantity'],
          properties: {
            sku: { type: 'string' },
            quantity: { type: 'integer', minimum: 1 },
          },
        },
      },
    },
  },
  response: {
    201: {
      type: 'object',
      required: ['orderId'],
      properties: {
        orderId: { type: 'string', format: 'uuid' },
        status: { type: 'string', enum: ['pending', 'confirmed'] },
      },
    },
    400: { $ref: 'ErrorResponse#' },
  },
} as const;
```

Then in the handler:

```ts
// routes/orders/handler.ts
import type { FastifyPluginAsync } from 'fastify';
import { createOrderSchema } from './schema';

const ordersRoutes: FastifyPluginAsync = async (app) => {
  app.post('/orders', { schema: createOrderSchema }, async (req, reply) => {
    const order = await app.orderService.create(req.body);  // req.body is typed
    reply.code(201).send(order);                            // response is validated
  });
};

export default ordersRoutes;
```

Use `@sinclair/typebox` if you want compile-time TypeScript types derived from the schema.

## Plugins (the right pattern for cross-cutting)

Fastify plugins are the right abstraction for things like auth, logging, observability:

```ts
// plugins/auth.ts
import fp from 'fastify-plugin';
import type { FastifyPluginAsync } from 'fastify';

const authPlugin: FastifyPluginAsync = async (app) => {
  app.decorateRequest('userId', '');
  app.addHook('onRequest', async (req, reply) => {
    const token = req.headers.authorization?.replace('Bearer ', '');
    if (!token) return reply.code(401).send({ error: 'unauthorized' });
    req.userId = await app.tokenService.verify(token);
  });
};

export default fp(authPlugin);   // fp wraps so plugin's decorators escape its scope
```

Always wrap plugins with `fastify-plugin` (`fp`) unless you specifically want plugin scoping.

## Error handling

Use `setErrorHandler` once, in a plugin:

```ts
// plugins/error-handler.ts
import fp from 'fastify-plugin';

export default fp(async (app) => {
  app.setErrorHandler((error, req, reply) => {
    req.log.error({ err: error, requestId: req.id }, 'request failed');
    if (error.validation) {
      return reply.code(400).send({
        error: 'validation_error',
        details: error.validation,
      });
    }
    if (error.statusCode && error.statusCode < 500) {
      return reply.code(error.statusCode).send({
        error: error.code ?? 'client_error',
        message: error.message,
      });
    }
    // Don't leak 5xx details
    return reply.code(500).send({ error: 'internal_error' });
  });
});
```

## Observability (per `observability` SKILL)

Fastify ships with `pino` as the default logger — structured JSON logs out of the box. Wire OpenTelemetry via `@opentelemetry/instrumentation-fastify`:

```ts
// src/server.ts
import Fastify from 'fastify';

const app = Fastify({
  logger: {
    level: process.env.LOG_LEVEL ?? 'info',
    serializers: {
      req: (req) => ({ method: req.method, url: req.url, requestId: req.id }),
    },
  },
  requestIdHeader: 'x-request-id',
  requestIdLogLabel: 'requestId',
  genReqId: () => crypto.randomUUID(),
});
```

OpenTelemetry auto-instruments routes; you get request → DB → external-call traces with correlation IDs flowing.

## Testing

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { build } from './server';   // factory function

test('POST /orders returns 201 with valid body', async () => {
  const app = await build({ logger: false });
  try {
    const res = await app.inject({
      method: 'POST',
      url: '/orders',
      headers: { authorization: 'Bearer test-token' },
      payload: { customerId: '...', items: [{ sku: 'X', quantity: 1 }] },
    });
    assert.equal(res.statusCode, 201);
    assert.match(res.json().orderId, /^[0-9a-f-]{36}$/);
  } finally {
    await app.close();
  }
});
```

`app.inject` simulates HTTP without binding a port — fast, deterministic, no network.

For integration tests, use Testcontainers (per `testing-strategy`) to spin up real Postgres / Redis / etc.

## Gotchas

- **Async hooks must return a promise** — don't `next()`-style callback unless on the rare sync path.
- **`reply.send()` happens once** — calling twice throws; structure handlers to send-or-return.
- **JSON Schema's `additionalProperties` defaults to `false` in Fastify** — extra fields fail validation. If you want lenient parsing, set explicitly.
- **`decorateRequest` with an object literal shares the reference across requests** — pass a primitive or use the function form.

## Performance baseline

| Workload | Express | Fastify | Speedup |
|---|---|---|---|
| Simple JSON response | ~22K rps | ~45K rps | ~2x |
| JSON + validation | ~14K rps | ~38K rps | ~2.7x |
| JSON + DB roundtrip | DB-bound (Fastify gives ~10% edge from less overhead) |

Per `nfr-definition`, choose Fastify when the latency budget or QPS target is meaningfully constrained.

## Official sources

- Fastify documentation: https://fastify.dev
- Pino (default logger): https://getpino.io
- `@fastify/swagger` (OpenAPI from schemas): https://github.com/fastify/fastify-swagger
- TypeBox (TS-compatible JSON Schema): https://github.com/sinclairzx81/typebox

## Common rationalizations (per `stack-node-ts` SKILL)

| Thought | Counter |
|---|---|
| "Express is fine; don't switch." | Express is fine for small services or where team familiarity dominates. For new services where perf or schema discipline matter, Fastify pays off. |
| "I'll skip schemas; types are enough." | Schemas validate runtime values; types vanish at compile. You need both for production. |
| "Plugins are too magical." | They're the right encapsulation for cross-cutting concerns. Compose; don't sprawl middleware. |

## When to leave Fastify

If you outgrow Fastify, the next stop is usually:
- **NestJS** — for highly-structured monoliths with heavy DI needs (`stack-node-ts/references/nestjs.md`)
- **Service-mesh + smaller services** — for true microservices

You rarely outgrow Fastify for performance reasons; the more common driver is team structure.
