---
name: memory-management
description: "Sister to `project-memory` — owns the read side of `.project/` at scale. Maintains an index across all memory-type subtrees (semantic/episodic/procedural/decision/operational/working), exposes retrieval queries the orchestrator and agents use to find relevant memory entries among many, and runs compaction when episodic/working entries age out so the directory stays usable past 500+ entries. Without this skill, project memory becomes search-by-grep at scale. Use whenever an agent needs to find prior decisions, related ADRs, recent incidents, or any subset of memory by topic/domain/time. Pushy trigger because retrieval gets skipped easily."
---

# Memory Management

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - project-memory
triggers:
  - "looking up prior decisions"
  - "finding related ADRs"
  - "retrieving incidents by service or date"
  - "compacting old episodic entries"
  - "searching project memory by tag or domain"
  - "checking what was decided about X"
outputs:
  - .project/INDEX.yaml (top-level index aggregated from per-subtree indexes)
  - retrieval results (markdown digests on query)
  - compacted entries (compressed summaries of aged-out content)
consumers:
  - using-praxis
  - all role agents (memory lookup on phase entry)
  - architecture-pattern-selection (retrieves prior architecture ADRs)
  - codebase-comprehension (correlates memory with repo intel)
references: []
```
<!-- praxis:metadata:end -->

The read side of `.project/`. Where `project-memory` writes, this skill indexes, retrieves, and compacts. Together they keep project memory usable past the 500-entry mark where naïve filesystem lookup falls apart.

## When this skill fires

- An agent enters a phase and needs to read relevant prior memory — *not the whole directory*, just the slice relevant to its task.
- An ADR is being considered and the SA needs to check what prior decisions might be relevant (impacted same domain, superseded by anything, related by tag).
- An incident is being triaged and operational memory needs lookup by service, by date, or by similar past incidents.
- `working/` entries age past slice boundaries and need compaction to `episodic/`.
- `episodic/` entries age past their relevance window and need summarization into compressed forms.

## The index

Each subtree of `.project/` has its own `INDEX.yaml` maintained by this skill, plus a top-level `.project/INDEX.yaml` that aggregates them.

### Per-subtree index format

```yaml
# .project/decision/INDEX.yaml
entries:
  - id: adr-0001-multi-tenancy-pool-model
    title: "Use pool model for tenant isolation"
    date: 2026-02-14
    author: solution-architect
    tags: [tenancy, isolation, postgres]
    impacted_domains: [billing, auth, data]
    confidence: high
    supersedes: null
    superseded_by: null
    related: [adr-0003-noisy-neighbor-controls]
  - id: adr-0003-noisy-neighbor-controls
    ...
```

The index is regenerated whenever `project-memory` writes a new entry; the orchestrator triggers this skill on every successful write.

### Top-level aggregation

```yaml
# .project/INDEX.yaml
counts:
  decision: 42
  semantic: 18
  procedural: 7
  episodic: 156
  operational: 23
  working: 3
by_tag:
  tenancy: [adr-0001, adr-0003, episodic/slice-12, ...]
  auth: [adr-0007, adr-0012, ...]
by_domain:
  billing: [adr-0001, semantic/entity-invoice, ...]
  auth: [adr-0007, semantic/entity-user, ...]
by_date:
  2026-02: [adr-0001, episodic/slice-3, ...]
  2026-03: [...]
```

This is what queries hit. The cost of maintaining it is O(1) per write (append to one or more index lists) plus an occasional rebuild on compaction.

## Retrieval queries

The skill exposes a small set of query patterns the orchestrator and agents call. Each returns a *digest* (titles + paths + frontmatter) rather than full content — the caller fetches full content for the entries it actually needs.

### Query patterns

**By topic/tag.**
```
query: tags=[tenancy]
→ all entries tagged 'tenancy', ranked by recency
```

**By domain.**
```
query: domain=billing
→ all entries impacting billing, grouped by subtree
```

**By relationship.**
```
query: supersedes=adr-0001
query: superseded_by=adr-0001
query: related_to=adr-0001
→ entries in the supersession or related-by chain
```

**By time window.**
```
query: subtree=operational, since=2026-01-01
→ all incidents/postmortems since the date
```

**Combined.**
```
query: subtree=decision, tags=[tenancy, isolation], domain=auth, confidence>=medium
→ filtered intersection
```

### Result shape

```yaml
results:
  - id: adr-0001-multi-tenancy-pool-model
    title: "Use pool model for tenant isolation"
    path: .project/decision/adr-0001-multi-tenancy-pool-model.md
    excerpt: <first 200 chars of body>
    relevance_score: 0.91   # for ranked queries
  - id: ...
