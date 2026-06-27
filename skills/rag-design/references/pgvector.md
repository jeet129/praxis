# Reference — pgvector

Loaded by `rag-design` when pgvector is the chosen vector store (recommended default for small-to-medium projects on Postgres).

## When to use

pgvector is the recommended starting point for vector search when:
- You're already on Postgres (most operations teams are).
- Corpus size is below ~10M vectors (well-tuned, can handle more).
- You want vector search + structured filtering in one query (the killer feature).
- You don't want a separate vector DB to operate.

Switch to a purpose-built vector DB (Qdrant, Pinecone, Weaviate, etc.) when:
- Corpus grows past tens of millions.
- Sub-millisecond p99 latency is mandatory.
- You need advanced features (cross-encoder reranking inline, hybrid search built-in, etc.).

## Setup

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS vector;
```

Most cloud Postgres services support pgvector:
- AWS RDS Postgres 15.2+, Aurora Postgres 15.3+
- Google Cloud SQL Postgres 14+
- Azure Database for Postgres
- Supabase, Neon, Render (default)

## Storage

```sql
CREATE TABLE document_chunks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     integer NOT NULL,
    content         text NOT NULL,
    embedding       vector(1536),  -- dimension depends on embedding model
    
    -- Per `rag-design` metadata for filtering + citation
    source_url      text,
    title           text,
    section         text,
    last_updated    timestamptz NOT NULL DEFAULT now(),
    document_type   text,
    version         text,
    tags            text[],
    access_tags     text[],
    
    -- House-keeping
    created_at      timestamptz NOT NULL DEFAULT now(),
    
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_chunks_access ON document_chunks USING GIN (access_tags);
```

Vector column type: `vector(N)` where N is the embedding dimension. Common dims:
- OpenAI text-embedding-3-small: 1536
- OpenAI text-embedding-3-large: 3072
- BGE-large: 1024
- all-MiniLM-L6-v2: 384

## Distance metrics

pgvector supports three distance operators:

| Operator | Distance | Used with |
|---|---|---|
| `<->` | L2 (Euclidean) | When embeddings aren't normalized to unit length. |
| `<#>` | Negative inner product | When embeddings are unit-normalized. Faster than cosine. |
| `<=>` | Cosine distance | The most common for normalized embeddings; identical to `<#>` for unit vectors but pgvector computes the actual cosine. |

Most modern embedding models output normalized vectors. **Use `<=>` (cosine) as the default.**

## Indexing — HNSW vs IVFFlat

pgvector supports two ANN index types:

### HNSW (Hierarchical Navigable Small World)

Best for: most use cases, especially when corpus updates often.

```sql
CREATE INDEX idx_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

Parameters:
- `m` (default 16): connections per node. Higher = better recall, more memory.
- `ef_construction` (default 64): build-time search width. Higher = better index, slower build.

Query-time recall vs speed:
```sql
SET hnsw.ef_search = 100;  -- default 40; higher = better recall, slower query
SELECT * FROM document_chunks 
ORDER BY embedding <=> $query_embedding 
LIMIT 10;
```

### IVFFlat (Inverted File with Flat Quantization)

Best for: large static corpora (rarely updated).

```sql
-- First populate the table, THEN create the index (IVFFlat needs data to learn centroids)
CREATE INDEX idx_chunks_embedding_ivf 
ON document_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 1000);  -- rule of thumb: sqrt(num_rows) for < 1M, num_rows/1000 for > 1M
```

Query-time:
```sql
SET ivfflat.probes = 10;  -- default 1; higher = better recall, slower query
SELECT * FROM document_chunks 
ORDER BY embedding <=> $query_embedding 
LIMIT 10;
```

### Choice in 2026: HNSW

HNSW added in pgvector 0.5.0 (2023) is generally better for production:
- Higher recall at the same latency.
- Doesn't require pre-populated data to build.
- Updates more gracefully.

Use IVFFlat only when memory is constrained and corpus is static.

## Querying patterns

### Basic similarity search

```sql
SELECT id, content, source_url, title, embedding <=> $1 AS distance
FROM document_chunks
ORDER BY embedding <=> $1
LIMIT 10;
```

### Hybrid: vector + metadata filter (the killer feature)

```sql
SELECT id, content, source_url, title, embedding <=> $1 AS distance
FROM document_chunks
WHERE document_type = 'user-guide'
  AND last_updated > now() - interval '180 days'
  AND 'public' = ANY (access_tags)
ORDER BY embedding <=> $1
LIMIT 10;
```

**The query planner needs help**: if the filter is highly selective, it might scan via the metadata index and lose the ANN benefit; if not selective enough, it might do too much vector comparison. Use `EXPLAIN ANALYZE` to verify.

### Hybrid: vector + full-text BM25

Per `rag-design` — hybrid is the production default.

```sql
-- Approach 1: combine in SQL with score normalization
WITH vector_results AS (
    SELECT id, embedding <=> $1 AS distance, ROW_NUMBER() OVER (ORDER BY embedding <=> $1) AS rank
    FROM document_chunks
    ORDER BY embedding <=> $1
    LIMIT 50
),
bm25_results AS (
    SELECT id, ts_rank(content_tsv, plainto_tsquery('english', $2)) AS score,
           ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, plainto_tsquery('english', $2)) DESC) AS rank
    FROM document_chunks
    WHERE content_tsv @@ plainto_tsquery('english', $2)
    LIMIT 50
)
SELECT 
    c.id, c.content, c.source_url, c.title,
    -- Reciprocal Rank Fusion (RRF)
    COALESCE(1.0 / (60 + v.rank), 0) + COALESCE(1.0 / (60 + b.rank), 0) AS rrf_score
