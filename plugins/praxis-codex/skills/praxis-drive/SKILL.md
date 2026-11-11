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

1. **Preflight the project.** Run `python3 <plugin-root>/hooks/project_root.py --project-dir "$PWD" --require-agents --check-write`. Use its printed absolute root for the runner, ledger, and every agent. If profiles are missing, run `$praxis-setup-subagents` at that root and start a new Codex session. If writing fails, fix the workspace/sandbox before dispatch. Never start a second `.project` under a nested working directory.

2. **Check the dial.** Read `<project-root>/.project/governance/autonomy.yaml` when present, otherwise the plugin default. Note `stop_after` (task | slice | phase | gate), `run_budget`, and `stall.max_iterations_without_ledger_change`. This is the optional human boundary — three non-negotiable stops (decision points, governance gates, budget/stall/exhaustion) fire regardless of this setting.

3. **Locate the active ledger.** Run `python3 <plugin-root>/scripts/codex_drive.py --project-dir <project-root> --audit` for a compact lane inventory. If none exists, route through `praxis-slice` first — delivery-lead → lead-developer produce the packet AND the ledger (per `../../references/loop-contracts.md` §2) before drive can start. Never fabricate a ledger. Unknown status tokens are reported, not guessed. If taking over an existing `in_progress` lane that predates the controller, first check that no other agent is still working there, then pass `--slice <id>` to adopt that lane explicitly; the controller will inspect partial work before verifying it.

4. **State the budget and stops once.** Before iterating, tell the user (once): the `stop_after` dial, the `run_budget` caps, the three non-negotiable stops, and that slice-close summaries post to `.project/telemetry/summaries/` regardless of the dial.

5. **Run it.** Choose the path from the user's request (a long-running / "run without me" request implies unattended):
   - **Unattended (deterministic loop):** run `python3 <plugin-root>/scripts/codex_drive.py --project-dir <project-root>` yourself and supervise until it exits. The controller uses the packaged `praxis-drive.sh` for one Codex iteration at a time, applies the run budget across lanes, and persists `.project/telemetry/codex-controller.json`. It emits a heartbeat at most 60 seconds apart while a child runs; surface meaningful progress to the user at least every 15 minutes. It writes the compact `.project/working/codex-active-index.json`, preserves the full JSONL for usage accounting, and validates closeout evidence before counting a slice as closed. A gate blocks its lane; another lane may proceed only if it explicitly declares `depends_on_slices` and does not depend on the blocked slice. Report the exit code and exact stop reason. For an entire workflow run (`--workflow`), use the packaged shell runner's workflow mode; the lane controller handles slice ledgers.
   - **In-session (you run the loop):** use `codex-active-index.json` to choose the lane, then iterate the drive protocol **continuously** within this session. Each pass is delivery-lead (`codex-agents/delivery-lead.toml`) executing exactly one `autonomous-drive` iteration — read the ledger and named task context, dispatch/complete, verify, update the ledger — then report the outcome and immediately begin the next pass. Complete the slice drain after implementation, with one formal review round and affected re-reviews. Apply the same lane dependency and closeout evidence rules as the unattended controller (see `references/controller-contract.md`). Stop at reached gates, decisions, budgets, and the dial boundary; never treat a future pending gate as already reached. Give a brief user-visible progress update at least every 15 minutes.

   The Codex-only Stop guard arms for an explicit `$praxis-drive` or `praxis drive` prompt. It can request another in-session pass when an active ledger remains open. It is a bounded fallback; the orchestrator still owns waiting, verification, and the full run budget.

## What you must not do

- Do NOT invent a task ledger to make a slice look drive-eligible — route through `praxis-slice` first.
- Do NOT loop past a decision point, governance gate, or budget/stall condition because "it's almost done."
- Do NOT skip stating the stops because the user seems eager to proceed.

## Reference

Full per-iteration protocol: `skills/autonomous-drive` (canonical). Loop contract and task ledger schema: `../../references/loop-contracts.md`. Autonomy dial: `../../governance/autonomy.yaml`.
Codex controller extensions and recovery: `references/controller-contract.md`.
