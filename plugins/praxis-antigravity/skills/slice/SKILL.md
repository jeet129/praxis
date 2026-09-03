---
name: slice
description: Run one implementation slice end-to-end via implementation-slice.yaml workflow. ALWAYS delegates to delivery-lead; never spawns specialists directly.
---

Run ONE implementation slice end-to-end. You do NOT execute the slice yourself. You do NOT spawn a specialist. You delegate the whole thing to `delivery-lead`, which orchestrates.

## What you do

Ask me which slice (if not obvious from the roadmap in `.project/working/`). Show me:
- Acceptance criteria
- Estimated size (must be 2-5 days; if larger, decompose first — reject the slice back to `/architect` or `/discover` if it's too big)
- Stack(s) involved
- Dependencies on prior slices

Once I confirm, delegate to delivery-lead:

Delegate to the **delivery-lead** agent — read `agents/delivery-lead.md`, adopt that role, and execute this brief:

> Run implementation-slice.yaml for slice <slice-id>.
>
> Follow the workflow STRICTLY. Do NOT skip any step.
>
> 1. Open the slice. Update .project/working/active-workflow.md.
>
> 2. Spawn lead-developer FIRST. Give it the slice spec, AC, and touched
>    modules. Wait for its output — BOTH artifacts, not just the first:
>      - the implementation packet at
>        .project/working/slice-<slice-id>-packet.md (decomposed tasks per
>        specialist, dependencies, relevant NFRs, test-plan skeleton)
>      - the task ledger at .project/working/slice-<slice-id>-tasks.yaml
>        (per references/loop-contracts.md §2: per-task agent, tier, ac,
>        verify command, depends_on). The ledger is what makes the slice
>        drive-eligible — without it /drive has nothing to iterate.
>
> 3. ONLY AFTER the packet + ledger exist, dispatch specialists.
>    PREFERRED: lead-developer dispatches them per the ledger's dependency
>    DAG (two-tier delegation — you route phases, Lead Developer routes
>    tasks). FALLBACK: only if the harness cannot nest agent spawns, you
>    dispatch specialists yourself, passing each its portion of the packet.
>    Run specialists in parallel where the DAG allows.
>
> 4. When every specialist has produced a PR, spawn (in parallel):
>      - code-reviewer for every PR
>      - ux-designer for visual review when the slice has UI tasks
>        (screenshots vs design plan + tokens, per frontend-design)
>      - security-reviewer if the slice is security-bearing
>        (touches auth, data-handling, public surface, deps, or
>        compliance-bearing code)
>      - qa-engineer for every PR
>
> 5. If any reviewer returns a blocker: fix loop. Same specialist that
>    owns the file gets the finding; re-review by the blocking reviewer.
>    Loop until all reviewers pass.
>
> 6. Close the slice. Write acceptance verdict and episodic entry.
>    Update .project/working/active-workflow.md with next-slice pointer
>    or workflow-complete marker.
>
> NEVER spawn a specialist directly for slice implementation. Lead
> Developer builds the packet first. This rule holds even if the slice
> looks small or only one specialist appears needed.

## What you do NOT do

- Do NOT spawn backend-developer, frontend-developer, data-engineer, or ml-ai-engineer directly from `/slice`. Delegate through delivery-lead.
- Do NOT spawn code-reviewer, security-reviewer, or qa-engineer directly. Delivery Lead spawns them at the review-gate step.
- Do NOT re-implement the workflow yourself. delivery-lead reads `workflows/implementation-slice.yaml` and follows it.
- Do NOT accept "skip lead-developer, the slice is small" as a shortcut. The packet is what reviewers consume. No packet = broken review flow.

## Slice DoD (what delivery-lead is enforcing)

- Every reviewer green (code-review, security if applicable, qa)
- Acceptance criteria met
- Artifacts in `.project/`: packet, slice episodic entry, review reports, QA report
- No open blockers; all fix loops closed

## Common rationalizations to ignore

- "Slice is small; I'll skip the packet." → small ≠ skip. All steps fire.
- "Only backend-developer is needed; skip lead-developer." → no. Packet is required. Lead Dev writes it.
- "The user is impatient." → delivery-lead reports progress; don't shortcut discipline.
- "I'll add tests later." → DoD requires tests. Now.
- "We can ship without observability." → DoD requires SLO + dashboards + alerts for new surfaces.
