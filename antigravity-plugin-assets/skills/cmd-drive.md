---
name: drive
description: Start or resume autonomous drive — iterate the drive protocol (skills/autonomous-drive) against the active task ledger, unattended or in-session, honoring the non-negotiable stops.
---

> **Antigravity note:** unattended *drive mode* is not supported on Antigravity yet
> — its headless/non-TTY execution has open upstream issues. Run this interactively;
> do not rely on unattended `agy -p` drive loops. (Claude Code / Codex support drive mode.)

Start or resume autonomous drive.

## Step 1 — Check the dial

Read `governance/autonomy.yaml`. Note `stop_after` (task | slice | phase | gate), `run_budget`, and `stall.max_iterations_without_ledger_change`. This is the OPTIONAL human boundary — the three non-negotiable stops (decision points, governance gates, budget/stall/exhaustion) fire regardless of this setting.

## Step 2 — Locate or confirm the active ledger

Look for `.project/working/slice-<id>-tasks.yaml` for the current slice (per `.project/working/active-workflow.md`). If none exists, there's nothing to drive yet — route through `/slice`, which delegates to `delivery-lead` → `lead-developer` to produce the packet AND the task ledger (per `references/loop-contracts.md` §2) before drive can start. Do not fabricate a ledger yourself.

If a ledger exists, confirm it against the user: slice id, task count, how many are already `done`, and any existing `stop_flags`.

## Step 3 — Explain the budget and stops once

Before iterating, tell the user (once, not every iteration):
- the `stop_after` dial and what it means for this run
- `run_budget` caps (`max_slices_per_run`, `max_iterations_per_run`, `max_task_attempts`, `cost_ceiling_proxy`)
- the three non-negotiable stops that fire regardless of the dial
- that slice-close summaries post to `.project/telemetry/summaries/` even when the loop doesn't wait

## Step 4 — Run it

Offer both paths; let the user pick (or infer from context — a long-running/background request implies unattended):

- **Unattended:** instruct the user to run the runner script, which invokes the harness headlessly per `governance/autonomy.yaml`'s `harnesses` block, enforcing iteration caps and stall detection outside the agent's own context. **Locating it:** the script ships inside the PLUGIN, not the project. Resolve the path first:
  - Auto-discovered plugin: `find .agents/plugins -name praxis-drive.sh 2>/dev/null | head -1`
  - Globally installed plugin: `find ~/.gemini/antigravity-cli/plugins -name praxis-drive.sh 2>/dev/null | head -1`
  - `install.sh` file install: `./scripts/praxis-drive.sh` in the project
  - Git clone used via `--plugin-dir`: `<clone>/scripts/praxis-drive.sh`
  Then run: `bash <resolved-path> --project-dir . --dry-run` first, and without `--dry-run` when satisfied. If the script is not found anywhere, the installed plugin predates drive mode — update the plugin. In-session drive (above) needs no script at all.
- **In-session:** iterate the drive protocol yourself, continuously, within this session — each iteration is `delivery-lead` executing exactly one `autonomous-drive` pass (see `agents/delivery-lead.md`'s Drive mode section) and reporting the outcome. **After a pass returns, immediately begin the next one — do NOT report a completed task and wait for me.** Nothing re-invokes delivery-lead in this path; you are the loop. Keep going through the slice drain (code review, security review, QA, closure) and into the next ledger, honoring the same stops as the unattended path. Stop cleanly ONLY when a non-negotiable stop or the dial's boundary is actually reached — a finished task under `stop_after: gate` is not one.

`--workflow` (or "drive the whole workflow") runs the top-level loop over workflow steps, each on its phase-tier model, stopping at governance gates and non-machine-verifiable boundaries (see `skills/autonomous-drive`'s "Workflow-drive" section and `references/phase-gates.md`).

## What you do NOT do

- Do NOT invent a task ledger to make a slice appear drive-eligible — route through `/slice` first.
- Do NOT loop past a decision point, governance gate, or budget/stall condition because "it's close to done."
- Do NOT skip explaining the stops because the user seems eager to proceed — say it once, then go.
