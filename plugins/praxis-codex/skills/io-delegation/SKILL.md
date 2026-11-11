---
name: io-delegation
description: "Delegate large-file reads to the light-tier worker."
---

# IO Delegation

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
listing_tier: B
dependencies:
  - adaptive-model-routing
  - llm-cost-optimization
triggers:
  - "reading a large file (>350 lines) — delegate to a cheap model?"
  - "token budget is tight — how do I reduce file-read costs?"
  - "configuring IO delegation threshold or timeout"
outputs:
  - worker answer to a specific question about large files (via bulk-read.sh)
  - telemetry record at .project/telemetry/io-delegation.jsonl
consumers:
  - delivery-lead
  - lead-developer
```
<!-- praxis:metadata:end -->

Keep large source files out of the expensive model's context. A hook blocks a
whole-file read of a big file; you then ask the light-tier worker a specific
question about it and get back only the answer.

Pattern adapted from Spotify's `shunt` plugin
([post](https://engineering.atspotify.com/2026/9/portal-by-spotify-cut-my-claude-code-token-usage-by-90),
[source](https://github.com/spotify/portal-ai-plugins), Apache-2.0).

## How to use it

When a read is blocked (or before reading any source file over ~350 lines, or
when a question spans three or more files), run:

```bash
bash "<plugin root>/skills/io-delegation/scripts/bulk-read.sh" \
  --question "<a specific question>" --paths <file1> [<file2> ...]
```

- Ask a real question ("which functions write to the orders table, and what do
  they validate first?"), not "summarise this file".
- Each call is independent. For a follow-up, call again with the same `--paths`;
  the files go to the worker, never into your context.
- The block message prints the exact script path for the current install.

## What must still be read directly

The worker's answer carries **no reliable line numbers** and it misses subtle
defects. Read the code yourself, with the Read tool's `offset` and `limit`
(targeted reads are never blocked), when you are about to:

- **edit** the file — read the section you will change first;
- **review** code for correctness, security or concurrency;
- **debug** a failure, or make an architecture decision that depends on it.

Use delegation for orientation and lookup. Do the reasoning yourself.

## What the hooks do

| Harness | Hook | Blocks |
|---|---|---|
| Claude Code | `hooks/io-delegate-read.sh` (PreToolUse `Read`) | whole-file Read of a source file over the threshold |
| Claude Code | `hooks/io-delegate-bash.sh` (PreToolUse `Bash`) | `cat`/`less`/`more`, and `head`/`tail` beyond the threshold, on such a file; pipes and redirects pass |
| Antigravity | `hooks/io-delegate-read-agy.py` (PreToolUse `view_file`) | whole-file `view_file` over the threshold |
| Codex | none | Codex reads through shell commands; call `bulk-read.sh` by choice |

The hooks never call a model. They fail open: on any error the read proceeds.

Never blocked: targeted reads; Markdown, YAML, TOML and other prose/config
files; anything under `.project/`, `.claude/`, `.agents/` or the Praxis plugin
itself (skills, references and ledgers must reach you verbatim).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `PRAXIS_IO_DELEGATE_MIN_LINES` | `350` | Files at or below this are read normally; below it, delegation overhead exceeds the saving |
| `PRAXIS_IO_DELEGATE_DISABLED` | `0` | Set to `1` to turn the hooks off |
| `PRAXIS_IO_DELEGATE_MODEL` | light tier | Override the worker model |
| `PRAXIS_IO_DELEGATE_TIMEOUT` | `90` | Worker timeout in seconds |

The worker model is the `light` tier for the current harness from
`governance/model-routing.yaml` (a project copy under `.project/governance/`
wins). See `adaptive-model-routing`.

## Telemetry

`.project/telemetry/io-delegation.jsonl` records each blocked read
(`decision: deny`), each `bulk_read` call (bytes sent, answer size), and each
targeted re-read of a previously blocked file (`reason: targeted_reread`). A high
re-read rate means the threshold is too low for the codebase; raise it.

Expect 10 to 30 seconds per delegation.
