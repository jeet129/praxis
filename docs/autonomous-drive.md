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

## Ceremony

Alongside `stop_after`, the task ledger carries a slice-level `ceremony` field
(`full | expedited | spike`, default `full`) that scales PRE-MERGE review
intensity — not the governance gates, which fire exactly as declared
regardless of ceremony. Lead Developer decides it once, at slice open,
scoring three signals 0–2 (reversibility, blast radius, production exposure)
per the rubric in `skills/autonomous-drive`: 3+ is `full`; ≤2 non-exploratory
work is `expedited`; ≤2 explicitly-exploratory work that will never merge is
`spike`-eligible. Any security-bearing surface (auth, data-handling, public
API, dependency changes) forces `full` regardless of score.

At drain, `full` runs the standard gate set; `expedited` runs one combined
blocker-only review plus a mandatory retro entry (majors logged as
tech-debt, owed at the next `full` slice touching the area — mirrors
`workflows/expedited-change.yaml`); `spike` runs no code gates at all — the
spike report is the exit criterion and the code never merges to a
production branch, per `workflows/spike.yaml`'s hard rule.
`governance/autonomy.yaml`'s `ceremony.allow_expedited` /
`ceremony.allow_spike` are the engagement-level safety rails — set both
`false` on a compliance project and every slice runs `full` regardless of
its rubric score.

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

**Locating the runner:** the script ships inside the plugin, NOT your
project. Plugin/marketplace installs (Claude Code):
`find ~/.claude/plugins -name praxis-drive.sh 2>/dev/null | head -1`.
`install.sh` file installs: `./scripts/praxis-drive.sh` in the project.
Git-clone via `--plugin-dir`: `<clone>/scripts/praxis-drive.sh`. Not found
anywhere = your installed plugin predates drive mode; update it. (In-session
`/drive` needs no script.)

**Unattended, headless:** the runner runs the outer loop
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

## Workflow-drive

`scripts/praxis-drive.sh --workflow` is an **outer ring** around everything
above: instead of looping a slice's *tasks*, it loops a workflow's *steps* —
reading `.project/working/workflow-state.yaml` (schema in
`references/phase-gates.md` §3) rather than a task ledger. Default OFF —
without `--workflow` the script is the unchanged slice-drive runner
documented in the rest of this page. Each step runs on **its own phase's
tier-resolved model**, exactly the same `TIER_MODEL_*` / model-flag
machinery slice-drive uses for tasks — this is how the orchestrator itself,
and every phase lead (product-manager, solution-architect, delivery-lead,
...), get per-step model routing instead of a static pin.

**The autonomy zone is C→D only** (`references/phase-gates.md` §1):
discovery and architecture (A/B) stay human-gated, because that is where the
exit criteria for the downstream phases get authored and frozen
(`requirements_freeze`, `architecture_sign_off`). A step outside the
ledger's `autonomy_zone` never runs unattended, regardless of whether its
`exit` happens to be machine-checkable.

**Three step kinds, three behaviors:**

| `kind` | Behavior |
|---|---|
| `gate` | ALWAYS a human stop — raises `gate_reached`, names the gate, halts. Governance is never machine-cleared. |
| `phase`, machine `exit`, in-zone | Launches the step's `agent` on its `tier`'s model, then the **runner** evaluates `exit` deterministically (`command` \| `artifact_exists` \| `artifact_contains` \| `verdict_file`). Pass → `status: done` + `completed_at` stamped, loop continues. Fail → applies `on_fail` (`route_back` \| `stop_and_flag` \| `escalate_to_human`) and stops. |
| `phase` with `sub_ledger` | The step's work IS a slice-drive run — the loop delegates to the existing slice-drive path over that ledger, then reads the slice-close summary as the step's exit. |
| out-of-zone, or `exit` has only a `fallback_gate` | Runs the step's agent once so the work is staged, then stops for a human, naming the `fallback_gate`. Covers `decision_node` steps too — an unresolvable boundary is a stop, never a guess. |

**Non-negotiable:** a step's status becomes `done` only when the runner's
own deterministic check passes — never because an agent asserted the work
looked complete. Silent self-assertion of a phase boundary is the same
protocol violation as draining past an unknown status token. Gates and
non-machine-verifiable boundaries always stop, regardless of the dial.

`governance/autonomy.yaml`'s `stop_after` now also drives this loop: `step`
(pause after each — the workflow-drive analogue of `task`), `phase` (stop
when the next eligible step belongs to a different workflow phase), or
`gate` (run continuously to the next gate, fallback boundary, or
budget/stall stop). `run_budget.max_steps_per_run` caps steps per run
(defaults to `max_slices_per_run` when unset). Telemetry lands in the same
`.project/telemetry/drive.jsonl`, tagged `mode: "workflow"` with `step`,
`phase`, `iteration_model`, and `exit_check` (`references/phase-gates.md`
§4) — `factory-routing-report.py` reports it alongside slice-drive runs.

See also `skills/autonomous-drive`'s "Workflow-drive (top-level loop)"
section, which this subsection mirrors.

## See also

- `references/loop-contracts.md` — the loop contract and task ledger schemas, the drive iteration protocol, and the telemetry shape.
- `references/phase-gates.md` — the workflow-step ledger schema, the phase-exit predicate registry, and the autonomy zone for workflow-drive.
- `governance/autonomy.yaml` — the autonomy dial, run budgets, stall thresholds, and per-harness invocation commands.
- `governance/model-routing.yaml` — `cost_weights` used for the cost proxy.
- `docs/operating-model.md` — where drive mode sits in the overall operating model and the slice lifecycle.
- `docs/telemetry.md` — the telemetry layers and how `factory-routing-report.py` reads them.
- `docs/quickstart.md` — "Let it run" section on moving from an interactive first slice to `/drive`.
