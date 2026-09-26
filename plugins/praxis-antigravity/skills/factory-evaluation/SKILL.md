---
name: factory-evaluation
description: "How the Praxis measures and evaluates ITSELF. The library's evals — skill efficacy, agent performance, workflow completion rate, gate clearance discipline, time-to-evidence per gate, defect leakage, slice cycle time, knowledge growth health. Distinct from `evaluation-engineering` (which evaluates the products you ship) — this skill evaluates the *factory that builds them*. Read by System Steward as the input for library-evolution proposals. Use when establishing baseline factory metrics, when investigating systematic regressions across projects, when proposing a skill change with evidence, when reviewing the library quarterly, or when the team feels something is degrading without knowing why."
---

# Factory Evaluation

<!-- praxis:metadata:begin -->
```yaml
capability: factory
domain: cross-cutting
state: active
dependencies:
  - skill-registry
  - memory-management
  - project-memory
  - engineering-standards
triggers:
  - "establishing baseline factory metrics for a new library install"
  - "quarterly library review"
  - "System Steward proposing a library change; evidence required"
  - "investigating cross-project regression (multiple projects degrading similarly)"
  - "evaluating whether a recent skill change improved or regressed outcomes"
  - "reporting library health to leadership"
outputs:
  - factory metric catalog (what we measure)
  - eval harness for the library (the harness itself)
  - quarterly factory report (the analysis)
  - skill efficacy report per skill
  - agent performance report per agent
  - knowledge-growth health report
consumers:
  - system-steward (primary consumer; proposes changes from evidence)
  - delivery-lead (consumes for orchestration retros)
  - principal (consumes for ROI conversations)
  - skill-registry (catalogs eval results per skill)
  - memory-management (memory health metrics)
references:
  - worked-examples.md
```
<!-- praxis:metadata:end -->

The discipline of evaluating the Praxis itself. Teams that don't measure their factory cannot improve it — they iterate on hunches, ship "improvements" that may regress, and accumulate skill bloat. This skill makes the factory measurable: skills measured for efficacy, agents measured for performance, workflows measured for completion + cycle time, governance gates measured for evidence-completeness + time-to-clear.

The principle: **what we measure improves. The library is no exception. Measure the library; improve the library.**

## When this skill fires

- Establishing baseline factory metrics for a new library install.
- Quarterly library review.
- System Steward proposing a library change with evidence.
- Investigating cross-project regression (multiple projects show similar degradation).
- Evaluating whether a recent skill change improved or regressed outcomes.
- Reporting library health to leadership / principal.

## What this skill is NOT

