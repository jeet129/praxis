# Memory consolidation — the model-side pass

Run this offline, between work sessions, on a standard-tier model (headless:
`claude -p`, `codex exec`, or an Antigravity task). The mechanical half has
already run (`praxis-memory consolidate`): closed-slice notes are archived,
review rounds collapsed, the inbox trimmed. Your job is the half that needs
judgement: keep what the project relies on **true**, and keep the layer that
is injected into every session **small**.

You are not doing project work. Do not change code. You only propose changes
to memory notes, as one patch for a human to review.

## What memory is for

Memory exists so the next session starts from what is known and verified
instead of re-deriving it, and does not repeat a mistake already made. A note
earns its place if a future session would act differently because of it. A
wrong note is worse than a missing one: agents trust what they read.

## Steps

1. **Read the map first.** `.project/local/bin/praxis-memory map`, then the
   injected files listed at the end of this prompt and the project's
   CLAUDE.md / AGENTS.md / GEMINI.md.
2. **Check every factual claim in the injected layer against its source.**
   Cloud provider, regions, service names, commands, file paths, versions,
   owners. Look in the code, infrastructure files, CI config and `git log`.
   For each claim that is wrong or no longer true, propose the corrected line
   and cite the file that proves it. Do not "fix" what you cannot verify;
   list it as unverified instead.
3. **Keep the injected layer small.** If an injected file is over its budget
   (`praxis-memory check`), move detail into a linked note and leave a
   one-line pointer. Never move a rule that prevents a known failure out of
   the injected layer.
4. **Merge duplicates.** Two notes saying the same thing become one; the other
   becomes a one-line pointer or is archived.
5. **Promote what recurs.** A lesson that appears in two or more episodic or
   review notes, and that a future session should apply, becomes one line in
   `procedural/` (or a diff-triggered check in `procedural/checks.yaml` when it
   can be recognised from a diff: give it a trigger and the incident or review
   it came from).
6. **Demote what is stale.** Assumptions marked resolved, plans that shipped,
   per-slice registers of closed slices: fold the still-true part into the
   durable register and archive the rest.
7. **Fix broken links** reported by `praxis-memory check`.

## Rules

- Quote sources verbatim when a fact matters; do not paraphrase a contract,
  an ADR decision or an error message into a summary.
- ADRs, incidents and risk acceptances are append-only: add a dated
  correction, never rewrite history.
- Do not add frontmatter ceremony. A note needs `type`, `date` and `source`;
  everything else is optional.
- Output: one unified diff against the current tree, followed by a short list
  of claims you could not verify. Nothing else.
