# The Operating Model

The big-picture page: how a user's intent turns into governed, evidence-based
delivery, and where drive mode fits as the loop that keeps things moving
between human touchpoints. Every box below names a real file, skill, or
agent in this repo — none of this is aspirational. For the phase-by-phase
prose walkthrough, see [`docs/lifecycle.md`](lifecycle.md); for the drive
loop specifically, see [`docs/autonomous-drive.md`](autonomous-drive.md).

## 1. Overall operating model

```mermaid
flowchart TD
    U[User intent] --> UP["using-praxis SKILL — front door / intent routing<br/>(skills/using-praxis/SKILL.md)"]
    UP --> WF{Workflow selection}
    WF -->|new project| GS[greenfield-saas.yaml]
    WF -->|new project| GA[greenfield-api-service.yaml]
    WF -->|existing codebase| BE[brownfield-enhancement.yaml]
    WF -->|rough idea| IR[ideation-refinement-loop.yaml]
    WF -->|one slice| IS[implementation-slice.yaml]
    WF -->|ship it| PR[production-release.yaml]
    WF -->|P0/P1 emergency| EC[expedited-change.yaml]
    WF -->|prove feasibility| SP[spike.yaml]
    WF -->|replace legacy system| MZ[modernization.yaml]

    GS --> DL
    GA --> DL
    BE --> DL
    IR --> DL
    IS --> DL
    PR --> DL
    EC --> DL
    SP --> DL
    MZ --> DL

    DL["delivery-lead orchestration<br/>(agents/delivery-lead.md, Layer 2 of using-praxis)"]
    DL --> AG["Agents + skills + tier routing<br/>(agents/*.md, skills/*, governance/model-routing.yaml)"]
    AG --> WP["Work products<br/>(.project/ semantic / working / episodic artifacts)"]
    WP --> GT["Gates<br/>(governance/governance.yaml — 19 gates)"]
    GT --> HA["Human approval<br/>(principal reviews evidence pack)"]
    HA -->|approved| NEXT[Next phase / next slice]
    HA -->|rejected| DL

    DR["Drive mode — scripts/praxis-drive.sh<br/>+ skills/autonomous-drive + /drive command"]
    DR -. "loop arrow: keeps AG -> WP -> GT moving<br/>between human touchpoints, per governance/autonomy.yaml" .-> AG
    GT -. "non-negotiable stop" .-> DR

    WD["Workflow-drive — scripts/praxis-drive.sh --workflow<br/>(outer ring over workflow STEPS, opt-in; references/phase-gates.md)"]
    WD -. "loops phase steps (WF-A, WF-B, WF-C1, ...),<br/>each on its phase-tier model; C-phase steps<br/>delegate to a nested slice-drive run over DR" .-> DL
    GT -. "gate / A-B human stop" .-> WD
```

Drive mode doesn't replace the gate/human-approval boundary — it's the loop
arrow that repeatedly re-invokes the agent/skill/tier-routing step so a
slice can advance through multiple tasks without a human re-prompting each
one, and it hands control back to the human at every gate, decision point,
or budget stop per `governance/autonomy.yaml`.

