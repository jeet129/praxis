---
name: capacity-resource-estimation
description: Translate NFR targets + expected load into resource sizing. Compute / memory / storage / IOPS / network per service; autoscaling policy with min/max bounds and scaling triggers; headroom (the buffer above expected steady-state); growth model (sizing for 12 and 24 months); environment cost envelope. Output drives `iac` provisioning, `deploy-release` resource requests/limits, `cost-finops` attribution, and `performance-testing` target setting. Platform/SRE runs this in the architecture phase and revises mid-project when usage data invalidates assumptions.
capability: build-and-deploy
domain: infra
state: active
dependencies:
  - nfr-definition
  - architecture-pattern-selection
  - iac
triggers:
  - "sizing infrastructure for a new project"
  - "sizing a new service before initial deploy"
  - "revisiting capacity after load data invalidates initial assumptions"
  - "preparing the production_go_live evidence package"
  - "growth-event planning (campaign, expansion, expected surge)"
outputs:
  - sizing model per service (compute / memory / storage / IOPS / network)
  - autoscaling policy (min / max / triggers)
  - capacity assumptions (workload model, dependency calls, growth curve)
  - headroom buffer per service
  - environment cost envelope (monthly $)
  - cost-vs-NFR tradeoff documentation
consumers:
  - platform-sre (primary author)
  - iac (consumes sizing for resource definitions)
  - deploy-release (consumes for pod/container resource requests + limits)
  - cost-finops (consumes for budgets and attribution)
  - performance-testing (load test scenarios match the sizing assumptions)
  - reliability-dr (DR sizing follows from this)
references: []
---

# Capacity & Resource Estimation

The discipline that turns NFR targets into provisioned infrastructure. Without it, projects either over-provision (paying for idle capacity) or under-provision (paging at peak load). With it, sizing is *evidenced* — explicit workload model, explicit assumptions, explicit growth curve — so revisions are honest and reproducible.

Capacity sizing isn't an exact science but it should be *visibly approximate* — when sizes are wrong, the *assumptions* that drove them should be visible enough to revise.

## When this skill fires

- A new project's infrastructure is being sized for the first time.
- A new service is being added; its size needs estimation before initial deploy.
- Mid-project, load data reveals the initial sizing assumptions were wrong; resize.
- The `production_go_live` gate needs evidence of capacity sufficiency.
- A growth event is being planned (marketing campaign, geographic expansion, expected surge).

## The procedure

### 1. Read the NFR register

From `nfr-definition`, extract the numbers that drive sizing:

- **Latency targets** (p50, p95, p99) per endpoint or operation.
- **Throughput targets** (sustained QPS, peak QPS, peak-duration).
- **Availability target** (drives multi-AZ / multi-region decisions).
- **Growth model** (12-month, 24-month projection).
- **RTO / RPO** (drives standby capacity, backup throughput, replication).
- **Cost envelope** if specified (the budget that sizing must fit within).

If any of these are missing or vague, escalate to PM / SA — sizing without targets is guessing.

### 2. Build the workload model

For each service, characterize the workload:

```
Service: order-service

Operations:
  POST /orders
    - p99 target: 200ms
    - peak QPS: 500 (sustained), 2000 (burst, max 15 min)
    - downstream calls: 2 DB writes, 1 cache write, 1 message publish
    - CPU per request (measured or estimated): 20ms
    - memory per request: 5 MB working set
  GET /orders
    - p99 target: 100ms
    - peak QPS: 5000 (sustained), 20000 (burst)
    - downstream: 1 DB read (90% cache hit)
    - CPU per request: 5ms
    - memory per request: 2 MB

Sustained workload sum:
  CPU/sec across all ops: 500 * 20ms + 5000 * 5ms = 35 CPU-seconds/sec → ~35 cores
  Memory steady state: 1 GB base + 100 MB/req-in-flight estimate

Peak workload sum (15-min burst):
  CPU/sec: 2000 * 20ms + 20000 * 5ms = 140 cores
  Memory: ~3 GB
```

The numbers are *approximations* with stated bases. CPU-per-request comes from profiling (measured) or analogue (estimated from similar services). Memory comes from typical observed working set.

### 3. Pick the instance topology

From the workload model:

