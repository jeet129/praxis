---
name: rag-design
description: Retrieval-Augmented Generation done right. Corpus design, chunking strategy, embedding model choice, hybrid retrieval (vector + BM25), reranking, query rewriting, citation, retrieval evaluation. Pairs with `evaluation-engineering` for measurement and with `agentic-architecture` for system integration. Most "the LLM made it up" failures are retrieval failures, not generation failures — get retrieval right and the generation problem shrinks dramatically. ML/AI Engineer owns this; Data Engineer co-designs the ingestion pipeline (per `data-pipeline`). Use whenever a feature needs the LLM to ground in specific documents, when designing the RAG corpus, when investigating low groundedness, or when choosing retrieval architecture.
---

# RAG Design


<!-- praxis:metadata:begin -->
```yaml
capability: agentic-ai
domain: ml
state: active
dependencies:
  - agentic-architecture
  - data-pipeline
  - data-quality
  - evaluation-engineering
triggers:
  - "designing a RAG system from scratch"
  - "investigating low groundedness / hallucinations"
  - "choosing embedding model + vector store"
  - "designing chunking strategy for a corpus"
  - "wiring hybrid retrieval (vector + BM25)"
  - "adding reranking or query rewriting"
  - "establishing citation discipline for grounded responses"
outputs:
  - retrieval architecture (embedder + vector store + BM25 + reranker)
  - ingestion pipeline spec (chunking + metadata + update strategy)
  - retrieval-eval suite (per `evaluation-engineering`)
  - citation policy (when + how to cite)
  - corpus governance (what goes in; what's excluded; freshness SLO)
consumers:
  - ml-ai-engineer (primary author)
  - data-engineer (operates the ingestion pipeline)
  - agentic-architecture (consumes for tool-call design)
  - evaluation-engineering (consumes for retrieval metrics)
  - llm-safety (consumes for grounded-output verification)
references:
  - pgvector.md
  - qdrant.md
  - weaviate.md
  - pinecone.md
  - vespa.md
  - elasticsearch.md
```
<!-- praxis:metadata:end -->

The discipline that makes LLMs accurate when accuracy depends on specific documents. Most "the LLM hallucinated" complaints are retrieval failures — the LLM was asked to generate from documents it didn't have access to, or had access to the wrong documents. Fix retrieval; the generation problem shrinks.

The principle: **garbage retrieval in, garbage generation out. The LLM is only as good as the documents it sees.**

## When this skill fires

- A feature needs the LLM to ground in specific documents (Q&A over docs, customer support over knowledge base, contract review, etc.).
- Hallucination / low groundedness investigation — almost always retrieval issue.
- Embedding model + vector store choice.
- Chunking strategy for a corpus.
- Hybrid retrieval, reranking, query rewriting being added.
- Citation discipline being established.

## The RAG flow

```
User query
  ↓ (optional) query rewriting / expansion
Retrieval (hybrid: vector + BM25)
  ↓ top-K candidates (often 20-50)
Reranking
  ↓ top-N most relevant (often 3-10)
LLM generation with retrieved context + citation
  ↓
Response with citations
```

Each stage has design choices. Errors compound — bad retrieval no reranker can fix.

## Corpus design

What goes in the retrieval corpus? The default mistake: dump everything.

Better:

- **Scope per use case** — Q&A over product docs has a different corpus than support tickets.
- **Authoritative versions only** — outdated docs, drafts, deprecated content actively hurt.
- **Metadata-rich** — every chunk carries source URL, last-updated, author, document-type, audience, version.
- **Access-aware** — chunks carry access tags; retrieval respects user permissions.

Corpus governance:

- **Ownership** — every document set has an owner who's accountable for currency.
- **Freshness SLO** — "support docs updated within 7 days of source change."
- **Removal** — deprecated content is *removed*, not just marked.
- **Tenancy** — for multi-tenant: per-tenant corpus or per-tenant filter (per `multi-tenancy`).

## Chunking strategy

Documents are split into chunks for retrieval. The strategy matters more than people initially appreciate.

| Strategy | When |
|---|---|
| **Fixed-size chunks (e.g., 512 tokens)** | Default starting point; works adequately for prose. |
| **Sentence-based** | When semantic boundaries are sentence-level. |
| **Paragraph-based** | When paragraphs encapsulate ideas (typical docs). |
| **Recursive (markdown / structure-aware)** | Best for structured docs — split by heading, then paragraph, then sentence. |
| **Semantic chunking** | LLM-assisted boundary detection; expensive but high-quality for important corpora. |
| **Hierarchical (parent-child)** | Small chunks for retrieval; larger parents passed to LLM. Modern best practice for long docs. |

