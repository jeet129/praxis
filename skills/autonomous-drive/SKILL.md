---
name: autonomous-drive
description: "The drive protocol the Delivery Lead executes inside each drive iteration — read the task ledger, complete exactly one drive-eligible task against its named context, run its verify, and honor the non-negotiable stops. Use when a drive session (via `/drive` or `scripts/praxis-drive.sh`) starts or resumes, when deciding what a single drive iteration must do, when a slice drains and gate reviewers need to run, or when evaluating whether a stop_flag must be raised. Distinct from `using-praxis` (the general orchestration runtime this protocol runs inside) and `implementation-slice.yaml` (the workflow whose fix loop this protocol iterates against) — this SKILL is the per-iteration discipline, not the workflow or the router."
---

# Autonomous Drive

<!-- praxis:metadata:begin -->
```yaml
capability: orchestration
domain: cross-cutting
state: experimental
dependencies:
  - using-praxis
  - adaptive-model-routing
  - definition-of-done
triggers:
  - "starting or resuming a drive session"
  - "what does one drive iteration do?"
  - "slice is draining — run the gate reviewers and close it"
  - "deciding whether a stop_flag must be raised this iteration"
  - "cross-slice continuation after a gate close"
outputs:
  - updated task ledger (.project/working/slice-<id>-tasks.yaml)
  - slice-close summary (.project/telemetry/summaries/slice-<id>-summary.md)
  - stop_flags (drive runner contract)
  - model-routing log entries (per task)
consumers:
  - delivery-lead (primary — executes this protocol every drive iteration)
  - scripts/praxis-drive.sh (the unattended runner; enforces caps this SKILL cannot)
references:
  - loop-contracts.md
  - phase-gates.md
```
<!-- praxis:metadata:end -->

One iteration, one task. This SKILL is what the Delivery Lead runs inside a drive session — ``.project/governance/autonomy.yaml` when the project carries an override, else the plugin's governance/autonomy.yaml` sets the dial for how often a human is consulted; this SKILL is what happens between those touchpoints. No contract, no loop: every claim here traces back to `references/loop-contracts.md`.

## When this SKILL fires

- A drive session starts or resumes (`/drive`, or `scripts/praxis-drive.sh` invoking the harness with the drive prompt).
- The Delivery Lead needs to decide what a single iteration does before exiting.
- A slice's tasks are all `done` and the slice needs to drain through its gates.
- A `stop_flags` decision must be made — is this a decision point, a gate, or genuinely clear to continue?

## One iteration = one task

Each drive iteration is a fresh-context invocation with a constant prompt — deliberately constant: identical prefixes are served from the harness prompt cache, keeping fresh contexts cheap. Keep the prompt stable; volatile ledger state lives in the files it reads, never in the prompt. Within it:

1. **Read.** Load the active task ledger (`.project/working/slice-<id>-tasks.yaml`) and ONLY the named context for the next open task — the slice packet, the task's named `ac`, any ADRs the task cites. Never widen to the whole `.project/` tree. The next task is the first whose `depends_on` are all `done`.
2. **Dispatch or complete.** If the task isn't drive-eligible (no runnable `verify`), stop and flag it — it runs interactively, not here. Otherwise dispatch the named specialist (or complete the work directly if the task is orchestration-only) against the task's `ac`.
3. **Verify.** Run the task's `verify` command. It must exit 0. A task moves to `done` only when `verify` passes AND its `ac` items are demonstrably met — not on "looks right." Verify commands are authored quiet (`pytest -q --tb=short -x`, `gradle -q --console=plain`, `npm test --silent`) and executed with output captured to `.project/working/verify-<task-id>.log` (`cmd > log 2>&1`). The iteration consumes ONLY the exit code plus, on failure, a failure extract (last ~40 lines, or the failing-test names via `grep`) — never the full log. The full log stays on disk for humans and re-runs; tool-result tokens are the largest avoidable context cost in a drive session, and build/test noise is most of it.
4. **Update.** Write `status` (`done` | `failed` | `blocked`) and increment `attempts` in the ledger; stamp `started_at` when a task moves to `in_progress` and `completed_at` when it moves to `done` or `failed` (ISO UTC), per `references/loop-contracts.md` §2 — these windows are what let interactive sessions get the same per-task token attribution drive already gets from `drive.jsonl`. At `max_task_attempts` (`governance/autonomy.yaml`), the task goes to `failed` and a `blocked` stop_flag is raised.
5. **Route the model.** Apply `adaptive-model-routing` for this task specifically — demote for mechanical work against an existing packet, promote for a task that failed at its default tier once already. Log the decision.

## Slice drain

