---
name: praxis-drive
description: Use when starting or resuming an autonomous drive run in Codex — iterating the active task ledger unattended or in-session. Triggers on "praxis drive", "keep going autonomously", "run this without me", or resuming a paused drive session.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: experimental
dependencies: [agentic-harness-orchestration, adaptive-model-routing]
triggers: [praxis drive, keep going autonomously, run this without me, resume drive, autonomous drive]
outputs: [updated_task_ledger, slice_close_summary, stop_flags, model_routing_log]
consumers: [praxis-slice, praxis-review]
references: [../../governance/autonomy.yaml, ../../references/loop-contracts.md]
```
<!-- praxis:metadata:end -->

# Praxis Drive

Start or resume autonomous drive. There are two paths and they loop differently:
the **unattended runner** loops for you (each `codex exec` it fires is one fresh
delivery-lead iteration, and the runner re-invokes until a stop); the
**in-session** path is a loop YOU run — you keep issuing iterations within this
session until a stop boundary. Do not conflate the two: "one iteration then
exit, no internal loop" applies to a delivery-lead invoked BY the runner, NOT to
the in-session orchestrator, which must continue.

## Steps

1. **Check the dial.** Read `../../governance/autonomy.yaml`. Note `stop_after` (task | slice | phase | gate), `run_budget`, and `stall.max_iterations_without_ledger_change`. This is the OPTIONAL human boundary — three non-negotiable stops (decision points, governance gates, budget/stall/exhaustion) fire regardless of this setting.

2. **Locate the active ledger.** Look for `.project/working/slice-<id>-tasks.yaml`. If none exists, route through `praxis-slice` first — delivery-lead → lead-developer produce the packet AND the ledger (per `../../references/loop-contracts.md` §2) before drive can start. Never fabricate a ledger.

3. **State the budget and stops once.** Before iterating, tell the user (once): the `stop_after` dial, the `run_budget` caps, the three non-negotiable stops, and that slice-close summaries post to `.project/telemetry/summaries/` regardless of the dial.

4. **Run it.** Offer both paths (a long-running / "run without me" request implies unattended):
   - **Unattended (deterministic loop):** point the user at `scripts/praxis-drive.sh --project-dir . --harness codex`, which invokes the harness headlessly, loops iteration-to-iteration itself, and enforces `run_budget` caps + stall detection outside this session's context. Each `codex exec` it fires is exactly one delivery-lead iteration; the runner handles the looping. This is the reliable way to drive a whole slice/workflow.
   - **In-session (you run the loop):** iterate the drive protocol yourself, **continuously**, within this session. Each pass is delivery-lead (`codex-agents/delivery-lead.toml`) executing exactly one `autonomous-drive` iteration — read ledger + named task context, dispatch/complete, run `verify`, update `status`/`attempts`, apply model routing — then report the outcome and **immediately begin the next pass**. Do NOT stop after one task and wait: keep going through the slice **drain** (full-ceremony code review, security review, QA, closure evidence) and on into the next slice's ledger. Per `skills/autonomous-drive` "stop_after semantics", per-slice review/QA are part of the drain, NOT governance gates — under `stop_after: gate` they do not end the run. Stop cleanly ONLY when a non-negotiable stop (decision point, governance gate, budget/stall/exhaustion) or the dial's `stop_after` boundary is actually reached.

## What you must not do

- Do NOT invent a task ledger to make a slice look drive-eligible — route through `praxis-slice` first.
- Do NOT loop past a decision point, governance gate, or budget/stall condition because "it's almost done."
- Do NOT skip stating the stops because the user seems eager to proceed.

## Reference

Full per-iteration protocol: `skills/autonomous-drive` (canonical). Loop contract and task ledger schema: `../../references/loop-contracts.md`. Autonomy dial: `../../governance/autonomy.yaml`.
