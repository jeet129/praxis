# Long-running work: controls, evidence and status

This page covers the v0.3.0 controls that make an unattended Praxis run safe to
leave alone. They work the same way in Claude Code, Codex and Antigravity
because they are enforced by one hook script, `hooks/praxis_guard.py`, not by
instructions in a skill.

## The four controls

| Control | How you use it | What happens |
|---|---|---|
| **Kill switch** | `touch .project/STOP` | Every tool call is refused with a message telling the agent to stop and report. `praxis-drive.sh` and the Codex controller stop before the next iteration. Delete the file to resume. |
| **Steer** | Write your note to `.project/STEER.md` | The note is added to the agent's context at its next prompt (Claude Code, Codex) or next model call (Antigravity), once, then archived as `.project/STEER.delivered-<time>.md`. |
| **Evidence gate** | Nothing to do; on by default | An edit that moves a ledger task to `done` is refused unless `praxis-verify` recorded a passing run of the task's current `verify` command against the current code. Agents run `.project/local/bin/praxis-verify <task-id>`; hand-written evidence is refused. When the agent stops, tasks completed in the last 24 hours are re-checked and the agent is sent back (at most twice) if evidence is missing. |
| **Verify freeze** | Nothing to do | A started task's `verify` command cannot change unless the edit adds `verify_changed_reason:`. |
| **Commit trailer** | Nothing to do (opt out: `PRAXIS_COMMIT_TRAILER=off`) | Each commit gets `Praxis-Verified: verify (...)`, `review` or `none`. |
| **Read-only reviewers** | Nothing to do | `code-reviewer`, `security-reviewer` and `architecture-challenger` cannot use file-editing tools. On Codex the formal review also runs in a separate read-only process (see below). |

`PRAXIS_EVIDENCE_GATE=warn` logs instead of blocking; `off` disables the gate.
Every decision is logged to `.project/telemetry/guard.jsonl`.

### What the evidence gate does not catch

- A task whose `verify` is `null` (human-checked) is exempt by design.
- The edit-time check sees edits made with the tool's file-edit tools. A ledger
  changed by a shell command (`sed -i`, a script) is caught by the stop-time
  re-check and by `scripts/praxis-status.py`, not at edit time.
- The guard blocks hand-writing evidence with file tools and with obvious shell
  writes into the evidence folders; a determined script could still forge a
  summary. The gate stops shortcuts, not an adversary; the commit trailer and
  `/praxis:evidence-audit` (which re-runs every done task) are the backstops.
- Freshness compares tree fingerprints of non-ignored files outside
  `.project/`. Untracked junk that is not gitignored counts as a code change;
  gitignore build output.

## Goals

A Praxis goal is always the same sentence, built from the ledger so it can be
checked from files and not from the agent's say-so:

```bash
python3 scripts/praxis-goal.py --slice S9          # prints the goal text
python3 scripts/praxis-goal.py --slice S9 --arm    # also arms the in-session drive
```

`/drive` arms it for you in each tool:

- **Claude Code and Antigravity:** `--arm` writes
  `.project/working/.drive-active`. The Praxis Stop hook then sends the agent
  back to the ledger while tasks are open (limit `PRAXIS_GOAL_MAX_CONTINUES`,
  default 25 per session). `--disarm` removes the marker. You can also paste
  the goal text after the tool's own `/goal`.
- **Codex:** with `features.goals` on (written by `praxis-setup-subagents`),
  `/praxis-drive` calls Codex's `create_goal` tool with the same text. Without
  it, the Praxis continuation hook keeps an armed drive going.

The kill switch always wins over an armed goal.

## Unattended runs and a heartbeat

`scripts/praxis-drive.sh` is the unattended runner for Claude Code and Codex.
Install a heartbeat so it runs on a schedule:

```bash
scripts/praxis-heartbeat.sh install --project-dir . --every 30 --harness claude-code --window 1-5
scripts/praxis-heartbeat.sh status
scripts/praxis-heartbeat.sh remove
```

This adds one tagged line to your crontab (re-installing replaces it). Each
beat takes a lock so two never overlap, is skipped while `.project/STOP`
exists, and starts from the files, so a crashed beat is picked up by the next
one. Output goes to `.project/telemetry/heartbeat.log`.

