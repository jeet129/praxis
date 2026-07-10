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
```
<!-- praxis:metadata:end -->

One iteration, one task. This SKILL is what the Delivery Lead runs inside a drive session — `governance/autonomy.yaml` sets the dial for how often a human is consulted; this SKILL is what happens between those touchpoints. No contract, no loop: every claim here traces back to `references/loop-contracts.md`.

## When this SKILL fires

- A drive session starts or resumes (`/drive`, or `scripts/praxis-drive.sh` invoking the harness with the drive prompt).
- The Delivery Lead needs to decide what a single iteration does before exiting.
- A slice's tasks are all `done` and the slice needs to drain through its gates.
- A `stop_flags` decision must be made — is this a decision point, a gate, or genuinely clear to continue?

## One iteration = one task

Each drive iteration is a fresh-context invocation with a constant prompt. Within it:

1. **Read.** Load the active task ledger (`.project/working/slice-<id>-tasks.yaml`) and ONLY the named context for the next open task — the slice packet, the task's named `ac`, any ADRs the task cites. Never widen to the whole `.project/` tree. The next task is the first whose `depends_on` are all `done`.
2. **Dispatch or complete.** If the task isn't drive-eligible (no runnable `verify`), stop and flag it — it runs interactively, not here. Otherwise dispatch the named specialist (or complete the work directly if the task is orchestration-only) against the task's `ac`.
3. **Verify.** Run the task's `verify` command. It must exit 0. A task moves to `done` only when `verify` passes AND its `ac` items are demonstrably met — not on "looks right."
4. **Update.** Write `status` (`done` | `failed` | `blocked`) and increment `attempts` in the ledger. At `max_task_attempts` (`governance/autonomy.yaml`), the task goes to `failed` and a `blocked` stop_flag is raised.
5. **Route the model.** Apply `adaptive-model-routing` for this task specifically — demote for mechanical work against an existing packet, promote for a task that failed at its default tier once already. Log the decision.

## Slice drain

When every task in the ledger is `done`: run the gate reviewers (`code-reviewer`, `security-reviewer` if triggered, `qa-engineer`) per `implementation-slice.yaml`, record each verdict under the ledger's `gates`, then evaluate `slice_acceptance_met`. Write the slice-close summary to `.project/telemetry/summaries/slice-<id>-summary.md`:

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

## What this SKILL does NOT do

- Define the task ledger schema or the loop contract fields — that's `references/loop-contracts.md`.
- Enforce iteration caps, run budgets, or stall detection — the drive runner (`scripts/praxis-drive.sh`) does that; this SKILL only sets `stop_flags` honestly.
- Decompose the slice into tasks — Lead Developer does that when it produces the ledger.
- Perform code review, security review, or QA — the gate reviewers do that; this SKILL only records their verdicts.
- Select the model tier from scratch — it applies `adaptive-model-routing`, it doesn't redefine routing.
