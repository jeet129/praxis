# Review rules and diff-triggered checks

Two project files tell reviewers what this codebase cares about. Both are read
from the **base branch** (`praxis-memory review-context --base <branch>`), never
from the branch under review, because a change must not be able to edit its own
judge. Their paths come from `.project/governance/memory-layout.yaml`
(`review_rules`, `review_checks`), also read from base.

## `.project/procedural/REVIEW.md`

Short, plain guidance for the primary reviewer: what matters most in this
codebase, what to ignore, known traps. Keep it under a page; it is passed to
every review lens. Tune this file before adding more reviewers.

## `.project/procedural/checks.yaml`

Each check is a lesson learned from a real incident, revert or review, with a
trigger a script can match against the diff. Reviewers evaluate only the checks
whose triggers match (typically a handful), so the list can grow without making
every review slower.

```yaml
checks:
  - id: RC-001
    trigger:
      paths: ["src/migrations/**"]   # globs; omit to match any changed file
      diff: "DROP COLUMN"            # optional regex over added lines
    check: "A migration that drops a column has a backfill step before it."
    origin: "incident-2026-08-12-orders-null"   # incident, review or PR it came from
    severity: blocker                            # optional default
```

Rules for adding a check (from how the Claude Code team runs theirs):

- The pattern has shown up in at least two PRs, reviews or incidents, and it is
  recognisable from a diff.
- Name its origin, so anyone can see why it exists and delete it when the
  underlying risk is gone.
- Try to disprove it first: would it have fired on recent clean merges? A check
  that fires on everything gets ignored.
- Prune: when a check has not fired usefully for a quarter, or the code it
  guards is gone, remove it. Unpruned rules cost every review.

`praxis-memory consolidate --print-prompt` asks the offline consolidation pass
to propose new checks from recurring lessons in episodic and review notes.

## Severity

Findings are `blocker`, `major`, `minor` or `pre-existing`. A pre-existing
problem is real but predates the change: it is reported, never blocks the
author, and belongs in the debt register.
