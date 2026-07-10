# API Design — REST + OpenAPI 3.1

Contract-first REST API design using OpenAPI 3.1. The spec is written and reviewed *before* implementation; code (server stubs, client SDKs, docs) is generated from it, not the other way around.

## Why contract-first

- The spec is the single source of truth consumers and providers both agree to.
- Breaking changes are caught in spec review, not in a consumer's production incident.
- Codegen eliminates hand-written serialization drift between the spec and the implementation.

Spec-last (annotate the code, generate the spec) is acceptable for small internal APIs but is a violation for anything with external or cross-team consumers — the spec becomes documentation of behavior, not a contract negotiated up front.

## OpenAPI 3.1 spec structure

3.1 aligns with JSON Schema 2020-12 (unlike 3.0's custom subset) — `nullable` is gone, use `type: [string, "null"]`; `exclusiveMinimum`/`exclusiveMaximum` are numeric, not boolean.

```yaml
openapi: 3.1.0
info:
  title: Orders API
  version: 2.3.0
  description: |
    Order lifecycle management. Breaking changes bump the major version
    in the URL path (`/v2/...`); additive changes bump `info.version` only.
  contact:
    name: Platform Team
    url: https://internal.example.com/teams/platform
servers:
  - url: https://api.example.com/v2
    description: Production
  - url: https://staging-api.example.com/v2
    description: Staging

paths:
  /orders/{orderId}:
    get:
      operationId: getOrder
      summary: Fetch an order by ID
      tags: [Orders]
      parameters:
        - $ref: '#/components/parameters/OrderId'
      responses:
        '200':
          description: Order found
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Order' }
        '404':
          $ref: '#/components/responses/NotFound'
      security:
        - bearerAuth: [orders:read]

components:
  parameters:
    OrderId:
      name: orderId
      in: path
      required: true
      schema: { type: string, format: uuid }

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

## oneOf / discriminator for polymorphic payloads

Use `discriminator` whenever a schema has variant shapes (event payloads, payment methods) — codegen tools need it to pick the right subtype, and human readers need it to know which fields apply.

```yaml
components:
  schemas:
    PaymentMethod:
      oneOf:
        - $ref: '#/components/schemas/CardPayment'
        - $ref: '#/components/schemas/BankTransferPayment'
      discriminator:
        propertyName: type
        mapping:
          card: '#/components/schemas/CardPayment'
          bank_transfer: '#/components/schemas/BankTransferPayment'

    CardPayment:
      type: object
      required: [type, last4, brand]
      properties:
        type: { type: string, enum: [card] }
        last4: { type: string, pattern: '^\d{4}$' }
        brand: { type: string, enum: [visa, mastercard, amex] }

    BankTransferPayment:
      type: object
      required: [type, iban]
      properties:
        type: { type: string, enum: [bank_transfer] }
        iban: { type: string }
```

Without `discriminator`, `oneOf` validation degrades to try-every-branch, which is slow and produces confusing errors when a payload matches none of the variants.

## Errors: RFC 9457 (`application/problem+json`)

Every error response uses the Problem Details shape — not a bespoke `{ "error": "..." }`. This gives consumers one error-handling code path across every endpoint and every team's API.

```yaml
components:
  schemas:
    Problem:
      type: object
      required: [type, title, status]
      properties:
        type:
          type: string
          format: uri
          description: URI identifying the problem type; "about:blank" if none.
        title: { type: string, description: Short, human-readable summary. }
        status: { type: integer }
        detail: { type: string, description: Instance-specific explanation. }
        instance: { type: string, format: uri }
        # Extension members are allowed — add domain-specific fields.
        errors:
          type: array
          items:
            type: object
            properties:
              field: { type: string }
              message: { type: string }

  responses:
    NotFound:
      description: Resource not found
      content:
        application/problem+json:
          schema: { $ref: '#/components/schemas/Problem' }
          example:
            type: https://api.example.com/errors/not-found
            title: Order not found
            status: 404
            detail: "No order with id 8fbd...  exists."
            instance: /v2/orders/8fbd...
```

Validation errors use the `errors` extension array for per-field detail. Clients should never need to string-match `title`; they branch on `status` and `type`.

## Versioning

- **Additive, backward-compatible changes** (new optional field, new endpoint, new enum value the client should ignore-if-unknown) — bump `info.version` minor/patch, no URL change, no deprecation needed.
- **Breaking changes** (removed field, renamed field, changed type, new required field, tightened validation) — new major version in the URL path (`/v1` → `/v2`). Old version stays live through a published deprecation window (typically 6–12 months), advertised via the `Deprecation` and `Sunset` HTTP headers (RFC 8594) on every response from the old version.
- **Enum extensibility**: document that consumers must treat unknown enum values as a generic fallback, not a parse error — this turns "add an enum value" from a breaking change into an additive one, if designed for from day one.
- Breaking-change classification and the version bump are checked in the `code-review` API/data-contract dimension: spec change ships *with* or *before* the code change, never after.

## Pagination, filtering, partial responses

```yaml
parameters:
  - name: pageSize
    in: query
    schema: { type: integer, minimum: 1, maximum: 100, default: 20 }
  - name: pageToken
    in: query
    schema: { type: string }
    description: Opaque cursor from the previous response's `nextPageToken`.
```

Cursor-based pagination (opaque token) over offset-based (`?page=3`) — offsets break under concurrent writes and don't scale past a few thousand rows.

## Codegen

```bash
# Server stubs + client SDKs from the spec — never hand-write both
npx @openapitools/openapi-generator-cli generate \
  -i openapi.yaml -g typescript-axios -o clients/ts

npx @openapitools/openapi-generator-cli generate \
  -i openapi.yaml -g spring -o server-stubs/

# Type-safe client generation (TS-native, faster, more idiomatic)
npx openapi-typescript openapi.yaml -o src/api-types.ts
```

The generated server stubs are the *routing + validation* layer; business logic is injected, never hand-edited into the generated files (regeneration would silently discard hand edits).

## Linting with Spectral

CI gate — malformed or inconsistent specs fail before merge, not after a consumer generates a broken client.

```yaml
# .spectral.yaml
extends: [[spectral:oas, all]]
rules:
  operation-operationId: error
  operation-description: warn
  no-$ref-siblings: error
  problem-details-on-error:
    description: Error responses must use application/problem+json
    given: "$.paths[*][*].responses[?(@property >= '400')]"
    then:
      field: content
      function: schema
      functionOptions:
        schema:
          required: ['application/problem+json']
```

```bash
npx @stoplight/spectral-cli lint openapi.yaml --fail-severity=warn
```

## Common violations to flag in review

- `nullable: true` (3.0 syntax) in a 3.1 spec — use `type: [string, "null"]`.
- Missing `operationId` — breaks codegen's method naming.
- Error responses shaped as ad hoc JSON instead of `application/problem+json`.
- Breaking change (removed/renamed field, new required field) without a major version bump.
- `oneOf` without `discriminator` on a schema with more than one variant.
- Request/response bodies with no `example` or `examples` — Spectral flags this; reviewers should too, since examples are what consumers actually read.
- Hand-edited generated client/server code (drifts from spec on next regen).
- Enums without a documented "unknown value" client-handling policy.