```

The agent reads the path for the entries it wants in full; this skill never returns full bodies in the digest. Keeps query results small.

## Compaction

Episodic and working subtrees grow fastest. Without compaction they dominate `.project/` and slow every query.

### Working → Episodic

On slice close, the slice's `working/` content is archived to `episodic/slice-{N}-{name}.md` with the slice timeline, decisions made, agents involved, and key handoffs. The full implementation packet is *not* preserved — only the durable narrative. Original `working/` content is then deleted (it served its purpose).

### Episodic compaction (aged entries)

Entries in `episodic/` older than the relevance window (default 6 months for sprint records, 12 months for milestones — configurable per project) are compacted: the skill produces a `compacted-{period}.md` summary that captures patterns, decisions, milestones, and the key episodic structure for that period, then the individual entries are archived to `episodic/archive/` (still readable but not in the active index).

Compaction is reversible — archived entries can be re-promoted if a later question needs them. But they don't clutter normal retrieval.

### Operational and decision: never compact

These two subtrees are append-only-forever. ADRs and incident records are the project's institutional memory; compacting them loses critical history. The index can be paginated for performance, but the entries stay full.

## Mode handling (G/B)

**Greenfield.** Start with empty indexes; build up as `project-memory` writes accumulate.

**Brownfield.** If `.project/` is being introduced to an existing project, this skill does a one-time bootstrap pass — scan everything in `.project/`, build the indexes from the frontmatter. If entries lack frontmatter (legacy ADRs converted from older formats), tag them `confidence: low` and add them to the index with whatever metadata can be inferred.

## What this skill does not do

- Write entries. That's `project-memory`.
- Decide what gets compacted when — the policy is in the skill body above; the *execution* is here.
- Cross-project memory. Each project has its own `.project/`.
- Embedding-based semantic search. The index is keyword + structured-metadata only. If semantic search becomes necessary, that's a future extension (the index file format is forward-compatible).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll grep for what I need." | Grep finds matches; it doesn't find what you didn't think to search for. The index surfaces related entries. |
| "Reading the whole `.project/` tree is fine." | At 50 entries, fine. At 500, untenable. The index is the scale-out path. |
| "Memory is for archives; live work is in head." | What's in head at session end is lost at session end. Live memory through `.project/` survives. |
| "I'll skip retrieval; just write." | Writing without first checking for existing memory creates duplicates, divergence, and forgotten prior decisions. Read first. |
| "Index is auto-magic; I don't need to think about it." | The index reads the seven-field frontmatter. Missing or wrong frontmatter = missing or wrong index entry. Hand-build it consciously. |
| "Compaction is premature optimization." | Without compaction, working memory grows forever and degrades retrieval signal. Quarterly compaction is the discipline. |

## Verification

You are done querying memory when:

- [ ] Query specified by topic / domain / type / time range (not just "find stuff").
- [ ] Returned entries are scored by relevance, not just date.
- [ ] At least one entry was read end-to-end (not just title-scanned).
- [ ] No surprise hits — if the query surfaced an entry the agent didn't expect, that's investigated.

You are done compacting memory when:

- [ ] Working memory entries older than the slice are graduated to episodic OR removed.
- [ ] Episodic entries with no consumers in 90 days are flagged for archive.
- [ ] Stale semantic entries (reality changed) are reconciled per `architecture-documentation`.
- [ ] Index is rebuilt after any structural change.

Evidence to check:
- Query latency stays under 1 second even at 1000+ entries.
- A new joiner can use the index to navigate without prior knowledge.

## Performance characteristics

The index is a flat YAML file. At 1000 entries the index is ~200 KB — trivially fast to load and search in any process. At 10,000 entries it's ~2 MB — still fine for in-memory query. Beyond that, paginated subtree indexes plus a top-level summary keep query latency bounded. We are not building a database; we are building a discoverable filesystem.