FROM document_chunks c
LEFT JOIN vector_results v ON v.id = c.id
LEFT JOIN bm25_results b ON b.id = c.id
WHERE v.id IS NOT NULL OR b.id IS NOT NULL
ORDER BY rrf_score DESC
LIMIT 20;
```

For full-text search, maintain a `tsvector` column:

```sql
ALTER TABLE document_chunks ADD COLUMN content_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_chunks_content_tsv ON document_chunks USING GIN (content_tsv);
```

## Per-tenant filtering (multi-tenancy)

Per `multi-tenancy` SKILL:

```sql
SELECT * FROM document_chunks
WHERE tenant_id = $1   -- ALWAYS include
  AND embedding <=> $2 < 0.5
ORDER BY embedding <=> $2
LIMIT 10;
```

Add `tenant_id` to the table + every query. Consider row-level security (RLS) for defense in depth.

## Inserting and updating

### Single insert
```sql
INSERT INTO document_chunks (document_id, chunk_index, content, embedding, source_url, title)
VALUES ($1, $2, $3, $4::vector, $5, $6);
```

### Bulk insert (much faster)
```python
import psycopg
from psycopg.rows import dict_row

with psycopg.connect(conninfo) as conn:
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO document_chunks 
               (document_id, chunk_index, content, embedding, source_url, title)
               VALUES (%(document_id)s, %(chunk_index)s, %(content)s, %(embedding)s, %(source_url)s, %(title)s)""",
            rows,
        )
```

For very large bulk loads, use `COPY` with vectors serialized as text.

### Update embeddings (after switching models)
This is expensive — every chunk needs re-embedding. Plan as a migration:

1. Add new column `embedding_v2 vector(N2)`.
2. Backfill in batches (with checkpointing).
3. Build new HNSW index on `embedding_v2`.
4. Cut queries over.
5. Drop old column.

## Performance characteristics

| Corpus size | Approximate query latency (HNSW, m=16, ef_search=40) |
|---|---|
| 100K vectors | ~1-5ms |
| 1M vectors | ~5-20ms |
| 10M vectors | ~20-100ms |
| 100M+ vectors | pgvector strained; consider purpose-built |

These assume `embedding` column is in shared_buffers. If it spills to disk, multiply by 10x.

Memory: ~2KB per vector for 1536-dim float32 + HNSW overhead. 1M vectors ≈ 2-3 GB.

## Gotchas

- **HNSW index build is slow** for large corpora — minutes to hours for 10M vectors. Build during off-hours.
- **HNSW index can't be created concurrently with `CREATE INDEX CONCURRENTLY`** as of pgvector 0.8. Plan for a brief lock or build on a read replica.
- **Vector column not in shared_buffers = slow** — size shared_buffers for the working set.
- **Cosine distance returns 1 - cosine_similarity**. So smaller = more similar. Don't confuse with similarity scores.
- **Don't use `<->` (L2) on un-normalized vectors and expect cosine semantics**. Normalize at embedding time OR use cosine operator.
- **Backups include the embeddings** — significant size impact. Plan retention.

## Hybrid with reranking (full RAG pipeline)

```python
# 1. Query vector store for top 50 candidates (vector OR hybrid)
candidates = await pg.fetch(
    "SELECT id, content, source_url, title FROM document_chunks "
    "ORDER BY embedding <=> $1 LIMIT 50",
    query_embedding,
)

# 2. Cross-encoder reranker scores each candidate against the query
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')
pairs = [(query, c['content']) for c in candidates]
scores = reranker.predict(pairs)

# 3. Sort by reranker score and keep top 5-10
top_n = sorted(zip(candidates, scores), key=lambda x: -x[1])[:5]

# 4. Pass to LLM for grounded generation
```

## Common rationalizations

| Thought | Counter |
|---|---|
| "We need Pinecone for serious work." | Most projects fit in pgvector. Switch when measured ANN search is your bottleneck. |
| "Single embedding model forever." | Models improve. Plan for embedding migration; design the schema with a versioned column. |
| "Cosine vs L2 doesn't matter." | It matters. Use the right operator for your embedding model's normalization. |
| "I don't need metadata filtering." | You will. Hybrid filtering is the killer feature; design metadata in from the start. |
| "Just store everything in one table." | Document → chunks design with foreign keys lets you cascade delete (per `compliance-privacy` DSR). |

## Verification (per `rag-design` SKILL)

- [ ] Extension enabled; correct vector dimension.
- [ ] HNSW index built; `ef_search` tuned for recall vs latency.
- [ ] Metadata columns + GIN indexes for filtering.
- [ ] Tenant isolation (column + query discipline).
- [ ] Hybrid (vector + BM25) implemented if production-grade.
- [ ] Reranker wired into the pipeline.
- [ ] Citation works (source_url + title surfaced in responses).
- [ ] Retrieval evaluation suite measures recall@K + precision@K (per `evaluation-engineering`).

## Official sources

- pgvector: https://github.com/pgvector/pgvector
- pgvector best practices: https://github.com/pgvector/pgvector#querying
- HNSW paper: https://arxiv.org/abs/1603.09320
- Reciprocal Rank Fusion paper: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
