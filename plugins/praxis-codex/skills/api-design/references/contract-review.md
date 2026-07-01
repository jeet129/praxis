# Reference — Contract Review Checklist

Checklist for reviewing a **contract baseline** (OpenAPI + gRPC/proto + AsyncAPI + shared schemas) as an artifact — not the per-endpoint review that happens at code review, but a pass over the whole generated surface. Used by the `/review contracts` command and by any reviewer (architecture-challenger, code-reviewer Dimension 6, security-reviewer) asked to vet contracts.

Why this exists: contract baselines are often produced in bulk by the Solution Architect (sometimes *after* `architecture_sign_off`), so they can land without an independent review. Schema-valid is not the same as design-sound or safe. This checklist covers semantics, evolvability, and safety.

Classify every finding: **BLOCK** (fix before any slice consumes the surface) / **FIX** (track + fix) / **ACCEPT** (note + rationale). Map each to the ADR / NFR / convention it touches.

## 1. Shared foundations (the `schemas/` source of truth)
- [ ] One event **envelope** defined once; every event references it. Topic/type and partition-key/subject rules stated and consistent.
- [ ] One **error model** defined once; every OpenAPI file `$ref`s it (no per-service bespoke error shapes).
- [ ] **ID scheme** documented (e.g. prefixed ULID) and applied consistently across resources.
- [ ] Shared OpenAPI components (`common.yaml`) exist and are `$ref`'d rather than copy-pasted.
- [ ] Standard headers (actor, idempotency, correlation/trace) defined once and referenced.

## 2. Consistency across the surface
- [ ] Naming is uniform (resource casing, plurality, verb conventions, event `type` namespacing).
- [ ] Pagination / filtering / sorting follow one convention everywhere, not per-file invention.
- [ ] Status codes + error codes used consistently for the same semantics across modules.
- [ ] No two contracts model the same concept with divergent shapes (drift between modules).
- [ ] Every `$ref` resolves; no dangling or duplicated type definitions.

## 3. Evolvability & versioning
- [ ] Versioning strategy stated (URL/header/media-type) and applied.
- [ ] Changes vs the previous baseline are **backward-compatible additions only**, or carry an explicit version bump. Breaking changes without a bump = BLOCK.
- [ ] Schemas follow **expand-contract** (add optional, deprecate, then remove across versions) — no destructive field changes.
- [ ] Deprecation policy present for anything marked deprecated (sunset date / successor).
- [ ] Enums are extensible or versioned (consumers won't break on a new value).

## 4. REST / OpenAPI hygiene
- [ ] Each operation has a unique `operationId` (codegen depends on it).
- [ ] Request/response bodies are typed (no free-form `object` without schema) at every boundary.
- [ ] Required vs optional fields are explicit; nullability intentional.
- [ ] Examples present for non-trivial payloads; they validate against the schema.
- [ ] Auth scheme declared per operation (no endpoint silently public).

## 5. gRPC / proto
- [ ] Field numbers stable; reserved numbers/names for removed fields (no reuse).
- [ ] Package + versioning convention consistent; `buf` lint/breaking clean.
- [ ] Internal-only services not also exposed externally by accident.
- [ ] Errors map to the shared error model (status + details), not ad-hoc strings.

## 6. Events / AsyncAPI
- [ ] Every topic uses the shared envelope; payload (`data`) typed per topic.
- [ ] Topic catalog is canonical (one place), names follow the namespacing convention.
- [ ] Consumers are **idempotent on the envelope id**; ordering/partition-key assumptions stated.
- [ ] Events are metadata-first where privacy requires it (no sensitive payloads on the bus unless justified).
- [ ] Schema evolution policy for events matches §3 (additive; consumers tolerate unknown fields).

## 7. Safety & privacy surfaces (highest priority)
- [ ] **Prohibited-intent generative paths are ABSENT** everywhere they must be (per the project's safety ADR) — e.g. no endpoint returns a generative answer for restricted intents; the human-handoff path is the only route.
- [ ] Authorization is required on every non-public operation; default-deny.
- [ ] **Actor is server-bound** (not client-asserted) where the security model requires it.
- [ ] **Idempotency keys** present on side-effecting / charging / tool-invoking operations.
- [ ] Privacy scope (e.g. private vs shared vs system) is enforceable from the contract — read/write scopes are explicit, not implied.
- [ ] PII minimized at boundaries; redaction points defined where data crosses a trust boundary (e.g. to an external model).
- [ ] Multi-tenant surfaces carry the tenant scope and can't leak across tenants.

## 8. Codegen & drift protection
- [ ] Contracts are the single source of truth; clients are generated, not hand-written.
- [ ] Codegen is (or will be) wired into each tier's build before the first slice consumes the surface.
- [ ] A schema/tool **drift CI gate** exists or is planned (spec change required with code change).
- [ ] An envelope/ID **conformance check** exists at the gateway/boundary.

## Verdict rubric
- **PASS** — no BLOCK findings; FIX items tracked; safety surfaces (§7) clean.
- **PASS WITH CONDITIONS** — no BLOCK on safety (§7); BLOCKs elsewhere scoped to specific surfaces and gating only the slices that consume them.
- **BLOCKED** — any unresolved §7 safety finding, any breaking change without a version bump, or a broken shared foundation (§1).

A run produces a review record at `.project/operational/reviews/contracts-<date>.md` with the top-line status (**OPEN → IN-REMEDIATION → CLOSED**), the findings table (id · severity · surface · ADR/NFR touched · **owner** · disposition · **status**), and the list of slices gated by any open BLOCKs. The record is CLOSED only when every BLOCK has been routed to its owner, fixed, and re-reviewed — or principal-accepted (safety/privacy BLOCKs require explicit principal sign-off, never owner self-accept). This closed loop mirrors the architecture-challenger → Solution-Architect remediation loop in Phase B.
