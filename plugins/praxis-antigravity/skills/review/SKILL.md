---
name: review
description: On-demand, closed-loop review of an architecture-significant artifact (contracts, roadmap, ADRs, or a path) produced outside a gate. Runs Challenger + Code Reviewer + Security Reviewer, then routes findings back to the owning agent to fix and re-reviews until clear.
---

Review the artifact named in $ARGUMENTS (e.g. `contracts`, `roadmap`, `adrs`, or a file/dir path).

This command exists for **architecture-significant artifacts produced outside a governance gate** — e.g. a contract baseline authored *after* `architecture_sign_off`, or a roadmap revised mid-build. It runs a structured, multi-role review AND closes the loop: findings are routed back to the responsible agent, fixed, and re-reviewed until no BLOCK remains. It does NOT replace `architecture_sign_off` or the per-slice review gates; it produces findings, drives remediation, and leaves a record.

Step 1 — Resolve scope from $ARGUMENTS:
- `contracts` → `contracts/` (schemas, openapi, proto, events). Load the checklist `api-design/references/contract-review.md`.
- `roadmap` → the phased-roadmap section in `.project/working/architecture/`.
- `adrs` → `.project/decision/` (the ADR set + INDEX).
- `<path>` → that specific file or directory.
Read the artifact **plus its governing inputs**: `.project/semantic/project-charter.md`, the relevant ADRs, `nfr-register.md`, and the shared conventions (M00 / `contracts/schemas/`).

Step 2 — Run reviewers in parallel, each with its lens:
- **architecture-challenger** — design soundness: coupling, evolvability/versioning, the cross-tier seam (BE↔FE↔AI), behavior under the NFR budgets. Use the relevant sub-personas.
- **code-reviewer (Dimension 6: API + data contracts)** — schema hygiene, `$ref` consistency, backward-compatible-only or explicit version bump, expand-contract, single error-model usage, naming.
- **security-reviewer** — safety/privacy surfaces: prohibited-intent generative paths ABSENT (per the project's safety ADRs), authz on every endpoint, server-bound actor, idempotency keys, PII at boundaries, tenant isolation.
For `contracts`, every reviewer uses `api-design/references/contract-review.md`.

Step 3 — Consolidate findings. For each: classify **BLOCK** / **FIX** / **ACCEPT**, map it to the ADR/NFR/convention it touches, and **assign an owner** (the agent responsible for the fix) per the ownership map:

| Artifact / finding type | Owner agent | Skill it fixes with |
|---|---|---|
| Contract surface, API/data shape, versioning | **solution-architect** | `api-design`, `data-modeling` |
| Phased roadmap / slicing | **solution-architect** | `project-phasing` |
| ADRs / decisions | **solution-architect** (principal for the decision) | `adr-decision-records` |
| Safety/privacy on AI surfaces (M17/M18/M19) | **solution-architect + ml-ai-engineer** | `llm-safety`, `agentic-architecture` |
| Per-module endpoint detail (when its slice lands) | the **specialist** owning that slice | the relevant `stack-*` |

Step 4 — **Route and remediate (the loop).** This is the point of the command — do not stop at a findings list:
1. Dispatch the BLOCK + FIX findings to the owning agent(s) from the map. Give each owner the specific finding, the ADR/NFR it touches, and the expected fix.
2. The owner fixes the artifact (SA edits the contract/roadmap/ADR; ml-ai-engineer fixes AI-safety surfaces; etc.).
3. **Re-review the changed surface** (re-run the relevant reviewer on just the touched files).
4. Repeat until **no BLOCK findings remain**. FIX items may be closed now or tracked with an owner + due slice.

Step 5 — **Disposition of disputes / accepted risk.** If an owner disagrees with a finding or wants to accept it rather than fix it, do not silently drop it — route it to the **principal** (mirrors `challenger_objection_override`): the principal accepts (with rationale, recorded as an ADR) or rejects (back to remediation). Safety/privacy BLOCKs (Step 2 security lens) are **not** accept-able by the owner alone; they require explicit principal sign-off.

Step 6 — Record + status. Write the review record to `.project/operational/reviews/<artifact>-<YYYY-MM-DD>.md` with the findings table (id · severity · surface · ADR/NFR · **owner** · disposition · **status**) and a top-line status: **OPEN → IN-REMEDIATION → CLOSED**. Update `.project/working/active-workflow.md`. A review is CLOSED only when every BLOCK is fixed-and-re-reviewed or principal-accepted.

Step 7 — Enforcement. While status ≠ CLOSED, BLOCK findings on a contract surface gate the slices that consume that surface — do not start those slices until resolved.

Rationalizations to ignore:
- "The SA generated it, so it's reviewed." → generation is not review. A different role reviews; the owner fixes.
- "Findings are logged, my job is done." → no. The loop isn't done until findings are fixed-and-re-reviewed or principal-accepted.
- "I'll just fix it myself as the reviewer." → the owner fixes, the reviewer re-reviews. Don't collapse the two roles.
- "Per-slice review will catch it." → only for that slice's surface; the baseline needs a pass before slices build on it.
- "Schema-validates, so it's fine." → schema-valid is not design-sound or safe.
