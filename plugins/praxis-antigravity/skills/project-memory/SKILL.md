---
name: project-memory
description: "Owns writes to the .project/ memory tree (semantic, episodic, procedural, decision, working, operational). Use when recording project state."
---

# Project Memory

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
listing_tier: A
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
  - per-entry frontmatter (type, date, source) for indexing by memory-management
consumers:
  - using-praxis
  - memory-management (consumes the writes)
  - all role agents (AOP Document step)
references: []
```
<!-- praxis:metadata:end -->

The persistent state primitive that makes the Praxis survive coding-assistant changes. `.project/` lives in the project's repository root (or a parallel directory if the project is being driven without source control), and any assistant that can read files can reconstruct the project's full state by reading it.

This skill owns the **write side**. `memory-management` (sister skill) owns the read side at scale — index, retrieval, compaction.

## When this skill fires

- At project initialization — orchestrator creates `.project/` with the six-type taxonomy (session start then adds the gitignored `.project/local/`, `.project/.gitignore` and `memory-layout.yaml`).
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

## Where things live (configurable)

The six folders above are defaults. `.project/governance/memory-layout.yaml`
(seeded at session start, the project copy wins) maps each kind to a path, so a
project whose ADRs already live in `docs/adr/` or `Ship/adr/` points `adr` there
instead of keeping two places. Resolve a path before writing:

```bash
.project/local/bin/praxis-memory where adr      # -> .project/decision, or the project's override
```

## What is not memory

Raw run output is **evidence**, not memory, and never goes in these folders:
test logs, JUnit XML, coverage, SQL dumps, screenshots, fixtures copied for a
run, `*-run/` directories. It lives in the gitignored `.project/local/`:

- verify output: `.project/local/bin/praxis-verify <task>` writes the full log to
  `.project/local/evidence/<task>/<run>/` and a small committed summary to
  `.project/operational/verification/`.
- other run artifacts: `.project/local/scratch/` (or `$PRAXIS_EVIDENCE_DIR`
  inside a verify command).

A memory note may *point* at evidence (path, run id, the summary file); it
never contains the raw output. `praxis-memory migrate-local` moves old
evidence out of existing projects.

## Frontmatter (three required fields)

```yaml
---
type: decision | episodic | semantic | procedural | operational | working
date: YYYY-MM-DD
source: <agent, human, or the slice/review/incident this came from>
# optional, add only when they help retrieval:
title: <if the first heading is not enough>
tags: [tag1, tag2]
impacted_domains: [billing, auth]
related: [<path or note name>]
supersedes: <id>        # decisions
confidence: high | medium | low
---
```

`praxis-memory index` builds `.project/INDEX.yaml` from whatever is there and
falls back to the folder, the filename date and the first heading, so a
missing optional field costs nothing. ADRs keep the full template from
`adr-decision-records`.

## When to write (and when not to)

Write a note when **a future session would act differently because of it**: a
decision and its reason, a verified fact about the system that is expensive to
rediscover, a correction to something memory got wrong, a lesson from a failure
that is likely to recur. Writing a note is a prediction that it will matter
again; most step-by-step progress will not.

Do not write: progress narration, a restatement of the diff, copies of tool
output, a new file per review round (append the round to the topic's file), or
a per-slice register for something that belongs in the durable register.

At the AOP **Document** step, the agent decides whether anything meets that
bar; "nothing new worth keeping" is a valid outcome. Required governance
records (ADRs, incident records, checkpoints a workflow demands, risk
acceptances) are always written; they are not optional notes.

Correct, don't accumulate: if an existing note is wrong, fix it (or for
append-only kinds, add a dated correction) rather than writing a second note
that disagrees with it.

## Mode handling (G/B)

**Greenfield.** Initialize `.project/` with the six-type structure (indexes are generated later by `praxis-memory index`; do not hand-write them). Seed `semantic/glossary.md` with empty headers; the PM and SA fill these in Phase A and B.

**Brownfield.** If `.project/` already exists, read it on entry — *do not overwrite*. If it doesn't exist (the codebase predates the platform), bootstrap by extracting what's available from existing ADR files, postmortem docs, README, etc. — and add `.project/episodic/bootstrap-{date}.md` recording what was reconstructed and what was inferred vs. found. Future writes follow the standard procedure.

## Parallel writers

When several agents or lanes run at once, give each writer its own files; never
have parallel writers edit one shared file (an inbox, a register, a table).
Shared-table writes overwrite each other.

- Inside a parallel lane (`$PRAXIS_PARALLEL_LANE` is set), write additions for
  shared files to `.project/working/lanes/<lane>/<topic>.md` with frontmatter
  `append_to: <target path>`. `praxis-memory consolidate` merges them into the
  target after the lane lands.
- Quote source material verbatim (contract terms, error text, ADR decisions)
  instead of summarising it into a shared table.
- Slice-named files (`slice-<id>-*.md`) are already per-lane.

For multi-project ownership (a single human running multiple projects from the
same toolset), each project has its own `.project/`; no cross-project memory at
this layer.

## What this skill does not do

- Retrieval at scale — that's `memory-management`. This skill writes; that one reads.
- Compaction — also `memory-management`.
- ADR templating — that's `adr-decision-records`; this skill receives the templated ADR and writes it to `decision/`.
- Indexing — `memory-management` maintains the index; this skill triggers the update.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'll keep state in my head; faster." | Your head ends at session end. The next session reads `.project/`; if the decision isn't there, the next agent starts from zero. |
| "I'll record everything, just in case." | Over-recording is the commonest memory failure: hundreds of stale files the next agent wades through or trusts. Write what will change a future decision. |
| "I'll paste the test output so the note is complete." | Output is evidence. Run `praxis-verify` and reference the run; the note stays readable and the log stays out of git. |
| "Memory-type choice is overhead." | Misfile semantic into working and it is archived with the slice. Pick the kind; `praxis-memory where` gives the path. |
| "I'll write a new note; the old one is wrong but someone might need it." | Two disagreeing notes are worse than one. Correct the old one (dated correction for ADRs/incidents). |
| "ADRs aren't memory; they're documents." | ADRs ARE decision-type memory, and they live where `memory-layout.yaml` says. |

## Verification

You are done writing a memory entry when:

- [ ] It meets the bar: a future session would act differently because of it.
- [ ] It is in the folder `praxis-memory where <kind>` returns.
- [ ] Frontmatter has `type`, `date`, `source`.
- [ ] It contains no raw tool output; evidence is referenced by path or run id.
- [ ] It does not duplicate or contradict an existing note (search first: `.project/INDEX.yaml`).
- [ ] Links resolve (`praxis-memory check` reports none broken).
- [ ] It reads in two minutes; longer content is split, with the detail linked.
- [ ] For decisions: ADR template followed; status is `proposed` / `accepted` / `superseded by ADR-NNN`.

## Portability

Because `.project/` is plain markdown with structured frontmatter, any coding assistant that can read files can consume it. Claude Code reads it as part of its context; Codex reads it via AGENTS.md routing; Cursor reads it via its memory mechanism. The format is the contract.
