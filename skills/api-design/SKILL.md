---
name: api-design
description: "Contract-first API design. Produces the API specification (OpenAPI 3.1 for REST, .proto for gRPC, AsyncAPI for events) BEFORE implementation begins, with explicit versioning, pagination, idempotency, error model, and deprecation policy. The Solution Architect runs this for any slice that introduces or changes an API surface; the Backend Developer consumes the spec as part of the implementation packet. Use whenever a new endpoint, RPC, event topic, or webhook is being introduced. Pushy trigger because skipping contract-first design produces APIs that have to be redesigned a quarter later."
---

# API Design

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: backend
state: active
dependencies:
  - engineering-standards
  - requirements-elicitation
  - nfr-definition
triggers:
  - "introducing a new API endpoint, RPC, or event topic"
  - "extending an existing API contract"
  - "versioning or deprecating an existing API"
  - "defining a webhook contract"
  - "designing a public API surface"
outputs:
  - OpenAPI/Proto/AsyncAPI specification file
  - versioning policy
  - deprecation policy
  - pagination/filtering/sorting conventions
  - idempotency strategy per mutation
  - error model (error codes, shape, examples)
consumers:
  - backend-developer (implements against the spec)
  - frontend-developer (consumes the spec for client code)
  - code-review (checks code against the spec)
  - api-documentation generators
references:
  - rest-openapi.md
  - grpc-proto.md
  - asyncapi-events.md
  - graphql.md
