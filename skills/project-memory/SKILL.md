---
name: project-memory
description: Owns the write side of `.project/` — the persistent project memory directory structured by the six memory types (semantic / episodic / procedural / decision / operational / working). Every agent reads `.project/` on entry and writes to it via the AOP Document step. Use this skill whenever the orchestrator initializes a project, an agent completes a phase and needs to record decisions or context, an ADR is created or superseded, an incident closes and needs operational memory recorded, or a slice opens and `working/` needs to be primed. Project memory is what makes the platform portable across coding assistants — any tool that can read files can reconstruct project state.
capability: foundation
domain: cross-cutting
state: active
dependencies: []
triggers:
  - "initializing a new project"
  - "completing a phase and recording outputs"
  - "creating or superseding an ADR"
  - "closing an incident or postmortem"
  - "opening or closing a slice (working memory)"
  - "capturing an assumption, constraint, risk, or open question"
outputs:
  - .project/ directory populated with the six memory types
  - per-entry frontmatter with metadata for indexing by memory-management
consumers:
  - using-praxis
  - memory-management (consumes the writes)
  - all role agents (AOP Document step)
references: []
---

# Project Memory

The persistent state primitive that makes the Praxis survive coding-assistant changes. `.project/` lives in the project's repository root (or a parallel directory if the project is being driven without source control), and any assistant that can read files can reconstruct the project's full state by reading it.

This skill owns the **write side**. `memory-management` (sister skill) owns the read side at scale — index, retrieval, compaction.

## When this skill fires

- At project initialization — orchestrator creates `.project/` with the six-type taxonomy.
- At phase exit — the agent completing the phase invokes this skill to write its outputs to the right subtree.
- At ADR creation, supersession, or amendment — writes to `decision/`.
- At incident close or postmortem — writes to `operational/`.
- At slice open — primes `working/` with the current implementation packet.
- At slice close — archives `working/` content to `episodic/` (or compacts via `memory-management`).
- At assumption / constraint / risk / open-question capture — writes to the appropriate subtree.

## The six memory types

The taxonomy follows how cognitive science describes long-term and working memory, and how AI-agent research has formalized it. Each subtree has a distinct lifecycle, write pattern, and reader audience.

```
.project/
├── semantic/        domain models, ubiquitous language, glossary
├── episodic/        sprint/iteration history, slice timeline, what-happened-when
├── procedural/      how-we-do-things, local engineering-standards overlays
├── decision/        ADRs (indexed), rejected alternatives, decision deltas
├── operational/     incidents, runbooks, postmortem index, change log
└── working/         current-slice state — implementation packet, in-flight work
```

### semantic/

The project's *what*. Domain entities, value objects, aggregates, bounded contexts (from `domain-discovery`), the ubiquitous-language glossary. Stable: once written, mostly read; updated when the domain model evolves.

Files: `glossary.md`, `bounded-contexts.md`, `entity-{name}.md` per significant entity.

### episodic/

The project's *story*. Sprint or iteration history, slice completion records, what-happened-when. Append-only. Compacted by `memory-management` when entries age past their relevance window (typically 6–12 months for sprint records; permanent for major milestones).

Files: `slice-{N}-{name}.md` per slice; `milestone-{date}-{name}.md` for releases.

### procedural/

The project's *how*. Local overlays on `engineering-standards` (e.g., this project uses 4-space indent against the 2-space house default), runbook conventions, deployment-specific procedures, escalation patterns. Stable.

Files: `local-standards.md`, `deployment-runbook.md`, `escalation.md`.

### decision/

The project's *why*. ADRs (managed by `adr-decision-records`), rejected alternatives, decision deltas (when a prior decision is superseded). Append-only; supersession is recorded, not destructive.

Files: `adr-{NNNN}-{slug}.md`. Index at `decision/INDEX.md` maintained by `memory-management`.

### operational/

The project's *production reality*. Incidents (per-incident records), postmortems (indexed by date and severity), change log (production deployments), runbook references. Append-only in incident granularity; postmortems may be amended with later learnings.

Files: `incident-{date}-{slug}.md`, `postmortem-{date}-{slug}.md`, `changelog.md`.

### working/

The project's *current state*. The implementation packet for the active slice, in-flight design notes, agent hand-off material. Per-slice and reset between slices. Archived to `episodic/` on slice close.

Files: `current-slice.md`, `implementation-packet.md`, `in-flight-{topic}.md`.

## Frontmatter schema

Every entry in `.project/` carries frontmatter so `memory-management` can index it:

