---
name: chaos-engineering
description: "Controlled failure injection in pre-prod (and progressively in prod) to validate resilience-patterns and DR plans in practice. Blast-radius scoping, hypothesis-driven experiments, GameDay cadence, findings → fix backlog. Catches the failure modes the team assumed away. Platform/SRE owns this; experiments live in `.project/operational/chaos/`. Use whenever resilience claims need verification, when running a quarterly GameDay, when adding a chaos experiment to the production_go_live evidence (for resilience-critical changes), or when investigating recurrent fragility."
---

# Chaos Engineering

<!-- praxis:metadata:begin -->
```yaml
capability: operations
domain: infra
state: active
dependencies:
 - reliability-dr
 - resilience-patterns
 - observability
 - incident-runbook
triggers:
 - "verifying a resilience claim before production_go_live"
 - "running a quarterly GameDay"
 - "investigating recurrent fragility in a service"
 - "validating multi-AZ failover claim"
 - "adding chaos coverage to a new service"
outputs:
 - experiment catalog (per service or per failure mode)
 - GameDay schedule + outcome attestations
 - findings report (what broke; what didn't break that should have)
 - remediation backlog (fed to tech-debt-management)
consumers:
 - platform-sre (primary author + executor)
 - reliability-dr (consumes findings for DR-plan refinement)
 - resilience-patterns (consumes findings for pattern revision)
 - production-release.yaml workflow (consumes pass-recency for evidence)
 - tech-debt-management (consumes remediation backlog)
references: []
```
<!-- praxis:metadata:end -->

The discipline that turns "the system is resilient" from a claim into a verified property. Without chaos, resilience claims accumulate untested — the multi-AZ topology that's never seen an AZ failure is *theoretically* resilient. With chaos, failure modes are surfaced cheaply in controlled conditions, before they surface expensively in production.

The principle: **resilience the system hasn't experienced doesn't exist.** Every resilience pattern the team applies is a hypothesis until chaos tests it.

## When this skill fires

- A resilience claim is being made for the production_go_live gate (e.g., "single-AZ failure tolerated") and needs verification before the gate clears.
- Quarterly GameDay cadence (default; project-specific cadence per `reliability-dr` policy).
- Recurrent fragility is observed; targeted experiments isolate the cause.
- A new service has been deployed and needs initial chaos coverage.
- A pattern from `resilience-patterns` has been added (circuit breaker, bulkhead) and the team wants to confirm it works under stress.

## The discipline

### 1. Hypothesis-driven experiments

A chaos experiment is *not* "let's randomly break things." It's a hypothesis:

```
HYPOTHESIS:
"If we terminate one of the 3 order-service pods, traffic redistributes
 across the remaining 2; user-facing error rate stays under 0.5% for 60
 seconds; HPA scales up a replacement within 90 seconds."

PRE-CONDITIONS:
- 3 healthy pods in order-service production
- HPA min=3, max=20, target=60% CPU
- Normal traffic (no other incidents in progress)

EXPERIMENT:
- t=0: kill one randomly-selected pod via chaos tool
- observe: error rate, latency, replacement pod startup time

EXPECTED RESULT:
- Error rate spike < 0.5% for < 60s, then return to baseline
- Replacement pod ready within 90s
- HPA scale-up triggers within 60s

ABORT CRITERIA:
- Error rate > 5% sustained 10s → roll back experiment
- Customer complaints → abort
- Other incident declared → abort

OBSERVATIONS:
<filled during/after the experiment>

VERDICT:
- HYPOTHESIS CONFIRMED / DISCONFIRMED
```

The experiment file is the documentation. Run it; compare actuals to expected; record verdict.

### 2. Blast-radius scoping

Every experiment has a *blast radius* — what's at risk if the hypothesis is wrong. The discipline ramps blast radius:

| Stage | Where | When |
|---|---|---|
| **Stage 1: Sandbox** | Isolated test environment with synthetic traffic. | First time a new experiment runs. |
| **Stage 2: Staging** | Staging environment with synthetic traffic. | After Stage 1 passes consistently. |
| **Stage 3: Pre-prod canary** | Staging with production-like traffic shadow. | When experiment is well-understood. |
| **Stage 4: Production small** | Production, but small subset (one pod, one tenant, one region). | Routine experiments with proven safety. |
| **Stage 5: Production full** | Full production. | Quarterly GameDays for biggest claims (region failover). |