```
<!-- praxis:metadata:end -->

Contract-first. The specification is written *before* implementation begins, reviewed (by the Architecture Challenger and the consuming agent), and locked. The implementation is then a faithful realization of the contract; deviations are caught at code review against the spec.

This is one of the highest-leverage skills in the library — APIs that ship without contract-first design accumulate inconsistencies, get redesigned a quarter later, and break consumers in the meantime.

## When this skill fires

- A slice introduces a new endpoint, RPC, event topic, or webhook.
- An existing contract needs to be extended (new field, new operation).
- A breaking change is being considered (triggers the versioning + deprecation policy).
- A client (frontend, mobile, partner) needs the contract before they can plan their work.

## The procedure

### 1. Choose the contract style

| Style | Use when | Reference |
|---|---|---|
| **REST + OpenAPI 3.1** | Resource-oriented APIs; browser/mobile clients; broad ecosystem support. Default for SaaS web products. | `references/rest-openapi.md` |
| **gRPC + Proto** | Service-to-service; high throughput; strong typing across languages. Less common for public APIs. | `references/grpc-proto.md` |
| **GraphQL** | Client-shaped queries; multiple consumers wanting different views; complex relational reads. Adds operational complexity (caching, N+1). | `references/graphql.md` |
| **AsyncAPI (events)** | Pub/sub or event-driven flows; webhooks; eventual-consistency surfaces. | `references/asyncapi-events.md` |

Mix is fine — REST for public, gRPC for internal, AsyncAPI for events. State the choice and rationale in an ADR if it's the first time.

### 2. Model resources or operations

For REST: resources, not actions. `POST /orders` (create order), not `POST /createOrder`.
For gRPC: services with verb-named RPCs. `OrderService.PlaceOrder(...)`.
For GraphQL: types + queries/mutations/subscriptions.
For events: topic + event-type + schema per event.

Each surface element has:
- **Name** (resource, RPC, type, topic).
- **Purpose** (one sentence).
- **Operations** (CRUD, query, command, event).
- **Authorization model** (who can call it; scopes/roles).
- **Idempotency** (whether the operation is idempotent; if not, the strategy — see below).

### 3. Define the request and response shapes

For each operation:
- **Request** schema with required/optional fields, types, validation constraints (lengths, ranges, formats).
- **Response** schema with successful shape(s) and HTTP/gRPC status codes.
- **Error** shape — uses the standard error model (below).
- **Examples** — at least one happy-path example per operation; one error-path example for the common errors.

### 4. The standard error model

Pick one error envelope and use it everywhere. Recommended:

```json
{
  "error": {
    "code": "ORDER_INSUFFICIENT_FUNDS",     // domain-meaningful, stable
    "message": "Customer balance is insufficient for this order",
    "details": {
      "customerId": "cust-42",
      "required": 50.00,
      "available": 12.30
    },
    "request_id": "req-abc123"               // correlation ID for support
  }
}
```

- `code` is a stable string consumers can program against. Don't change codes without deprecation.
- `message` is human-readable; localized at the client layer if needed.
- `details` is structured; varies per error code.
- `request_id` is always present; links to logs/traces.

Map error codes to HTTP/gRPC status codes consistently. Document every error code in the spec.

### 5. Idempotency strategy per mutation

Every state-changing operation declares its idempotency strategy:

- **Idempotent by design** — `PUT /orders/{id}` with the full state is naturally idempotent.
- **Idempotency key** — `POST /orders` with `Idempotency-Key: <client-uuid>` header; server dedupes within a window (24h typical).
- **Idempotent retry** — server detects and short-circuits replays via natural-key uniqueness (e.g., the order has a `client_order_ref` unique constraint).
- **Not idempotent** — explicitly flagged; consumers must handle this carefully (rare; typically a design smell).

Document the strategy in the spec per operation.

### 6. Pagination, filtering, sorting

Pick one convention per API and use it consistently:

- **Cursor-based pagination** (preferred for large or actively-mutating collections). `?cursor=<opaque>&limit=50` request; response includes `next_cursor` if more.
- **Offset-based pagination** (acceptable for small, static collections). `?page=2&per_page=50`. Document the max page depth.
- **Filtering** — explicit query parameters, never SQL-like grammar in URLs. `?status=paid&customer_id=cust-42`.
- **Sorting** — `?sort=created_at:desc,amount:asc`. Document allowed sort fields per collection.

### 7. Versioning policy

State the policy explicitly in the spec:

- **Path versioning** (`/v1/orders`) vs **header versioning** (`Accept: application/vnd.product.v1+json`). Path is simpler and more debuggable; header is more REST-pure. Default: path.
- **Major version** changes are breaking. New major version = parallel surface; old version stays supported for the deprecation window.
- **Minor changes** are backward-compatible. Adding new optional fields, new endpoints, new enum values clients ignore.
- **Deprecation window** — typical 6 months for internal, 12 months for partner APIs, 18+ months for public APIs. Stated explicitly per API.

### 8. Deprecation policy

When deprecating an endpoint, field, or version:

1. Mark the surface element `deprecated: true` in the spec with the deprecation date and sunset date.
2. Add a `Deprecation` and `Sunset` response header at runtime (RFC 8594).
3. Notify consumers (the deprecation event goes to `.project/operational/changelog.md`).
4. Track consumer usage; sunset only after usage drops below the agreed threshold or the sunset date arrives.

### 9. Backward compatibility rules

The hard rules (violating these is a breaking change):

- Don't remove a field that clients may read.
- Don't change a field's type or semantics.
- Don't tighten validation (e.g., shorten max length).
- Don't remove an enum value.
- Don't change error codes for the same condition.
- Don't change idempotency semantics.

The safe additions:

- Adding new optional fields.
- Adding new endpoints.
- Adding new enum values (clients should handle unknown values gracefully — document this expectation).
- Loosening validation (e.g., expanding max length).

### 10. Document the spec

The spec file itself is the documentation. Inline descriptions per operation, field, error code. Tools (Swagger UI, Redoc, Buf) render the spec as human docs. The spec lives in the repo at a canonical path (`api/openapi.yaml`, `proto/`, `asyncapi.yaml`) and is part of the implementation packet handed to the Backend Developer.

## Outputs

| Output | Location | Audience |
|---|---|---|
| OpenAPI/Proto/AsyncAPI spec | `api/<name>.yaml` (versioned in repo) | BE Dev, FE Dev, partners, generated docs |
| Versioning + deprecation policy | `api/POLICY.md` (one per project) | All API consumers |
| ADR for major decisions | `.project/decision/` via `adr-decision-records` | Future-readers |

## Mode handling (G/B)

**Greenfield.** Design from scratch following the procedure.

**Brownfield.** Read the existing spec (or reverse-engineer it from `.repo-intel/`) as the baseline. The brownfield rule: **extend the existing API consistently**, even if its conventions differ from the house standard. Fixing an inconsistent existing API is a separate refactoring task, not a feature PR. Mark such drift in `.project/working/api-drift.md` for `tech-debt-management` to triage.

## What this skill does not do

- Implement the API — that's the Backend Developer with the spec as input.
- Generate the docs site — that's tooling (Swagger UI, Redoc); the spec is the source of truth.
- Test the API — that's `testing-strategy` (contract tests, integration tests).
- Secure the API — that's `secure-coding` and `authn-authz`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll generate the OpenAPI spec from the code." | Code-first → spec is "what is" not "what should be." Spec-first locks the contract before implementation drifts. |
| "Versioning is YAGNI; we control the consumers." | Hyrum's Law: every observable behavior gets depended on. Even controlled consumers benefit from explicit versioning. |
| "Error responses can be inferred." | They cannot. Document every error response: status, body shape, when it fires. Otherwise consumers code-by-guess. |
| "Pagination at query parameters is fine for everything." | At small scale yes; at large scale cursor pagination is the only stable shape. Decide deliberately. |
| "Resource names are obvious from the domain." | They aren't — pluralization, hyphenation, casing all vary. Pick a convention and document it. |
| "Idempotency is for unsafe verbs only." | Idempotency-Key headers on POST allow safe retries. Without them, network blips become duplicate orders. |

## Verification

You are done when:

- [ ] OpenAPI / GraphQL schema / gRPC proto exists and validates.
- [ ] Every endpoint has: summary, parameters, request body schema, all response codes with body schemas, examples.
- [ ] Versioning strategy documented (URL path / Accept header / Vary-by) with deprecation policy.
- [ ] Error schema is consistent across endpoints (one error shape, well-known codes).
- [ ] Idempotency strategy for unsafe operations documented (Idempotency-Key or natural ID).
- [ ] Pagination strategy documented (cursor or offset; consistent across collection endpoints).
- [ ] Authentication / authorization documented per endpoint (refs `authn-authz`).
- [ ] Rate limits + quota documented per endpoint class.
- [ ] Contract tests exist for at least the critical-path endpoints.

Evidence to check:
- Consumer can generate a typed client from the spec.
- Spec lints clean against Spectral or equivalent.
- Examples in the spec match contract-test fixtures.

## Anti-patterns

- Implementing first, generating the spec second. The spec must precede or the design discipline is lost.
- One-off error shapes per endpoint. Use the standard envelope everywhere.
- Versioning by changing the same path's behavior silently. Either it's a new version or it's backward-compatible.
- "We'll add pagination later when the list gets big." Add it from day one — adding pagination later is a breaking change.
- Skipping idempotency design for mutations. Every mutation needs an answer to "what happens on retry?"