Antigravity has no headless runner, so use its own `/schedule` with a prompt
such as "Run /drive on the open Praxis slice". Claude Code's scheduled tasks
work the same way if you prefer them to cron.

To be told when a run stops, set a command in `governance/autonomy.yaml`:

```yaml
summaries:
  notify_command: 'curl -s -d "$PRAXIS_NOTIFY_MESSAGE" https://ntfy.sh/my-topic'
```

To bound fan-out, set `run_budget.max_subagent_depth` and
`run_budget.max_concurrent_subagents` (Claude Code), and
`[agents] max_concurrent_threads_per_session` in `.codex/config.toml` (Codex).

## Status

```bash
python3 scripts/praxis-status.py            # or --json
```

Shows, from files only: kill switch and steer state, each slice's task counts,
tasks marked done without evidence, guard and IO-delegation activity, recent
review verdicts, and when each tool last wrote telemetry.

## Codex: sandboxed reviewers

Codex ignores `sandbox_mode` in a custom agent role file, so a reviewer spawned
as a subagent can write. Praxis therefore runs the formal review as its own
process:

```bash
python3 <plugin>/scripts/codex_review.py --role code-reviewer --project-dir . \
  --prompt "Review slice S9: branch feature/s9, tasks S9-T1..T3"
```

It runs `codex exec --sandbox read-only`, returns a JSON verdict in
`.project/working/reviews/`, and exits 0 (pass), 1 (changes requested or
blocked) or 2 (could not run; never treated as a pass).

## Codex: parallel lanes in worktrees

```bash
python3 <plugin>/scripts/codex_lanes.py --project-dir . --max-parallel 2 --dry-run
python3 <plugin>/scripts/codex_lanes.py --project-dir . --max-parallel 2
```

Each eligible slice runs the normal single-lane controller in its own git
worktree (`.praxis-worktrees/<slice>`, branch `praxis/lane-<slice>`).

- **Eligible** means ready, and the ledger declares `depends_on_slices` with
  every listed slice closed. Write `depends_on_slices: []` to say a slice is
  independent. A slice that declares nothing is never run in parallel.
- **Merge policy:** lanes merge into the starting branch one at a time, in
  slice order, with `git merge --no-ff`. On a conflict the merge is aborted
  and the branch and worktree are kept; the lane is reported as
  `needs_manual_merge`. A lane whose controller failed is not merged. Nothing
  is ever forced or overwritten.
- **Requirements:** a git repository on a branch, with no uncommitted changes
  to tracked files.

## Claude Code: workflow scripts

Two dynamic workflows ship in `claude-workflows/` (see its README):
`/praxis:pre-merge-review` and `/praxis:evidence-audit`. They need Claude Code
v2.1.154 or later with dynamic workflows turned on.

## Context budget

Long runs spend most of their tokens re-reading context: every tool call
re-sends the conversation so far. Praxis keeps sessions short and hands off
through the ledger. Settings live under `context_budget:` in
`governance/autonomy.yaml` (project copy wins); the reasoning and the rules for
compact, clear, rewind and subagents are in `references/context-budget.md`.

| Control | Default | What it does |
|---|---|---|
| `max_turns_by_tier` | deep 40, standard 30, light 20 | `claude -p --max-turns` per headless drive task |
| `iteration_alert_tokens` | 2,000,000 | flags a task whose context reads exceed it (`praxis-status.py`, `.project/telemetry/budget-alerts.jsonl`) |
| `on_session_budget` | continue | in-session drive keeps going at a budget step and hints that it is a good moment to clear; `ask` stops instead |
| `session_max_tasks` | 3 | a budget step every this many finished tasks |
| `session_max_context_tokens` | 350,000 | ...or every this many tokens of transcript since the last compaction (estimate) |
| `turns_map` (model-routing.yaml) | deep 80, standard 60, light 30 | subagent `maxTurns` |

In-session drive hands every task to a fresh subagent, so the main session
stays small and nothing waits on you. At a budget step you see one line (Claude
Code and Codex) saying it is a good moment to start a fresh session; clearing is
optional, and if you do, run the drive command again and the ledger carries the
state. Antigravity has no user-facing hook message, so there the step is only
logged (`context_hint` in `.project/telemetry/guard.jsonl`).

Run `.project/local/bin/praxis-memory context-setup --apply` once per project to
add compaction instructions to CLAUDE.md and `.codex/config.toml`.

