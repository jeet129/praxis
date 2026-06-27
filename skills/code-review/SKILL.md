---
name: code-review
description: Structured pull-request review against engineering-standards, the active stack pack, security, NFR impact, and test sufficiency. Produces a severity-tagged review report (blocker / major / minor / nit) with diff-anchored locations and concrete fix suggestions. Used by the Code Reviewer agent and as a pre-merge gate. Distinct from Security Reviewer (different remit, different tool scope). Use on every PR; pushy trigger because skipping reviews is the single most common cause of accumulated tech debt.
---

# Code Review


<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
 - engineering-standards
 - secure-coding
 - testing-strategy
triggers:
 - "reviewing a pull request"
 - "verifying code against the engineering standards"
 - "checking test sufficiency for a PR"
 - "evaluating NFR impact of a change"
 - "gating a merge"
outputs:
 - severity-tagged review report (blocker/major/minor/nit)
 - diff-anchored findings with concrete fixes
 - pass/fail verdict (used as merge gate)
 - standards & NFR-impact checklist completion
consumers:
 - code-reviewer (agent that runs this skill; introduces this agent in Chunk C)
 - security-reviewer (also uses for security-aspect of reviews; distinct remit)
 - delivery-lead (reads the verdict at slice close)
 - backend-developer (consumes findings, responds with fixes)
 - frontend-developer (consumes findings, responds with fixes)
references:
 - java-spring.md
 - node-ts.md
 - python.md
 - web-frontend.md
```
<!-- praxis:metadata:end -->

Pre-merge quality gate. Not a generic "this looks fine" exercise — a structured pass against a defined set of dimensions, producing severity-tagged findings that the author addresses before the gate clears.

The Code Reviewer agent uses this skill on every PR. The Security Reviewer agent runs the security-specific dimensions on PRs that touch sensitive surface area (handled here as a sub-pass that consults `secure-coding`). QA Engineer signs off on acceptance after Code Reviewer signs off on quality.

## When this skill fires

- A PR is opened — the Code Reviewer agent picks it up.
- A PR is updated (developer pushes fixes) — re-review focused on the new commits.
- A PR claims to be ready-to-merge — the merge gate runs this skill as the verdict.

## The review dimensions

Run each dimension in order. Each produces findings (or "none — checked" notes).

### Dimension 1: Engineering-standards conformance

Read `engineering-standards/SKILL.md` and the active stack-pack reference. Walk the diff against the standards:

- KISS — is the change simpler than the alternatives? Or has cleverness been added without an NFR demanding it?
- DRY — does the change duplicate knowledge that already lives elsewhere?
- SOLID — is the change respecting single-responsibility and dependency inversion? New classes with five responsibilities are violations.
- YAGNI — has the change added flexibility or abstractions for hypothetical future needs?
- Naming — do the names express intent in the domain language? Booleans read as predicates? Functions verb-first?
- Boundaries — does the change put code in the right bounded context / layer? Does the dependency direction flow inward?
- Error handling — domain-typed exceptions? Catch narrow? No swallowing?
- Logging — structured, with correlation ID, no PII?

### Dimension 2: Stack-specific idioms

Read the active stack pack (`stack-java-spring`, `stack-node-ts`, `stack-python`). Walk the diff:

- Does the code use the stack's idiomatic patterns (constructor injection vs field injection; pydantic at boundaries; zod schemas as source of truth; etc.)?
- Are stack-specific anti-patterns present (the "common violations to flag in review" sections of the stack pack)?

### Dimension 3: Security (via secure-coding)

Run `secure-coding` as a sub-skill against the diff. Flag any:

- Injection sinks (SQL, command, template, header).
- Missing input validation at boundaries.
- Authorization checks missing on protected paths.
- Hardcoded secrets / credentials.
- PII handling violations (logging, persistence without encryption-when-required).
- Crypto misuse (weak algorithms, MD5 for passwords, `Math.random` for tokens).
- SSRF / XXE / deserialization risks.

Security findings inherit `secure-coding`'s severity scheme. **Any security blocker fails the gate immediately.**

### Dimension 4: NFR impact

For each change in the diff, ask: does this change impact any NFR target from `nfr-definition`?

- **Performance**: did the change introduce N+1 queries, unbounded loops, synchronous calls where async is needed, missing indexes?
- **Availability**: did the change introduce a new failure mode without resilience (timeout, retry, circuit-breaker)?
- **Scalability**: does the change scale with load, or does it have hidden O(n²) behavior?
- **Cost**: does the change introduce expensive operations (new managed service, large egress, large storage growth)?
- **Observability**: are new endpoints/operations instrumented (logs, metrics, traces)?

Flag any NFR-impacting changes; ensure they have explicit acknowledgment in the PR description.

### Dimension 5: Test sufficiency (via testing-strategy)

Run `testing-strategy` as a sub-skill. Verify:

- New code paths have tests at the right layer (unit for logic; integration for boundaries).
- Tests assert behavior, not implementation (no over-mocking).
- Test names describe behavior.
- No skipped or commented-out tests.
- Coverage gates met (project-defined thresholds).
- For brownfield: characterization tests cover existing behavior before changes were made.

### Dimension 6: API + data contracts (if applicable)

If the PR touches APIs or schemas:

- API changes: backward-compatible additions only, or explicit version bump per `api-design`. Breaking changes without a version bump are blockers.
- Schema changes: expand-contract pattern followed (`data-modeling`). Destructive migrations are blockers unless explicit ADR + rollback plan.
- Spec file is updated (OpenAPI / Proto / schema) BEFORE or WITH the code change, not after.

### Dimension 7: Documentation and naming

- README / inline comments are updated if the change affects public-facing API or developer onboarding.
- ADRs are added for non-trivial choices (verified against `adr-decision-records`).
- The PR description states *what* and *why*. "Refactor" without context is a yellow flag; "Refactor to enable X" is fine.

## Severity tagging

| Severity | Definition | Gate behavior |
|---|---|---|
| **blocker** | Must be fixed before merge. Security blockers, broken tests, missing tests on new logic, breaking API changes without version bump, secrets in code, standards violations that significantly affect maintainability. | Gate fails. |
| **major** | Fix in this PR or before next release. NFR-impacting changes without acknowledgment, missing observability on new endpoints, partial test coverage, stack-idiom violations on important code paths. | Gate passes only with reviewer acknowledgment of each major. |
| **minor** | Fix soon; can be a follow-up PR. Naming inconsistencies, opportunities to apply a better pattern, dead code. | Gate passes; tracked in `tech-debt-management` if accumulating. |
| **nit** | Style preference; non-blocking. Whitespace, alphabetical ordering, etc. | Advisory only. |

## The review report format

```markdown
# Code Review — PR #<number>

