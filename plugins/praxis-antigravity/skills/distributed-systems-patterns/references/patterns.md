# Distributed Systems Patterns — Worked Examples

Supporting worked examples and templates for `distributed-systems-patterns/SKILL.md`. Pulled out here to keep the main skill file scannable; referenced by pointer from the relevant sections.

## Choice-per-store example

```markdown
# ADR-NNN: Consistency Model — Orders Database

## Decision
Strong consistency (linearizable) within a single AWS region;
eventual consistency for cross-region replicas.

## Rationale
Orders are financial transactions. A read returning a stale order
state could double-charge, double-ship, or fail to honor a cancellation.

## Trade-offs accepted
- Latency: writes wait for synchronous replication within region (single-digit ms penalty).
- Availability: single-region writes pause if the regional primary is unreachable.
  Multi-region failover requires explicit cutover (RTO 5 min) — accepted per the NFR register.

## Mechanism
Aurora Postgres with multi-AZ synchronous replication;
cross-region async replication for DR.
```

## Outbox

```
WITHIN ONE TRANSACTION:
  1. INSERT INTO orders (...) VALUES (...);
  2. INSERT INTO outbox (event_type, payload) VALUES (...);
COMMIT;

ASYNCHRONOUSLY, A BACKGROUND PROCESS:
  3. SELECT * FROM outbox WHERE published_at IS NULL;
  4. Publish to message bus.
  5. UPDATE outbox SET published_at = NOW() WHERE id = ...;
```

The outbox row is written in the same transaction as the business state. The publisher is at-least-once (idempotent consumers handle duplicates). This eliminates the "wrote to DB but failed to publish" inconsistency that plagues naive dual-writes.

## Saga

```
Workflow: Place Order
  Step 1: Reserve inventory (Inventory service)
    → Compensation: Release reservation
  Step 2: Authorize payment (Payment service)
    → Compensation: Void authorization
  Step 3: Create shipment (Shipping service)
    → Compensation: Cancel shipment

If Step 3 fails:
  - Run Step 2's compensation (void authorization)
  - Run Step 1's compensation (release reservation)
```

## ADR template

```markdown
# ADR-NNN: <Decision> — <Component>

## Context
<NFRs that drive the choice; the operating environment>

## Decision
<Concise statement>

## Consistency model
<linearizable | sequential | causal | eventual | read-your-writes>
<per-store; per-operation if it varies>

## Partitioning / replication
<topology: single-leader | multi-leader | leaderless>
<partition strategy: hash | range | geographic | composite>
<partition key: <specific>>

## Trade-offs accepted
- CAP position: <CP / AP>
- PACELC position: <EC / EL>
- Specific implications: <latency, availability, recovery time>

## Partial-failure behavior
<For each component-loss scenario, what the system does>

## Why we rejected alternatives
<Brief on the 1-2 alternative approaches considered>

## Verification
<How chaos-engineering will verify these properties hold>
```