Never skip stages. The first time a new experiment runs in production should *not* be the first time it runs at all.

### 3. Abort criteria

Every experiment has explicit abort criteria *before* it starts:

- **Customer impact threshold** — beyond this error rate or this latency, abort.
- **Concurrent-incident rule** — if another incident is in progress, the experiment aborts.
- **Time limit** — experiments have a maximum duration regardless of signal.
- **Manual abort** — the operator can abort at any time.

Abort triggers a rollback of the chaos *and* a record of why it aborted (also a learning).

### 4. Experiment catalog

Per service (or per failure-mode), maintain a catalog of experiments. Mature projects have:

```
.project/operational/chaos/
├── order-service/
│ ├── pod-kill.md single pod terminated
│ ├── node-drain.md entire node drained
│ ├── az-isolation.md single AZ network-isolated
│ ├── db-slowdown.md database latency injection
│ ├── cache-eviction.md Redis cache flushed
│ ├── network-partition.md partition between order-service and billing
│ └── external-api-fail.md external payment API returns 500
├── billing/
│ └── ...
└── platform/
 ├── cluster-autoscaler-stress.md sudden 10x traffic
 └── etcd-pressure.md K8s control plane stressed
```

Each file is the hypothesis + procedure + last-run attestation.

### 5. GameDay cadence

A GameDay is a planned, multi-experiment session — a focused exercise of multiple chaos experiments to validate the larger system's reliability story.

Default cadence: **quarterly**. Higher for high-reliability projects; lower for internal tools.

GameDay structure:

- **Pre-day brief** — what experiments, what hypotheses, who's running, who's observing, abort policy.
- **Day-of execution** — experiments run in scoped sequence; abort criteria active throughout.
- **Post-day debrief** — what was confirmed; what was discomfirmed; what surprised the team.
- **Action items** — findings flow to `tech-debt-management`.

A GameDay attestation lives in `.project/operational/drills/gameday-{date}.md` and is part of the production_go_live evidence package for resilience-critical changes.

### 6. Coverage

A mature chaos coverage set spans:

- **Compute** — pod kills, node drains, container OOM, CPU saturation.
- **Network** — partition, latency injection, DNS failure, TLS cert expiry.
- **Storage** — disk full, IO throttle, backup failure.
- **Data plane** — database slowdown, cache eviction, replication lag.
- **Dependency** — external API failure, slow response, malformed response.
- **Configuration** — wrong config rolled out, secret rotation failure.
- **Multi-AZ / multi-region** — AZ isolation, region failover.
- **Time** — clock skew, time-based bugs.

Cover the failure modes that are NFR-bearing. A service whose NFR commits to availability through AZ failure needs an AZ-failure experiment.

### 7. Tooling

Common tools:

| Tool | Strength |
|---|---|
| **Chaos Mesh** | K8s-native; rich experiment types; YAML-defined; GitOps-friendly. Default for K8s projects. |
| **Litmus** | K8s-native; chaos hub of community experiments; growing experiment catalog. |
| **AWS FIS** | Cloud-native fault injection for AWS resources; integrates with CloudWatch. |
| **Gremlin** | Managed SaaS chaos platform; broad scope (network, infra, app). |
| **Hand-rolled scripts** | For specific custom experiments not covered by tools. |

Per the cloud + K8s decision: Chaos Mesh is the default for the cloud-agnostic K8s baseline; AWS FIS / Azure equivalent for cloud-specific experiments (cloud packs).

### 8. Pre-prod experiments vs. production experiments

**Pre-prod first** — every experiment runs in staging or sandbox before production, end of story.

Production experiments have additional rules:

- **Notification** — team knows when production chaos is running; status page may note "scheduled resilience testing in progress."
- **Customer-traffic awareness** — never during marketing campaigns, never during business-critical events (Black Friday, major launches).
- **Smaller blast radius** — one pod, one tenant, one region first; expand only after proven safe.
- **Always-on abort** — operator can hit the stop button anytime.

