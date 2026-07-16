# Loop contracts and the task ledger

The two schemas that make autonomous iteration safe in Praxis. Every loop in
the factory — the slice fix loop, the ideation refinement loop, the outer
drive loop — must conform to a loop contract; every driven slice must have a
task ledger. No contract, no loop.

Design rule (non-negotiable): **loops only exist where the exit condition is
machine-verifiable.** Tests pass, a validator exits 0, a file exists, a gate
evidence pack is complete. "Looks good" is not an exit condition — that is
what reviewers and humans are for.

---

## 1. Loop contract

Declared on any looping construct in a workflow YAML (`type: bounded_loop`)
and honored by the drive runner and delivery-lead:

```yaml
loop_contract:
  exit_criteria:                    # ALL must be machine-checkable
    - tests_pass: "verify command exits 0"
    - no_blocker_findings: "review verdict file contains no BLOCK"
  max_iterations: 3                 # hard cap for this loop
  on_no_progress: stop_and_flag     # ledger/artifact hash unchanged after an iteration
  on_exhaustion: escalate_to_human  # never silently retry past the cap
  escalation: promote_one_tier_and_retry_once   # per governance/model-routing.yaml
```

Field semantics:

| Field | Meaning |
|---|---|
| `exit_criteria` | List of named, deterministically checkable conditions. The loop exits when ALL pass. |
| `max_iterations` | Hard iteration cap. The runner enforces it even if the agent disagrees. |
| `on_no_progress` | What to do when an iteration changes nothing (hash of the governed artifact/ledger unchanged): always `stop_and_flag`. |
| `on_exhaustion` | What to do at the cap: always `escalate_to_human` with the attempt trail. |
| `escalation` | Optional mid-loop tier adjustment before exhaustion, per the routing escalation policy. |

`scripts/validate-workflows.py` fails any `bounded_loop` without a
`loop_contract` carrying `exit_criteria`, `max_iterations`, and
`on_exhaustion`.

---

## 2. Task ledger

The machine-readable form of Lead Developer's slice decomposition — the fuel
for the drive loop. Written at slice open, updated after every iteration.

Path: `.project/working/slice-<id>-tasks.yaml`

```yaml
slice: S9
packet: .project/working/slice-S9-packet.md   # the prose packet stays authoritative for context
opened: 2026-07-10
ceremony: full                        # full | expedited | spike — decided at slice open, see below
ceremony_rationale: "schema migration touches shared enrolment table: reversibility=2, blast radius=1, prod exposure=1 -> full"
tasks:
  - id: S9-T1
    summary: "Enrolment read-model consumer, idempotent"
    agent: backend-developer            # canonical agent slug
    tier: standard                      # capability tier; drive may adjust ±1 per adaptive-model-routing
    ac:
      - "consumes session.scheduled type=class idempotently"
      - "duplicate event produces no second row"
    verify: "./gradlew :modules:learning:test --tests '*EnrolmentConsumer*' -q --console=plain > .project/working/verify-S9-T1.log 2>&1"
    depends_on: []
    status: done                         # open | in_progress | done | failed | blocked
    attempts: 1
    started_at: 2026-07-10T12:03:00Z    # stamped when status moved to in_progress
    completed_at: 2026-07-10T12:41:00Z  # stamped when status moved to done|failed
    notes: ""
  - id: S9-T2
    summary: "GET /classes browse endpoint behind ClassSearchPort"
    agent: backend-developer
    tier: standard
    ac:
      - "lang/category filters honored"
      - "contract matches m0X-learning.yaml"
    verify: "./gradlew :modules:learning:test --tests '*ClassBrowse*' -q --console=plain > .project/working/verify-S9-T2.log 2>&1"
    depends_on: [S9-T1]
    status: open                        # started_at/completed_at omitted — not yet touched
    attempts: 0
    notes: ""
gates:                                  # populated as gate verdicts land
  code_review: pending                  # pending | pass | fail
  security_review: n/a                  # n/a when not triggered
  visual_review: n/a                    # n/a when the slice has no UI tasks
  qa: pending
state: open                             # open | draining | gates | closed
stop_flags: []                          # drive stops when non-empty: decision_required |
                                        # gate_reached | blocked | budget_exceeded | stalled
```

