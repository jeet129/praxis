---
description: Run a configurable creator/reviewer/enhancer loop over an ideation artifact. Harnesses are runtime bindings, so creator/reviewer can be Claude, Codex, Cursor, OpenCode, or custom adapters.
---

Run the `ideation-refinement-loop` workflow for the artifact or topic named in $ARGUMENTS.

Usage examples:

- `/refine-idea product-brief.md`
- `/refine-idea product-brief.md --creator claude --reviewer codex`
- `/refine-idea "new onboarding concept" --creator claude --reviewer codex --enhancer claude --arbiter codex --max-passes 5 --quality-bar rigorous`

Argument parsing:

- The first non-option argument is the artifact path or free-form ideation topic.
- `--creator <harness>` binds the creator role. Default: `claude`.
- `--reviewer <harness>` binds the reviewer role. Default: `codex`.
- `--enhancer <harness>` binds the enhancer role. Default: same as creator.
- `--arbiter <harness>` binds the convergence/user-summary role. Default: `codex`.
- `--max-passes <n>` sets the loop bound. Default: 5.
- `--quality-bar <standard|high|rigorous>` sets the review strictness. Default: `high`.

Step 1 - Resolve the artifact or topic. If it is a path, read it. If it is a topic,
create the initial working artifact under `.project/working/ideation/`.

Step 2 - Record the harness role bindings in the run log:
`creator_harness`, `reviewer_harness`, `enhancer_harness`, `arbiter_harness`,
`quality_bar`, `max_passes`, timestamp, and source artifact/topic.

Step 3 - Invoke the workflow:
`workflows/ideation-refinement-loop.yaml`

Step 4 - Enforce the role separation:

- creator creates or expands the artifact.
- reviewer critiques and produces severity-tagged findings.
- enhancer evaluates the critique, accepts/rejects findings with rationale, and rewrites.
- arbiter checks convergence and prepares the user-facing approval summary.

The same harness may be bound to more than one role only if the user explicitly
requests it or a default says so. Even then, keep role prompts separate and record
that the same harness served multiple roles.

Step 5 - Continue until:

- no unresolved major-or-higher findings remain, and
- the next pass is expected to produce only cosmetic or low-value changes, or
- `--max-passes` is reached.

Step 6 - Present the final result to the user with:

- final artifact path,
- role binding record,
- pass count,
- major changes made,
- accepted/rejected reviewer findings,
- remaining risks/open questions,
- recommendation: approve now or run another pass.

Do not describe the artifact as "100% perfect." Use convergence language:
`ready for approval`, `needs another pass`, or `blocked on user decision`.
