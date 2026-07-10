# Autonomous Drive Mode — Operator Guide

How to let Praxis run an implementation slice unattended between human
touchpoints, what actually enforces the guardrails, and how to read the
stop conditions when the loop halts.

## What drive mode is

Drive mode is an **outer loop**: `scripts/praxis-drive.sh` repeatedly
re-invokes a fresh, stateless harness call (`claude -p`, `codex exec`, or
`gemini -p`) against the current state of the task ledger on disk, one task
per iteration, until a stop condition fires. Be honest about the division of
labor — **the agent does the work; the runner enforces the guardrails.**
Nothing inside the harness invocation is trusted to self-limit; the runner
(a plain shell script, not an LLM) is what counts iterations, checks ledger
hashes, and reads `stop_flags` after every pass. Each iteration is fresh
context: the only state that survives between iterations is what's written
to disk (the task ledger, `.project/working/`, telemetry) — see
`references/loop-contracts.md` for the ledger schema and iteration protocol,
and `governance/autonomy.yaml` for the dial and budgets below.

## The autonomy dial

`governance/autonomy.yaml` sets `stop_after`, the OPTIONAL human boundary —
how far the loop runs before pausing even when nothing has gone wrong:

| `stop_after` | Behavior |
|---|---|
| `task` | Pause after every task. Use while building trust in a new workflow or a new harness. |
| `slice` | Pause after every slice closes. |
| `phase` | Pause at phase boundaries. |
| `gate` | Continuous — run until a governance gate, decision point, or budget stop. Slice-close summaries still post asynchronously even though the loop doesn't wait for a human to read them. |

Three stops are **non-negotiable** and fire regardless of `stop_after`:

1. **Decision points** — any `decision_node` whose predicate isn't
   machine-evaluable, anything that produces an ADR, any KUACQ escalation
   marked `required: true`, any delivery-planner re-plan trigger.
2. **Governance gates** — per `governance/governance.yaml`, always pause.
3. **Budget/stall/exhaustion** — a run budget hit, a stalled ledger, or a
   task that exhausted its loop contract. Clean stop at the next task
   boundary, never mid-task.

**First-slice-of-phase rule:** the first slice of any new phase always
pauses for a human, regardless of the `stop_after` setting — intent drift is
most expensive at phase starts, so the dial can't be trusted to skip that
checkpoint.

## Run budgets and exit codes

`governance/autonomy.yaml`'s `run_budget` block caps a single drive session:

- `max_slices_per_run` (default 3)
- `max_iterations_per_run` (default 40)
- `max_task_attempts` (default 3 — attempt, fix, tier-promoted retry)
- `cost_ceiling_proxy` (tier-weighted units, per `cost_weights` in
  `governance/model-routing.yaml`)
- `max_budget_usd` (passed natively to the harness where supported, e.g.
  `claude -p --max-budget-usd`; `null` disables it)

`scripts/praxis-drive.sh` exits with a code that tells you why it stopped:

| Exit code | Meaning | What happened at the stop |
|---|---|---|
| `0` | Natural stop | `stop_after` boundary reached cleanly, or all ledger tasks reached a terminal state. |
| `3` | Stalled | Ledger hash unchanged for `stall.max_iterations_without_ledger_change` (default 2) consecutive iterations — the loop was spinning without progress. |
| `4` | Budget | A `run_budget` ceiling was hit (iterations, slices, task attempts, or cost proxy). |
| `5` | Blocked | A task exhausted its loop contract (`max_task_attempts`) or a non-negotiable stop fired (decision point, gate, KUACQ escalation). |

## The task ledger — what makes a task drive-eligible

Lead Developer writes the task ledger at slice open:
`.project/working/slice-<id>-tasks.yaml` (full schema in
`references/loop-contracts.md`). A task is **drive-eligible** only if it
carries a `verify` field — a runnable, machine-checkable command whose exit
code decides done vs. not-done (e.g.
`./gradlew :modules:learning:test --tests '*EnrolmentConsumer*'`). No
`verify` command means the task is not drive-eligible and must run
interactively — the design rule behind this (`references/loop-contracts.md`)
is that **loops only exist where the exit condition is machine-verifiable**;
"looks good" is not an exit condition.

Each task also tracks `attempts` (enforced against `max_task_attempts`),
`depends_on` (ordering — the next open task is the first whose dependencies
are all `done`), and `status` (`open | in_progress | done | failed |
blocked`). `stop_flags` at the ledger level is the drive runner's contract:
agents raise flags (`decision_required | gate_reached | blocked |
budget_exceeded | stalled`); the runner reads them after every iteration and
stops when any is present.

## Slice-close async summaries

When a slice drains, the iteration that closes it writes a summary to
`.project/telemetry/summaries/slice-<id>-summary.md` regardless of whether
the loop is waiting for a human (per `summaries.slice_close` in
`governance/autonomy.yaml`). At `stop_after: gate`, the loop doesn't pause to
let you read it — it keeps going — so check the summaries directory
periodically rather than assuming a pause will prompt you. `summaries.notify`
controls whether closing also prints to `terminal` or stays `file-only`.