When every task in the ledger is `done`: honor the ledger's `ceremony` field (see "Ceremony" below) to decide review intensity, then run the applicable gate reviewers (`code-reviewer`, `security-reviewer` if triggered, `ux-designer` visual review if the slice has UI tasks, `qa-engineer`) per `implementation-slice.yaml`, record each verdict under the ledger's `gates`, then evaluate `slice_acceptance_met`. Write the structured checkpoint entry to `.project/episodic/` (boundary: slice_close, per `references/factory-metrics-schema.md`) and copy it as the async slice-close summary to `.project/telemetry/summaries/slice-<id>-summary.md`:

```markdown
## Slice close — <slice-id>
- What shipped: <one-paragraph summary>
- AC evidence: <per-AC trace — test, demo, or verification note>
- Gate verdicts: code_review=<verdict>, security_review=<verdict|n/a>, qa=<verdict>
- Deviations: <anything cut, waived, or filed as tech-debt>
- Cost proxy: <tier-weighted units this slice consumed>
- What's next: <next task/slice, or the stop reason>
```

The summary is never optional — a slice does not count as drained without it, even when the loop is about to stop for a gate anyway.

## stop_after semantics and the non-negotiable stops

`governance/autonomy.yaml`'s `stop_after` sets the OPTIONAL boundary: `task` (pause every task — trust-building), `slice` (pause every slice close), `phase` (pause at phase boundaries), or `gate` (run continuously until a real stop). Regardless of the dial, three stops are NON-NEGOTIABLE and fire even under `stop_after: gate`:

1. **Decision points** — any Decision Node whose predicate isn't machine-evaluable, anything producing an ADR, any KUACQ escalation with `required: true`, any delivery-planner re-plan trigger.
2. **Governance gates** — per `governance/governance.yaml`, always pause.
3. **Budget/stall/exhaustion** — run budget hit, ledger hash unchanged (stall), or a task exhausted its loop contract.

**First slice of a new phase always pauses**, regardless of the dial — intent drift is most expensive at phase starts.

## Cross-slice continuation

At `stop_after: gate`, a slice close does not end the session: close the slice, archive its working memory to `.project/episodic/`, have Lead Developer produce the next ledger from the roadmap (per `references/loop-contracts.md` §2), and continue iterating. The drive runner (not this SKILL) still enforces `run_budget` caps across that continuation.

## stop_flags discipline

Raising a `stop_flags` entry early is correct behavior — it costs one paused iteration. Ploughing past a decision point to finish "just one more task" is a protocol violation: it produces exactly the outcome the non-negotiable stops exist to prevent. When in doubt about whether something is a decision point, flag it.

## Verification

You are done with a drive iteration when:

- [ ] Exactly one task was completed (or one drain/gate action taken) — not zero, not several.
- [ ] The task's `verify` ran and exited 0 before `status` moved to `done`.
- [ ] `attempts` was incremented; `max_task_attempts` was checked.
- [ ] `adaptive-model-routing` ran for this task and the decision was logged.
- [ ] On drain: all applicable gate verdicts are recorded and the slice-close summary was written.
- [ ] `stop_flags` reflects the true state — no decision point, gate, or budget/stall condition was silently passed over.

## Anti-patterns

- Marking a task `done` without its `verify` passing.
- Inventing a `verify` command after the fact to make a task look drive-eligible.
- Retrying the identical approach after `on_no_progress` fired — that's what `stop_and_flag` exists to prevent.
- Treating the slice-close summary as optional busywork.
- Widening context beyond the named task's inputs "while I'm in there."
- Continuing past a decision point because the iteration was "almost done anyway."
- Piping full test/build output into context — capture to a log file, read back the exit code and failure extract only.

## Ceremony

The task ledger's slice-level `ceremony` field (`full | expedited | spike`, default `full`) scales PRE-MERGE review intensity at slice drain — set once at slice open per `references/loop-contracts.md` §2, never changed mid-loop. It is not a way around governance: workflow-declared gates (`production_go_live`, etc.) fire exactly as declared regardless of ceremony.