Chunk overlap:

- 10-20% overlap helps catch boundary cases.
- Too much overlap (>30%) wastes retrieval slots and embedding storage.

Default for new projects: **recursive markdown-aware chunking + 15% overlap**. Move to hierarchical when documents are long and structured.

### Chunk metadata

Every chunk carries:

```json
{
  "id": "doc-uuid:chunk-N",
  "content": "...",
  "source_url": "...",
  "title": "...",
  "section": "Setup → Installation",
  "last_updated": "2026-10-12",
  "document_type": "user-guide",
  "version": "v4.2",
  "tags": ["installation", "configuration"],
  "access": ["public"]
}
```

The LLM uses metadata for citation; retrieval can filter by metadata.

## Embedding model choice

Embedding model maps chunks + queries to vectors. Choices:

| Class | Examples | Use when |
|---|---|---|
| **Open-source small** | all-MiniLM-L6-v2, BGE-small | Self-hosted; budget-constrained; English. |
| **Open-source large** | BGE-large, mxbai-embed-large | Self-hosted; higher quality. |
| **Multilingual** | multilingual-e5, BGE-M3 | Non-English / multilingual corpora. |
| **Domain-specific** | code (codebert), biomedical (PubMedBERT) | Specialized domain. |
| **Hosted (commercial)** | OpenAI text-embedding-3-large, Cohere Embed v3, Voyage AI | Higher quality; pay-per-use; no self-hosting. |

Default for new projects: **OpenAI text-embedding-3-large** (or Voyage for higher quality) for hosted; **BGE-large or M3** for self-hosted.

### Re-embedding cost

When you change the embedding model, the entire corpus must be re-embedded. Plan:

- Embed twice during migration (old + new) for atomic cutover.
- Compute cost: corpus size × embedding cost-per-token.
- Don't switch embedding models casually.

## Vector store choice

| Store | Strength |
|---|---|
| **pgvector** | Postgres extension; familiar; good for < 10M vectors with proper indexing. Default for small-to-medium. |
| **Qdrant** | Open-source; high performance; rich filtering. |
| **Weaviate** | Open-source; built-in modules; multi-modal. |
| **Pinecone** | Managed; great DX; cost grows with scale. |
| **Vespa** | Yahoo's; very large scale + complex ranking. |
| **Elasticsearch** | If already running ES for search; vector support via dense_vector field. |

Default: **pgvector** for small-to-medium projects already on Postgres. **Qdrant** or **Pinecone** for purpose-built. Per the cloud + the agnostic stance, refs are provided for each.

## Hybrid retrieval

Pure vector retrieval misses exact-match queries (`SKU-12345`) and keyword-heavy queries.

**Hybrid** combines vector + BM25 (keyword search):

```
query → [vector search top-50] + [BM25 search top-50] → union → reranker → top-N
```

Implementation:

- **In one store** (Elasticsearch, Vespa, modern Qdrant) — both done natively.
- **In two stores** — vector store + Elasticsearch/OpenSearch; union at the application layer.

Hybrid typically improves recall by 10-30% over vector-only on real-world corpora. **Hybrid is the default for production RAG** in 2026.

## Reranking

After initial retrieval (top 20-50), a reranker scores each candidate against the query for relevance and keeps the top N.

| Reranker | Use when |
|---|---|
| **Cross-encoder (e.g., BGE-reranker, Cohere Rerank)** | Standard; significant accuracy lift. |
| **LLM-as-reranker** | Highest quality; expensive; reserve for low-volume high-stakes. |
| **Custom learned reranker** | When you have labeled relevance data. |

Reranking adds latency + cost but typically lifts retrieval precision substantially.

## Query rewriting

User queries are often poorly suited to retrieval:

- **Underspecified**: "what about the issue?" — what issue?
- **Conversational context required**: "what does that do?" — that what?
- **Multi-question**: "what is X and how does it interact with Y?" — two retrievals needed.

Solutions:

- **HyDE** (Hypothetical Document Embeddings) — LLM generates a hypothetical answer; embed that for retrieval.
- **Query expansion** — LLM rewrites the query into multiple variants; retrieve for each; merge.
- **Multi-query rewriting** — split compound questions.
- **Context conditioning** — rewrite query with conversation history.

Query rewriting has cost; apply when retrieval quality without it is insufficient.

## Citation discipline

Every grounded response cites its sources:

```
Answer: To install the SDK, run `npm install @company/sdk` and add the import to
your `app.ts` file. After import, initialize with your API key from the dashboard.

Sources:
[1] Setup → Installation (last updated 2026-10-12)
[2] Quickstart (last updated 2026-10-05)
```

