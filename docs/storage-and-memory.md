# Storage, evidence and memory

What Praxis keeps in `.project/`, what it keeps out of git, and how memory stays
small. Applies to Claude Code, Codex and Antigravity alike: everything here is
plain files plus scripts that any of them can run.

## Layout

```
.project/
  .gitignore                    managed block: local/, raw telemetry, locks
  governance/memory-layout.yaml where each kind of memory lives (project copy wins)
  semantic/ episodic/ procedural/ decision/ operational/   durable memory (committed)
  operational/verification/     praxis-verify run summaries (committed, small)
  working/                      ledgers and active-slice notes (committed)
  working/lanes/<lane>/         per-lane additions to shared files
  index/ INDEX.yaml             generated index
  telemetry/                    raw *.jsonl (ignored); summaries/ (committed)
  local/                        GITIGNORED, machine-local, safe to delete
    evidence/<task>/<run>/      full verify output and artifacts
    evidence/legacy/            old evidence moved out by migrate-local
    scratch/                    run scratch
    bin/                        shims: praxis-verify, praxis-memory, praxis-commit-trailer
    reports/                    weekly dry-run memory reports
```

Session start creates all of this, idempotently, in every tool. It installs the
`prepare-commit-msg` hook only where the repository has none.

## Verification

```bash
.project/local/bin/praxis-verify T3            # run task T3's verify command, record the result
git log --grep "Praxis-Verified: none"          # commits nothing on record verified
```

See `references/loop-contracts.md` for the gate rules.

## Memory

| Command | What it does |
|---|---|
| `praxis-memory map` | The ≤ 40-line map the session banner shows |
| `praxis-memory where adr` | Path for a kind (from `memory-layout.yaml`) |
| `praxis-memory index` | Regenerate `.project/INDEX.yaml` and `.project/index/` |
| `praxis-memory check` | Frontmatter, broken links, budgets, raw evidence in memory |
| `praxis-memory migrate-local [--apply]` | Move old logs, JUnit, dumps, screenshots into `local/evidence/legacy/` and untrack them |
| `praxis-memory consolidate [--apply]` | Archive closed-slice and stale working notes, collapse review rounds, trim the inbox, merge lane notes, prune old evidence |
| `praxis-memory consolidate --print-prompt` | Prompt for the model-side pass that re-checks injected facts |
| `praxis-memory review-context --base main` | REVIEW.md and the matching diff-triggered checks, read from base |

Everything that changes files is a dry run unless `--apply` is given. `--apply`
moves notes with `git mv`, never deletes a memory note, never rewrites git
history, and leaves a record plus an old→new path map in
`.project/operational/memory-maintenance/`.

## Migrating an existing project

1. Start a session (or run `python3 <plugin>/hooks/praxis_project.py ensure . --plugin-root <plugin>`)
   so `.project/.gitignore` and the shims exist.
2. `praxis-memory migrate-local` — read the dry run, then `--apply`, then commit
   the removals with `.project/.gitignore`. Files stay on disk; only git stops
   tracking them. Git history keeps the old blobs; shrinking it needs
   `git filter-repo` and a re-clone for everyone, which is a separate decision.
3. `praxis-memory consolidate` — read the dry run, then `--apply`, commit.
4. `praxis-memory index` and `praxis-memory check`.
5. If your ADRs (or other kinds) live elsewhere, edit
   `.project/governance/memory-layout.yaml` once.
