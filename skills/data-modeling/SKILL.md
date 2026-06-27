---
name: data-modeling
description: Logical and physical data design — entity modeling, schema design, normalization vs denormalization decisions, indexing strategy, partitioning strategy, migration discipline (expand-contract for zero-downtime), and polyglot persistence choices. The Solution Architect runs this whenever a slice introduces or changes persistence; the Backend Developer consumes the schema + migration plan as part of the implementation packet. Use whenever new entities are added, existing schemas need changes, performance requires reshaping, or a new persistence store is being introduced.
---

# Data Modeling


<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: backend
state: active
dependencies:
 - engineering-standards
 - nfr-definition
 - domain-discovery
triggers:
 - "designing the schema for a new bounded context"
 - "adding entities to an existing schema"
 - "changing existing schemas (column additions, type changes, denormalization)"
 - "planning a zero-downtime migration"
 - "choosing the right persistence store (SQL / document / KV / time-series)"
 - "deciding indexing or partitioning strategy"
outputs:
 - logical data model (per bounded context)
 - physical schema (DDL or ORM definitions)
 - migration plan (expand-contract steps for any change to live tables)
 - indexing strategy
 - persistence store choice + rationale (ADR)
consumers:
 - backend-developer (implements the schema and queries)
 - data-engineer (consumes for analytical model design)
 - code-review (checks code against the model)
 - capacity-resource-estimation (sizes against expected row counts)
references:
 - postgres.md
 - mysql.md
 - mongodb.md
 - dynamodb.md
 - polyglot-persistence.md
