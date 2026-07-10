# RAG worked examples

Worked artifacts and reference tables supporting `rag-design`. Load this file when you need the full artifact behind a SKILL.md pointer.

## Chunk metadata — worked JSON example

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

## Citation — worked example

```
Answer: To install the SDK, run `npm install @company/sdk` and add the import to
your `app.ts` file. After import, initialize with your API key from the dashboard.

Sources:
[1] Setup → Installation (last updated 2026-10-12)
[2] Quickstart (last updated 2026-10-05)
```

## Embedding model classes — full table

| Class | Examples | Use when |
|---|---|---|
| **Open-source small** | all-MiniLM-L6-v2, BGE-small | Self-hosted; budget-constrained; English. |
| **Open-source large** | BGE-large, mxbai-embed-large | Self-hosted; higher quality. |
| **Multilingual** | multilingual-e5, BGE-M3 | Non-English / multilingual corpora. |
| **Domain-specific** | code (codebert), biomedical (PubMedBERT) | Specialized domain. |
| **Hosted (commercial)** | OpenAI text-embedding-3-large, Cohere Embed v3, Voyage AI | Higher quality; pay-per-use; no self-hosting. |
