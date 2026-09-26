# Phase gates and the workflow-step ledger

The two schemas that make the **workflow-drive** (the top-level loop) run
unattended between human sign-offs. This is the outer ring around the
slice-drive loop documented in `loop-contracts.md`: slice-drive loops over
*tasks*; workflow-drive loops over *workflow steps*, each launched on its
phase's tier-resolved model.

Design rule (inherited, non-negotiable): **a step advances unattended only
when its exit is machine-verifiable.** Where a phase boundary's condition is
genuinely a judgment call, it is a **human gate**, not a machine gate — the
workflow-drive stops there. The loop runs *between* the human gates that
defined its exit criteria; it never runs *through* them.

---

## 1. The autonomy zone

Exit criteria are born, and frozen, at the human sign-offs:

| Phase | Criteria defined here | Frozen at (human gate) | Machine-verifiable downstream? |
|---|---|---|---|
| A — discovery | Acceptance criteria, NFR targets | `requirements_freeze` | AC/NFRs become task `verify` + phase predicates |
| B — architecture | `nfr_satisfied`, contract shapes, slice plan | `architecture_sign_off` | predicates become checkable evaluators |
| C — implementation | per-task `verify`, DoD gates | (per-slice review gates) | YES — this is slice-drive's home |
| D — release | evidence pack completeness | `production_go_live` | evidence-existence checks |

**The workflow-drive's genuine autonomous span is C→D.** A and B are
high-judgment and stay interactive/human-gated — you cannot drive
implementation before requirements+architecture are signed off, because
that is where the machine-checkable exits are created. That ordering is the
safety property, not a limitation.

---

## 2. Phase-exit predicate registry

Every workflow `decision_node` / phase boundary that the workflow-drive may
cross unattended MUST resolve its predicate to one of three checkable forms
(never prose the model self-asserts):

```yaml
# in the workflow YAML, on a decision_node or phase-exit step
predicate:
  name: nfr_satisfied
  check: artifact_contains        # command | artifact_exists | artifact_contains | verdict_file
  args:
    path: .project/working/architecture/nfr-verification.md
    must_contain: "VERDICT: SATISFIED"
  on_fail: route_back             # route_back <step> | stop_and_flag | escalate_to_human
  fallback_gate: architecture_sign_off   # if uncheckable at runtime, becomes a human gate
```

Check kinds:

| `check` | Passes when | Use for |
|---|---|---|
| `command` | the shell command exits 0 (quiet, captured to log) | tests, linters, validators, build |
| `artifact_exists` | the named file exists and is non-empty | "the ADR was written", "evidence item present" |
| `artifact_contains` | the file exists AND matches `must_contain` (literal or regex) | reviewer verdict tokens (`VERDICT: PASS`), NFR attestations |
| `verdict_file` | a named reviewer/gate agent wrote a verdict file whose status field is clear of BLOCK/FAIL | gate reviewers, challenger sign-off |
| `status_field` | the file at `path` contains a dotted `field` whose value string-equals `expect` | reading a recorded status (pipeline_status, capacity_verdict) a step wrote to a file |

`status_field` example — reads a value from a file the step wrote and
compares it:

```yaml
    exit:
      check: status_field
      args:
        path: .project/working/pipeline-status.json   # a file the step produced
        field: pipeline_status                        # dotted key (a.b.c) in json/yaml
        expect: passed
      on_fail: route_back
```

Note: a predicate that references a *runtime value no step has written to a
readable file* (e.g. "blocker_findings.count == 0" held only in an agent's
head) is NOT machine-checkable — it must declare a `fallback_gate` and stop
for a human, not a machine `check`. `check: command` with no runnable
`cmd:`/`command:` arg is a false-pass trap (empty command exits 0) and is
rejected by `validate-workflows.py`.

**Hard rule:** a predicate the runner cannot evaluate deterministically is
NOT a machine gate. It must declare a `fallback_gate` and the workflow-drive
stops there for a human. Silent LLM assertion of a phase boundary is a
protocol violation — the same failure class as the `pending` status escape.
`scripts/validate-workflows.py` fails any decision_node whose predicate is
neither a registered `check` form nor backed by a `fallback_gate`.

