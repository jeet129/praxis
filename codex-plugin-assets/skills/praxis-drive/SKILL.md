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

Start or resume autonomous drive. You do NOT loop internally — each iteration is a fresh delivery-lead invocation.

## Steps

1. **Check the dial.** Read `../../governance/autonomy.yaml`. Note `stop_after` (task | slice | phase | gate), `run_budget`, and `stall.max_iterations_without_ledger_change`. This is the OPTIONAL human boundary — three non-negotiable stops (decision points, governance gates, budget/stall/exhaustion) fire regardless of this setting.

2. **Locate the active ledger.** Look for `.project/working/slice-<id>-tasks.yaml`. If none exists, route through `praxis-slice` first — delivery-lead → lead-developer produce the packet AND the ledger (per `../../references/loop-contracts.md` §2) before drive can start. Never fabricate a ledger.

3. **State the budget and stops once.** Before iterating, tell the user (once): the `stop_after` dial, the `run_budget` caps, the three non-negotiable stops, and that slice-close summaries post to `.project/telemetry/summaries/` regardless of the dial.

4. **Run it.** Offer both paths:
   - **Unattended:** point the user at `scripts/praxis-drive.sh`, which invokes the harness headlessly and enforces caps outside this session's context.
   - **In-session:** launch delivery-lead (`codex-agents/delivery-lead.toml`) in Drive mode, one iteration at a time — read ledger + named task context, dispatch/complete, run `verify`, update `status`/`attempts`, apply model routing — reporting the outcome each time and stopping the moment a non-negotiable stop or the dial's boundary is reached.

## What you must not do

- Do NOT invent a task ledger to make a slice look drive-eligible — route through `praxis-slice` first.
- Do NOT loop past a decision point, governance gate, or budget/stall condition because "it's almost done."
- Do NOT skip stating the stops because the user seems eager to proceed.

## Reference

Full per-iteration protocol: `skills/autonomous-drive` (canonical). Loop contract and task ledger schema: `../../references/loop-contracts.md`. Autonomy dial: `../../governance/autonomy.yaml`.
