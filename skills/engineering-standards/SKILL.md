---
name: engineering-standards
description: The house engineering standards bar. Use whenever code is being written, reviewed, or refactored to ensure conformance to KISS / DRY / SOLID / YAGNI principles, package/module boundaries, naming conventions, error-handling discipline, logging hygiene, and dependency direction. Every implementation skill, code-review pass, and developer agent reads this — it is the single source of truth for the engineering bar. Pushy trigger because skills tend to under-trigger on standards.
capability: foundation
domain: cross-cutting
state: active
dependencies: []
triggers:
  - "writing new code"
  - "refactoring existing code"
  - "reviewing a pull request"
  - "applying KISS / DRY / SOLID / YAGNI"
  - "checking style or conventions"
  - "deciding package or module boundaries"
  - "handling errors or logging"
outputs:
  - standards-reference
  - violation-findings (when run as review)
consumers:
  - backend-developer
  - frontend-developer
  - data-engineer
  - ml-ai-engineer
  - code-review
  - architecture-pattern-selection
  - all stack-* skills
references:
  - java-spring.md
  - node-ts.md
  - python.md
---

# Engineering Standards

The single source of truth for the engineering bar. Every implementation skill, every reviewer, every stack pack defers to this skill rather than restating its rules. If the standards change, you edit one file and the whole team moves with it.

## When this skill fires

- A developer agent is about to write code → reads this skill for the bar, then reads the stack-specific reference for idioms.
- A reviewer (`code-review`, Security Reviewer agent) is evaluating a PR → uses this skill plus the stack reference as the bar against which findings are tagged.
- The Solution Architect is making package or module boundary decisions → uses the "Boundaries and dependency direction" section.
- An ADR is being written that affects standards → the ADR explicitly notes which standard it overrides or extends.

## The principles

These five drive every concrete rule below. When in doubt, return to them.

**KISS — Keep It Simple, Stupid.** Choose the simplest design that meets the NFRs. Cleverness has a maintenance cost; pay it only when the NFR demands it. The simplest version that passes the test pyramid and the NFR register wins.

**DRY — Don't Repeat Yourself.** Knowledge should have a single, unambiguous, authoritative representation within the system. Note: DRY is about *knowledge*, not about superficial code duplication. Two functions that happen to look alike but encode different domain concepts are *not* DRY violations. Duplicated knowledge of a business rule across modules *is*.

