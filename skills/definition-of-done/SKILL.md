---
name: definition-of-done
description: "The per-slice Definition of Done contract — the explicit set of gates a slice must clear before it counts as merged and shippable: code review verdict, security verdict (when triggered), visual review verdict (when the slice has UI tasks), tests at the layers the test plan names, acceptance criteria demonstrably met, docs updated, telemetry/observability hooks present, no unresolved blocker findings, and tech-debt entries filed for any accepted shortcuts. Use whenever a slice is nearing completion and needs to be checked against the merge bar, when the Lead Developer assembles the implementation packet's closure criteria, or when a reviewer/QA needs the authoritative checklist for what 'done' means on this slice. Distinct from `testing-strategy` (which defines the test plan) and `code-review` (which produces one of the verdicts this skill checks for) — this skill is the aggregation contract that ties every gate together."
---

# Definition of Done

<!-- praxis:metadata:begin -->
```yaml
capability: delivery
domain: cross-cutting
state: active
dependencies:
  - code-review
  - testing-strategy
  - tech-debt-management
triggers:
  - "assembling the definition-of-done checklist for a slice"
  - "is this slice actually done — what gates must clear before close?"
  - "slice close requested — verify DoD before archiving"
  - "reviewer asks what the done bar is for this PR"
outputs:
  - definition-of-done checklist (per slice)
  - DoD verdict (met | not-met, with blocking gaps listed)
consumers:
  - lead-developer (primary author, assembles per slice)
  - code-review (contributes verdict; reads checklist to know the bar)
  - qa-engineer (verifies AC + test-layer coverage against the checklist)
  - security-reviewer (contributes verdict when security review is triggered)
  - ux-designer (contributes the visual-review verdict on UI-bearing slices)
  - tech-debt-management (receives filed entries for accepted shortcuts)
references: []
```
<!-- praxis:metadata:end -->

The contract that turns "I think this is done" into a checkable fact. Every slice closes against the same set of gates — no slice merges on vibes. The Lead Developer assembles this checklist as part of the implementation packet; reviewers and QA use it as the authoritative bar for that slice.

## When this skill fires

- A slice's implementation is functionally complete and is about to go to code review.
- The Lead Developer is assembling the implementation packet's closure section for a slice.
- A reviewer or QA engineer needs to know exactly what "done" means before approving.
- A shortcut was taken mid-slice and needs to be reconciled against the DoD (either fixed or filed as tech debt).

## The contract

A slice is **Done** only when every applicable gate below is satisfied. Gates that don't apply to the slice (e.g., no security-relevant surface touched) are marked N/A with a one-line reason, not silently skipped.

1. **Code review verdict.** `code-review` has run and returned an `approve` (or `approve with follow-ups`, with follow-ups filed) verdict. No open blocker findings.
2. **Security verdict, when triggered.** If the slice touches auth, data handling, external input, dependencies, or infra — per `security-review`'s trigger criteria — a security verdict exists and is clear of unresolved blockers.
3. **Visual review verdict, when the slice has UI tasks.** The `visual_review` pass (ux-designer, per `frontend-design`) has run against implementation screenshots and returned a verdict clear of blockers. N/A for slices with no user-facing pixels.
4. **Tests at the layers the test plan names.** `testing-strategy` defines which layers apply to this slice (unit / integration / component / E2E / contract / etc.). Each named layer has tests written, passing, and committed. A test plan that names a layer with zero tests is not satisfied by omission.
5. **Acceptance criteria demonstrably met.** Every AC from the slice's user stories (`requirements-elicitation`) has been exercised — by a test, a demo, or an explicit verification note — not just implemented and assumed correct.
6. **Docs updated.** User-facing docs, API docs, README/runbook entries, or ADRs affected by the change are updated in the same slice, not deferred.
7. **Telemetry/observability hooks present.** Per `observability`: structured logs, RED-metric instrumentation, and any manual spans the slice's operations require are in the code, not planned for later.
8. **No unresolved blocker findings.** Across code review, security review, visual review, and QA — every finding tagged blocker is resolved or explicitly waived via ADR. Non-blocker findings may be deferred but must be tracked.
9. **Tech-debt entries filed for accepted shortcuts.** Anything deliberately cut to hit the slice boundary (skipped edge case, deferred refactor, temporary workaround) is filed via `tech-debt-management` with a reason and a suggested follow-up slice — not left undocumented.

