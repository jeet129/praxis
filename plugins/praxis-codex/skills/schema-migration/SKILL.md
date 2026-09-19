---
name: schema-migration
description: "Safe database schema evolution using expand/contract (parallel change): add before removing, backfill as a separate step, never ship a destructive change in the same release that stops writing to the old shape. Covers migration tooling discipline (versioned, forward-only preferred, rollback tested) and zero-downtime rules. Use whenever a schema change is being planned (new column, renamed field, changed type, dropped table, split/merged table) or an existing migration needs a rollback plan. Distinct from `data-modeling` (designs the schema shape; this skill evolves an existing shape safely) and `api-design`'s expand/contract (that's the API contract layer; this is the storage layer underneath it — they often run in parallel but are separate contracts)."
---

# Schema Migration

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: backend
state: experimental
dependencies:
  - data-modeling
  - deploy-release
triggers:
  - "planning a schema change (add/rename/retype/drop column or table)"
  - "writing a migration script"
  - "planning the backfill for a schema change"
  - "an existing migration needs a rollback plan"
  - "brownfield: establishing the current schema baseline before changing it"
outputs:
  - migration scripts (versioned, forward + tested rollback)
  - expand/contract plan (stages, each independently deployable)
  - backfill job (separate from the schema change itself)
  - zero-downtime checklist per release
consumers:
  - database-engineer (zero-downtime migrations, lock analysis, backfills on live tables)
  - backend-developer (writes and runs migrations)
  - data-engineer (coordinates with pipeline schema dependencies)
  - platform-sre (executes migrations against production, owns rollback)
  - code-review (checks migration against zero-downtime rules)
