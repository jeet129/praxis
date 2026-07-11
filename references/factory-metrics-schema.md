# Factory Metrics Schema

This document specifies the on-disk format for praxis telemetry. Every entry in `.project/operational/factory-metrics/` follows this schema, regardless of which tool produced it (Claude Code, Codex, Cursor, Gemini, OpenCode, Copilot, Kiro, Antigravity) or which mechanism captured it (PostToolUse hook, workflow YAML step, slash command, manual entry).

The schema's purpose is to let the System Steward synthesize across projects, tools, and capture mechanisms without per-source adapters.

## File location

```
.project/operational/factory-metrics/<type>s/<name>/<YYYY-MM-DD>-<random>.md
```

Where:
- `<type>` is one of: `skill`, `agent`, `workflow`, `command`, `hook`, `gate`, `reference`
- `<name>` is the artifact's identifier (e.g., `requirements-intake`, `delivery-lead`, `brownfield-enhancement`)
- `<YYYY-MM-DD>` is UTC date
- `<random>` is a 6-character lowercase alphanumeric suffix to prevent collisions

Aggregate or quarterly synthesis files use a different layout:

```
.project/operational/factory-metrics/<type>s/<name>/<YYYY-Q1>.md   # quarterly synthesis
.project/operational/factory-metrics/<quarter>.md                  # cross-artifact quarterly report
```

## File format

Each entry is a markdown file with YAML frontmatter and an optional body. Frontmatter fields are stable across tools; the body is optional free-text observation.

### Required frontmatter fields

| Field | Type | Description | Example |
|---|---|---|---|
| `artifact_type` | enum | `skill` \| `agent` \| `workflow` \| `command` \| `hook` \| `gate` \| `reference` | `skill` |
| `artifact_name` | string | The artifact's identifier (kebab-case) | `requirements-intake` |
| `date` | ISO 8601 UTC | When the invocation happened | `2026-06-28T14:23:00Z` |
| `tool` | enum | Which coding tool fired the event | `claude-code` |
| `trigger` | enum | What caused the entry to be written | `auto-hook` |
| `invocation` | enum | What kind of invocation | `read` \| `spawn` \| `fire` \| `evaluate` \| `complete` \| `invoke` |

### Optional frontmatter fields

| Field | Type | Description |
|---|---|---|
| `artifact_state` | enum | `experimental` \| `active` \| `deprecated` \| `merged` \| `removed` \| `unknown` |
| `session` | string | Session identifier (per-tool format) |
| `slice` | string | Slice id (if in a slice context) |
| `agent` | string | The agent that invoked the artifact (if known) |
| `duration_seconds` | number | Time spent on the invocation (if measurable) |
| `outcome` | enum | `success` \| `failure` \| `partial` \| `null` |
| `mode` | enum | `per-use` \| `aggregate-slice` \| `auto-stub` |

### Body

The body is optional markdown. When present, it should contain at least one of:

- `## Observation` — what was noticed during the invocation
- `## What worked` — discipline that landed correctly
- `## Friction` — places the discipline was clunky
- `## Edge cases` — situations the artifact didn't anticipate
- `## Suggested refinements` — what should change

For `auto-stub` entries (recorded by hooks without human observation), the body may be empty. The Steward fills body content during synthesis or asks the agent to backfill.

## Trigger enum semantics

| Trigger | Means |
|---|---|
| `auto-hook` | A PostToolUse / SubagentStart / UserPromptSubmit hook caught the invocation. The most common case in Claude Code. |
| `workflow-step` | A YAML workflow step explicitly invoked the recorder. Used for gates and high-frequency aggregate captures. |
| `slash-command` | A user-typed slash command (`/praxis:factory-record`) explicitly captured this. |
| `manual` | A human directly invoked the recorder or wrote the file by hand. |
| `session-end` | The SessionEnd hook fired (best-effort end-of-session capture). |
| `validator` | The validator gate flagged a missing telemetry and synthesized a placeholder. |

## Invocation enum semantics

| Invocation | Means | Typical artifact type |
|---|---|---|
| `read` | The artifact's source file was read into context | skill, workflow, reference |
| `spawn` | An agent sub-process was started | agent |
| `fire` | A hook script executed | hook |
| `evaluate` | A governance gate was evaluated | gate |
| `complete` | An agent sub-process finished | agent |
| `invoke` | A slash command was invoked | command |

## Examples

### Auto-stub from PostToolUse hook (the most common entry)

```markdown
---
artifact_type: skill
artifact_name: requirements-intake
artifact_state: experimental
date: 2026-06-28T14:23:00Z
session: 8f3c-a1b2
tool: claude-code
trigger: auto-hook
invocation: read
mode: auto-stub
---
```

