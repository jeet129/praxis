---
name: distributed-systems-patterns
description: "Cross-service data and coordination patterns for distributed systems. Consistency models (strong / eventual / causal / linearizable), partitioning and sharding, replication topology, consensus and leader election (Raft / Paxos), the outbox and saga patterns, system-level idempotency and exactly-once semantics, time and ordering (logical clocks, hybrid logical clocks), partial-failure design, CAP and PACELC trade-offs stated explicitly. Distinct from `resilience-patterns` (in-process, single-dependency failure-handling — timeouts, retries, circuit breakers, bulkheads) and `reliability-dr` (system-level availability architecture — redundancy, failover, RTO/RPO). Used by SA during architecture design for any system with multiple stateful components, and by BE Dev during implementation for state coordination. Pushy trigger because distributed-systems edge cases are catastrophic when missed."
---

# Distributed Systems Patterns

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: active
dependencies:
  - architecture-pattern-selection
  - data-modeling
  - resilience-patterns
triggers:
  - "designing a system with multiple stateful components"
  - "choosing a consistency model for a data store"
  - "designing partitioning or sharding strategy"
  - "deciding replication topology"
  - "implementing leader election or coordination"
  - "designing for exactly-once semantics"
  - "stating CAP / PACELC trade-offs in an ADR"
outputs:
  - per-store consistency decision (with CAP/PACELC trade-off explicit)
  - partitioning and sharding strategy
  - replication topology
  - consensus or coordination requirements (if any)
  - outbox and saga designs for cross-service consistency
  - ordering and time-handling design (if temporal correctness matters)
  - partial-failure design (what does the system do during partitions)
consumers:
  - solution-architect (primary author)
  - architecture-challenger (reliability + scale sub-personas attack these)
  - backend-developer (implements coordination per these decisions)
  - data-modeling (consumes consistency choices for schema design)
  - resilience-patterns (consumes for per-component failure design)
references:
  - references/patterns.md
```
<!-- praxis:metadata:end -->

The patterns that handle **correctness across multiple stateful components**. Where `resilience-patterns` makes one service tolerant of one dependency's failure, this skill makes a *system* of cooperating components correct in the presence of network partitions, partial failures, concurrent updates, and the fact that nodes don't agree on time.

The principle: **the network is not reliable; nodes fail independently; time doesn't exist as a global concept; and these are facts to design around, not hide.**

## When this skill fires

- A system has multiple stateful components (databases, caches, message brokers) and they need to coordinate.
- A new data store is being chosen; its consistency properties matter.
- Sharding or partitioning strategy is being decided.
- Replication topology needs to match RTO/RPO targets.
- Leader election or coordination is required (cron-like work, primary writer, etc.).
- Exactly-once semantics are being designed.
- Cross-region / multi-region correctness is being designed.
- An ADR documents the CAP/PACELC trade-off the team accepted.

## Consistency models

Pick deliberately, per store. Each has cost and constraint.

### Strong consistency (linearizable)

Every read returns the most recent write. After a write completes, no read returns the prior value.

- Achieved via single-primary replication (writes go through a coordinator) or consensus protocols (Raft, Paxos).
- **Cost**: latency (writes wait for confirmation); availability (no writes when the coordinator is unreachable).
- **Use when**: financial transactions, inventory counts, leader-election state, authorization decisions where staleness can't be tolerated.

### Sequential consistency

Operations appear in some global order consistent with each client's program order. Weaker than linearizable; still strong enough for many cases.

### Causal consistency

Operations causally related (A happened-before B) are seen in order; concurrent operations may be seen in any order.

- Captured via vector clocks or hybrid logical clocks.
- **Use when**: social feeds (your reply appears after the parent you replied to, but unrelated posts can interleave), collaborative editing.

### Eventual consistency

Replicas eventually agree, but may temporarily disagree.

- **Cost**: clients may see stale data; conflict resolution needed for concurrent writes.
- **Use when**: high availability matters more than recency; staleness measured in seconds is acceptable; the data has natural conflict-resolution (last-writer-wins or CRDTs).

### Read-your-writes consistency

A client always sees their own writes (even if other clients see stale data).

- Implemented via session affinity (route the client to the same replica) or token-based reads (client passes a write-token; replica blocks until caught up).
- **Use when**: web apps where the user-perceived consistency matters.

### Choice per store

Different data stores in the same system can have different consistency models. The system's correctness depends on each being explicit. Worked ADR example (Orders Database — strong in-region, eventual cross-region): `references/patterns.md#choice-per-store-example`.

## CAP and PACELC

CAP: In a network partition (P), a system must choose Consistency (C) or Availability (A).

PACELC: even when there's no partition (else), a system must choose between Latency (L) and Consistency (C).

Most real systems land at one of:

| | Partition behavior | No-partition behavior |
|---|---|---|
| **CP+EC** | Consistent during P; gives up availability. | Consistent at the cost of latency. (Spanner, etcd, Aurora primary writes.) |
| **AP+EL** | Available during P; gives up consistency. | Low latency at the cost of consistency. (Cassandra, DynamoDB with eventual-consistency reads.) |
| **CP+EL** | Consistent during P; gives up availability. | Low latency under no partition. (Rare; trade-offs aren't naturally compatible.) |
| **AP+EC** | Available during P; gives up consistency. | Consistent under no partition. (Some quorum-based systems.) |

State the project's choice per-store explicitly. "We have eventual consistency" is too vague — *during what conditions* eventual? *what does the application do* during inconsistency?

## Partitioning and sharding

For data that exceeds a single node's capacity (storage or write throughput):

**Hash partitioning** — distribute by hash of a key. Even distribution; range queries hard.

**Range partitioning** — distribute by ranges of a key. Range queries efficient; hot ranges possible.

**Geographic partitioning** — partition by region. Locality + regulatory compliance; cross-region operations expensive.

**Composite** — combine. Common: shard by tenant_id (range or hash), partition by date within tenant (range).

The **partition key** matters more than the strategy. Choose to:

- Distribute load evenly (no hot partitions).
- Co-locate data that's queried together (avoid cross-partition queries).
- Match the natural multi-tenancy boundary (if multi-tenant).
- Tolerate skew (if one tenant is 1000x another, sharding only by tenant won't distribute).

Resharding is expensive. Design the partition strategy assuming you'll keep it for years.

## Replication topology

| Topology | Use when |
|---|---|
| **Single-leader (primary-replica)** | Default for SQL stores. Strong consistency; failover requires election. |
| **Multi-leader** | Multi-region with active-active writes. Conflict resolution required (CRDT, vector clocks, last-writer-wins). |
| **Leaderless (quorum)** | Cassandra-style. Read/write quorum sizes determine consistency-vs-availability. |

Replication has lag. Read-from-replica must accommodate lag (read-your-writes via session affinity, or explicit "read from primary" for fresh-required reads).

## Consensus and leader election

When a system needs to agree on something — who's the primary writer, what the next sequence number is, whether a transaction is committed — consensus protocols make agreement under partial failure possible.

**Raft** — the modern standard. Implemented in etcd, Consul, CockroachDB, many systems. Understandable; well-documented.

**Paxos** — older; conceptually similar; less approachable. Use libraries (Google's Spanner), not roll-your-own.

**Multi-Paxos / EPaxos / Zab** — variants for specific patterns.

For most projects: **don't implement consensus**. Use a system that does (etcd, ZooKeeper, Consul) for coordination state. The bugs in hand-rolled consensus are catastrophic.

Common coordination needs:

- **Leader election** — single-writer pattern; failover. Use etcd/Consul lock or K8s lease objects.
- **Distributed locks** — bounded duration; with fencing tokens to prevent stale-leader writes.
- **Service discovery** — health-checked registration. K8s Services + DNS handle this for in-cluster; Consul/etcd for cross-cluster.

## Outbox

For cross-service consistency: a service that needs to *both* persist locally and publish an event must not do these in two separate transactions (the second can fail leaving inconsistent state). Transactional outbox: write the event to an outbox table in the same transaction as the business state; a background process publishes from the outbox and marks it published, at-least-once. This eliminates the "wrote to DB but failed to publish" inconsistency that plagues naive dual-writes. Worked example (transaction + publisher loop): `references/patterns.md#outbox`.

## Saga

For long-running, cross-service workflows that need to maintain consistency without distributed transactions, the saga pattern decomposes the workflow into local transactions per service + compensating actions for rollback. Worked example (order-placement saga with compensations): `references/patterns.md#saga`.

Two implementations:
- **Choreography** — services react to events; no central coordinator. Simpler but harder to reason about.
- **Orchestration** — a saga orchestrator (often a workflow engine like Temporal, Camunda) coordinates. More visible state; preferred for complex sagas.

Sagas are inherently eventually-consistent. They don't *prevent* failures; they ensure the system reaches a consistent state (success or compensated-rollback) regardless of mid-workflow failures.

## Idempotency at the system level

`resilience-patterns` addresses single-call idempotency (idempotency keys on one mutation). This skill addresses *system-level* idempotency:

- **Exactly-once semantics** — strictly impossible in distributed systems (without infinite memory). Approximations:
  - **At-least-once delivery + idempotent consumer** — practical and common.
  - **Idempotent producer + at-most-once delivery** — Kafka-style.
- **Deduplication** — by message ID, by natural-key, by idempotency key.
- **Compensating actions** — undo the side effects of a partial workflow (the saga pattern, above).

The team's vocabulary should distinguish these. "We need exactly-once" is usually answered with "you need at-least-once + idempotent consumer."

## Time and ordering

The network doesn't agree on time. Clocks drift; events happen on different nodes; ordering matters.

**Physical clocks** — wall-clock time. Useful for human-facing timestamps; bad for ordering in distributed systems.

**Logical clocks (Lamport timestamps)** — counter per node; messages carry timestamps; receivers update their clock to max(local, received) + 1. Total ordering of causally-related events.

**Vector clocks** — counter per node per peer. Can detect concurrent events.

**Hybrid logical clocks (HLC)** — combines physical and logical. Bounded skew from wall-clock; logical ordering for causal correctness. Used by CockroachDB, MongoDB, others.

For most projects: use a store that handles this internally. When designing the application, ask: do we *need* event ordering, or are we relying on it accidentally?

## Partial-failure design

In a single-machine system, the machine either works or it doesn't. In distributed systems, *parts* can fail independently. Design explicitly:

- **Component A unreachable from component B** — what does each do?
- **Component A slow, not failed** — what's B's timeout, retry, circuit-break behavior?
- **Component A returns inconsistent data** (caught a stale replica) — does the application detect or fail silently?
- **One AZ unreachable, others fine** — does the system continue?
- **One region degraded** — what's the failover behavior?

These are not edge cases; they're routine. The architecture should *name* the response for each.

## ADR template for distributed-system decisions

Context / decision / consistency model / partitioning-replication / CAP-PACELC trade-offs / partial-failure behavior / rejected alternatives / verification — full template at `references/patterns.md#adr-template`.

## Outputs

| Output | Location |
|---|---|
| Per-store consistency decision + ADR | `.project/decision/adr-NNN-consistency-{component}.md` |
| Partition / shard strategy | `.project/semantic/data-model-{context}.md` (extended) |
| Replication topology | `.project/operational/dr-plan-{service}.md` (in `reliability-dr`) |
| Coordination requirements | `.project/decision/adr-NNN-coordination-{component}.md` |
| Partial-failure design | `.project/operational/runbooks/` + architecture doc |

## Mode handling (G/B)

**Greenfield.** Design distributed-systems properties into the architecture; state CAP/PACELC trade-offs explicitly in ADRs.

**Brownfield.** Audit the existing system's actual behavior — what's its true consistency model under partition? Often the answer surprises (eventual consistency claimed; actually relies on single-leader and breaks during failover). Document reality, then propose deliberate changes.

## What this skill does not do

- Single-component / single-dependency failure handling (timeouts, retries, circuit breakers, bulkheads, per-call idempotency) — that's `resilience-patterns`.
- System-level availability architecture (redundancy, failover, RTO/RPO, DR tiers, backup/restore) — that's `reliability-dr`.
- Verify these properties — that's `chaos-engineering`.
- Schema-level design — that's `data-modeling`.
- Pick the storage technology — that's `architecture-pattern-selection` (informed by this skill).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We're 'distributed' but really just a service + DB." | Then say so. The patterns matter when you actually distribute state; pretending you do adds complexity for no value. |
| "Strong consistency is always better." | Strong consistency = lower availability under partition (CAP). Default to strong is fine; ASSUMING strong is dangerous. |
| "Sagas are too complex; we'll just use distributed transactions." | XA / 2PC across services is rarely actually deployed and rarely works well. Sagas are the operationally-realistic shape. |
| "Outbox pattern is overkill for our scale." | Outbox is the single most reliable way to publish-after-commit. Skipping = lost events when crashes happen between commit and publish. |
| "Idempotency is the consumer's problem." | Idempotency at-most-once is the publisher's design too. Either: idempotency key in the message, or idempotent operations. |
| "Order of events doesn't matter." | Until it does — and then it matters absolutely. Decide explicitly: total order, partial order, or no order. |
| "We'll figure out the consistency model when we add replicas." | Adding replicas changes the consistency model whether you choose or not. Decide first; build to it. |

## Verification

You are done when:

- [ ] Consistency model explicit per data store: strong / bounded staleness / eventual / causal — and the trade-offs documented.
- [ ] CAP/PACELC stance is stated per partition-tolerance-required system.
- [ ] Cross-service workflows that need atomicity use a documented saga (orchestrated or choreographed).
- [ ] Event publishing uses outbox or equivalent commit-and-publish-atomic pattern.
- [ ] Idempotency strategy for every event-driven endpoint (key + dedupe window).
- [ ] Ordering requirements explicit per topic / partition.
- [ ] Failure modes mapped (per `incident-runbook`'s severity matrix).

Evidence to check:
- Stress test under partition: data converges to expected consistency model.
- Replay test: rebuilding from event log produces the same state.
- Saga compensation paths exercised.

## Anti-patterns

- "We have multi-region" without naming consistency model.
- Distributed locks without fencing tokens (stale-leader race conditions).
- Hand-rolled consensus.
- Assuming network is reliable.
- Assuming clocks are synchronized.
- Wall-clock-based ordering in distributed protocols.
- Multi-leader replication without conflict resolution strategy.
- "Eventually consistent" stated without "eventually within what?"
- "Exactly-once" semantics promised.
- No explicit partial-failure behavior for each component-loss scenario.