## Stall detection

The "witness" check: if the task ledger's content hash is unchanged after
`stall.max_iterations_without_ledger_change` (default 2) consecutive
iterations, the runner stops and flags it — nothing on disk changed, so
continuing to spend iterations would just spin. This catches the case where
an agent keeps re-attempting the same task without making verifiable
progress, distinct from a hard exhaustion (`max_task_attempts`) on one task.

## How to start

**Supervised, in-session (recommended for a first run):** invoke the
`/drive` command (see the `autonomous-drive` skill,
`skills/autonomous-drive/SKILL.md`) from inside an interactive Claude Code
session. You watch each iteration land, ledger updates are visible in your
own context, and you can interrupt at any point — this is the way to build
trust in a new workflow or harness before handing it to the unattended
runner.

**Unattended, headless:** `scripts/praxis-drive.sh` runs the outer loop
without a human watching each iteration, invoking the configured harness
command from `governance/autonomy.yaml`'s `harnesses:` block. Recommended
preconditions before running unattended:

- Start with `stop_after: task` or `stop_after: slice` until you trust the
  workflow, then relax toward `gate`.
- Run in a sandboxed environment (container, disposable VM, or worktree) —
  drive mode executes real commands (`verify`, builds, tests) with no human
  reviewing each one before it runs.
- Everything under version control, committed before the run starts, so a
  bad iteration is a `git diff`/`git reset` away from recoverable.
- Confirm the task ledger's `verify` commands are correct and fast before
  walking away — a slow or flaky verify command wastes the iteration budget
  and can trigger false stalls.

## Cost expectations

Drive mode doesn't track real token spend by default — it tracks a **cost
proxy**: `cost_ceiling_proxy` in `run_budget` is denominated in the same
tier-weighted units as `cost_weights` in `governance/model-routing.yaml`
(`deep: 5.0`, `standard: 1.0`, `light: 0.25`) — coarse relative weights, not
dollar figures (see `docs/telemetry.md` for the same caveat applied to the
routing report). Every drive iteration appends a record to
`.project/telemetry/drive.jsonl` with `tier` and `cost_proxy` fields (see
`references/loop-contracts.md` §4 for the exact shape).
`scripts/factory-routing-report.py` reads this file and adds a drive section
to its output — read it for iterations-per-slice, cost proxy per run, and
stall/exhaustion counts. That's the number to watch quarter over quarter,
not an absolute dollar estimate.

## Safety posture

Drive mode **never crosses decision points, gates, or ADRs** — those are the
three non-negotiable stops above, and they fire independent of the autonomy
dial. The design rule behind why this is safe to automate at all
(`references/loop-contracts.md`): **loops only exist where the exit
condition is machine-verifiable** — a `verify` command exits 0, a review
verdict file contains no `BLOCK`, a gate evidence pack is complete. Anywhere
the exit condition requires human judgment, the loop contract does not
apply, and the runner stops instead of guessing. This is why drive mode can
be trusted to run a slice unattended but is not, and is not meant to be, a
substitute for the governance gates in `governance/governance.yaml` or the
human review at `production_go_live`.

## Troubleshooting

| Exit / state | Likely cause | What to do |
|---|---|---|
| `3` stalled | The current task's `verify` command isn't actually achievable as scoped, or the agent is retrying the same failing approach without new information. | Read the ledger's `notes` field for the task, fix the ambiguity or split the task, reset `attempts`, restart the run. |
| `4` budget | Run legitimately needs more iterations/slices than the default caps, or a runaway tier escalation is burning cost proxy. | Check `factory-routing-report.py`'s drive section for where the proxy went; raise the relevant `run_budget` field deliberately (don't just raise all of them) and re-run. |
| `5` blocked — task exhaustion | A task hit `max_task_attempts` without a passing `verify`. | Read the attempt trail in the ledger's `notes`; the task likely needs a human to unblock (bad spec, missing dependency, wrong `verify` command) rather than another automated retry. |
| `5` blocked — decision/gate | A non-negotiable stop fired mid-slice (decision node, ADR-producing step, required KUACQ, or a gate in `governance.yaml`). | This is expected behavior, not a failure — resolve the decision or approve the gate, then resume the run. |
| Ledger never advances but no stall exit yet | `stall.max_iterations_without_ledger_change` hasn't been hit; check sooner by lowering it temporarily. | Inspect the ledger hash logic and the most recent `.project/telemetry/drive.jsonl` entries for repeated identical outcomes. |

## See also

- `references/loop-contracts.md` — the loop contract and task ledger schemas, the drive iteration protocol, and the telemetry shape.
- `governance/autonomy.yaml` — the autonomy dial, run budgets, stall thresholds, and per-harness invocation commands.
- `governance/model-routing.yaml` — `cost_weights` used for the cost proxy.
- `docs/operating-model.md` — where drive mode sits in the overall operating model and the slice lifecycle.
- `docs/telemetry.md` — the telemetry layers and how `factory-routing-report.py` reads them.
- `docs/quickstart.md` — "Let it run" section on moving from an interactive first slice to `/drive`.
