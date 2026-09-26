---
name: performance-testing
description: "Pre-prod load, soak, stress, and spike testing against the NFR register's performance targets. Validates capacity sizing, surfaces bottlenecks before production, and produces the perf-test-soak-pass evidence for the production_go_live gate. QA Engineer + Platform/SRE co-own this; SA contributes the scenarios; Backend Developer interprets results. Use whenever NFR-bearing changes are being released, when capacity sizing needs validation, when investigating perf regressions, or when establishing perf-test cadence."
---

# Performance Testing

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: cross-cutting
state: active
dependencies:
  - nfr-definition
  - capacity-resource-estimation
  - observability
triggers:
  - "verifying a service meets its NFR performance targets"
  - "validating capacity sizing under load"
  - "investigating a perf regression"
  - "preparing perf-test evidence for production_go_live"
  - "scheduled perf test on release candidate"
outputs:
  - load-test plan (scenarios, durations, ramps)
  - test scripts (k6, Gatling, Locust, or JMeter)
  - results report (NFR-target met / not met, with measurements)
  - bottleneck inventory (what saturated, at what load)
  - perf-test-soak-pass attestation (for production_go_live)
consumers:
  - database-engineer (query/index performance under load)
  - qa-engineer (primary author of tests)
  - platform-sre (co-author for infra/capacity-side scenarios)
  - solution-architect (consumes results for architecture decisions)
  - capacity-resource-estimation (consumes for sizing revision)
  - production-release.yaml workflow (consumes pass attestation as evidence)
references:
  - k6.md
  - gatling.md
  - locust.md
```
<!-- praxis:metadata:end -->

The discipline that turns NFR performance targets from claims into verified properties. Capacity sizing (`capacity-resource-estimation`) sets the *hypothesis*; this skill *tests* it. Without performance testing, perf regressions ship to production and capacity surprises happen during business-critical events.

The principle: **NFR claims that haven't been tested under load aren't claims — they're hopes.**

## When this skill fires

- A NFR-bearing change is being released — verify it meets the targets before production.
- Capacity sizing needs validation — does the chosen instance topology actually support the load?
- A perf regression is suspected — isolate and quantify.
- Production-release evidence (production_go_live gate) requires perf-test-soak-pass.
- Quarterly perf-test cadence (default for projects with active production).

## The four test types

Each answers a different question.

### Load test

**Question:** Does the system meet its NFR targets at *expected* sustained peak load?

**Pattern:** Ramp to target QPS over 5–10 minutes; hold for 30–60 minutes; ramp down. Measure latency, error rate, throughput against NFR targets.

**Use case:** Pre-release verification of every NFR-bearing change.

### Soak test (endurance)

**Question:** Does the system stay healthy under sustained load over hours?

**Pattern:** Hold at target peak for 4–24 hours. Measure for memory leaks, connection-pool exhaustion, log-volume problems, slow degradation.

**Use case:** Pre-production release readiness for high-availability services. Required for production_go_live evidence on NFR-bearing systems.

### Stress test

**Question:** What's the system's breaking point? What does it do when it breaks?

**Pattern:** Ramp past target peak (2x, 5x, 10x) until something fails. Identify which component saturates first.

**Use case:** Capacity ceiling discovery; planning headroom; chaos-engineering hypothesis input.

### Spike test

**Question:** Does the system survive sudden traffic bursts?

**Pattern:** Sudden jump from baseline (e.g., 100 QPS) to peak (e.g., 5000 QPS) within seconds. Measure recovery behavior.

**Use case:** Validating autoscaler reaction; HPA cooldown calibration; queue absorption design.

## The procedure

### 1. Build the workload model

From `nfr-definition` and (where available) production traffic mix:

```
Scenario: Place Order

Endpoint mix (% of total traffic):
  GET /products:        40%
  GET /products/:id:    15%
  POST /cart:           10%
  GET /cart:            15%
  POST /checkout:        5%
  GET /orders:           10%
  POST /reviews:          5%

Per-endpoint targets:
  GET /products:        p99 < 100ms, error rate < 0.1%
  POST /checkout:       p99 < 500ms, error rate < 0.5%

Concurrency model:
  Steady state:         500 virtual users
  Peak:                 2000 virtual users
  Spike test:           5000 virtual users from baseline of 500

Test data:
  100K product SKUs
  10K user accounts (subset for auth flows)
  Realistic cart contents (1-5 items, varied)
```

The workload must approximate real traffic — *patterns matter as much as volume*. A perf test of one endpoint at 1000 QPS is not a perf test of the system at 1000 QPS.

### 2. Write the test scripts

Choose tooling per project:

| Tool | Strength |
|---|---|
| **k6** | JavaScript scripting; CLI-first; cloud-native CI integration; default for most projects. |
| **Gatling** | Scala/Java DSL; rich reporting; deep stats. |
| **Locust** | Python scripting; distributed by design; good for very large tests. |
| **JMeter** | GUI + XML; legacy; broadly known. |

Reference files cover per-tool specifics. Default: **k6** for new projects.

### 3. Run against pre-production

Tests run against **staging or a perf-test environment** that's production-parity per `environments`. Production performance testing happens only in carefully controlled scenarios (with rollback ready); pre-prod perf testing is the standard.

### 4. Interpret results

For each NFR target, the test produces a verdict:

```
NFR: p99 GET /products < 100ms at sustained peak (500 vUsers).

