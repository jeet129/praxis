# Context budget for long, multi-slice runs

Why tokens pile up, and what Praxis does about it on every tool.

## The cost model

Every tool call re-sends the whole conversation so far (mostly from the prompt
cache). A task's cost is therefore roughly **turns × context size**, and a
session that is carried from task to task re-reads all of its history on every
call of every later task. In one project's drive telemetry the median task read
about 1.6M tokens of context, and the most expensive were failed or blocked
attempts.

## Rules

| Situation | Do | Why |
|---|---|---|
| Next task or slice | Fresh session (`/clear`, Codex `/new`); the ledger is the hand-off | Costs a few thousand tokens to re-orient; carrying the session re-reads everything |
| Same task, context bloated by exploration | Compact with a focus hint (`/compact keep task T3, failing tests, decisions`) | Lossy but keeps continuity |
| An approach failed | Rewind to before it, or write task `notes` and start fresh | Appending corrections keeps the failed attempt in every later call |
| Verbose, throw-away output (tests, logs, wide search) | Subagent; only its conclusion returns | Keeps intermediate output out of the parent |
| Specialist work | New subagent per task, report under ~1,500 tokens | Resumed subagents re-read their whole history |

## What Praxis enforces

- **Headless drive** (`praxis-drive.sh`, Codex controller) runs one task per
  fresh session, with a per-tier turn cap (`context_budget.max_turns_by_tier`
  in `governance/autonomy.yaml`), and flags any task whose context reads exceed
  `iteration_alert_tokens` (`.project/telemetry/budget-alerts.jsonl`, status view).
- **In-session drive** (`/drive` on Claude Code and Antigravity, `$praxis-drive`
  on Codex) runs every task in a fresh specialist subagent; the orchestrating
  session only keeps briefs and short reports, so it grows by a few thousand
  tokens per task instead of hundreds of thousands. No hook can clear a session,
  so the drive never stops for the budget: at every `session_max_tasks` finished
  tasks, or `session_max_context_tokens` of transcript since the last compaction,
  it keeps going (automatic compaction handles growth) and the person sees a
  one-line hint that it is a good moment to `/clear` (Codex `/new`) and restart
  the drive. `on_session_budget: ask` restores a stop-and-ask hand-off.
- **Subagents** carry `maxTurns` per tier (`governance/model-routing.yaml`
  `turns_map`). The delivery-lead briefs by path, asks for short reports, and
  never resumes a long-running specialist.
- **Compaction instructions**: `praxis-memory context-setup --apply` adds a
  managed `# Compact instructions` block to CLAUDE.md and a `compact_prompt` to
  `.codex/config.toml`, so automatic compaction keeps the task id, verify
  command, failing tests, decisions and next step and drops raw output.

## Parallel lanes

Running independent slices in parallel worktrees does not, by itself, cost more
tokens than running them one after another: each lane is a fresh session either
way. What changes is when the tokens are spent and what can go wrong:

- **Rate, not total.** Parallel lanes spend the same tokens in a shorter time, so
  they hit the plan's rolling usage window and the API rate limits sooner.
- **Prompt cache.** Sessions started back to back in one checkout can reuse the
  cached system prompt and project instructions; worktrees at different paths
  generally start their own cache. This is a small cost (one prefix per session).
- **Rework.** A lane works from the base as it was when the lane started. If two
  "independent" slices turn out to touch the same code, the conflict or the
  re-done exploration is real extra cost that serial runs avoid, because the
  second slice would have started from the first one's merged result.

So limit lanes for rate limits and conflict risk, and declare `depends_on_slices`
honestly. Agent teams are different: teammates coordinate and run in parallel on
one task, and Claude Code's docs put them at about seven times a standard
session's tokens in plan mode.