(No body — the agent didn't backfill yet. The Steward sees the use happened.)

### Rich observation from a workflow step

```markdown
---
artifact_type: skill
artifact_name: code-review
artifact_state: active
date: 2026-06-28T16:45:00Z
session: 8f3c-a1b2
tool: claude-code
trigger: workflow-step
invocation: read
slice: slice-3
agent: code-reviewer
duration_seconds: 420
outcome: success
mode: per-use
---

## Observation
Caught 2 minor issues + 1 major (untested error path). Major required a rework slice.

## What worked
The severity-tagged output made the rework decision obvious; principal approved without debate.

## Friction
Diff annotation was tedious because the PR touched 14 files. The skill could suggest grouping comments by file for high-fanout PRs.

## Suggested refinements
Add an "if PR touches > 8 files, group comments by file" rule to the procedure.
```

### Gate evaluation

```markdown
---
artifact_type: gate
artifact_name: requirements_freeze
date: 2026-06-28T11:00:00Z
session: 8f3c-a1b2
tool: claude-code
trigger: workflow-step
invocation: evaluate
slice: null
outcome: success
mode: per-use
---

## Observation
Evidence pack complete on first try; principal approved in 2h.
Time-to-evidence: 1d 4h (target ≤ 2d). Within band.
```

### SubagentStart capture

```markdown
---
artifact_type: agent
artifact_name: solution-architect
date: 2026-06-28T09:15:00Z
session: 8f3c-a1b2
tool: claude-code
trigger: auto-hook
invocation: spawn
slice: slice-3
mode: per-use
---
```

## Cross-tool consistency

When telemetry comes from a tool other than Claude Code, the `tool` field changes and the `trigger` may differ (Codex / Cursor / etc. typically have less native hook support — many entries from those tools will be `trigger: workflow-step` or `trigger: manual`). The Steward synthesis should NOT treat one tool's entries as canonical and the others as second-class. All entries are equally weighted; sampling biases per tool should be noted in the quarterly synthesis.

## Schema versioning

This is schema version 1.0 (2026-06-28). Field additions are allowed in minor versions; field removals or renames require a major version bump and a migration script in `scripts/factory-metrics-migrate.sh`. The Steward's synthesis tools must be robust to unknown frontmatter fields (ignore them rather than error).

## What is NOT in this schema

- Per-skill custom metadata. If a particular SKILL wants to record domain-specific signals (e.g., `code-review` recording number of comments), put them in the body under `## Observation` or `## Custom metrics`. Don't extend frontmatter — it kills cross-skill synthesis.
- Sensitive data. Telemetry files commit to git. Don't write user secrets, tokens, customer data, or anything you wouldn't want in a public repo.

## Validation

Run `scripts/validate-factory-metrics.sh` to check all entries parse correctly and meet schema requirements. CI should run this on every PR that touches `.project/operational/factory-metrics/`.

## Telemetry JSONL schemas

### Routing-decision fallback: routing-*.md frontmatter

`model-routing.jsonl` is agent-written and can be skipped under load. The
authoritative fallback is the `routing:` block delivery-lead embeds in every
`routing-{timestamp}.md` frontmatter (agent, default_tier, chosen_tier,
score, reason). `scripts/factory-routing-report.py` merges these as decided
records (source: `prose-frontmatter`), so routing-discipline coverage
reflects either form. If BOTH are missing while spawns occurred, adaptive
routing is genuinely not being practiced.

Two append-only JSONL files under `.project/telemetry/` carry structured routing/cost telemetry. Unlike the markdown records above, these are one-JSON-object-per-line, machine-written, and never hand-edited. Both are optional — their absence just means the coverage-dependent tools (see below) fall back to prose logs and static defaults.

### `.project/telemetry/agent-spawns.jsonl`

Written by `hooks/tap.sh` on the `Task` (subagent spawn) and `SubagentStop` (completion) hook events. Two event shapes share the file:

```jsonc
// spawn — written when a sub-agent is launched
{"ts": "2026-06-28T09:15:00Z", "event": "spawn", "session": "8f3c-a1b2", "agent": "solution-architect", "model": null}

// complete — written when a sub-agent finishes
{"ts": "2026-06-28T09:42:00Z", "event": "complete", "session": "8f3c-a1b2", "agent": "solution-architect", "status": "success", "input_tokens": null, "output_tokens": null}
```

| Field | Type | Present on | Description |
|---|---|---|---|
| `ts` | ISO 8601 UTC | both | When the event fired |
| `event` | enum | both | `spawn` \| `complete` |
| `session` | string | both | Session identifier |
| `agent` | string | both | Agent name (matches `agents/*.md` filename) |
| `model` | string \| null | spawn | Resolved model name if the spawner passed one explicitly; `null` means the agent frontmatter default applied |
| `status` | string | complete | Outcome as reported by the harness (`success`, `failure`, etc.) |
| `input_tokens` / `output_tokens` | number \| null | complete | Token usage when the harness provides it; `null` otherwise |

This is the deterministic half of routing telemetry — it captures what actually happened (spawn + model, completion + status/usage) regardless of whether the delivery-lead remembered to log a routing decision.

### `.project/telemetry/model-routing.jsonl`

Written by the delivery-lead per `skills/adaptive-model-routing/SKILL.md`, before each agent spawn — the deliberate half of routing telemetry (the rubric decision, not just the outcome):

```jsonc
{"ts": "2026-06-28T09:14:00Z", "agent": "solution-architect", "default_tier": "standard", "chosen_tier": "deep", "score": 8, "reason": "payment + compliance + cross-cutting = deep tier"}
```

| Field | Type | Description |
|---|---|---|
| `ts` | ISO 8601 UTC | When the routing decision was made |
| `agent` | string | Agent the decision applies to |
| `default_tier` | enum | `deep` \| `standard` \| `light` — the agent's baseline tier per `capability_tier:` in `agents/<agent>.md` |
| `chosen_tier` | enum | `deep` \| `standard` \| `light` — the tier actually selected after scoring |
| `score` | number | Rubric score (signals summed — see `skills/adaptive-model-routing/SKILL.md`) |
| `reason` | string | Short rationale for the chosen tier, especially when it differs from `default_tier` |

`scripts/factory-routing-report.py` also tolerates the richer field names shown in `skills/adaptive-model-routing/references/routing-examples.md` (`tier`/`resolved_tier` as aliases for `chosen_tier`, `default` as an alias for `default_tier`) — either shape parses correctly.

### `.project/telemetry/drive.jsonl`

Written by `scripts/praxis-drive.sh` (the outer drive runner), one line per drive iteration — the outer loop's telemetry layer, distinct from the per-agent `agent-spawns.jsonl` above. Copied here from `references/loop-contracts.md` section 4, the pinned spec:

```jsonc
{"ts":"2026-07-10T12:00:00Z","run_id":"drive-20260710-1200","iteration":4,
 "slice":"S9","task":"S9-T2","agent":"backend-developer","tier":"standard",
 "outcome":"done","ledger_hash":"a1b2c3","stop_flags":[],"cost_proxy":1.0}
```

| Field | Type | Description |
|---|---|---|
| `ts` | ISO 8601 UTC | When the iteration completed |
| `run_id` | string | Identifies one drive session (`drive-<YYYYMMDD-HHMMSS>`); stable across every iteration in that session |
| `iteration` | number | 1-indexed iteration counter within the run |
| `slice` | string | Slice id the ledger belongs to |
| `task` | string | Task id processed this iteration |
| `agent` | string | Agent dispatched for the task (matches `agents/*.md` filename) |
| `tier` | enum | `deep` \| `standard` \| `light` — the task's tier at the time of this iteration |
| `outcome` | string | The task's ledger `status` after the iteration (`done` \| `failed` \| `in_progress` \| `open` \| `blocked`, or `unknown` if unreadable) |
| `ledger_hash` | string | sha256 of the ledger file after the iteration — the stall-detection signal |
| `stop_flags` | array of strings | Ledger `stop_flags` observed after the iteration; empty when clear |
| `cost_proxy` | number | Tier-weighted cost unit for this single iteration (`cost_weights` from `governance/model-routing.yaml`) |

### `scripts/praxis-drive.sh` exit codes

The runner is fail-safe: every stop is a clean exit with a human summary, never a crash.

| Exit code | Meaning |
|---|---|
| `0` | Natural stop — `gate_reached`/`decision_required` stop_flag, the task queue drained, or the `stop_after` dial's boundary (`task`/`slice`) was reached |
| `2` | No active task ledger found (and none named via `--slice`) — nothing to drive; run `/slice` first |
| `3` | Stalled — ledger hash unchanged for `stall.max_iterations_without_ledger_change` consecutive iterations |
| `4` | Run budget hit — `max_iterations_per_run`, `cost_ceiling_proxy`, or `max_slices_per_run` from `governance/autonomy.yaml` |
| `5` | Blocked/exhausted — a task hit `max_task_attempts` and raised a `blocked` stop_flag, or no task in the ledger is drive-eligible |

### Reading the telemetry: `scripts/factory-routing-report.py`

Run `python3 scripts/factory-routing-report.py --project-dir <path-to-or-above-.project> --format md|json --out <file>` to aggregate both JSONL files above plus the prose `.project/working/routing-*.md` dispatch logs, `.project/operational/factory-metrics/` usage records, and `.project/telemetry/drive.jsonl` drive-run telemetry into one report: data coverage, per-slice dispatches, per-agent activity, tier & cost-proxy totals (using `cost_weights` from `governance/model-routing.yaml`), routing-discipline coverage, drive-run summaries (iterations/slices/tasks/cost per run, stop reasons, human-touchpoint density), and heuristic recommendations. Zero dependencies beyond the Python 3 standard library; fails soft (exit 0) when telemetry is absent — every section just reports zero records and says so.
