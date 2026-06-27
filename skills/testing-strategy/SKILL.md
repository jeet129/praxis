---
name: testing-strategy
description: "The test pyramid in practice — what to unit-test vs integration-test vs contract-test vs E2E-test vs load-test, coverage targets per layer, test data strategy, TDD where it fits, mutation testing for critical paths, and the merge-gate's coverage check. The QA Engineer agent owns this skill; every developer consumes it to know what tests their slice requires."
---

# Testing Strategy


<!-- praxis:description:full -->
## Full description

The test pyramid in practice — what to unit-test vs integration-test vs contract-test vs E2E-test vs load-test, coverage targets per layer, test data strategy, TDD where it fits, mutation testing for critical paths, and the merge-gate's coverage check. The QA Engineer agent owns this skill; every developer consumes it to know what tests their slice requires. Use whenever a slice is being planned (decide the test plan), when implementing (write the tests at the right layer), or at code review (verify tests exist at the right layer).

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
 - engineering-standards
 - requirements-elicitation
 - nfr-definition
triggers:
 - "planning a slice's test coverage"
 - "deciding test layer for new functionality (unit vs integration vs E2E)"
 - "setting coverage gates for the merge"
 - "designing test data strategy"
 - "applying TDD or characterization tests"
 - "reviewing a PR for test sufficiency"
outputs:
 - per-slice test plan (which tests at which layer)
 - test scaffolds in the active stack pack
 - coverage gates (numbers used in CI)
 - mutation testing targets for critical paths
 - test verdict (used as merge gate)
consumers:
 - backend-developer (writes tests against this plan)
 - frontend-developer (writes tests against this plan; FE specifics in stack-web-frontend)
 - qa-engineer (orchestrates the test strategy)
 - code-review (uses for test-sufficiency checks)
 - cicd-pipeline (consumes coverage gates)
references:
 - java-junit5.md
 - node-vitest.md
 - python-pytest.md
```
<!-- praxis:metadata:end -->

The discipline of testing the right thing at the right layer with the right rigor. Wrong-layer testing is the most common test smell — exhaustive unit tests that mock the entire collaboration graph, or laden E2E suites that test logic the unit layer could test cheaply.

This skill produces the *test plan* per slice: which tests exist at which layer, the coverage targets, the test-data strategy, and the merge-gate behavior. The Backend Developer writes tests against this plan; QA Engineer verifies the plan is honored before approving the slice.

## When this skill fires

- A slice is being planned — the QA Engineer (or Backend Developer in solo) writes the test plan as part of the implementation packet's test-plan section.
- A slice is being implemented — the developer writes tests at the right layers.
- A PR is being reviewed — the Code Reviewer verifies tests exist at the right layers per the plan; the merge gate checks coverage.
- A slice is being closed — the QA Engineer signs off on acceptance.

## The test pyramid

Pick the right layer for each test. Most tests live at the bottom (fast, focused); fewer at the top (slow, broad).

```
 /\
 / \ E2E (very few; whole-system happy-paths)
 /----\
 / \ Contract (per integration point)
 /--------\
 / \ Integration (services + real deps)
 /------------\
 / \ Unit (most tests; pure logic)
 /----------------\
