---
name: doubt-driven-decisions
description: "Subjects every non-trivial decision to a fresh-context adversarial review BEFORE it stands. CLAIM → EXTRACT → DOUBT → RECONCILE → STOP. Pairs with `architecture-challenger` (which is macro-level adversarial review of the whole architecture); this SKILL is the per-decision keyboard-level equivalent. Use when correctness matters more than speed, when working in unfamiliar code, when stakes are high (production, security-sensitive, irreversible), or any time a confident output would be cheaper to verify NOW than to debug later."
---

# Doubt-Driven Decisions

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - source-grounded-coding
  - code-review
triggers:
  - "about to make an architectural decision under uncertainty"
  - "about to commit non-trivial code"
  - "about to claim a non-obvious fact ('this is safe', 'this scales', 'this matches the spec')"
  - "working in code I don't fully understand"
  - "the LLM session has accumulated context; assumptions may have hardened"
  - "stakes are high — production / security / irreversible / data migration / public API"
outputs:
  - written claim + why-it-matters statement
  - extracted artifact + contract (the minimum reviewable unit)
  - fresh-context adversarial review findings
  - reconciliation table (per finding: dismiss / mitigate / re-do)
  - stop-condition met (trivial findings OR 3-cycle limit OR user override)
consumers:
  - every implementation agent (per-commit adversarial review)
  - code-review (consumes the doubt-cycle artifacts as PR evidence)
  - architecture-challenger (macro-level peer; different scope)
  - delivery-lead (consumes for high-stakes decisions)
references: []
```
<!-- praxis:metadata:end -->

A confident answer is not a correct one. Long agent sessions accumulate context that quietly hardens assumptions into "facts" without anyone noticing. **Doubt-driven decisions** is the discipline of materializing a fresh-context reviewer — biased to **disprove**, not approve — before any non-trivial output stands.

This is NOT `code-review` (a verdict on a finished artifact). This is an **in-flight posture**: non-trivial decisions get cross-examined while course-correction is still cheap.

This is NOT `architecture-challenger` (macro-level review of the whole architecture). This is the **per-decision keyboard-level equivalent**.

The principle: **if a wrong answer would be expensive, the doubt cycle is cheap. Buy the verification.**

## When this SKILL fires

A decision is **non-trivial** when at least one is true:

- Introduces or modifies branching logic that affects multiple call sites.
- Crosses a module or service boundary.
- Asserts a property the type system or compiler cannot verify (thread safety, idempotence, ordering, invariants, transactional semantics).
- Correctness depends on context the future reader cannot see.
- Blast radius is irreversible (production deploy, data migration, public API change, schema change with no backfill plan).

Apply the SKILL when:

- About to make an architectural decision under uncertainty.
- About to commit non-trivial code.
- About to claim a non-obvious fact ("this is safe", "this scales", "this matches the spec").
- Working in code you don't fully understand.
- The session has been long; you've been generating output for a while.

**When NOT to use:**

- Mechanical operations (renaming, formatting, file moves).
- Following a clear, unambiguous user instruction with no ambiguity.
- Reading or summarizing existing code.
- One-line changes with obvious correctness.
- Pure tooling operations (running tests, listing files).
- The user has explicitly asked for speed over verification.

If you doubt every keystroke, you ship nothing. The SKILL applies only to non-trivial decisions as defined above.

## The five-step cycle

### Step 1: CLAIM — surface what stands

Name the decision in two or three lines. Write it down:

```
CLAIM: The new outbox-based notification path delivers events
       at-least-once with no duplicates inside the same
       transaction-boundary, even on retry.
WHY THIS MATTERS: a duplicate notification charges users twice;
                  a missed notification leaves orders unfulfilled.
