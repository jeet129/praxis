---
name: feature-flags-progressive-delivery
description: "Feature flag lifecycle and progressive delivery discipline: flag types (release/ops/experiment/permission), creation with a mandatory expiry date, percentage/cohort/ring rollout, kill switches, and scheduled cleanup — every flag is tech debt with a TTL, not a permanent conditional. Use whenever a new flag is being introduced, a rollout percentage is being planned or advanced, a flag is nearing (or past) its expiry, or a kill switch is needed for a risky change. Distinct from `deploy-release` (ships the artifact to an environment; this skill governs who is exposed to it once shipped — deployment is not release) and `chaos-engineering` (injects failure to test resilience; a kill switch here disables a known-bad code path, it doesn't simulate failure)."
---

# Feature Flags & Progressive Delivery

<!-- praxis:metadata:begin -->
```yaml
capability: build-and-deploy
domain: cross-cutting
state: experimental
dependencies:
  - deploy-release
  - observability
  - testing-strategy
triggers:
  - "introducing a new feature flag"
  - "planning or advancing a percentage/cohort/ring rollout"
  - "a flag is nearing or past its expiry date"
  - "designing a kill switch for a risky change"
  - "flag cleanup / flag debt review"
outputs:
  - flag registry entry (name, type, owner, expiry date, rollout plan)
  - rollout plan (stages, gates, abort criteria)
  - flag-state telemetry wiring
  - flag cleanup ticket (post-rollout removal)
consumers:
  - backend-developer (implements flag checks)
  - frontend-developer (implements flag checks in client code)
  - platform-sre (owns kill switches and rollout gates in production)
  - observability (receives flag state as telemetry dimension)
  - tech-debt-management (tracks flags past expiry as debt)
references: []
```
<!-- praxis:metadata:end -->

Feature flags decouple deploy from release: code ships dark, then exposure is turned on deliberately and incrementally. This skill governs the flag's entire life — from creation with an expiry date, through rollout, to deletion — so flags don't calcify into permanent, undocumented branches in the codebase.

## When this skill fires

- A slice needs to ship behind a flag (risky change, incomplete rollout, A/B experiment, entitlement gate).
- A rollout is ready to advance a stage (5% → 25% → 100%) or needs to be paused/aborted.
- A flag is approaching, or has passed, its expiry date.
- A production incident requires disabling a code path immediately (kill switch).
- Flag debt review: auditing the flag registry for stale or orphaned flags.

## Flag types

| Type | Purpose | Lifespan | Cleanup trigger |
|---|---|---|---|
| **Release** | Decouple deploy from release for a specific feature | Days–weeks | Feature at 100% and stable → flag deleted, code de-branched |
| **Ops** | Operational control (circuit breaker, kill switch, load shedding) | Long-lived by design | Re-evaluated at each major redesign, not deleted reflexively |
| **Experiment** | A/B or multivariate test | Duration of the experiment (weeks) | Experiment concludes → winning branch kept, flag deleted |
| **Permission** | Entitlement / plan-gating (paid tier, admin-only) | Long-lived by design | Re-evaluated when the entitlement model changes |

Release and experiment flags are always temporary — they get an expiry date at creation. Ops and permission flags are long-lived by design but still need periodic ownership review; they are not exempt from the registry.

## The flag lifecycle

1. **Create.** Register the flag: name, type, owner, purpose, default state, and — for release/experiment flags — an **expiry date** (typically 2–6 weeks out). No flag is created without an owner and, for temporary types, a date.
2. **Implement both branches.** Code both the flag-on and flag-off path; both must be tested (see below). A flag with only one tested branch is half-implemented.
3. **Roll out progressively.** Advance exposure per the strategy below, with a gate and abort criteria at each stage.
4. **Observe.** Flag state is a dimension in telemetry (see Integration with observability) so behavior can be correlated with exposure.
5. **Decide.** At 100% and stable, or at experiment conclusion, decide: keep the winning branch permanently, or revert.
6. **Clean up.** Remove the flag and the losing branch's code in a dedicated cleanup slice — not deferred indefinitely. This is the step most commonly skipped; treat it as part of the flag's definition of done, not optional follow-up.

## Progressive rollout strategies

| Strategy | Mechanism | Use when |
|---|---|---|
| **Percentage** | Random N% of traffic/users, stable via consistent hashing on a user/session ID | General-purpose rollout; no need to target specific users |
| **Cohort** | Explicit user list or attribute match (internal users, beta list, region) | Need known, reproducible participants (dogfooding, regional rollout) |
| **Ring** | Concentric deployment rings (internal → canary → early-access → GA) | Enterprise/B2B products with graduated trust tiers |

Every stage has: an entry gate (what must be true to advance), a bake time (minimum observation window before the next stage), and explicit abort criteria (error rate, latency, business-metric thresholds that trigger automatic or manual rollback of exposure — not of the deployment).

## Kill switches

A kill switch is an ops flag that disables a specific code path immediately, without a deploy. Requirements:

- **Pre-wired, not improvised.** The kill switch exists in code before the risky path ships, not added reactively during an incident.
- **Fast to flip.** Toggling it must not require a deploy, a build, or SRE-only tooling — on-call needs to flip it in the incident timeframe.
- **Fails safe.** The off-state is the known-good behavior, verified by test, not merely "whatever happens when the flag check evaluates false."
- **Logged.** Every flip is logged with who, when, and why — feeds the incident timeline (`incident-runbook`).