Citation format options:

- **Inline footnotes** [1] [2] — readable.
- **Sources block at end** — clean.
- **Hover / clickable** — for rich UIs.

The LLM is instructed (via system prompt) to cite. The application post-processes to ensure citations exist for grounded responses. Missing citations are a quality issue.

## Retrieval evaluation (handoff to `evaluation-engineering`)

Retrieval is *measured* via:

- **Recall@K** — fraction of relevant docs in top-K.
- **Precision@K** — fraction of top-K that are relevant.
- **MRR** (Mean Reciprocal Rank) — position of first relevant doc.
- **nDCG** — graded relevance with position discount.

Per `evaluation-engineering`, build a labeled retrieval test set (queries + known-relevant docs) and run regression evals.

End-to-end RAG also evaluated for:

- **Groundedness** — does the answer reflect the retrieved docs (no hallucinated facts)?
- **Faithfulness** — does the answer contradict the retrieved docs?
- **Answer relevance** — does the answer address the query?

LLM-as-judge or rule-based metrics for these. The eval suite is `evaluation-engineering`'s territory.

## Outputs

| Output | Location |
|---|---|
| Retrieval architecture | `.project/decision/adr-NNN-rag-architecture.md` |
| Ingestion pipeline spec | `pipelines/rag-ingest/` |
| Chunking strategy | inline in ingestion pipeline |
| Citation policy | `.project/procedural/citation-policy.md` |
| Corpus governance | `.project/procedural/rag-corpus-governance.md` |
| Retrieval-eval suite | per `evaluation-engineering` |

## Mode handling (G/B)

**Greenfield.** Build the corpus with metadata + governance from day one. Hybrid + reranker from day one.

**Brownfield.** Audit existing RAG. Common findings: single embedding, no reranker; flat dump of all docs; no metadata; no eval; no citation. Most production RAG systems have improvement opportunities measured in weeks of work, not months.

## What this skill does not do

- Generate the LLM response — that's the LLM call (per `agentic-architecture`'s call-graph design).
- Evaluate end-to-end — that's `evaluation-engineering`.
- Safety / content filtering — that's `llm-safety`.
- Cost optimization — that's `llm-cost-optimization`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Hallucinations are the LLM's fault." | Almost always retrieval's fault. Fix retrieval first; the generation problem shrinks. |
| "One embedding model is fine." | One embedding + naive retrieval is the entry-level setup. Hybrid + reranker is the 2026 production default. |
| "Dump all the docs; retrieval will sort it." | Corpus governance matters. Stale + draft + deprecated content actively hurts retrieval. |
| "Chunks of 512 tokens for everything." | Recursive markdown-aware chunking + 15% overlap is a better default; hierarchical for structured docs. |
| "Metadata is optional." | Metadata enables citation, filtering, access control. Mandatory. |
| "Citations are vibes-y." | Citations are verifiability + audit trail + trust. Enforce them. |
| "Retrieval doesn't need evaluation." | Without retrieval-eval, you don't know if changes help. Recall@K + nDCG matter. |

## Verification

You are done when:

- [ ] Corpus design documented: scope, authoritative versions, metadata schema, access tags.
- [ ] Chunking strategy chosen (recursive markdown-aware default); overlap configured.
- [ ] Embedding model chosen + version pinned.
- [ ] Vector store chosen + indexed.
- [ ] Hybrid retrieval (vector + BM25) configured.
- [ ] Reranker configured (cross-encoder or equivalent).
- [ ] Query rewriting strategy decided per use case.
- [ ] Citation discipline: every grounded response cites sources.
- [ ] Retrieval-eval suite: Recall@K, nDCG, MRR.
- [ ] Corpus governance: ownership, freshness SLO, removal policy.

Evidence to check:
- Eval suite catches retrieval regressions before deploy.
- A response with hallucinated citation fails validation.

## Anti-patterns

- Single embedding model, no reranker, no hybrid.
- Dump the whole knowledge base; no curation.
- No metadata on chunks (no filtering, no citation).
- Chunks too small (loss of context) or too large (one chunk per doc; bad retrieval).
- No retrieval evaluation (works "in our demo").
- LLM hallucinates → blame the LLM (almost always retrieval problem first).
- Embedding model changed without re-embedding (corpus + queries in different spaces).
- No corpus governance (stale + deprecated + draft content polluting retrieval).
- Citations claimed but not enforced (LLM "makes up" plausible citations).
- "RAG is solved with pgvector + chat" — RAG is solved with sustained engineering on each stage.