```

If you can't write the claim that compactly, you have a vibe, not a decision. Surface it first; scrutinize it second.

### Step 2: EXTRACT — smallest reviewable unit

A fresh-context reviewer needs the **artifact** and the **contract**, not the journey.

- **Code:** the diff or the function — not the whole file.
- **Architectural decision:** the proposal in 3-5 sentences plus the constraints it has to satisfy.
- **Data change:** the migration + the rollback + the assumed invariant.

Strip out your reasoning. The reviewer is checking the artifact, not validating your thought process.

### Step 3: DOUBT — adversarial fresh-context review

Spawn a fresh-context reviewer (a sub-agent OR a clean prompt) with an explicit **disprove-bias** instruction:

```
You are reviewing the following CLAIM and ARTIFACT.

Your job is to DISPROVE the claim — not to approve it.

Find at least one way the claim could be false, even if unlikely.
Specifically check:
- Edge cases the artifact doesn't handle
- Assumptions the artifact makes that may not hold
- Concurrency / ordering / failure-mode gaps
- Interactions with neighboring code the artifact doesn't account for
- Whether the contract matches what consumers actually expect

If you can find no flaw after a sincere attempt, say so explicitly:
"Sincere disprove attempt failed; the artifact appears to satisfy the
 claim under the stated contract."

CLAIM: <paste>
CONTRACT (what the artifact must satisfy): <paste>
ARTIFACT: <paste>
```

The disprove-bias is essential. Without it, the reviewer slips into approval mode (LLMs default to agreeable). With it, the reviewer surfaces real findings.

### Step 4: RECONCILE — classify every finding

For each finding the reviewer surfaces:

| Class | Action |
|---|---|
| **Real and material** | Re-do the artifact. The original claim was wrong or incomplete. |
| **Real but immaterial** | Document as an explicit non-goal or accepted limitation. |
| **Misunderstanding by the reviewer** | Strengthen the contract (the reviewer's misread suggests the contract was unclear). |
| **Out of scope** | Defer; log to backlog. |

The reconciliation is your artifact. The reviewer's findings + your classification + your response becomes a record. Code Reviewer can verify the classification in minutes.

### Step 5: STOP — meet a stop condition

The cycle terminates when ONE of the following holds:

1. **Trivial findings only** — the reviewer's findings are all immaterial or out of scope.
2. **Three cycles done** — convergence didn't happen; surface to the human ("doubt-driven-decisions has run 3 cycles without convergence; need your input").
3. **User override** — the user explicitly accepts the residual risk.

The 3-cycle bound prevents infinite scrutiny. Real disagreement at cycle 3 is a human conversation, not a model conversation.

## Loading constraints

This SKILL is designed for the **main-session orchestrator**, where Step 3 (DOUBT) can spawn a fresh-context reviewer.

- **Do NOT add this SKILL to a specialist agent's `skills:` frontmatter** without reading the orchestration constraint. A specialist that follows Step 3 would spawn another specialist — the two-tier orchestration rule explicitly forbids this.
- **If running from inside a subagent context** (where the platform prevents nested subagent spawn): the preferred path is to surface to the user that doubt-driven-decisions cannot run nested and let the main session handle it. As a last resort only, a degraded self-questioning fallback exists — rewrite ARTIFACT + CONTRACT as a fresh self-prompt with a hard mental separator from your prior reasoning, and walk Steps 1-5. This is **not fresh-context review** (you carry your own context with you), so flag the result as degraded and escalate to the user whenever they're reachable.

## Worked example

```markdown
# Doubt cycle — Outbox idempotency

## Claim
The new outbox-based notification path delivers events at-least-once with
no duplicates inside the same transaction-boundary, even on retry.

## Why it matters
Duplicate notification → double-charged user; missed → unfulfilled order.

## Contract
- Outbox row written in the same DB transaction as the business event.
- Worker reads unprocessed rows, sends notification, marks row as
  processed in a transaction.
- Retry on worker failure produces the same outcome.

## Artifact
[20 lines of outbox writer + worker code]

## DOUBT findings (fresh-context reviewer)
1. Worker marks-processed-then-sends. If marking succeeds and sending
   fails (network), the notification is lost. → REAL, MATERIAL.
2. Worker is single-instance. At scale, parallel workers may double-send
   if they pick up the same row. → REAL, MATERIAL.
3. Outbox table has no TTL. Will grow unbounded. → REAL but IMMATERIAL
   for this slice; OUT OF SCOPE; add to debt register.