**Rubric** (score each 0–2, mirrors `adaptive-model-routing`'s style):

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| Reversibility | Feature-flagged / easily reverted | Revertible with some cost | Schema or data migration |
| Blast radius | Isolated module | Several modules, one service | Cross-service / public contract |
| Production exposure | Not user-facing / behind flag | Limited prod exposure | Direct prod hot path |

Score 0–2: `spike`-eligible only if the work is explicitly exploratory AND will never merge. Non-exploratory work at score ≤2: `expedited`. Score 3+: `full`. **Any security-bearing surface (auth, data-handling, public API, dependency changes) forces `full` regardless of score.**

**Drain behavior, per ceremony:**

- `full` — current behavior: code review + security review (when triggered) + visual review (when UI) + QA.
- `expedited` — ONE combined review pass (`code-reviewer`, blocker-only bar) plus a MANDATORY retro entry in the slice-close checkpoint: majors get logged as tech-debt, full review is owed at the next `full`-ceremony slice touching the area. Same philosophy as `workflows/expedited-change.yaml`'s compressed-now/repaid-later loan — cite it in the checkpoint.
- `spike` — no code gates fire; the spike report artifact is the exit criterion; ledger `gates` are all `n/a`. Code from a `spike`-ceremony slice NEVER merges to a production branch, per `workflows/spike.yaml`'s hard rule.

**Non-negotiables:** security forces `full`; `spike` never merges; an `expedited` retro is owed, not optional; governance gates are untouched by ceremony choice.

## Workflow-drive (top-level loop)

An **outer ring** around everything above. Slice-drive (this SKILL, so far)
loops over a slice's *tasks*; workflow-drive loops over a workflow's *steps*
— one altitude up. `scripts/praxis-drive.sh --workflow` reads
`.project/working/workflow-state.yaml` (schema: `references/phase-gates.md`
§3) instead of a task ledger, and each step runs on **its phase's
tier-resolved model** — this is how the orchestrator and every phase lead
(product-manager, solution-architect, delivery-lead, ...) get routed by
task instead of pinned to one static model. Default OFF: without
`--workflow`, `praxis-drive.sh` is exactly the slice-drive runner described
above, unchanged.

### The autonomy zone: C→D only

Per `references/phase-gates.md` §1, workflow-drive's genuine unattended span
is **implementation → release (C→D)**. Discovery and architecture (A/B) stay
human-gated: that is where exit criteria for the phases *downstream* of them
get created and frozen (`requirements_freeze`, `architecture_sign_off`). A
step whose `phase` falls outside the ledger's `autonomy_zone` is never driven
unattended, regardless of whether it happens to carry a machine-checkable
`exit` — the zone boundary is checked first.

### The three step kinds

- **`kind: gate`** — ALWAYS a human stop. The runner raises `gate_reached`
  and halts immediately, naming the gate. Governance is never
  machine-cleared, no matter how the autonomy dial is set.
- **`kind: phase`, machine-verifiable `exit`, in the autonomy zone** — runs
  unattended: launch the step's `agent` on its `tier`'s resolved model, then
  the RUNNER (not the agent) evaluates `exit` deterministically (`command` |
  `artifact_exists` | `artifact_contains` | `verdict_file`, per
  `references/phase-gates.md` §2). Pass → `status: done`, `completed_at`
  stamped, loop continues. Fail → apply `on_fail` (`route_back` reopens the
  named step, `stop_and_flag` or `escalate_to_human` just stop) and halt —
  a failed exit is always a stop, never a silent retry.
- **`kind: phase` with a `sub_ledger`** — the step's work IS a slice-drive
  run: this SKILL's loop executes over that task ledger (nested invocation
  or an equivalent call — see the script's implementation), then the
  step's `exit` reads the slice-close summary it produced. Workflow-drive
  and slice-drive nest cleanly; this is the seam between the two altitudes.
- **Outside the zone, OR the `exit` carries only a `fallback_gate` (no
  `check`)** — run the step's agent once so its work is staged, then STOP
  for a human, naming the `fallback_gate`. This also covers `decision_node`
  steps and anything the runner cannot classify confidently: when in doubt,
  stop, don't guess.

### The non-negotiable

**Never self-assert a phase exit.** A step's `status` only becomes `done`
when the runner's own deterministic check passes — not because the agent
said the work looks complete, not because a fallback step "seemed fine."
Silent LLM assertion of a phase boundary is the same failure class as
draining past a `pending` status token: a protocol violation, not a judgment
call. Gates and non-machine-verifiable boundaries ALWAYS stop, exactly as
`stop_after: gate` never crosses a decision point in slice-drive above —
same discipline, one altitude up.

`governance/autonomy.yaml`'s `stop_after` also drives this loop: `step`
(pause after each), `phase` (stop when the next eligible step belongs to a
different workflow phase), or `gate` (run continuously to the next gate,
fallback boundary, or budget/stall stop). `run_budget.max_steps_per_run`
caps steps processed per run (defaults to `max_slices_per_run` when unset);
stall detection hashes `workflow-state.yaml` the same way slice-drive hashes
the task ledger. Telemetry lands in the same `drive.jsonl`, tagged
`mode: "workflow"` with `step`, `phase`, `iteration_model`, and `exit_check`
per `references/phase-gates.md` §4 — `factory-routing-report.py` reports it
alongside slice-drive runs.

## What this SKILL does NOT do

- Define the task ledger schema or the loop contract fields — that's `references/loop-contracts.md`.
- Enforce iteration caps, run budgets, or stall detection — the drive runner (`scripts/praxis-drive.sh`) does that; this SKILL only sets `stop_flags` honestly.
- Decompose the slice into tasks — Lead Developer does that when it produces the ledger.
- Perform code review, security review, or QA — the gate reviewers do that; this SKILL only records their verdicts.
- Select the model tier from scratch — it applies `adaptive-model-routing`, it doesn't redefine routing.