**`fallback_gate` is a human review BOUNDARY, not a governance gate.** The two
are deliberately different: a `kind: gate` step names a governance gate in
`governance/governance.yaml` (approvers + evidence, e.g. `production_go_live`)
and is ALWAYS a human stop; a `fallback_gate` is simply where the runner stops
because *this* predicate isn't machine-checkable at runtime. A fallback_gate
MAY coincide with a governance gate (e.g. `architecture_sign_off`), but it need
not, and most don't (e.g. `capacity_verification`, `spike_topic_routing`).
Accordingly, `validate-workflows.py` does NOT require fallback_gate names to
exist in `governance.yaml` — only `kind: gate` / `type: gate` names are
cross-checked there.

---

## 3. Workflow-step ledger

The workflow instance `delivery-planner` produces, made drive-legible. It is
the *step-level* analogue of the slice task ledger — same discipline, one
altitude up.

Path: `.project/working/workflow-state.yaml`

```yaml
workflow: greenfield-saas
instance_of: workflows/greenfield-saas.yaml
opened: 2026-07-12
autonomy_zone: [C, D]                  # phases the workflow-drive may run unattended
steps:
  - id: WF-A                           # phase / step id
    phase: A
    kind: phase                        # phase | gate | decision_node
    agent: product-manager
    tier: standard                     # phase-tier; runner resolves to a model
    outputs: [.project/semantic/requirements.md, .project/semantic/nfr-register.md]
    exit:
      check: artifact_exists
      args: {path: .project/semantic/nfr-register.md}
    fallback_gate: requirements_freeze # A is high-judgment -> human gate
    status: done                       # open | in_progress | done | failed | blocked
    started_at: 2026-07-12T09:00:00Z
    completed_at: 2026-07-12T11:30:00Z

  - id: WF-B
    phase: B
    kind: phase
    agent: solution-architect
    tier: deep                         # architecture -> deep model
    depends_on: [WF-A]
    outputs: [.project/working/architecture/overview.md, .project/decision/INDEX.md]
    exit:
      name: nfr_satisfied
      check: artifact_contains
      args: {path: .project/working/architecture/nfr-verification.md, must_contain: "VERDICT: SATISFIED"}
    fallback_gate: architecture_sign_off
    status: open

  - id: WF-C1
    phase: C
    kind: phase
    agent: delivery-lead               # opens a slice -> hands to slice-drive
    tier: standard
    depends_on: [WF-B]
    sub_ledger: .project/working/slice-CS1-tasks.yaml   # this step IS a slice-drive run
    exit:
      check: artifact_contains
      args: {path: .project/telemetry/summaries/slice-CS1-summary.md, must_contain: "slice_acceptance_met: true"}
    status: open

  - id: GATE-PROD
    phase: D
    kind: gate                         # governance gate -> ALWAYS a human stop
    gate: production_go_live
    depends_on: [WF-C1]
    status: open
state: open                            # open | draining | closed
stop_flags: []                         # gate_reached | decision_required | blocked | budget_exceeded | stalled
```

Rules (in addition to the slice-ledger rules, which apply unchanged):

- **`kind: gate` is always a human stop.** The workflow-drive raises
  `gate_reached` and halts, regardless of the autonomy dial. Governance is
  never machine-cleared.
- **`kind: phase` in the `autonomy_zone` with a machine `exit`** runs
  unattended: the runner launches `agent` on the `tier`'s model, then
  evaluates `exit`. Outside the zone, or with only a `fallback_gate`, it
  stops for a human after the step's work is staged.
- **`kind: phase` with a `sub_ledger`** delegates to slice-drive: the step's
  work IS a slice-drive run over that task ledger; its `exit` reads the
  slice-close summary. Workflow-drive and slice-drive nest cleanly.
- **`tier` is the phase tier** (architecture→deep, implementation→standard,
  etc., per `skills/adaptive-model-routing` phase defaults). The runner
  resolves it to a model exactly as slice-drive resolves task tiers — this
  is how the orchestrator's own per-step reasoning gets routed.
- **Same closed `status` vocabulary, same timestamp stamping, same
  single-writer discipline** as the task ledger.

---

## 4. Workflow-drive telemetry

Each step append to `.project/telemetry/drive.jsonl` carries `mode: workflow`
to distinguish it from slice iterations:

```json
{"ts":"2026-07-12T11:30:00Z","run_id":"wfdrive-20260712-0900","mode":"workflow",
 "step":"WF-B","phase":"B","agent":"solution-architect","tier":"deep",
 "iteration_model":"opus","outcome":"done","exit_check":"artifact_contains",
 "stop_flags":[],"cost_proxy":5.0}
```

`factory-routing-report.py` reports workflow-drive runs alongside slice runs;
the per-step model column is the direct evidence that the orchestrator and
phase leads are being routed by task, not pinned.