```yaml
---
type: decision | episodic | semantic | procedural | operational | working
title: <human-readable title>
date: YYYY-MM-DD
author: <agent or human name>
tags: [tag1, tag2, ...]                    # for retrieval by topic
impacted_domains: [billing, auth, ...]      # bounded contexts touched
confidence: high | medium | low             # how settled is this?
supersedes: <entry-id-if-applicable>       # for decision/ entries
superseded_by: <entry-id-if-applicable>   # back-reference
related: [<entry-id>, ...]                  # cross-references
slice: <slice-id-if-applicable>             # which slice produced this
---
```

The `tags`, `impacted_domains`, and `confidence` fields are what make retrieval at scale possible (R3.2). Without the metadata, 500-entry `.project/` becomes search-by-grep.

## The AOP Document step

Every agent invokes this skill at the **Document** step of the AOP lifecycle (Section 7 House Conventions). The agent passes:

1. The memory type its output belongs to.
2. The full entry content (markdown body).
3. The frontmatter metadata (the agent knows the slice, the author, the impacted domains, etc.).

This skill validates the frontmatter, writes the entry to the correct subtree, and triggers `memory-management` to update the index. Writes are serialized when multiple agents finish in parallel on the same slice — the orchestrator owns the lock.

## Mode handling (G/B)

**Greenfield.** Initialize `.project/` with the six-type structure and empty `INDEX.md` files in each subtree. Seed `semantic/glossary.md` with empty headers; the PM and SA fill these in Phase A and B.

**Brownfield.** If `.project/` already exists, read it on entry — *do not overwrite*. If it doesn't exist (the codebase predates the platform), bootstrap by extracting what's available from existing ADR files, postmortem docs, README, etc. — and add `.project/episodic/bootstrap-{date}.md` recording what was reconstructed and what was inferred vs. found. Future writes follow the standard procedure.

## Single-writer discipline

`.project/` is a single-writer-at-a-time store. The orchestrator serializes writes when multiple agents run in parallel on the same slice. Concurrent writes are a violation; the orchestrator queues them. This keeps the directory deterministic and prevents merge conflicts during agent execution.

For multi-project ownership (a single human running multiple projects from the same toolset), each project has its own `.project/`; no cross-project memory at this layer.

## What this skill does not do

- Retrieval at scale — that's `memory-management`. This skill writes; that one reads.
- Compaction — also `memory-management`.
- ADR templating — that's `adr-decision-records`; this skill receives the templated ADR and writes it to `decision/`.
- Indexing — `memory-management` maintains the index; this skill triggers the update.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll keep state in my head; faster." | Your head ends at session end. The next session reads `.project/`; if it's empty, the next agent starts from zero. |
| "Memory-type choice is overhead." | The taxonomy is what makes recall work. Misfile semantic into working and it disappears at session end. |
| "Seven-field frontmatter is verbose." | Memory-management indexes by frontmatter. No frontmatter = invisible to retrieval = not really memory. |
| "I'll write it as plain text; format it later." | Memory written without frontmatter never gets indexed; it sits forgotten. Format at write time. |
| "ADRs aren't memory; they're documents." | ADRs ARE decision-type memory. Same write-side discipline; same indexable frontmatter. |
| "We don't need episodic memory; just write incidents in a log." | Episodic memory carries lessons. A log is data; episodic is structured insight. Different artifact. |

## Verification

You are done writing a memory entry when:

- [ ] File is in the correct subdirectory (semantic / episodic / procedural / decision / operational / working).
- [ ] Seven-field frontmatter is present and complete: `type`, `title`, `date`, `author`, `tags`, `confidence`, plus type-specific fields.
- [ ] Filename follows the type's naming convention (`YYYY-MM-DD-NNN-title.md` for episodic; `INDEX.md` exists for decision).
- [ ] Cross-references to related memory entries are explicit (`see: <path>`).
- [ ] Content is short enough to be read in 2 minutes (long content gets split or summarized).
- [ ] For decisions: ADR template followed; status is `proposed` / `accepted` / `superseded by ADR-NNN`.
- [ ] For working memory: aging policy noted (when this graduates to episodic OR gets removed).

Evidence to check:
- `memory-management` can index the entry without modification.
- A reader who finds the entry via index can act on it without reading other files.

## Portability

Because `.project/` is plain markdown with structured frontmatter, any coding assistant that can read files can consume it. Claude Code reads it as part of its context; Codex reads it via AGENTS.md routing; Cursor reads it via its memory mechanism. The format is the contract.