## Flag hygiene anti-patterns

| Anti-pattern | Why it's a problem | Fix |
|---|---|---|
| Nested flags (flag inside a flag-gated branch) | Combinatorial state explosion; untestable | Flatten — sequence the rollouts instead of nesting them |
| Permanent "temporary" flag | No expiry was set, or the expiry was ignored | Every release/experiment flag gets an expiry date at creation, enforced by the registry |
| Flag-driven architecture | Business logic branches so pervasively on flags that the codebase has no single source of truth for behavior | Flags gate *exposure* to a feature, not fork core architecture; if a flag is load-bearing for structure, that's a design smell |
| Flag checked in more than a handful of call sites | Hard to reason about, hard to clean up | Centralize the check behind a single seam (a service/adapter), not scattered `if (flag)` calls |
| Stale flag with no owner | Nobody knows if it's safe to delete | Registry requires an owner at creation; ownerless flags are flagged in cleanup review |
| Flag left at 100% "temporarily" for months | Never converted to permanent code; two code paths rot in parallel | Treat 100%-and-stable as a trigger to schedule cleanup, not a resting state |

## Testing both branches

- Unit and integration tests exist for both flag-on and flag-off paths — not just whichever is currently the default.
- CI runs both branches where feasible (parameterized test runs, or explicit flag-override in test setup).
- QA verifies both states before a rollout stage advances past internal cohorts.
- A flag that has been at 100% for a full release cycle with the off-path untested is a sign the off-path should be deleted, not left to bit-rot untested.

## Integration with deploy-release

Deployment ships the artifact; this skill governs who is exposed to what's inside it. A deploy can ship a feature fully dark (flag off for everyone) with zero user-visible change — that's the point of decoupling. Rollback of a bad *release* is usually a flag flip (fast, no deploy); rollback of a bad *deployment* (crash, broken build) is `deploy-release`'s job. Don't reach for a redeploy to fix a bad rollout percentage — flip the flag.

## Integration with observability

Flag state must be a first-class dimension in telemetry: logs, metrics, and traces are tagged with the active flag variant for the request. Without this, an incident during a partial rollout is undiagnosable — you can't correlate the error spike with "was this request in the 10% cohort." See `observability` for the tagging convention.

## Mode handling (G/B)

**Greenfield.** Stand up the flag registry and rollout tooling (LaunchDarkly, Unleash, Flagsmith, or a homegrown table) before the first flag is created. Bake the expiry-date requirement into the registry schema itself.

**Brownfield.** Audit existing flags first — most brownfield codebases have accumulated flag debt. Inventory every flag reference in the codebase, classify by type, assign an owner, and backfill an expiry date for any release/experiment flag that's missing one. Flags with no discoverable owner or purpose go on the cleanup backlog, triaged via `tech-debt-management`, before new flags are added on top of the mess.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "This flag is basically permanent, no need for an expiry date." | If it's ops or permission type, fine — say so explicitly. If it's release or experiment type, "basically permanent" is exactly the debt this skill exists to prevent. |
| "We'll clean up the flag after the next sprint." | Cleanup slides indefinitely once the flag stops being top-of-mind. Schedule the cleanup slice when the flag is created, not after. |
| "It's faster to nest this flag inside the existing one." | Nesting multiplies the number of states that need testing. Sequence the rollouts instead. |
| "We don't need to test the off-path, it's the current behavior." | It's the current behavior until someone else's flag change or a config error flips it. Untested paths fail silently. |
| "Kill switch isn't needed, we'll just redeploy if something breaks." | A redeploy takes minutes to tens of minutes under incident pressure. A pre-wired kill switch takes seconds. |

## Verification

You are done when:

- [ ] Flag is registered with name, type, owner, and — for release/experiment types — an expiry date.
- [ ] Both flag-on and flag-off code paths are implemented and tested.
- [ ] Rollout plan has explicit stages, gates, bake times, and abort criteria.
- [ ] Flag state is wired into telemetry as a queryable dimension.
- [ ] A kill switch exists for any change assessed as high-risk (per `nfr-definition` risk criteria).
- [ ] A cleanup ticket exists, scheduled for after the flag reaches its terminal state.

Evidence to check:
- The flag registry has no release/experiment-type entry without an expiry date.
- Flag flips are logged and visible in the incident timeline tooling.

## Anti-patterns

- Creating a flag without registering it — "just a quick `if` behind an env var" that nobody tracks.
- Advancing a rollout stage without observing the prior stage for its full bake time.
- Treating a kill switch as equivalent to a proper rollback — it disables a path, it doesn't undo data written while the path was live.
- Letting the number of live flags grow unbounded because cleanup is nobody's job.

## What this skill does NOT do

- Ship the deployment artifact — that's `deploy-release`; this skill governs exposure after the artifact is already in the environment.
- Inject failure to test resilience — that's `chaos-engineering`; a kill switch here turns off a known-risky path, it doesn't simulate one.
- Design the experiment's statistical methodology — that's a data-science/experimentation concern this skill assumes is already decided; it only handles the delivery mechanics.
- Define the test plan for the flagged feature — that's `testing-strategy`; this skill requires both branches be covered by it.