```
<!-- praxis:metadata:end -->

The schema is the system's most expensive thing to change in production. Get it right early, and the team has freedom; get it wrong, and every future slice fights the schema.

This skill produces both the *logical* model (entities, attributes, relationships in domain terms) and the *physical* schema (tables, columns, indexes, constraints) plus the migration plan when changing live tables. It is the single source of truth for persistence design.

## When this skill fires

- A new bounded context introduces persistent state.
- A slice adds new entities to existing schemas.
- An existing schema needs changes — column additions, type changes, denormalization for performance.
- A zero-downtime migration is being planned (existing prod data + new shape).
- A new persistence store is being introduced (relational, document, KV, time-series, graph, search).

## The procedure

### 1. Logical modeling (domain-driven)

Start in the domain language, not in SQL syntax. From `domain-discovery`:

- **Entities** — things with identity that persist (Order, Customer, Invoice).
- **Value objects** — things without identity that describe state (Money, Address, OrderLineItem).
- **Aggregates** — clusters of entities + value objects with a root entity that owns transactional consistency. The aggregate boundary is where transactions live.
- **Relationships** — between entities; their cardinality and ownership.

Output: a logical model diagram per bounded context, in `.project/semantic/data-model-{context}.md`.

Discipline: **aggregate boundaries respect bounded contexts**. Cross-context aggregates are a smell — usually means the bounded contexts were drawn wrong.

### 2. Persistence store choice

For each bounded context, choose the persistence technology based on the data's actual shape and access pattern:

| Pattern | Default |
|---|---|
| Transactional, relational data with ad-hoc queries | **PostgreSQL** (default) |
| Document-shaped with deeply-nested optional fields | MongoDB, DocumentDB |
| Wide-column, very high write throughput, simple query patterns | Cassandra, ScyllaDB |
| Key-value, high throughput, simple lookup | DynamoDB, Redis (persistent) |
| Time-series telemetry | TimescaleDB, InfluxDB |
| Full-text search across content | Elasticsearch, OpenSearch, Postgres + pgvector for hybrid |
| Graph relationships dominate queries | Neo4j, Amazon Neptune |

**Default to PostgreSQL** unless an NFR forces otherwise. Postgres handles relational, JSONB document, full-text, and (with extensions) time-series and vectors well enough for the majority of projects.

**Polyglot persistence is allowed** but earns its complexity. One store per project until an NFR demands more. Each additional store is an ADR.

### 3. Physical schema design

For SQL stores:

- **Primary keys** — surrogate (UUID, bigint identity) by default. Natural keys are tempting but change over time; pay the price upfront with surrogates.
- **Foreign keys** — declare them. Don't rely on application enforcement.
- **Constraints** — NOT NULL by default; nullable is the exception, documented.
- **Indexes** — per query path, not by guessing. Cover the queries the slice's NFRs require; resist creating indexes "for future use" (YAGNI).
- **Naming** — snake_case, consistent table/column conventions; document them per project.

For document stores:

- **Schema-on-write validation** where the store supports it (MongoDB validators, DynamoDB conditional writes).
- **Denormalization is deliberate**, not accidental. Document the access pattern that justifies it.

### 4. Indexing strategy

For each table:

- Identify the query patterns the slice introduces (and the ones the existing code already runs against this table).
- For each query path that needs to be fast: index it. Composite indexes match the query's WHERE + ORDER BY shape.
- Partial indexes for skewed queries (e.g., `WHERE status = 'pending'` on a table where 1% of rows are pending).
- Cost of indexes: write amplification (every index slows writes), storage, vacuum overhead. Don't over-index.
- For high-cardinality joins: indexes on both sides of the FK.
- Periodic review of unused indexes (`pg_stat_user_indexes`) is part of `tech-debt-management`.

### 5. Partitioning strategy

For tables expected to grow large (> 10M rows or > 50 GB, rough thresholds):

- **Time-partitioned** (`PARTITION BY RANGE (created_at)`) for time-series and append-mostly tables.
- **Hash-partitioned** for evenly-distributed loads.
- **List-partitioned** for tenant isolation (one partition per tenant, when tenant count is moderate).

If multi-tenant (per `multi-tenancy` skill that skill): tenant_id is *always* the leading column of compound indexes and is the natural partitioning key when the tenant model is pool or bridge.

### 6. Migration plan (zero-downtime expand-contract)

Any change to a live table follows the expand-contract pattern:

**Expand phase** (deployed first, backward-compatible):
1. Add new columns / tables. Required columns are added with defaults or as nullable initially.
2. Backfill existing rows (in batches if large).
3. Write to both old and new shapes from the application.

**Migrate phase** (after expand has stabilized):
4. Read from new shape; verify correctness against old.
5. Stop writing to old shape.

**Contract phase** (deployed last, after all readers updated):
6. Drop old columns / tables.

Each phase is a separate deployment. Don't combine expand + contract in one deploy — that breaks the zero-downtime property.

Migrations are versioned and idempotent. Tools: Flyway (Java), Prisma migrate (Node), Alembic (Python). NEVER auto-apply via ORM `ddl-auto: update`.

### 7. Document the model + plan

| Output | Location |
|---|---|
| Logical model | `.project/semantic/data-model-{context}.md` |
| Physical schema (DDL or migration files) | repo's `db/migrations/` or equivalent |
| Persistence-store ADR | `.project/decision/` via `adr-decision-records` |
| Migration plan (per change to live tables) | `.project/working/migration-plan-{slice}.md` |
| Indexing strategy | inline in the migration files + summary in `.project/semantic/` |

## Mode handling (G/B)

**Greenfield.** Design schemas to match the logical model; choose Postgres unless an NFR demands otherwise.

**Brownfield.** The existing schema is the strong default. Every change to a live table follows the expand-contract pattern — *no* destructive migrations on shared databases without explicit ADR and rollback plan. Read `.repo-intel/conventions.md` for the codebase's existing schema conventions (naming, ID strategy, ORM patterns).

## What this skill does not do

- Choose the bounded contexts — that's `domain-discovery`.
- Design the API surface — that's `api-design` (consumes this skill's output for response shapes).
- Implement the queries — that's the Backend Developer.
- Tune query performance at scale — that's a concern (`performance-testing`, observability-driven tuning).
- Design data pipelines — that's `data-pipeline`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Normalize everything; denormalize later if needed." | "Later" rarely happens at the boundary where it matters; design with read patterns informing schema. |
| "ORM will handle the schema." | ORM generates a default that's rarely production-shaped. Migration discipline starts at the SQL, not the ORM. |
| "Indexes are easy to add later." | True technically; expensive operationally on large tables. Add at design when access patterns are known. |
| "Constraints slow writes; skip them." | Constraints catch bugs at the database boundary. Removing them moves the bug elsewhere, not away. |
| "We'll use JSON columns for flexibility." | JSON columns hide schema; queries become string-match; analytics breaks. Use for genuinely-variant data only. |
| "Schema migrations are one-shot scripts." | Production migrations need: backward-compatible step, deploy, backward-incompatible step. Big-bang migrations cause incidents. |
| "Auto-DDL on startup is convenient." | Auto-DDL in production = silent schema drift between environments = irreproducible bugs. Disable. |

## Verification

You are done when:

- [ ] ERD / schema diagram exists at `.project/working/architecture/data-model.md`.
- [ ] Per-table: primary key, foreign keys, indexes, constraints, tenancy column (if multi-tenant).
- [ ] Migration plan documented (per `data-warehouse-modeling` if warehouse; per stack pack if OLTP).
- [ ] Access patterns enumerated — each query path maps to an indexed access.
- [ ] N+1 risks identified and mitigated.
- [ ] Cardinality estimates for the next 12 months captured (per `capacity-resource-estimation`).
- [ ] Multi-tenant boundary explicit per table (per `multi-tenancy`).
- [ ] Soft-delete vs hard-delete policy decided per table.

Evidence to check:
- Explain plans for top queries show index usage.
- Migration runs cleanly in staging at production-data-sized scale.
- Backup + restore tested.

## Anti-patterns

- `spring.jpa.hibernate.ddl-auto: update` or equivalent auto-migration in production. Blocker violation.
- Destructive migrations on shared databases without ADR + rollback plan. Blocker.
- Indexes "for future use." YAGNI.
- Natural keys as primary keys (they change; surrogates don't).
- Cross-context aggregates (bounded contexts drawn wrong).
- Adding required columns to existing tables without a default (breaks expand-contract).
- One giant `users` or `events` table doing everything.