```

### Unit tests — most numerous

- **What:** Pure logic — domain entities, value objects, application services with mocked ports, utility functions.
- **Why:** Fast feedback (milliseconds); catches logic bugs at the layer where they live.
- **Coverage target:** 80–90% line / branch on domain and application layers. Coverage on presentation and infrastructure layers is *secondary* — those are tested by integration tests.
- **Tools:** JUnit 5 + AssertJ + Mockito (Java); vitest / jest (Node); pytest (Python).
- **Speed:** Whole unit suite under 10 seconds locally; under 30 seconds in CI. If it's slower, you have integration tests masquerading as unit tests.

### Integration tests — moderate count

- **What:** Application services running against *real* infrastructure dependencies — real Postgres, real Redis, real message broker (via Testcontainers). NOT mocked.
- **Why:** Catches bugs at the boundary between application code and real infrastructure (the ORM-vs-actual-SQL trap, the in-memory-fake-doesn't-quite-match-prod trap).
- **Coverage target:** Every critical user path has at least one integration test. Not every code branch.
- **Tools:** Testcontainers (real Postgres, never H2 as substitute); JUnit 5 / vitest / pytest with the test framework.
- **Speed:** Whole integration suite under 3 minutes locally; under 5 minutes in CI. Parallelize where possible.

### Contract tests — one per integration point

- **What:** Per pair of consumer + provider, a contract test verifies the consumer's expectations match what the provider actually returns. Pact, Spring Cloud Contract, or hand-rolled.
- **Why:** Microservices and external integrations break each other silently when the contract is not validated. Contract tests catch this at PR time, not in prod.
- **Coverage target:** Every external integration; every internal service-to-service contract.
- **Tools:** Pact (most languages); Spring Cloud Contract (JVM); hand-rolled via OpenAPI schema validation as a lighter alternative.

### End-to-end (E2E) tests — very few

- **What:** Whole-system happy paths exercised through the public API (HTTP / gRPC / UI). Real deployment, real network.
- **Why:** Final smoke; catches deployment / integration / configuration mistakes.
- **Coverage target:** A small fixed number — the critical user journeys, not every story. **One to three E2E per significant user flow**.
- **Tools:** Playwright (UI), Postman/Newman/k6 (API), supertest (Node API).
- **Speed:** E2E suite under 10 minutes in CI; if it's longer, you have too many E2E.

### Load / performance tests — per NFR

- **What:** Verification that the system meets the NFR targets at expected load.
- **Why:** Performance NFRs are claims; load tests verify them.
- **Coverage target:** Every NFR with a verification method of "load test." Run on a schedule or pre-release, not per PR.
- **Tools:** k6, Gatling, Locust.
- **Wave:** Lands as `performance-testing` skill; this skill ensures the *target numbers* from `nfr-definition` flow into the load test plan.

## TDD where it fits

Test-driven development is *one* discipline, not the *only* one. Apply it where it pays off:

- **TDD for well-specified behavior** — when the acceptance criteria are clear and the design is mostly understood, write the test first. The test acts as the spec.
- **TDD for bug fixes** — write a failing test that reproduces the bug; fix until it passes. Prevents regression.
- **Tests-after for exploration** — when the design is being discovered, write tests after the code stabilizes. Premature tests against unstable code are a tax.

Both modes still produce tests. PRs with no tests are blocker violations regardless of which mode the developer used.

## Mutation testing for critical paths

For code that *must* be correct (payment processing, security-critical paths, billing calculations, ML inference correctness checks), apply mutation testing. Pitest (Java), Stryker (JS/TS), mutmut (Python).

Mutation testing introduces small changes to the code (mutants) and verifies the test suite *catches* them by failing. A test suite that passes despite mutations is incomplete — the mutation score (% of mutants killed) is the metric.

Target: >80% mutation score on critical paths. Optional but high-value.

## Test data strategy

Test data is part of the test design, not an afterthought.

- **Unit tests** — minimal hand-crafted data. Builder patterns or factories for objects.
- **Integration tests** — seed data per test, isolated per test (transactional rollback or schema-per-test). Never share state across tests.
- **E2E tests** — dedicated test data in the test environment; cleaned up between runs.
- **Sensitive data in tests** — use synthetic or anonymized data. Real PII never appears in test fixtures.

## Coverage gates (merge-gate behavior)

The merge gate enforces:

- **Line coverage** — minimum 70% globally, 80% on domain + application layers. Numbers are project-specific (set in `nfr-definition`'s observability section).
- **Branch coverage** — minimum 60% globally. Branch coverage catches "the if was hit but the else wasn't."
- **No tests deleted without justification** — a PR that reduces coverage requires an explicit comment from the author and reviewer acknowledgment.
- **No skipped tests** — `@Disabled` / `it.skip` / `@pytest.mark.skip` requires a comment with the issue and the date.

Coverage is a *necessary but not sufficient* signal. High coverage with shallow assertions is worse than slightly lower coverage with deep assertions. Code review (next skill) verifies that tests actually test behavior.

## Stack-specific references

Concrete tool choices, patterns, and idioms per language:

- `references/java-junit5.md` — JUnit 5, AssertJ, Mockito, Testcontainers patterns.
- `references/node-vitest.md` — vitest, supertest, Testcontainers patterns; describe/it discipline.
- `references/python-pytest.md` — pytest, pytest-asyncio, Testcontainers, fixtures.

## Mode handling (G/B)

**Greenfield.** Test from day one. The walking skeleton has tests; the first feature slice has tests at all the right layers. Don't accumulate test debt early.

**Brownfield.** Read `.repo-intel/test-coverage-gaps.md` for the existing state. **Characterization tests come first** — when modifying untested legacy code, write tests that *characterize the current behavior* before changing it. Then change with confidence. Coverage targets apply incrementally: new code meets the target; existing code is improved opportunistically via `tech-debt-management`.

## What this skill does not do

- Run the tests in CI — that's `cicd-pipeline`; this skill defines what should be run.
- Performance load testing — that's `performance-testing`.
- Chaos testing — that's `chaos-engineering`.
- LLM/agent system evaluation — that's `evaluation-engineering`.
- Manual exploratory testing — that's the QA Engineer's craft, lightly guided here.

## Verification

You are done when:

- [ ] Test pyramid established: unit (most) / integration / contract / E2E (few).
- [ ] Unit tests verify behavior, not implementation.
- [ ] Integration tests use real dependencies via Testcontainers (no in-memory substitutes for production stores).
- [ ] Contract tests per consumer integration.
- [ ] E2E suite covers critical user journeys only.
- [ ] Test coverage measured + reported; assertions reviewed for quality.
- [ ] Mutation testing (where supported) verifies test quality.
- [ ] CI gates on test failures; flakes quarantined.
- [ ] Test data strategy: fixtures, factories, synthetic.

Evidence to check:
- A bug-fix PR includes a failing test that the fix makes pass.
- Coverage trend stable or improving; mutation score acceptable.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll add tests later." | "Later" doesn't happen at meaningful rates. Either now or never; choose now. |
| "The code is obviously correct." | Obvious-to-write ≠ obvious-to-read-six-months-from-now. The test is the executable spec. |
| "Coverage is at 95%." | Coverage is necessary, not sufficient. Read the assertions. High-coverage / low-assertion is theater. |
| "Tests would just duplicate the code." | A test that mirrors the implementation tests nothing. Re-design the test to verify behavior, not structure. |
| "E2E tests are real tests." | Some are; mostly they're slow and flaky. Use them for broad smoke, not for behavior. The pyramid exists for reasons. |
| "Unit tests are enough." | They're necessary but they don't catch integration boundaries, contract drift, or real-data shape mismatches. |
| "Adding tests after the bug fix is just paying tax." | Failing test → fix → green test is the protection that prevents regression. Skip it and the bug returns. |

## Anti-patterns

- Unit tests that mock everything and assert calls — they verify the implementation, not the behavior.
- Integration tests using in-memory database substitutes (H2 for Postgres, sqlite for production stores). Use Testcontainers.
- E2E test counts in the dozens or hundreds. E2E is broad-smoke; the bulk of behavior testing is lower.
- "Coverage is at 95% — we're good." Coverage is necessary, not sufficient. Read the assertions.
- Skipped or commented-out tests. Either run them or delete them.
- Test code held to a lower bar than production code. Tests need to be readable, maintained, and reviewed too.
