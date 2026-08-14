---
name: praxis-slice
description: Use when running one Praxis implementation slice in Codex. ALWAYS launches delivery-lead as the orchestrator session; never launches specialists directly. Follows implementation-slice.yaml with subagents, review gates, QA, and closeout.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [source-grounded-coding, code-review, secure-coding, testing-strategy, cicd-pipeline, deploy-release]
triggers: [praxis slice, implementation slice, build next slice, run slice]
outputs: [slice_status, prs, review_reports, qa_report, documentation_check, episodic_entry]
consumers: [praxis-release, praxis-review]
references: [../../workflows/implementation-slice.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Slice

Run one implementation slice end-to-end. You do NOT execute the slice yourself. You launch the delivery-lead session, which orchestrates.

## Steps

1. Identify the next slice from `.project/working/active-workflow.md` and the phased roadmap. If unclear, ask the user for the slice id.

2. **Launch the delivery-lead subagent session** using `codex-agents/delivery-lead.toml`. Give it this prompt:

   ```
   Run implementation-slice.yaml for slice <slice-id>.

   Follow the workflow STRICTLY. Do NOT skip any step.

   1. Open the slice. Update .project/working/active-workflow.md.

   2. Launch lead-developer FIRST (codex-agents/lead-developer.toml).
      Give it the slice spec, AC, and touched modules. Wait for its
      output — the implementation packet at
      .project/working/slice-<slice-id>-packet.md AND the task ledger
      at .project/working/slice-<slice-id>-tasks.yaml, which include:
        - decomposed tasks per specialist
        - dependencies between tasks (on ARTIFACTS, not on agents
          finishing: FE depends on the API contract task, not on the
          backend implementation; test scaffolding depends on AC +
          contract, not on code)
        - relevant NFRs
        - test-plan skeleton

   3. ONLY AFTER the packet + ledger exist, dispatch specialists.
      PREFERRED (two-tier, canonical): lead-developer dispatches the
      specialist sessions itself per the ledger DAG, launching
      parallel-safe tasks concurrently (FE + BE + mobile + test
      scaffolding all start once the contract tasks land), and runs
      integration validation when they report back, then reports
      slice completion to you.
      FALLBACK (only if this Codex environment cannot nest session
      launches from the lead-developer session): you launch the
      specialist sessions yourself — but strictly per lead-developer's
      ledger DAG and parallelism plan, never your own decomposition,
      and you hand lead-developer the specialists' outputs for
      integration validation before proceeding.

   4. When lead-developer reports integration-validated completion
      (every specialist task done, slice composes end-to-end),
      launch (in parallel):
        - code-reviewer for every PR
        - ux-designer for visual review when the slice has UI tasks
          (evidence: implementation screenshots at 2-3 viewports incl.
          empty/loading/error states, scored against the design plan +
          tokens per the frontend-design skill)
        - security-reviewer if the slice is security-bearing
          (touches auth, data-handling, public surface, deps,
          compliance)
        - qa-engineer for every PR

   5. If any reviewer returns a blocker: fix loop. Same specialist
      that owns the file gets the finding; re-review by the blocking
      reviewer. Loop until all reviewers pass.

   6. Close the slice. Write acceptance verdict and episodic entry.

   NEVER launch a specialist session directly for slice implementation.
   Lead Developer builds the packet first. This rule holds even if the
   slice looks small or only one specialist appears needed.
   ```

3. Do NOT launch a specialist session yourself. delivery-lead is the ONLY session $praxis-slice launches. delivery-lead launches everything else.

## What you must not do

- Do NOT launch backend-developer, frontend-developer, data-engineer, or ml-ai-engineer sessions directly. Delegate through delivery-lead.
- Do NOT launch code-reviewer, security-reviewer, qa-engineer, or ux-designer (visual review) sessions directly. delivery-lead launches them at the review-gate step, after lead-developer reports integration-validated completion.
- Do NOT serialize frontend/test work on backend implementation completion. The dependency is the contract artifact (OpenAPI spec, schema), which lands early; parallelize from that point.
- Do NOT skip lead-developer. The implementation packet is the artifact reviewers consume; without it, review can't happen.
- Do NOT collapse owner and reviewer roles.

## Slice DoD (what delivery-lead is enforcing)

- Every reviewer green (code-review, security if applicable, qa)
- Acceptance criteria met
- Artifacts under `.project/`: packet, slice episodic entry, review reports, QA report
- No open blockers; all fix loops closed

## Reference workflow

`workflows/implementation-slice.yaml` (canonical). delivery-lead reads and follows it. If the path can't be resolved from the current session, delivery-lead falls back to the workflow's step semantics documented above.