- Evaluating products / AI features you ship (that's `evaluation-engineering` for agentic; `ml-training-evaluation` for ML; `testing-strategy` for application code).
- Measuring individual contributor performance (this is about the factory, not the worker).
- A replacement for retros (it informs retros).

## The factory metric catalog

Five metric families.

### 1. Skill metrics (per SKILL)

| Metric | What it measures | Signal |
|---|---|---|
| **Invocation rate** | How often the skill fires across projects | Discoverability problem if invocation < expected. |
| **Trigger precision** | When the skill fires, was it the right skill? | Trigger description quality. |
| **Trigger recall** | When the skill SHOULD have fired, did it? | Missing trigger phrases. |
| **Time-to-output** | How long from invocation to producing the output | Skill bloat / clarity issue if growing. |
| **Output acceptance rate** | Reviewers accept the skill's output without major rework | Skill quality. |
| **Downstream rework rate** | Outputs that downstream skills had to rework | Skill incompleteness or boundary leak. |
| **Reference drift** | How often references go stale | Maintenance load. |
| **Lifecycle state** | experimental / active / deprecated / merged | Health snapshot. |

### 2. Agent metrics (per ROLE AGENT)

| Metric | What it measures | Signal |
|---|---|---|
| **Hand-off latency** | Time agent waits between getting a packet and acting | Coordination overhead. |
| **Decision quality** | Sample-reviewed decisions vs principal's would-be-decision | Agent calibration. |
| **Escalation rate** | How often the agent escalates to principal | Either correctly escalating (good) or under-confident (bad). |
| **Per-AOP-step time distribution** | Where in the AOP the agent spends most time | Bottleneck identification. |
| **Tool-call efficiency** | Number of tool calls per outcome | Agent verbosity / loop discipline. |
| **Cross-agent contention** | Tasks waiting on this agent | Bottleneck. |

### 3. Workflow metrics (per WORKFLOW)

| Metric | What it measures | Signal |
|---|---|---|
| **Completion rate** | Workflows that reach exit_criteria | Process health. |
| **Phase cycle time** | Time per phase (PM, SA, Implementation, Release) | Bottleneck. |
| **Decision Node distribution** | Branches taken at each Decision Node | Workflow fit; rare-branch over-engineering. |
| **Gate clearance time** | Time from gate-reached to gate-cleared | Governance overhead vs evidence depth. |
| **Defect leakage** | Defects found in slice N that originated in slice N-K | Quality gates regressing. |
| **Rework rate** | Slices reopened after closure | DoD discipline. |

### 4. Governance metrics (per GATE)

| Metric | What it measures | Signal |
|---|---|---|
| **Evidence completeness on first submission** | Was the evidence pack right the first time? | Skill / agent training quality. |
| **Time-to-clear** | From gate-reached to approver decision | Governance load; principal bandwidth. |
| **Reject + iterate rate** | Gates that needed multiple rounds | Quality of upstream work. |
| **Conditional gate fire rate** | Conditional gates that actually triggered | Activation rule calibration. |
| **Override usage** | Challenger objections overridden / security findings accepted | Risk posture trend. |

### 5. Library health metrics

| Metric | What it measures | Signal |
|---|---|---|
| **Skill count** | Total SKILLs | Approaching 101+ → consolidation. |
| **Capability balance** | Skill count per capability area | Imbalance — one area expanding unmanaged. |
| **Skill lifecycle distribution** | % active / experimental / deprecated | Pruning discipline. |
| **Memory volume per type** | Lines per memory class (semantic / episodic / etc.) | Memory bloat per `memory-management`. |
| **Memory stale rate** | Memory entries unrefreshed beyond SLO | Reconciliation discipline. |
| **Reference count per skill** | References attached to each skill | Knowledge growth in references not skills. |
| **Pattern catalog size** | Pattern count and adoption | Pattern reuse discipline. |

## The factory eval harness

### Capture: mined artifacts (primary) + stub layer (supplementary)

Early versions of this harness tried to catch usage at the tool-event layer
(hook-fired stubs for every SKILL read, preload, and session boundary).
Real-world capture ratio proved to be ~5% — plugin-injected skills never
fire a `Read` event, and main-session orchestration (no sub-agent `Task`
spawn) produces no spawn event either. That approach has been retired for
skill/agent usage; the read/preload/session stub types are no longer
written.

**Primary sources — mined from mandatory workflow artifacts** (near-100%
capture because these are required outputs, not tool-event side effects):

| Source | What it gives | Read by |
|---|---|---|
| `.project/episodic/checkpoint-*.md` | The universal aggregation record, written at every closure boundary (gate/phase/slice/loop/disposition/workflow-end): agents dispatched, skills consumed, cost proxy, human touchpoints, deviations. See `references/factory-metrics-schema.md`, "Checkpoint records." | `scripts/factory-usage-report.py` |
| `.project/working/slice-*-packet.md` + `slice-*-tasks.yaml` | Skills named in the packet, agents assigned per task | `scripts/factory-usage-report.py` |
| `.project/working/routing-*.md` | Dispatch records + routing-decision frontmatter | `scripts/factory-usage-report.py`, `scripts/factory-routing-report.py` |
| `.project/telemetry/{agent-spawns,model-routing,drive,sessions}.jsonl` | Structured spawn/completion, routing-decision, drive-run, and session events | `scripts/factory-routing-report.py`, `scripts/factory-usage-report.py` |

**Supplementary — the stub layer** (still written, but no longer primary
evidence for skill/agent usage):

| Layer | What it catches | How | Reliability |
|---|---|---|---|
| **Command invocations** | User invoked a praxis command directly | `UserPromptSubmit` parsed for `/praxis:<cmd>` or `/cmd` → `.project/operational/factory-metrics/commands/` (invocation: `invoke`) | ~100% in Claude Code |
| **Human observations** | Rich, human-authored notes on a specific use | `/praxis:factory-record` slash command (manual) | Discipline-dependent |

Skill-read, output-apply, and agent-preload stub types (formerly Layers 0/2/3
above) are retired: they don't fire for plugin-injected skills or
main-session orchestration, and the mined sources above cover the same
ground with much higher capture.

### Invocation enum

The frontmatter `invocation:` field on every telemetry file distinguishes how the artifact was used:

- `invoke` — a slash command was invoked (still stubbed by the tap; the live command-usage source)
- `fire` — a hook script executed
- `evaluate` — a governance gate was evaluated
- `complete` — a sub-agent finished
- `read` / `apply` / `preload` / `spawn` — legacy invocation types written by the retired
  read/preload/session stub layer. Files bearing these still exist from before the slimdown
  and are counted by the report tools as the "legacy stub layer," but nothing writes new
  ones — skill/agent usage now comes from the mined sources above.

### Storage

- Per-use telemetry at `.project/operational/factory-metrics/<type>s/<name>/<date>-<rand>.md` (one file per invocation).
- Quarterly synthesis at `.project/operational/factory-metrics/{quarter}.md` (Steward writes).
- Per-artifact quarterly rollup at `.project/operational/factory-metrics/<type>s/<name>/<quarter>.md`.
- Format spec: `references/factory-metrics-schema.md`.

### Helper scripts (ship with the plugin)

| Script | Purpose | When run |
|---|---|---|
| `scripts/factory-usage-report.py` | **Primary usage analytics** — mines `.project/episodic/checkpoint-*.md`, working packets/task ledgers, routing logs, command stubs, and session telemetry into a per-skill / per-agent / per-workflow / per-command usage report | Steward review + CI smoke test |
| `scripts/factory-routing-report.py` | Routing/cost aggregation — reads `.project/telemetry/` (`agent-spawns.jsonl`, `model-routing.jsonl`, `drive.jsonl`) + `.project/working/routing-*.md` prose logs to report tier & cost-proxy totals per agent | Steward review + CI smoke test |
| `scripts/factory-record.sh` | Universal recorder — writes one telemetry file (commands + manual observations) | Called by hooks, slash commands |
| `hooks/tap.sh` | Command-invocation + spawn/session tap | Wired in `hooks/hooks.json` |
| `scripts/factory-frequency.sh` / `scripts/factory-aging.sh` | Legacy stub-layer aggregation/aging — see deprecation notes in each script; superseded by `factory-usage-report.py` for skill/agent usage, still useful for command-stub aging | Steward review + CI gate |
| `/praxis:factory-record` slash command | Human-authored rich observation | User-invoked |

### Implementation details

- **Dedup per session**: auto-stub entries dedupe within a session via `.project/working/.factory-tap/<session-id>` (don't write 50 entries for one SKILL re-read 50 times in one conversation).
- **Fail-soft**: telemetry NEVER blocks Claude. All hook errors swallowed; recorder exit 0 unless arg error.
- **Tool-agnostic format**: the file format works for all 8 supported coding tools; only the trigger (hook vs workflow step vs manual) varies per tool.

## The quarterly factory report

Reports library counts, top/bottom-5 skills by invocation, agent performance, workflow completion, gate clearance, findings, and recommendations handed to System Steward. Load `references/worked-examples.md` for the full worked template.

## The skill efficacy report

Per skill, periodic deep-dive covering invocation counts, trigger precision/recall, output acceptance, downstream rework, and recommendations. Load `references/worked-examples.md` for the full worked template (`code-review` example). System Steward consumes these to propose changes.

## Knowledge growth health

Per the Knowledge Growth Policy (blueprint Section 14): new knowledge grows in references / patterns / examples / evaluations — NOT skills.

Metric:

- Skill additions this quarter: 0 expected at steady state; reviewed if > 2.
- Reference additions: typical 3-8 per quarter at steady state.
- Pattern additions: typical 1-3.
- Example additions: typical 2-6.

Skill count creep (skills added that should have been references) is the leading indicator of library decay.

## Outputs

| Output | Location |
|---|---|
| Factory metric catalog | this SKILL + `references/factory-metrics-catalog.md` |
| Eval harness scripts | `factory-eval/` |
| Quarterly factory report | `.project/operational/factory-metrics/{quarter}.md` |
| Skill efficacy reports | `.project/operational/factory-metrics/skills/{skill}/{quarter}.md` |
| Agent performance reports | `.project/operational/factory-metrics/agents/{agent}/{quarter}.md` |
| Knowledge-growth health | included in quarterly report |

## Mode handling

Same in greenfield and brownfield — the factory eval applies regardless of project mode. The library installation date is the start of telemetry.

## Critical disciplines

**Telemetry from day one.** Without telemetry there's no eval; without eval there's no improvement.

**Sample-based quality eval.** Some metrics (decision quality, output acceptance) require human review — sample N items, don't try to instrument everything.

**Evidence-driven proposals only.** System Steward proposals reference factory-eval evidence. "It feels like X is slow" is not evidence.

**Quarterly cadence default.** More frequent reviews tend toward over-tweaking; less frequent let problems compound. Quarterly is the default sweet spot.

**Don't optimize the metric.** Goodhart's law applies — once a metric becomes a target it stops being a good measure. Watch for measure-gaming.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We feel like the library is healthy." | Feel isn't measurement. Metrics are the calibration. |
| "Telemetry is over-engineering." | Without telemetry, the System Steward operates on hunches. Evidence-based proposals require data. |
| "Quarterly is too often." | Annual misses 4 quarters of compounding issues. Quarterly is the sweet spot. |
| "Single skill metric is enough." | One metric ignores precision-vs-recall, output-vs-cost, etc. Five families exist for reasons. |
| "Goodhart's law is theoretical." | It isn't. Once a metric is a target, the metric games itself. Watch the indirect signals. |
| "Improvements are obvious from inspection." | Hunches are wrong half the time. Evidence-based proposals avoid wasted churn. |

## Verification

You are done when:

- [ ] Telemetry collection in place across skills/agents/workflows/governance.
- [ ] All five metric families computed: skill / agent / workflow / governance / library health.
- [ ] Quarterly report at `.project/operational/factory-metrics/<quarter>.md`.
- [ ] Per-skill efficacy reports for the top-10 most-invoked + bottom-10 least-invoked.
- [ ] Knowledge-growth metric tracked (skills vs references vs patterns vs examples).
- [ ] Goodhart-watch: indirect signals reviewed for measure-gaming.
- [ ] Recommendations grouped into `steward-promotion` proposals.
- [ ] Items NOT proposed explicitly listed (discipline against over-reacting).

Evidence to check:
- A proposed change cites specific metric movement.
- Past quarterly recommendations have measurable follow-through.

## Anti-patterns

- No telemetry; "improvements" proposed from feel.
- Single metric used to judge everything ("invocation count").
- Quality metrics computed without sampling (LLM-judge of skill outputs is tempting but biased the same way as in `evaluation-engineering`).
- Quarterly report becomes performative; recommendations don't drive action.
- Over-tweaking — change something every week based on noise.
- Measuring everything; analyzing nothing.
- No baseline — "is this good?" can't be answered without prior data.
- Goodhart on a single skill metric (boosting invocation counts to look healthy).
- Factory-eval skipped in busy quarters; library decays unobserved.
- Skill changes without before-after evidence (System Steward can't operate without this).