references: []
```
<!-- praxis:metadata:end -->

Schema changes are deployed independently of application code but must never break either the old or the new application version while both are briefly live. The core discipline is **expand/contract** (a.k.a. parallel change): every schema change is split into stages that are each individually safe to deploy, with the destructive step deferred until nothing depends on the old shape anymore.

## When this skill fires

- A slice needs a new column, table, index, constraint, or relationship.
- An existing column needs to be renamed, retyped, or moved to a different table.
- A table or column is being deprecated and needs to be dropped.
- A migration is being written and needs a rollback plan before it ships.
- Brownfield: the current schema needs to be baselined before any change is planned against it.

## Expand/contract: the core pattern

Never combine "add the new shape" and "remove the old shape" in one release. Split into three stages, each its own deployable, tested release:

1. **Expand.** Add the new column/table/constraint alongside the old one. The old shape keeps working exactly as before. Application code is *not yet* changed to depend on the new shape.
2. **Migrate.** Deploy application code that writes to *both* old and new shapes (dual-write), or writes only to the new shape while a backfill job (see below) catches up historical data. Reads may start shifting to the new shape once backfill is verified complete.
3. **Contract.** Once no code path reads or writes the old shape — verified, not assumed — remove it: drop the column/table, drop the dual-write code. This is the only stage allowed to be destructive, and only after a full deploy cycle has confirmed nothing depends on the old shape.

Each stage ships as its own release. Skipping straight to a combined expand+contract is what causes downtime: the old application version (still running during a rolling deploy) breaks the moment the old shape disappears.

### Example: renaming a column

| Stage | Schema change | App behavior | Deployable alone? |
|---|---|---|---|
| Expand | Add `full_name`, keep `name` | App still reads/writes `name` only | Yes |
| Migrate | — | App writes both `name` and `full_name`; backfill fills `full_name` for existing rows; app cuts reads over to `full_name` | Yes |
| Contract | Drop `name` | App no longer references `name` anywhere | Yes, only after Migrate is confirmed complete in production |

## Backwards-compatible steps

At every stage, both the previous and the next application version must work correctly against the schema as it exists at that point — because rolling deploys mean both versions are briefly live simultaneously. Concretely:

- Adding a nullable column or one with a default is safe; adding a `NOT NULL` column without a default is not (breaks the old version's inserts).
- Adding an index is safe if done concurrently/online (check the database's non-locking index-build mechanism); a blocking index build is a change that needs a maintenance window or online-DDL tooling.
- Widening a type (int32→int64) is generally safe; narrowing is not — old rows may already violate the new constraint.
- Changing a column's meaning without changing its name is the most dangerous kind of "compatible" change — it silently breaks the old version's logic. Always rename when semantics change.

## Migration tooling discipline

- **Versioned.** Every migration has a monotonic version/timestamp and lives in version control alongside the code that depends on it. No hand-run, undocumented DDL against production.
- **Forward-only, preferred.** Prefer writing a new forward migration to fix a mistake over editing/reverting an already-applied migration — once a migration has run in any shared environment, treat it as immutable history.
- **Rollback tested.** Every migration that's reasonably reversible has a tested `down` migration exercised in CI or staging, not just written and assumed to work. For genuinely irreversible steps (a contract-stage drop), the rollback plan is "redeploy the previous app version against the pre-drop schema" — which only works if contract hasn't run yet, reinforcing why contract is the last, separately-gated stage.
- **Idempotent execution.** Migration runner tracks applied versions so re-running the pipeline doesn't reapply an already-run migration.
- **Reviewed like code.** Migrations go through `code-review` with the zero-downtime rules as an explicit checklist item, not folded silently into a feature PR's diff.

## Zero-downtime rules

The hard rule: **no destructive change ships in the same release that stops writing to the old shape.** Corollaries:

- Don't drop a column/table in the same release where the app stops using it — wait a full deploy cycle (and ideally one rollback-safe window) after the app-side cutover is confirmed live everywhere.
- Don't add a `NOT NULL` constraint to an existing column without first expanding (backfilling all rows) and verifying zero nulls remain.
- Don't rename in place — rename is expand (new name) + migrate (dual-write/backfill) + contract (drop old name), never a single `ALTER ... RENAME` deployed alongside app code that assumes the new name exists.
- Don't run long-locking DDL (table rewrites, non-concurrent index builds) against a live, high-traffic table without an online-DDL tool or an explicit maintenance window agreed with `deploy-release`.

## Data backfills as separate steps

A backfill (populating the new shape from the old, for historical rows) is its own job, decoupled from both the migration script and the deploy pipeline:

- Runs as a background job/script, batched, rate-limited, and resumable — not a single blocking transaction over the whole table.
- Verified with a count/checksum reconciliation between old and new shape before the migrate stage is declared complete.
- Never bundled into the migration script itself — a migration that also loops over millions of rows inline is a deploy-time outage waiting to happen.

## Mode handling (G/B)

**Greenfield.** Design the schema per `data-modeling` first; migrations from that point forward still follow expand/contract for every subsequent change, even early on — bad habits formed on day one compound.

**Brownfield.** Baseline the current schema first: generate or verify a migration history that accurately reflects what's actually running in production (drift between migration files and live schema is common — reconcile it before adding new migrations on top). Any change to a table with unknown or undocumented dependents gets an impact-analysis pass (`impact-analysis`) before the expand stage is written, since brownfield schemas often have unofficial readers (reporting jobs, other services) that "app doesn't reference it" would miss.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We can add the NOT NULL column directly, the app deploys atomically anyway." | Deploys are rolling, not atomic. The old version is live against the new schema for the duration of the rollout. |
| "It's a small table, we can just lock it for a few seconds." | "A few seconds" during traffic is a customer-visible outage. Use online DDL or the expand/contract split regardless of table size. |
| "We'll skip the down migration, we're not going to roll back." | You don't decide that in advance — an untested rollback path is a bet made under incident pressure, the worst time to discover it doesn't work. |
| "Backfill can run inline in the migration, it's not that much data." | Data volume grows; migration scripts don't get re-reviewed for scale later. Decouple from day one. |
| "Renaming a column is just one ALTER statement." | It's one DDL statement and three deploy stages. The statement is the easy part. |

## Verification

You are done when:

- [ ] The change is staged as expand → migrate → contract, each independently deployable.
- [ ] No stage combines "stop writing the old shape" with "remove the old shape" in the same release.
- [ ] Every migration has a version, lives in the repo, and has a tested rollback (or documented reason it's irreversible).
- [ ] Any backfill is a separate, batched, resumable job with a reconciliation check.
- [ ] The migration was reviewed against the zero-downtime checklist in `code-review`.
- [ ] Brownfield only: the pre-change schema was baselined and reconciled against actual production state.

Evidence to check:
- The migrate stage can be deployed, verified, and left running in production for a full cycle before contract is even scheduled.
- A rollback of the expand or migrate stage does not lose data or break the currently-live application version.

## Anti-patterns

- Editing an already-applied migration file instead of writing a new forward migration.
- Dropping a column "to clean up" in the same PR that stops the app from using it.
- Treating the backfill as done because the job finished running, without a reconciliation count.
- Running ad hoc DDL directly against production outside the versioned migration pipeline "just this once."

## What this skill does NOT do

- Design the target schema shape — that's `data-modeling`; this skill only governs how to get from the current shape to that target safely.
- Version or evolve the API contract — that's `api-design`'s own expand/contract discipline at the API layer; the two often run in parallel (new API field ↔ new column) but are separate contracts with separate consumers.
- Execute the deployment pipeline — that's `deploy-release`; this skill produces the migration as an artifact that pipeline runs.
- Decide when a maintenance window is warranted — that's a joint call with `deploy-release` and `platform-sre`; this skill only flags when a change needs one.