Rules:

- **One writer.** Only the delivery-lead (or the specialist it dispatched for
  the current task) updates the ledger; parallel writes are serialized by the
  single-writer discipline.
- **`verify` is the exit criterion.** A task moves to `done` only when its
  verify command exits 0 AND its `ac` items are demonstrably met. No verify
  command → the task is not drive-eligible and must run interactively.
- **`verify` is authored quiet, executed to a log.** The command itself must
  use a quiet/silent flag (`pytest -q --tb=short -x`, `gradle -q
  --console=plain`, `npm test --silent`) — full output is never the model's
  problem to hold in context. Execution captures everything to
  `.project/working/verify-<task-id>.log` (`cmd > log 2>&1`); the model reads
  back only the exit code, and on failure a failure extract (last ~40 lines,
  or the failing-test names via `grep`) — never the full log. The log stays
  on disk for humans and for re-runs.
- **`ceremony` is decided once, at slice open.** `full | expedited | spike`
  (default `full`), scored per the rubric in `skills/autonomous-drive`, never
  changed mid-loop, recorded with a one-line rationale in the slice-open
  checkpoint (`ceremony_rationale` above). Ceremony only scales PRE-MERGE
  review intensity — workflow-declared governance gates
  (`production_go_live` etc.) are untouched regardless of ceremony. Any
  security-bearing surface (auth, data-handling, public API, dependency
  changes) forces `full` regardless of score.
- **`attempts` is enforced.** At `max_task_attempts` (governance/autonomy.yaml)
  the task goes to `failed`, a `blocked` stop flag is raised, and the human
  gets the trail.
- **Whoever moves a task's `status` stamps the corresponding timestamp.**
  `in_progress` sets `started_at`; `done` or `failed` sets `completed_at`
  (ISO UTC, e.g. `2026-07-10T12:03:00Z`). These windows power per-task token
  attribution in interactive sessions (drive already measures token usage
  exactly per task via `drive.jsonl`; this is what makes the same
  attribution possible outside drive).
- **`stop_flags` is the drive runner's contract.** Agents raise flags; the
  runner reads them after every iteration and stops when any is present
  (subject to the autonomy dial for `gate_reached` at slice close).
- **`depends_on` gates ordering.** The next open task is the first whose
  dependencies are all `done`. Write dependencies against **contract
  artifacts, not sibling implementations**: the frontend task depends on
  the API-contract task, not on the backend implementation task; test
  scaffolding depends on AC + contract. Serializing on full
  implementations is the most common false dependency and destroys the
  parallelism the DAG exists to expose.

---

## 3. Drive iteration protocol (summary)

Each drive iteration is one fresh-context harness invocation with a constant
prompt (see `skills/autonomous-drive`). Within the iteration the agent:

1. Reads the ledger + the named context for the next open task (scoped — not
   the whole `.project/` tree).
2. Completes ONE task: implement, run `verify`, update `status`/`attempts`.
3. On slice drain: runs the gate reviewers, records verdicts under `gates`,
   evaluates `slice_acceptance_met`, writes the slice-close summary, and per
   the autonomy dial either raises `gate_reached` or closes the slice and
   opens the next ledger.
4. Sets `stop_flags` honestly. Raising a flag early is correct behavior;
   ploughing past a decision point is a protocol violation.

The runner (not the agent) enforces: iteration caps, run budgets, stall
detection (ledger hash unchanged), and non-negotiable stops.

---

## 4. Telemetry

Every iteration appends to `.project/telemetry/drive.jsonl`:

```json
{"ts":"2026-07-10T12:00:00Z","run_id":"drive-20260710-1200","iteration":4,
 "slice":"S9","task":"S9-T2","agent":"backend-developer","tier":"standard",
 "outcome":"done","ledger_hash":"a1b2c3","stop_flags":[],"cost_proxy":1.0}
```

`scripts/factory-routing-report.py` aggregates drive runs: iterations per
slice, cost proxy per run, stall/exhaustion counts, and human-touchpoint
density (the headline metric: touches per slice).