Test result:
  p50 GET /products: 12ms
  p95 GET /products: 45ms
  p99 GET /products: 78ms    ← target met
  p99.9 GET /products: 312ms
  Error rate: 0.02%           ← target met

Verdict: PASS
```

For failures, identify *what saturated*:

```
NFR: p99 POST /checkout < 500ms at peak.

Test result:
  p99 POST /checkout: 1450ms  ← target failed
  Error rate: 2.3%             ← target failed

Bottleneck analysis:
  Database connection pool exhausted at peak.
  Pool max = 20; observed in-use = 20 sustained.
  Pool wait time average 1100ms.
  Recommendation: increase pool to 50; investigate query slowness.

Verdict: FAIL
```

### 5. Feed results into capacity + architecture

Pass results inform `capacity-resource-estimation`'s sizing assumptions (the model was right or needs revision). Fail results route to:

- Architecture (if the bottleneck is structural — wrong service decomposition, missing cache layer).
- Code (if the bottleneck is a slow query, an N+1, an inefficient algorithm).
- Capacity (if the bottleneck is undersized resources).

### 6. Cadence + attestation

| Trigger | What runs |
|---|---|
| Pre-release (NFR-bearing change) | Load test against target peak. |
| Quarterly (production active) | Full battery: load + soak + spike. |
| Pre-major-event (campaign, expansion) | Capacity-validation test at projected peak. |
| Post-incident | Targeted regression test reproducing the incident scenario. |

The latest passing soak test produces an attestation in `.project/operational/perf-tests/soak-{date}.md` consumed as `perf_test_soak_pass` evidence in production_go_live.

## Outputs

| Output | Location |
|---|---|
| Load-test plan | `.project/procedural/perf-test-plan.md` |
| Test scripts | `tests/perf/` in repo |
| Results report (per run) | `.project/operational/perf-tests/run-{date}.md` |
| Bottleneck inventory | inline in results report |
| Soak-pass attestation | `.project/operational/perf-tests/soak-{date}.md` |

## Mode handling (G/B)

**Greenfield.** Build perf tests from day one; run on first release candidate before production_go_live.

**Brownfield.** Audit existing perf testing posture. Common findings: never tested at peak; staging too small to be predictive; one-endpoint tests masquerading as load tests. Prioritize a single good test over comprehensive paperwork.

## What this skill does not do

- Define the targets — that's `nfr-definition`.
- Size the infrastructure — that's `capacity-resource-estimation`.
- Inject failures (vs. pure load) — that's `chaos-engineering`.
- Test in production — production_smoke is a different (smaller, safer) activity per `deploy-release`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Load testing once at release is enough." | Load behavior drifts with code changes. Continuous load testing catches regressions early. |
| "We can extrapolate from low load." | Non-linear behavior emerges at high load (lock contention, queue depth, GC). Test at target. |
| "Load test tool is the bottleneck." | Single-machine load gen has limits. Distribute (k6 cluster, Locust workers, Gatling Frontline). |
| "Synthetic workload matches real." | It's a model, not the workload. Calibrate against production telemetry. |
| "Latency p50 is the metric." | p99 is what users feel in the tail. Measure the distribution, not the average. |
| "Soak tests are nice-to-have." | Soak surfaces leaks, slow degradation, drift that short tests miss. Run them. |
| "Pass = pass." | Always investigate "passed" results that look suspicious (too good, oddly stable). Real workloads are noisier. |

## Verification

You are done when:

- [ ] Performance test plan defined: baseline / load / stress / soak / spike, with NFR targets per type.
- [ ] Test data realistic in size + shape.
- [ ] Per-test: target metric, threshold, abort criteria.
- [ ] Tests run in a load-test environment representative of prod (per `environments`).
- [ ] Results compared to baseline; regression triggers ticket.
- [ ] Soak ≥ 24-hour run with no unbounded resource growth.
- [ ] Spike test verifies recovery within target time.
- [ ] Latency distribution (p50/p95/p99/p99.9) captured, not just averages.
- [ ] Bottleneck identified from profiling integration (per `observability`).

Evidence to check:
- A passing test reproduces; flaky perf tests investigated.
- Latency distribution is shape-stable across runs (consistent shape signals signal-not-noise).

## Anti-patterns

- Tests that hit one endpoint (not realistic workload mix).
- Tests run from a single source (network bottleneck on the test rig, not the system).
- Staging too small to be production-predictive.
- "It performed fine in dev" (dev sizing is irrelevant).
- Results without bottleneck analysis (PASS / FAIL without "what saturated").
- Soak tests under 4 hours (too short to surface leaks).
- No baseline (each test is interpreted in isolation; trends invisible).
- Perf tests not part of CI cadence (drift accumulates between manual runs).