## Assembling the checklist

The Lead Developer produces the DoD checklist as part of the implementation packet, instantiating the nine gates above against the specific slice:

```markdown
## Definition of Done — <slice-id>

- [ ] Code review verdict: <approve | approve-with-follow-ups | N/A-reason>
- [ ] Security verdict: <clear | waived-per-ADR-NNNN | N/A: no security-relevant surface>
- [ ] Tests present at: <layers named by testing-strategy>, all passing
- [ ] Acceptance criteria met: <link to AC-by-AC verification>
- [ ] Docs updated: <list of docs touched, or N/A>
- [ ] Observability hooks present: <logs/metrics/traces confirmed>
- [ ] Blocker findings: none open (or waived per ADR-NNNN)
- [ ] Tech-debt filed for: <list of shortcuts, or "none taken">
```

Each checkbox needs evidence, not a checkmark on faith — a link to the review verdict, the test run, the AC trace, the doc diff, the tech-debt entry.

## Who checks what

| Gate | Primary evidence owner | Who verifies |
|---|---|---|
| Code review verdict | code-review | Lead Developer confirms verdict is clear |
| Security verdict | security-reviewer | Lead Developer confirms when triggered |
| Tests at named layers | developer who wrote the slice | QA engineer cross-checks against test plan |
| AC demonstrably met | developer + QA | QA engineer signs off per story |
| Docs updated | developer | Lead Developer spot-checks diff |
| Telemetry hooks present | developer | Lead Developer or SRE spot-checks |
| No unresolved blockers | orchestrator (aggregates) | Lead Developer confirms before merge |
| Tech-debt filed | developer | Lead Developer confirms entries exist |

## Mode handling (G/B)

**Greenfield.** All nine gates apply from the first slice; there's no legacy baseline to reconcile against.

**Brownfield.** The same nine gates apply, plus: any characterization tests required by `requirements-elicitation`'s `changes_existing_behavior` flag must exist before the slice counts as tested. Pre-existing tech debt encountered but not caused by this slice is *not* this slice's responsibility to file — only debt introduced or knowingly deepened by the slice itself.

## What this skill does not do

- Perform the code review — that's `code-review`; this skill checks that a verdict exists.
- Perform the security review — that's `security-review`; this skill checks that a verdict exists when triggered.
- Define the test plan — that's `testing-strategy`; this skill checks coverage against that plan.
- Track tech debt over time — that's `tech-debt-management`; this skill is where shortcuts get filed at the moment they're taken.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Tests pass, ship it — the rest is paperwork." | Docs, telemetry, and tech-debt filing are part of the slice's cost, not optional extras. Skipping them moves the cost downstream, silently. |
| "Security review wasn't triggered, so we're fine." | Confirm the trigger criteria were actually evaluated, not assumed absent. |
| "We'll file the tech-debt ticket after merge." | It doesn't get filed after merge. File it before the checklist closes, or it never happens. |
| "AC coverage is implied by the tests passing." | Tests can pass while missing an AC entirely. Trace each AC explicitly. |
| "This is a small slice; DoD is overkill." | Small slices are exactly where corners get cut invisibly. The checklist costs minutes; the gap costs a production incident. |

## Verification

You are done when:

- [ ] DoD checklist exists for the slice with all eight gates addressed (checked or explicitly N/A with reason).
- [ ] Every checked gate has linked evidence (verdict link, test run, AC trace, doc diff, tech-debt entry).
- [ ] No gate is marked done without evidence.
- [ ] Any N/A gate has a one-line justification, not a blank.
- [ ] Tech-debt entries (if any) are filed in `tech-debt-management`'s register, not just mentioned in the checklist.

Evidence to check:
- A reviewer unfamiliar with the slice can read the DoD checklist and independently confirm the slice is mergeable.
- No blocker finding from any review remains open at the time the checklist is signed off.

## Anti-patterns

- Marking a gate done because it's "probably fine" rather than because there's evidence.
- Treating N/A as a default instead of a justified exception.
- Filing tech-debt entries as an afterthought weeks later, disconnected from the slice that created them.
- Reusing a stale DoD checklist from a prior slice without re-verifying each gate against the current one.