**Reviewer:** code-reviewer (agent)
**Date:** YYYY-MM-DD
**Verdict:** PASS / PASS_WITH_MAJORS / FAIL

## Summary

<one paragraph: scope of the change, overall quality assessment>

## Findings

### Blockers (must fix before merge)

1. **[Security]** `src/billing/presentation/order_controller.py:42` — SQL injection via string concatenation.
 Suggested fix: use parameterized queries with the SQLAlchemy ORM. See `stack-python` reference.

2. **[Tests]** `src/billing/application/refund_use_case.py` — new logic with no unit tests.
 Suggested fix: add `tests/billing/application/test_refund_use_case.py` covering at least the happy path and the insufficient-funds case.

### Majors (fix in this PR; reviewer-acknowledged if deferred)

1. **[NFR — Performance]** `src/billing/infrastructure/persistence/order_repository.py:78` — N+1 query in `find_orders_with_items`.
 Suggested fix: use `joinedload(Order.line_items)`.

### Minors (track or follow-up)

1. **[Naming]** `src/billing/domain/order.py:15` — `isStat` should be `isActive` (boolean reads as predicate).

### Nits

1. `src/billing/__init__.py` — alphabetize imports.

## Verdict rationale

<one paragraph: why PASS / FAIL given the findings above>

## Checklist completion

- [x] Engineering-standards conformance
- [x] Stack-specific idioms
- [x] Security (secure-coding)
- [x] NFR impact
- [x] Test sufficiency
- [x] API/data contracts (applicable)
- [x] Documentation and naming
```

## Re-review on update

When the author pushes fixes, this skill re-runs but focuses on:

- Are the previously-flagged findings addressed?
- Did the fixes introduce new issues?
- Has the verdict changed?

The re-review report references the prior report and lists what's resolved vs. outstanding.

## Mode handling (G/B)

**Greenfield.** Standard review against the standards.

**Brownfield.** The bar is `engineering-standards` *augmented by* `.repo-intel/conventions.md` for the codebase's actual conventions. Match-existing-conventions on a feature PR; refactor toward the standard in dedicated refactoring slices. This is the brownfield mode of `engineering-standards`.

## Verification

You are done when:

- [ ] All review dimensions exercised (engineering standards / correctness / clarity / tests / security / observability / performance).
- [ ] Each dimension produced findings OR an explicit "none — checked" note.
- [ ] Findings tagged with severity: blocker / non-blocker / nit.
- [ ] Verdict recorded: approve / request-changes / comment-only.
- [ ] If approved: reviewer name + date in PR.
- [ ] Re-review on update applied to the changed portions, not the whole PR.
- [ ] PR description references which `engineering-standards` and stack pack apply.
- [ ] `code-simplification-heuristics.md` reference applied if simplification surfaced.

Evidence to check:
- Findings include line numbers where applicable.
- "None — checked" notes appear for dimensions that legitimately had no findings.
- Re-review history shows that prior comments were addressed.

## What this skill does not do

- Approve security waivers — that's the `security_finding_waiver` gate per governance.yaml; this skill *surfaces* findings and proposes severity.
- Decide architectural direction — that's the SA's call; this skill checks against the chosen architecture.
- Run the tests — CI does that; this skill *verifies* tests exist at the right layer.
- Final acceptance — that's QA Engineer's sign-off after this skill passes the quality gate.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I trust the author; quick LGTM." | Trust is the basis for engagement, not its substitute. Review the dimensions. |
| "Small PR; doesn't need real review." | Small PRs hide bugs in the noise. Size isn't the predictor of risk; surface is. |
| "The tests passed; that's the review." | Tests verify what they're written to verify. The review checks what the tests don't. |
| "I'll skip the simplicity dimension; they're a senior dev." | Senior devs ship over-engineered code too. The dimension exists because the discipline matters. |
| "Comments are noise; just approve." | A review without findings is fine. A review with findings only after merge is the problem. |
| "Review speed > review depth; we're behind." | Slow merge from fast review = high bug rate = slow throughput overall. Same trade-off as testing. |
| "I'll catch issues post-merge." | Issues post-merge become user-visible incidents or silent regressions. The cost is much higher. |

## Anti-patterns

- "LGTM" without engagement. The verdict means nothing without the dimensions checked.
- Severity inflation (everything tagged blocker). Erodes trust in the verdict; major findings get ignored when everything's a blocker.
- Severity deflation (security issues marked nit). Doesn't prevent the issue from shipping; weakens the gate.
- Review fatigue on large PRs. PRs > 500 lines diff are split unless the change genuinely cannot be smaller — large PRs get superficial review.
- Reviewing the author, not the change. The change is being reviewed; collegial framing of findings keeps it that way.
