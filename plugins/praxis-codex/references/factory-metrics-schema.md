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