- **Cores needed at sustained peak** = sum of CPU-seconds/sec across ops + 30% headroom.
- **Memory needed** = working set + buffer cache + JVM/runtime overhead.
- **Replicas needed** = cores / cores-per-instance, with min 3 for HA (one per AZ).
- **Instance type** = matches memory:CPU ratio of the workload.

For order-service at sustained peak of 35 cores:
- Sustained sizing: ceiling(35 * 1.3 / 4) = 12 instances of 4-core type, distributed across 3 AZs.
- Peak burst sizing: ceiling(140 * 1.3 / 4) = 46 instances. Autoscaler max = 50 (some headroom above the burst).

The 30% headroom is the standard buffer above steady-state. Higher for spiky workloads (50%); lower for very smooth workloads (15%) at high cost-discipline.

### 4. Autoscaling policy

The min and max bounds define the autoscaler's freedom:

```
min replicas: 6  (HA; survives single-AZ outage with 4 remaining per AZ)
max replicas: 50 (handles burst peak with margin)
target CPU utilization: 60% (room to scale before saturation)
scale-up cooldown: 60s
scale-down cooldown: 300s
```

Cooldowns matter:
- **Short scale-up cooldown** so the system reacts to load.
- **Longer scale-down cooldown** so the system doesn't oscillate during traffic dips.

For services with cold-start cost (JVM, large container images), the scale-up cooldown must accommodate startup time. If startup is 60 seconds, the cooldown is meaningfully longer — capacity decisions are made faster than capacity can arrive.

### 5. Storage and IOPS

For stateful resources:

```
Database (Postgres):
  Storage size: <current> + 24-month growth (linear or exponential per growth model)
    Initial: 50 GB
    12-month projection: 150 GB
    24-month: 400 GB
    Provisioned: 500 GB (with auto-expand enabled if available)
  IOPS:
    Read peak: <queries/sec> * <pages/query estimate>
    Write peak: <writes/sec> * <pages/write estimate>
    Provisioned IOPS or gp3 throughput sized to peak + 30% headroom
  Connections:
    Peak concurrent connections = max replicas * connections-per-replica
    Database max_connections sized accordingly; pgbouncer / connection pooler if > a few hundred
```

For object storage:

```
Object store (S3 / GCS / Azure Blob):
  Storage volume: <current> + growth
  Request rate: <ops/sec>
  Egress: bytes/sec at peak (cost driver)
  Lifecycle policy: aging objects to cheaper tiers
```

### 6. Network

- **Per-pod / per-instance bandwidth** — typical cloud instance has bandwidth tied to instance size; verify the workload doesn't saturate.
- **Cross-AZ traffic** — costs money (cloud-specific); high-throughput services that span AZs should account for it.
- **External egress** — bandwidth to the internet, to other clouds, to partners. Sized per call rate × payload size.

### 7. Headroom and growth

**Headroom** is the buffer above expected steady-state. Standard headroom: 30%. The headroom absorbs:

- Day-of-week and time-of-day variation.
- Modest growth (the next 1-2 months) before autoscaling fully reacts.
- Single-instance failures (one of N instances out doesn't push the rest above limits).

**Growth model** from the NFR register:

- Linear (steady customer acquisition): sizing covers 12-month projection.
- Exponential (PLG / viral): sizing covers 6-month; revisit quarterly.
- Stepped (planned campaigns, geographic expansion): pre-scale ahead of each step.

Document the growth model and re-validate quarterly. Capacity that worked at 100 customers may not at 10,000.

### 8. Resource requests and limits (Kubernetes-specific)

For container-orchestrated services:

- **Requests** (the floor the scheduler guarantees) = workload's typical use × 1.0.
- **Limits** (the ceiling) = requests × 1.5 to 2.0 (for CPU); = requests × 1.2 (for memory, since OOM-kill is harsh).

For CPU:
- Limits > requests gives burst headroom for spiky tasks.
- Limits = requests (no burst) for predictable steady-state services.

For memory:
- Tight limits force OOM-kill during memory bugs (good — fail fast).
- Loose limits absorb leaks but mask them (bad — hides the bug, eventually OOMs anyway).

Per-service config goes in `platform-k8s` manifests (next skill in this chunk).

### 9. Cost envelope

Multiply sizing by cloud pricing to estimate monthly cost:

```
order-service monthly cost (production):
  Compute: 12 × instance-cost × hours = $X
  Storage: 500 GB × $/GB = $Y
  IOPS: <provisioned IOPS> × $/IOPS = $Z
  Network egress: <bytes/month> × $/GB = $W
  Total: $X + $Y + $Z + $W = $monthly
```

Repeat per environment (dev cheaper than production). The sum is the project's run-cost envelope; it goes into `cost-finops` as the baseline for FinOps tracking.

If the envelope exceeds the cost target from `nfr-definition`, raise it. Trade-offs:
- Smaller instance types (lower performance reserve).
- Spot / preemptible for non-critical workloads.
- Less aggressive autoscaler max (accepts slower response under burst).
- Architectural change (caching layer, async pattern) to shed load.

### 10. Validation against `performance-testing`

Sizing is a hypothesis until validated. `performance-testing` runs load against staging at production-equivalent sizing and verifies:

- The system meets the NFR latency targets at sustained peak.
- The system meets the NFR availability targets during simulated AZ failure.
- The autoscaler reacts within expected bounds.

If validation fails, the sizing is wrong. Revise; document; revalidate.

## Outputs

| Output | Location |
|---|---|
| Sizing model per service | `.project/operational/capacity-sizing-{service}.md` |
| Autoscaling policy | inline in `platform-k8s` manifests |
| Capacity assumptions log | `.project/operational/capacity-assumptions.md` (revisit quarterly) |
| Environment cost envelope | `.project/operational/cost-envelope.md` |
| Cost-vs-NFR tradeoff doc | inline in the relevant ADR |

## Mode handling (G/B)

**Greenfield.** Build the sizing model from the NFR register + initial workload estimates. Validate as soon as load data arrives (initial weeks of prod).

**Brownfield.** Real load data exists. **Use it.** Replace estimates with measurements from `observability` dashboards. Revise the sizing model against the actuals; document the delta. Existing oversizing is opportunity (cost reduction); existing undersizing is debt (reliability risk).

## What this skill does not do

- Provision the resources — that's `iac`.
- Run the load tests that validate sizing — that's `performance-testing`.
- Pick the cloud provider — that's the Resolved Decisions phase.
- Tune query performance to reduce sizing — that's an architecture / data-modeling concern.
- Optimize cost beyond initial envelope — that's `cost-finops` (ongoing optimization).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We'll size for current load; auto-scale handles the rest." | Auto-scale has limits (warmup, max, cost). Size for projected 12-month load; auto-scale for spikes. |
| "Bigger boxes are safer." | Over-sizing wastes money + masks bugs. Right-size + load-test. |
| "Peak is 3x average; we'll provision for peak." | Peak might be 10x; quiet might be 0.1x. Model the distribution, not a single number. |
| "We don't have load data; guess." | Even a back-of-envelope cite (`expected requests/day × pages/request × bytes/page`) beats a guess. Show the work. |
| "Compute is the constraint." | Often it's I/O (DB connections, network bandwidth, disk IOPS). Profile to identify. |
| "Stateless apps are easy to scale." | Until you hit the DB connection pool ceiling. State + concurrency + connection limits all matter. |

## Verification

You are done when:

- [ ] Workload characterized: requests/sec, payload sizes, distribution shape (steady / bursty / batch), peaks.
- [ ] Per-component sizing rationale documented (compute, memory, storage, network, DB).
- [ ] Growth projection: 3-month, 12-month, 24-month estimates.
- [ ] Bottleneck identified (CPU / memory / IO / network / DB connections / queue depth).
- [ ] Buffer factor explicit (default 30-50% headroom).
- [ ] Auto-scaling policy documented (min / max / scale-up + scale-down triggers + cooldown).
- [ ] Cost projection ties to sizing (per `cost-finops`).
- [ ] Capacity stress test plan (per `performance-testing`) verifies the model.

Evidence to check:
- A 2x traffic spike test confirms the estimate.
- Capacity dashboards alert before bottleneck saturation.

## Anti-patterns

- Sizing from gut feel without a workload model.
- Headroom of 5% (no buffer for failures or growth).
- Headroom of 200% (paying for idle capacity).
- Same sizing across all environments (production-grade dev environments waste money).
- Static replica counts when autoscaling would respond to demand.
- Autoscaler max set arbitrarily ("we'll figure it out") — bound it deliberately.
- Sizing for "current load" with no growth projection.
- Cost envelope tracked nowhere; surprise bills.
- Treating sizing as one-time; load characteristics change with feature releases.