### 9. Integration with production_go_live

For resilience-critical changes, the production_go_live gate (+) requires a chaos pass-recency attestation:

```yaml
evidence:
 chaos_engineering_pass_recent:
 last_run: 2026-10-15
 experiments_passed: [pod-kill, node-drain, az-isolation, db-slowdown]
 experiments_failed: []
 cadence: quarterly
 next_due: 2026-12-15
 within_cadence: true
```

If the recent chaos pass is outside the cadence window, the release pauses until a fresh chaos pass.

## Outputs

| Output | Location |
|---|---|
| Experiment catalog | `.project/operational/chaos/<service>/<experiment>.md` |
| GameDay schedule | `.project/operational/chaos/gameday-schedule.md` |
| GameDay attestations | `.project/operational/drills/gameday-{date}.md` |
| Findings report (per run) | inline in the experiment file (latest run section) |
| Remediation backlog | `.project/working/chaos-findings.md` → `tech-debt-management` |

## Mode handling (G/B)

**Greenfield.** Start with the lowest-blast-radius experiments (pod kill, restart loops) in staging once the service is deployed. Build coverage as confidence builds.

**Brownfield.** Audit what *isn't* covered by chaos — the NFR claims for resilience that have never been tested are highest priority. Start with sandbox-stage versions of those experiments.

## Verification

You are done when:

- [ ] Steady-state hypothesis defined (what "normal" looks like in measurable terms).
- [ ] Failure injection chosen with a stated hypothesis (predicted outcome before running).
- [ ] Blast radius bounded (which subset of traffic / tenants / region; abort criteria).
- [ ] Experiment runs in staging first; promotion to production with explicit go/no-go.
- [ ] Observability instrumented to detect the failure being injected.
- [ ] GameDay attendees + roles documented; runbook prepared.
- [ ] Findings logged to `.project/operational/chaos-experiments/<date>-<name>.md`.
- [ ] Each finding either fixed OR explicitly accepted with rationale.

Evidence to check:
- Abort criteria were tested (the experiment can be stopped quickly).
- A finding from the last GameDay translated into a code/config change.

## What this skill does not do

- Detect incidents — that's `observability`.
- Define reliability targets and DR architecture (SLOs, RTO/RPO, redundancy, failover) — that's `reliability-dr`.
- Implement in-process fault-handling patterns (timeouts, retries, circuit breakers, bulkheads) — that's `resilience-patterns`.
- Design cross-service coordination and correctness (saga, outbox, consensus, consistency models) — that's `distributed-systems-patterns`.
- Run on-call response — that's `incident-runbook`.
- Fix the issues chaos finds — those flow to tech-debt-management for prioritized remediation.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Our system rarely fails." | "Rarely" is the lagging indicator. Resilience patterns are unverified until exercised. |
| "We have retries and circuit breakers; that's chaos-proof." | Configured ≠ verified. Half the configured retries don't behave as expected under real failure. |
| "GameDay is just a fire drill; skip it." | The fire drill is the SKILL. People + runbooks + dashboards together fail in surprising ways. |
| "Chaos in production is too risky." | Start in staging; graduate to controlled production injection with blast radius bounded. Not chaos at random; chaos with hypothesis + abort criteria. |
| "We did chaos last quarter; we're good." | Cadence-based, not point-in-time. The system changed; the exercise needs to refresh. |
| "We can't afford the engineering time." | A 4-hour GameDay is cheaper than an unplanned 8-hour incident. The exercise pays for itself within a quarter typically. |

## Anti-patterns

- "Random chaos" without hypotheses (no learning, just damage).
- Skipping pre-prod stages and going straight to production.
- Running chaos during incidents in progress (compound failure).
- Running chaos during high-traffic business events.
- Chaos experiments without abort criteria.
- Findings that go nowhere — backlog created, never triaged.
- "We don't need chaos because we have multi-AZ" — multi-AZ that's never been tested isn't multi-AZ.
- Production chaos without team awareness (surprise drills are not drills, they're outages).
- GameDays that pass without surprises (then the experiments aren't challenging enough — escalate scope).