**SOLID — five principles, applied with judgment.** Single-responsibility (each module has one reason to change), Open/closed (open for extension, closed for modification — within reason), Liskov substitution (subtypes honor their supertype contract), Interface segregation (no client forced to depend on methods it doesn't use), Dependency inversion (depend on abstractions, not concretions, where the abstraction is meaningful — not for the sake of an interface per class).

**YAGNI — You Aren't Gonna Need It.** Don't build flexibility for hypothetical future needs. Build for the concrete needs in front of you; extend when the real need arrives. Premature abstraction is more costly than late abstraction.

**Explicit over implicit.** Magic constants, hidden coupling, mutation of shared state, and "clever" patterns that require reader inference are violations even when they pass tests. Code is read more than written; optimize for the reader.

## Concrete rules

### Naming

- Names express intent in the domain language. `ProcessOrder` beats `DoStuff`; `tenant_id` beats `tid`.
- Booleans read like predicates: `isActive`, `hasPermission`, `canRetry`. Avoid double-negatives.
- Function names contain a verb; type names contain a noun.
- Avoid abbreviations except for universally understood ones (`id`, `url`, `http`). When in doubt, spell it out.

### Boundaries and dependency direction

- Modules and packages reflect *bounded contexts* from `domain-discovery`, not technical layers. `billing/` beats `controllers/` + `services/` + `repositories/`.
- Dependencies flow inward toward the domain. Application services depend on domain; infrastructure depends on application; presentation depends on application. Domain depends on nothing outside itself. Inverted dependencies (domain depends on infrastructure) are violations.
- No circular dependencies between modules. The skill-registry validation catches these at build time for skills; the same rule applies to code modules.

### Error handling

- **Errors are not exceptional** in well-designed code paths. Validation failures, missing-resource conditions, and contract violations are expected; they should produce typed, actionable error returns or domain-typed exceptions, not generic `Exception` / `Error`.
- Catch narrow types; let unexpected exceptions propagate. A blanket `catch (Exception e)` that swallows everything is a violation.
- Never log-and-rethrow at multiple layers. Log at the boundary where the error is handled; rethrow without logging elsewhere.
- Error messages name the operation and the offending value (within PII rules). `"Failed to charge tenant_id=42, amount=$50.00"` beats `"Charge failed"`.

### Logging hygiene

- Use **structured logging** — key-value pairs, not string concatenation. `log.info("order placed", order_id=oid, tenant=tid, amount=amt)`.
- Levels mean what they say: `DEBUG` for development noise; `INFO` for state transitions worth observing in prod; `WARN` for recoverable anomalies that warrant attention; `ERROR` for actual failures. `FATAL` only for unrecoverable startup failures.
- **No PII in logs** unless explicitly cleared by `compliance-privacy`. Emails, phone numbers, payment data, SSNs, and access tokens are redacted at the log boundary.
- Every log line carries the correlation ID propagated by `observability`. Tenant ID where applicable. No exceptions.

### Null, optional, and absence

- In statically-typed stacks (Java, TS, Python with type hints): make optionality explicit. `Optional<T>`, `T | null` in TS, `Optional[T]` in Python. No silent nulls passed as `T`.
- Empty collections beat null collections. A method that returns "no items" returns an empty list, not null.
- `Optional.get()` without `isPresent()` (Java), `!.` (TS), or `Optional.value` (Python without check) is a violation — they discard the whole point.

### State and mutability

- Prefer immutable data structures for domain values. Mutable state is allowed but scoped — typically inside an aggregate boundary, not exposed.
- Shared mutable state across modules is a violation unless protected by an explicit concurrency primitive *documented* alongside it.

### Tests

- Production code without tests is incomplete. The test pyramid lives in `testing-strategy`; this skill enforces only that *something* tests new code paths.
- Test names describe behavior, not implementation. `placesOrder_whenTenantHasCredit_chargesAndConfirms` beats `testPlaceOrder1`.
- No commented-out tests. Either it runs or it's deleted.

### Comments and documentation

- Comments explain *why*, not *what*. The code shows what; the comment supplies context that the code can't.
- Public APIs (anything cross-module) carry doc comments. Private functions do not require them unless the *why* isn't obvious.
- `// TODO` and `// FIXME` carry an owner and a date or ticket reference. Bare `// TODO` is a violation.

### Configuration and secrets

- No secrets in code, ever. No exceptions. `secrets-config` skill owns the secret-store integration.
- Configuration values that vary by environment go through the config layer; the codebase never reads env vars directly outside that layer.
- Defaults are explicit and visible at the config boundary, not scattered inline.

## Mode handling (G/B)

**Greenfield.** Apply these standards verbatim to new code.

**Brownfield.** First read the codebase's actual conventions via `codebase-comprehension`'s `.repo-intel/` output. The brownfield rule: **match the existing convention where it is consistent, and nudge toward the standard where the existing code is inconsistent or absent**. Do not "fix" existing code to match this skill on a feature PR — that's a separate refactoring task and gets its own ADR.

## Stack-specific references

For language-and-framework-specific expression of these principles, read the reference for the active stack:

- Java / Spring Boot: `references/java-spring.md`
- Node / TypeScript: `references/node-ts.md`
- Python: `references/python.md`

Only the relevant reference loads — progressive disclosure keeps the cross-stack content out of context when it doesn't apply.

## Outputs

When invoked as a *bar* (during code generation): no artifact; the standards are the reference, not the deliverable.

When invoked as a *review* (during code review or refactoring assessment): produces a severity-tagged violation report with diff-anchored locations and concrete fix suggestions. Severities: `blocker` (must fix before merge), `major` (fix this PR), `minor` (fix soon, can be a follow-up), `nit` (style preference).

## What this skill is not

- Not a style guide. Style (tabs vs. spaces, brace placement) lives in linter configs per stack pack. This skill is about *engineering discipline*.
- Not a security policy. `secure-coding` and `threat-modeling` own that surface.
- Not a testing strategy. `testing-strategy` owns that.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "These are just principles, not rules." | The principles ARE the rules. Treat them as binding; violations need ADR justification. |
| "KISS / DRY / SOLID / YAGNI conflict with each other." | They do, deliberately. The discipline is choosing which applies; not picking one and ignoring the others. |
| "The codebase already violates these; one more doesn't matter." | Yes it does. Standards drift one PR at a time; halting at "we'll fix later" is how. |
| "These standards are for production code; not for prototypes." | Prototypes ship. The "prototype" you wrote becomes the foundation. Either label it throwaway-and-actually-throw-away, or hold it to the standard. |
| "Naming conventions are bikeshedding." | Naming is the cheapest documentation. Consistent names are the cheapest comprehension aid. Not bikeshedding. |
| "DRY everywhere — extract every duplication." | DRY too early creates wrong abstractions. Rule of three: tolerate two duplications; refactor on the third when the pattern is clear. |

## Verification

You are done when:

- [ ] The code under review follows the project's standards as documented here.
- [ ] Violations (if any) carry an explicit ADR with rationale + scope.
- [ ] Naming, error handling, and logging are reviewed against the section checklist.
- [ ] No dependencies point in the wrong direction (e.g., domain depending on infra).
- [ ] Reference-loaded stack packs are consulted for stack-specific norms (Java/Spring, Node/TS, Python).
- [ ] The reference `git-workflow-checklist.md` was applied for commits and PRs.
- [ ] The reference `code-simplification-heuristics.md` was applied before merge.

Evidence to check:
- PR description references which standards were followed (or which were deliberately violated, with ADR link).
- A reviewer can find the standard the code conforms to without inferring.

## Versioning

Changes to this skill carry an ADR — because every other skill references this one, a change here propagates everywhere. The ADR documents what changed, why, and what migration (if any) existing code requires.
