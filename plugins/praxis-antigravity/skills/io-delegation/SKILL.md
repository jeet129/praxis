---
name: io-delegation
description: >-
  Portal-style IO delegation — intercept large file reads via PreToolUse hooks,
  summarize with a light-tier model, and deny the original read to save tokens.
---

# IO Delegation

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - adaptive-model-routing
  - llm-cost-optimization
triggers:
  - "reading a large file (>350 lines) — delegate to a cheap model?"
  - "token budget is tight — how do I reduce file-read costs?"
  - "configuring IO delegation threshold or timeout"
outputs:
  - summarized file content injected via deny reason
  - telemetry record at .project/telemetry/io-delegation.jsonl
consumers:
  - delivery-lead
  - lead-developer
```
<!-- praxis:metadata:end -->

Portal-style token optimization inspired by
[Spotify's Portal](https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90).

## What it does

When the primary model requests a `Read` of a file exceeding the line
threshold (default 350), a PreToolUse hook intercepts the call:

1. Counts lines in the target file
2. If above threshold, shells out to a **light-tier subagent** (resolved via
   `governance/model-routing.yaml`) to produce a structured bullet summary
3. **Denies** the original Read — feeding the summary as the deny reason
4. The expensive model receives the summary instead of the raw file

The expensive model never sees the full file content, saving tokens
proportional to the file's size.

## Harness support

| Harness | Status | Failure mode | Script |
|---|---|---|---|
| Claude Code | ✅ Implemented | Fail-open (safe) | `hooks/io-delegate-read.sh` |
| Antigravity | ✅ Implemented | Fail-closed → timeout+allow fallback | `hooks/io-delegate-read-agy.py` |
| Codex CLI | ❌ Not supported | N/A — `tool_name` is always `"Bash"` | — |

### Claude Code

- PreToolUse hook on `Read` matcher in `hooks/hooks.json`
- Resolves `light` tier → `haiku` via `resolve-model.py`
- Calls `claude --model <model> -p` for one-shot summarization
- 30-second default timeout; any failure allows the read normally
- Deny survives `--dangerously-skip-permissions`

### Antigravity

- Separate `praxis-io-delegation` hook group in `plugins/praxis-antigravity/hooks.json`
- Resolves `light` tier → `flash` (advisory — agy applies nothing programmatically)
- **3-second aggressive timeout** because agy is fail-closed
- Falls back to `{"decision":"allow"}` on ANY failure
- `--dangerously-skip-permissions` bypasses hooks entirely (disables delegation)
- Token usage not exposed in hooks — savings not measurable programmatically

### Codex CLI

Not implemented. Codex routes everything through Bash, so `tool_name` is always
`"Bash"` — there's no way to reliably intercept file reads at the hook level
without fragile command-string parsing.

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `PRAXIS_IO_DELEGATE_MIN_LINES` | `350` | Line threshold to trigger delegation |
| `PRAXIS_IO_DELEGATE_TIMEOUT` | `30` (CC), `3` (agy) | Summarizer timeout in seconds |
| `PRAXIS_IO_DELEGATE_DISABLED` | `0` | Set to `1` to disable delegation entirely |

## Model routing

The summarizer model is resolved via the standard Praxis model-routing chain:

```
resolve-model.py --harness <harness> --tier light --field model
  → project override (.project/governance/model-routing.yaml)
  → plugin default (governance/model-routing.yaml)
```

Default resolutions:
- Claude Code: `light` → `haiku`
- Antigravity: `light` → `flash` (advisory)

Override per-engagement by setting `light` tier in your project's
`.project/governance/model-routing.yaml`.

## Telemetry

Each delegation decision is logged to:
```
.project/telemetry/io-delegation.jsonl
```

Record schema:
```json
{
  "ts": "2026-10-12T...",
  "event": "io_delegation",
  "harness": "claude-code|antigravity",
  "decision": "deny|allow",
  "reason": "delegated|summarizer_failed|no_resolve_script",
  "file": "/path/to/file.py",
  "file_lines": 842,
  "summary_lines": 45,
  "threshold": 350,
  "model": "haiku"
}
```

The telemetry stream is compatible with `scripts/factory-routing-report.py`
and the existing `cost_weights` in `model-routing.yaml` for proxy cost
estimation.

## Summarizer prompt

The light-tier model receives a structured prompt asking for:
- Every exported function/class/type with a one-line description
- Key imports and dependencies
- File's primary responsibility
- Side effects (global state, I/O, env var reads)
- Output capped at 80 lines
- No large code block reproduction

File content is capped at 50K characters to bound summarizer input cost.

## When NOT to delegate

IO delegation is intentionally conservative:
- Files ≤350 lines pass through normally (the summary would cost more than the savings)
- Binary files, images, PDFs are not intercepted (Read tool handles these differently)
- The `offset`/`limit` partial-read pattern is not intercepted (already optimized)

## Disabling

Set `PRAXIS_IO_DELEGATE_DISABLED=1` in your environment, or remove the
PreToolUse hook entry from `hooks.json`.

## Relationship to adaptive model routing

IO delegation operates at the **tool level** (PreToolUse hooks), orthogonal to
the **agent level** adaptive model routing (delivery-lead ±1 tier shifts).
A delivery-lead that has demoted an agent to `light` tier is already running
on the cheap model — IO delegation on top of that is redundant. The
escalation policy (`on_gate_failure: promote_one_tier_and_retry_once`) does
not apply to IO delegation failures; those fail-open silently.
