# Reference — Express (Node/TypeScript)

Loaded by `stack-node-ts` when Express is the chosen HTTP framework.

## When to use

Express remains a reasonable default when:
- Team has deep Express experience and the perf delta of Fastify doesn't justify the switch.
- You depend on a third-party library that only ships Express middleware.
- Brownfield: the codebase is already Express; matching the existing pattern is cheaper than migration.

For new services without an Express-specific reason, **prefer Fastify** (see `fastify.md`).

## Project layout

```
src/
├── server.ts                wire-up; binds the Express app to a port
├── app.ts                   creates the app; useful for tests
├── middleware/              cross-cutting (auth, logging, error-handler)
│   ├── auth.ts
│   ├── error-handler.ts
│   └── observability.ts
├── routes/                  route modules
│   └── orders/
│       ├── index.ts         Router export
│       ├── schema.ts        validation (zod / valibot / joi)
│       └── handler.ts       business handlers
├── services/                domain services (no Express dependency)
├── repositories/            persistence
└── lib/                     cross-cutting utilities
```

## Validation (Express has none built in)

Express delegates validation entirely. Use **zod** as the default; it gives you both runtime validation AND TypeScript types from one schema:

```ts
// routes/orders/schema.ts
import { z } from 'zod';

export const createOrderSchema = z.object({
  customerId: z.string().uuid(),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
  })).min(1),
});

export type CreateOrderBody = z.infer<typeof createOrderSchema>;
```

Validate at the route boundary:

```ts
// routes/orders/index.ts
import { Router } from 'express';
import { createOrderSchema } from './schema';
import { createOrder } from './handler';

const router = Router();

router.post('/', async (req, res, next) => {
  const parsed = createOrderSchema.safeParse(req.body);
  if (!parsed.success) {
    return res.status(400).json({
      error: 'validation_error',
      details: parsed.error.format(),
    });
  }
  try {
    const result = await createOrder(parsed.data);
    res.status(201).json(result);
  } catch (err) {
    next(err);
  }
});

export default router;
```

## Async error handling (the Express trap)

Express 4 doesn't catch errors from async handlers. Two options:

**Option 1 — `express-async-errors`** (simple):
```ts
import 'express-async-errors';   // patches Express; must import once at startup
```

After import, thrown errors in async handlers reach your error middleware.

**Option 2 — manual try/catch or asyncHandler wrapper**:
```ts
const asyncHandler = (fn: any) => (req: Request, res: Response, next: NextFunction) =>
  Promise.resolve(fn(req, res, next)).catch(next);

router.get('/', asyncHandler(async (req, res) => {
  // can throw; will be caught
}));
```

**Express 5** (when stable) handles async correctly natively. As of 2026 Express 5 is still rc; use Express 4 + `express-async-errors`.

## Error handler

Single error middleware (must have 4 args; that's how Express identifies error handlers):

```ts
// middleware/error-handler.ts
import type { ErrorRequestHandler } from 'express';

export const errorHandler: ErrorRequestHandler = (err, req, res, _next) => {
  req.log?.error?.({ err, requestId: req.id }, 'request failed');
  const status = err.statusCode ?? 500;
  if (status >= 500) {
    return res.status(500).json({ error: 'internal_error' });
  }
  res.status(status).json({
    error: err.code ?? 'client_error',
    message: err.message,
  });
};
```

Register LAST in the middleware chain.

## Observability

Express has no built-in logger. Wire `pino-http`:

```ts
import pinoHttp from 'pino-http';
import crypto from 'node:crypto';

app.use(pinoHttp({
  genReqId: (req) => req.headers['x-request-id'] as string ?? crypto.randomUUID(),
  customLogLevel: (req, res, err) => {
    if (err || res.statusCode >= 500) return 'error';
    if (res.statusCode >= 400) return 'warn';
    return 'info';
  },
  serializers: {
    req: (req) => ({ method: req.method, url: req.url, requestId: req.id }),
  },
}));
```

OpenTelemetry auto-instruments via `@opentelemetry/instrumentation-express` — per `observability` SKILL.

## Testing

Use `supertest` against the Express app (no port binding required):

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { buildApp } from './app';

test('POST /orders returns 201 with valid body', async () => {
  const app = await buildApp({ logger: false });
  const res = await request(app)
    .post('/orders')
    .set('authorization', 'Bearer test-token')
    .send({ customerId: '...', items: [{ sku: 'X', quantity: 1 }] });
  assert.equal(res.status, 201);
});
```

For integration tests, Testcontainers per `testing-strategy`.

## Common Express middleware (default stack)

```ts
import express from 'express';
import helmet from 'helmet';
import cors from 'cors';
import compression from 'compression';
import pinoHttp from 'pino-http';

const app = express();
app.use(helmet());                                // security headers
app.use(cors({ origin: ALLOWED_ORIGINS, credentials: true }));
app.use(compression());                           // gzip responses
app.use(express.json({ limit: '1mb' }));          // body parsing with limit
app.use(pinoHttp({ /* ... */ }));                 // structured logging
```

Order matters: helmet first (sets headers); body parsing before routes; error handler last.

## Gotchas

- **`res.send()` followed by more middleware logic** — once sent, the response is closed. Use `if (res.headersSent) return` guards or restructure.
- **`req.body` is `{}` when no body parser is registered** — easy to miss in tests; results in confusing validation errors.
- **CORS preflight** — `app.options('*', cors())` if you need explicit preflight handling.
- **`Router.use` order** — middleware on a router applies to all routes registered after; order errors silently produce bugs.

## Performance baseline

Express handles ~15-25K rps for typical JSON workloads on commodity hardware. Latency adds ~1-3ms per request from framework overhead. If those numbers are a problem, look at Fastify.

## Official sources

- Express docs: https://expressjs.com
- zod: https://zod.dev
- pino + pino-http: https://getpino.io
- helmet: https://helmetjs.github.io
- supertest: https://github.com/ladjs/supertest

## Common rationalizations

| Thought | Counter |
|---|---|
| "Express 5 will be stable soon; just wait." | Express 5 has been "soon" for years. Use Express 4 + `express-async-errors` for now. |
| "I'll skip helmet; it's overhead." | Helmet sets a dozen security headers in ~10μs. Always on. |
| "Validation in the route is duplication." | It isn't; the schema is the contract. Skipping it = trusting the network. |
| "We can roll our own logging middleware." | You can; you'll re-derive what `pino-http` already gives you. Don't. |
