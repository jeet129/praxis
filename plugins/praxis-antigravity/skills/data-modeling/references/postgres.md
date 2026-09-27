# Reference — PostgreSQL

Loaded by `data-modeling` when PostgreSQL is the chosen relational store (the recommended default for OLTP).

## When to use

PostgreSQL is the right default for almost any new transactional workload in 2026:
- ACID with serializable isolation available.
- Rich type system (jsonb, arrays, ranges, custom types, full-text search).
- Strong extension ecosystem (pgvector, PostGIS, TimescaleDB, Citus).
- Excellent operational maturity across all major clouds.
- Stable, predictable performance.

Skip Postgres only when there's a specific reason (DynamoDB for global single-digit-ms KV at massive scale; Snowflake/BigQuery for analytical workloads; specialized stores for vector/time-series/graph at scale).

## Schema patterns

### Naming
- `snake_case` for tables, columns, indexes.
- Plural table names (`orders`, `customers`) by convention.
- Index naming: `idx_<table>_<columns>` for B-tree, `idx_<table>_<columns>_gin` for GIN.

### Primary keys
- **UUID v7** (time-ordered UUIDs) are the modern default — globally unique + good index locality.
- Avoid `bigserial` for distributed systems (hot-spot insertion).
- If using UUIDs, store as `uuid` type (16 bytes), not `text` (37 bytes + slower).

### Timestamps
- Always `timestamp with time zone` (`timestamptz`), never `timestamp without time zone`.
- Store as UTC; let the application present in user timezone.

### Soft delete
- Don't soft-delete by default — most "we'll need this back" use cases never materialize.
- When soft delete is required: `deleted_at timestamptz` (null = active). Add to every query's `WHERE`. Consider a partial index: `CREATE INDEX idx_users_active ON users(id) WHERE deleted_at IS NULL`.

### Common columns pattern
```sql
CREATE TABLE orders (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     uuid NOT NULL REFERENCES customers(id),
    status          text NOT NULL CHECK (status IN ('pending','confirmed','shipped','cancelled')),
    total_cents     integer NOT NULL CHECK (total_cents >= 0),
    metadata        jsonb NOT NULL DEFAULT '{}',
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    deleted_at      timestamptz
);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status_created ON orders(status, created_at DESC);
CREATE INDEX idx_orders_metadata_gin ON orders USING GIN (metadata jsonb_path_ops);
```

### Updated_at trigger
```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_orders BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

## Money

NEVER use `float`/`double` for money. Use `numeric(p,s)` for precision OR integer cents for compactness.

```sql
-- Option 1: store cents (simpler queries, smaller storage)
total_cents     integer NOT NULL

-- Option 2: numeric (when fractional cents or multi-currency precision matters)
total_amount    numeric(15,2) NOT NULL
currency_code   char(3) NOT NULL
```

## Indexing — the high-leverage rules

1. **Index the columns you filter, join, or order by.** Not the columns you select.
2. **Composite indexes match left-to-right.** `(a, b, c)` serves `WHERE a=?`, `WHERE a=? AND b=?`, NOT `WHERE b=?`.
3. **Partial indexes for sparse predicates.** `CREATE INDEX ON orders(status) WHERE status = 'pending'` — much smaller than full index when most rows are 'shipped'.
4. **GIN for jsonb, full-text, array containment.** `jsonb_path_ops` is faster + smaller than the default for containment.
5. **Avoid indexes on highly-mutable columns.** Each update rewrites index entries.
6. **Check unused indexes:** `SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;`

## JSONB — power tool with cost

JSONB is a real-world weapon when used right:

```sql
-- Indexed containment query (fast with GIN jsonb_path_ops)
SELECT * FROM orders WHERE metadata @> '{"channel": "mobile"}';

-- Path extraction
SELECT metadata->>'channel' AS channel, COUNT(*) FROM orders GROUP BY 1;
```

Anti-pattern: using JSONB as the entire data model. If you're querying inside JSON columns more than you query their containing rows by ID, your schema is wrong.

## Common query patterns

### Pagination — cursor over offset

`OFFSET` becomes painfully slow past a few thousand rows. Use cursor pagination:

```sql
-- Page 1
SELECT * FROM orders WHERE status='shipped' ORDER BY created_at DESC, id DESC LIMIT 50;

-- Subsequent pages: pass last (created_at, id) as cursor
SELECT * FROM orders
WHERE status='shipped'
  AND (created_at, id) < ($last_created_at, $last_id)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

Add a composite index: `(status, created_at DESC, id DESC)`.