**Workflow-drive is the outer ring around that loop.** Where drive mode
(above) loops a slice's *tasks*, `scripts/praxis-drive.sh --workflow` loops a
whole workflow's *phase steps*, one altitude up: `user → workflow-drive loops
phase steps (each launched on its phase-tier model, per
`skills/adaptive-model-routing`'s phase defaults) → within a C-phase step,
slice-drive loops tasks → specialists`. Its genuine unattended span is the
**C→D autonomy zone** only (implementation → release) — A (discovery) and B
(architecture) stay human-gated because that's where downstream exit
criteria are authored and frozen, and every `kind: gate` step is always a
human stop regardless of the dial. Opt-in via `--workflow`; schema and step
kinds in `references/phase-gates.md`, protocol in `skills/autonomous-drive`.

The 9 workflow files above are templates, not project plans — `delivery-planner`
instantiates each per-project (activating/deactivating branches by flag), and a
scenario only earns a new file when its gate topology differs; see
`skills/using-praxis/SKILL.md`'s Workflow composition policy.

## 2. The layer mental model

```mermaid
flowchart TD
    USER["User"]
    CMD["Commands (optional entry)<br/>commands/*.md — /start /discover /architect /slice<br/>/release /audit /steward /review /refine-idea<br/>/factory-record /drive"]
    WFL["Workflows<br/>workflows/*.yaml — 9 named compositions"]
    SKL["Skills<br/>skills/*/SKILL.md — 91 SKILLs, incl. skills/using-praxis (front door)<br/>and skills/autonomous-drive (drive protocol)"]
    AGH["Agents / harnesses<br/>agents/*.md role personas, run via each harness<br/>(claude-code / codex / gemini-cli)"]
    MOD["Models via capability tiers<br/>governance/model-routing.yaml — deep / standard / light"]

    USER --> CMD
    CMD --> WFL
    USER -.->|direct request, no slash command| WFL
    WFL --> SKL
    SKL --> AGH
    AGH --> MOD
```

Commands are an optional entry point — a user can also address a workflow
directly through `using-praxis`'s Layer 1 routing without typing a slash
command. Every layer below commands is mandatory: workflows always resolve
to skills, skills are consumed by agent personas, and every agent spawn
resolves to a concrete model through the tier table, never a hardcoded model
name.

## 3. The drive loop sequence

```mermaid
sequenceDiagram
    participant R as scripts/praxis-drive.sh (runner)
    participant H as Fresh harness invocation<br/>(claude -p / codex exec / gemini -p)
    participant DL as delivery-lead<br/>(skills/autonomous-drive protocol, one task)
    participant L as Task ledger<br/>.project/working/slice-<id>-tasks.yaml
    participant HU as Human

    loop Until a stop condition fires
        R->>H: invoke with constant drive prompt
        H->>DL: fresh context, no memory of prior iterations
        DL->>L: read next open task (depends_on satisfied)
        DL->>DL: implement task, run its verify command
        DL->>L: update status/attempts, set stop_flags if warranted
        L-->>R: ledger content + hash
        R->>R: check stop_flags, run_budget, stall (ledger hash unchanged?)
        alt non-negotiable stop (gate / decision / ADR / required KUACQ)
            R->>HU: pause, exit 5 (blocked)
        else budget ceiling hit
            R->>HU: pause, exit 4 (budget)
        else ledger hash unchanged N times
            R->>HU: pause, exit 3 (stalled)
        else stop_after boundary reached (task/slice/phase per governance/autonomy.yaml)
            R->>HU: pause, exit 0 (natural)
        else no stop condition
            R->>H: loop — next iteration
        end
    end
```

The runner, not the agent, is what enforces iteration caps, run budgets,
stall detection, and the non-negotiable stops — see
`references/loop-contracts.md` §3 for the iteration protocol this diagram
summarizes and `docs/autonomous-drive.md` for what each exit code means in
practice.

## 4. Slice lifecycle (task ledger states)

```mermaid
stateDiagram-v2
    [*] --> open: Lead Developer decomposes slice,<br/>writes slice-<id>-tasks.yaml
    open --> open: task done, next open task<br/>(depends_on satisfied) picked up
    open --> draining: all tasks done or failed/blocked
    draining --> gates: run Code Review / Security Review / QA<br/>per implementation-slice.yaml
    gates --> draining: gate verdict fail, back to fix
    gates --> closed: gates.code_review == pass<br/>gates.security_review == pass or n/a<br/>gates.qa == pass
    closed --> [*]: slice-close summary written to<br/>.project/telemetry/summaries/,<br/>next ledger opened

    open --> stopped: stop_flags raised<br/>(decision_required | gate_reached | blocked | budget_exceeded | stalled)
    gates --> stopped: stop_flags raised at gate boundary
    stopped --> open: human resolves, drive resumes
    stopped --> gates: human resolves, drive resumes
```

`state` in the ledger tracks `open | draining | gates | closed`;
`stop_flags` is the drive runner's contract — non-empty means the loop halts
at the next task boundary regardless of which ledger `state` it's in.  Full
field semantics: `references/loop-contracts.md` §2.

## Cross-links

- [`docs/lifecycle.md`](lifecycle.md) — the six human-facing phases and the
  gates they close with.
- [`docs/autonomous-drive.md`](autonomous-drive.md) — the operator guide to
  the autonomy dial, run budgets, and troubleshooting drive-mode stops.
- [`docs/model-routing.md`](model-routing.md) — how the tier table in
  diagram 2 resolves to concrete models per harness.
- [`docs/telemetry.md`](telemetry.md) — the telemetry layers that back the
  drive loop's cost proxy and the routing report.
- `references/loop-contracts.md` — the loop contract and task ledger
  schemas referenced by diagrams 3 and 4.
- `references/phase-gates.md` — the workflow-step ledger schema, the
  phase-exit predicate registry, and the C→D autonomy zone that
  workflow-drive (diagram 1) reads.
- `skills/using-praxis/SKILL.md` — the front door and orchestration runtime
  referenced in diagram 1.