4. Reviewer asks: "what if the DB itself rolls back the outbox row
   after the send?" → MISUNDERSTANDING; the contract says outbox is
   in the same transaction as the business event.

## Reconciliation
- Finding 1: re-do. Switch to send-then-mark (with idempotency key on
  the receiving end so re-send is safe).
- Finding 2: add row-level lock with SKIP LOCKED so parallel workers
  don't pick up the same row.
- Finding 3: tech-debt-management entry DEBT-2026-091.
- Finding 4: strengthen contract wording in this doc.

## Stop condition
2 of 4 findings required artifact change. After updating, run a second
DOUBT cycle on the updated artifact. Stopped at cycle 2 with trivial
findings only.
```

This whole document becomes the PR description. Code Reviewer reviews the artifact AND the doubt cycle.

## Mode handling (G/B)

**Greenfield.** Apply at every non-trivial decision from day one. Build the muscle.

**Brownfield.** Apply at every change that touches load-bearing code, especially around concurrency, idempotency, and data migrations. Don't apply to comprehension-only reads.

## Verification

You are done when:

- [ ] CLAIM written compactly (2-3 lines) with why-it-matters.
- [ ] EXTRACT: artifact + contract in the smallest reviewable form.
- [ ] DOUBT: fresh-context reviewer invoked with disprove-bias instruction.
- [ ] RECONCILE: every finding classified (real-material / real-immaterial / misunderstanding / out-of-scope).
- [ ] STOP condition met: trivial findings only, OR 3 cycles reached, OR user override documented.
- [ ] If degraded-fallback used: explicitly flagged as degraded.
- [ ] Doubt cycle document persisted to PR description or `.project/operational/doubt-cycles/`.

Evidence to check:
- The reviewer's findings include at least one item the author hadn't considered.
- The reconciliation classifications were applied (re-do for material; documented for accepted).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I'm confident in this; doubt cycle is overkill." | Confidence is not calibrated to correctness. The cycle is the calibration. |
| "It's just X lines of code." | Concurrency bugs hide in 5 lines. Size isn't the predictor; non-triviality is. |
| "We don't have time." | The cycle is 5-10 minutes. Debugging the resulting bug is hours-to-days. |
| "Code review will catch it." | Code Reviewer reviews artifacts; they don't simulate the failure mode. Doubt cycle does. |
| "The Architecture Challenger covered this." | Challenger is macro. This is per-decision. Different scope. |
| "I'll just self-review." | Self-review carries your assumptions with you. The "fresh context" is the whole point. |
| "Step 3 fresh-context isn't possible here." | Use the degraded fallback (see Loading constraints) and FLAG IT as degraded. Don't silently skip. |

## Outputs

| Output | Location |
|---|---|
| Doubt cycle document | PR description OR `.project/operational/doubt-cycles/<change>-<date>.md` |
| Reconciliation table | inline in doubt cycle document |
| Findings → backlog | tech-debt-management entries OR open tickets |

## What this SKILL does NOT do

- Verify framework / library facts — that's `source-grounded-coding`.
- Macro-level architecture review — that's `architecture-challenger` (5 sub-personas).
- Final PR review — that's `code-review`.
- Security audit — that's `security-review`.
- General testing — that's `testing-strategy`.

## Anti-patterns

- Doubt cycle skipped on "obvious" code that turns out to have concurrency / ordering bugs.
- Fresh-context reviewer prompted without disprove-bias (drifts into approval).
- Reviewer findings dismissed without reconciliation classification.
- Cycle runs forever; never stops; never decides.
- Self-review claimed as fresh-context (it isn't; you carry your own context).
- "We'll doubt-cycle if review catches something" — that's reactive; the SKILL is preemptive.
- Doubt cycle applied to trivial mechanical changes (cycle fatigue; calibrate when it fires).
- Degraded fallback used silently without the explicit "degraded" flag.
- Doubt cycle exists only in head; never written down; can't be reviewed.
- Findings logged as "fixed" without re-running the cycle on the updated artifact.