### Upsert
```sql
INSERT INTO inventory (sku, quantity)
VALUES ($1, $2)
ON CONFLICT (sku) DO UPDATE
SET quantity = inventory.quantity + EXCLUDED.quantity,
    updated_at = now();
```

### Bulk insert
```sql
INSERT INTO events (id, type, payload)
SELECT * FROM unnest($1::uuid[], $2::text[], $3::jsonb[]);
```

Single round-trip; much faster than per-row inserts.

## Concurrency

### Row locking
```sql
-- For workers consuming from a queue table
SELECT * FROM jobs
WHERE status = 'pending'
ORDER BY created_at
LIMIT 10
FOR UPDATE SKIP LOCKED;
```

`SKIP LOCKED` is the key: workers don't block each other; each picks a different row.

### Advisory locks
```sql
-- Application-defined locks for "only one process should do this"
SELECT pg_try_advisory_lock(hashtext('reindex-orders'));
```

### Optimistic concurrency
```sql
UPDATE orders SET status='shipped', version = version + 1
WHERE id = $1 AND version = $2;
-- If affected_rows = 0, someone else updated; refetch and retry
```

## Connection pooling

Postgres allocates one process per connection — expensive. Pool, always.

- **Application-level**: HikariCP (Java), pgbouncer-client libs.
- **Server-side**: **pgBouncer** in transaction-pooling mode is the standard.

Caveat with pgBouncer transaction-pooling: no session-level features (prepared statements, advisory locks, listen/notify) survive between transactions. Configure your driver to disable prepared-statement caching OR run pgBouncer in session-pooling mode (less pooling benefit).

Rule of thumb: max DB connections = (number_of_app_replicas × per-replica-pool-size). Plan for the math; don't let it surprise you.

## Migrations

Always **expand-migrate-contract** for schema changes (per `data-modeling` SKILL):

1. **Expand**: add new columns/tables; both old and new code work.
2. **Migrate**: backfill data; deploy new code that reads/writes new.
3. **Contract**: remove old columns/tables once nothing reads them.

Tooling:
- **Flyway** — battle-tested, supports any language. SQL-first.
- **golang-migrate** — Go-friendly.
- **dbmate**, **Liquibase**, **Sqitch** — language-agnostic alternatives.
- **Alembic** — Python (SQLAlchemy ecosystem).

NEVER run migrations from auto-DDL (`ddl-auto: update`, ORM auto-migrate). Migrations are versioned, reviewed code.

## Backups & PITR

Postgres supports point-in-time recovery via WAL archiving.

- Managed services (RDS, Aurora, Cloud SQL, Azure DB for Postgres) handle this — verify retention + restoration timing matches your RPO.
- Self-hosted: pgBackRest is the leading tool; wal-g for cloud storage.
- **Test restoration regularly** — backups you've never restored are not backups (per `reliability-dr`).

## Performance baseline

- Single-node Postgres on modern hardware: 10K-100K rps depending on workload.
- Read replicas for scale-out reads.
- Citus / Postgres-XL for sharding (rarely needed; usually a sign of premature scale-out).
- Connection pool exhaustion is the most common scaling cliff — measure first.

## Postgres extensions worth knowing

| Extension | Use case |
|---|---|
| `pgcrypto` | UUID generation, hashing |
| `pgvector` | Vector similarity for RAG (per `rag-design/references/pgvector.md`) |
| `PostGIS` | Geospatial queries |
| `pg_stat_statements` | Query stats — essential for performance work |
| `timescaledb` | Time-series workloads on Postgres |
| `pg_partman` | Automatic partition management |

## Common rationalizations

| Thought | Counter |
|---|---|
| "JSONB everywhere for flexibility." | JSONB is fast in Postgres but discoverability dies. Use it for genuinely-variant data only. |
| "Indexes are easy to add later." | True technically; expensive operationally on large tables. Add at design when access patterns are known. |
| "ORM auto-migrate is convenient." | Auto-migrate ships schema drift. Always use real migrations. |
| "We don't need pgBouncer; the app pools." | App pools + many replicas = thousands of connections to Postgres → backend process explosion. pgBouncer at the door. |
| "Use float for money; close enough." | Never. Numeric or integer cents only. |

## Official sources

- Postgres documentation: https://www.postgresql.org/docs/16/
- pgBouncer: https://www.pgbouncer.org
- pgvector: https://github.com/pgvector/pgvector
- Use The Index, Luke! (book — best practical indexing guide): https://use-the-index-luke.com
