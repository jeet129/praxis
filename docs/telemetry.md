# Telemetry

Praxis captures three layers of telemetry, with deliberately different
reliability guarantees. Read this before trusting a number from a report —
two of the three layers are deterministic (hook-written, no agent
cooperation required); the third depends on the delivery-lead actually
following the routing discipline. The report tool labels every figure by
which layer it came from so you're never guessing.

## The three layers

### Layer (a) — usage records (deterministic)

**What:** One markdown file per artifact invocation (SKILL read, agent
spawn, workflow step, command run, gate evaluation, reference read).

**Path:** `.project/operational/factory-metrics/<type>s/<name>/<date>-<rand>.md`
— for example `.project/operational/factory-metrics/skills/threat-modeling/2026-06-28-a1b2.md`.

**How it's written:** `hooks/tap.sh` fires on Claude Code's PostToolUse /
SubagentStart / SubagentStop / UserPromptSubmit / SessionStart /SessionEnd
hooks, reads the event payload, and calls `scripts/factory-record.sh --type
<type> --name <name> ...` to write the file. This requires no cooperation
from the agent — it's wired at the tool layer. Session-based de-duplication
means re-reading the same SKILL file repeatedly within a session doesn't
spam the directory with near-identical records.

**Reliability:** Deterministic. Captures roughly 97% of invocations — the
residual gap is SKILL uses that involve neither a file read, an observable
output, nor a sub-agent spawn (rare in practice).

**Schema:** `references/factory-metrics-schema.md` — required/optional
frontmatter fields, trigger/invocation enum semantics, worked examples
(auto-stub from PostToolUse, rich workflow-step observation, gate
evaluation, SubagentStart capture).

### Layer (b) — structured spawn events (deterministic)

**What:** Two JSON-object-per-line event shapes appended to one file:

```jsonc
// spawn — written when a sub-agent is launched
{"ts": "2026-06-28T09:15:00Z", "event": "spawn", "session": "8f3c-a1b2", "agent": "solution-architect", "model": null}

// complete — written when a sub-agent finishes
{"ts": "2026-06-28T09:42:00Z", "event": "complete", "session": "8f3c-a1b2", "agent": "solution-architect", "status": "success", "input_tokens": null, "output_tokens": null}
```

**Path:** `.project/telemetry/agent-spawns.jsonl`

**How it's written:** `hooks/tap.sh`, on the `Task` (spawn) and
`SubagentStop` (completion) hook events. Same deterministic guarantee as
layer (a) — no agent cooperation needed.

**Reliability:** Deterministic for the fact of the spawn/completion and
status. `model`, `input_tokens`, and `output_tokens` are `null` whenever the
harness doesn't expose them — that's expected, not a bug; the report tool
treats `null` as "unknown," never as zero.

### Layer (c) — routing decisions (discipline-dependent)

**What:** The delivery-lead's own record of *why* it chose a tier for a
given spawn — the deliberate half of routing telemetry, not just the
outcome:

```jsonc
{"ts": "2026-06-28T09:14:00Z", "agent": "solution-architect", "default_tier": "standard", "chosen_tier": "deep", "score": 8, "reason": "payment + compliance + cross-cutting = deep tier"}
```

**Path:** `.project/telemetry/model-routing.jsonl` (structured) plus prose
dispatch notes at `.project/working/routing-*.md` (delivery-lead's own
working notes, not machine-parsed line-by-line but scanned for coverage).

**How it's written:** The delivery-lead writes this itself, per
`skills/adaptive-model-routing/SKILL.md`, before each spawn — it is
discipline, not hook-enforced automation. If the delivery-lead skips logging
a decision (distraction, a fast-path shortcut, a bug), there's no
lower-level mechanism catching the gap. This is the layer to treat with
appropriate skepticism.

**Reliability:** Discipline-dependent. The routing report surfaces a
"routing-discipline coverage %" figure specifically so you can see how much
of layer (b)'s spawn volume has a matching layer (c) decision — low coverage
means the delivery-lead is routing off default tiers without logging the
override reasoning, which is worth flagging in the quarterly steward review.

## Running the reports

**Weekly usage aggregation:**

```bash
scripts/factory-frequency.sh --type skill --since $(date -v-7d +%Y-%m-%d) --top 10
```

Aggregates layer (a) records — top-N SKILLs/agents by invocation count over
a period.

**Coverage gate for experimental SKILLs:**

```bash
scripts/factory-aging.sh --strict-window 30
```

Flags `state: experimental` SKILLs with stale or missing layer (a)
telemetry — a signal for the System Steward to decide promote vs. prune.

**Full routing + cost report (aggregates all three layers):**

```bash
python3 scripts/factory-routing-report.py --project-dir <path> --format md --out <file>
```

- `--project-dir` — the project root, or a `.project` directory directly.
  Defaults to cwd.
- `--format` — `md` (default) or `json`.
- `--out` — output path. Default for `md`:
  `.project/telemetry/reports/routing-report-<YYYY-MM-DD>.md`. Default for
  `json`: stdout unless `--out` is given.

Reads (fail-soft — every source is optional; a missing one just degrades
that section of the report, never crashes it):
- `.project/telemetry/model-routing.jsonl` (layer c, structured)
- `.project/telemetry/agent-spawns.jsonl` (layer b)
- `.project/working/routing-*.md` (layer c, prose)
- `.project/operational/factory-metrics/**` (layer a)

Report sections:

1. **Data coverage** — how much of each layer is present, so you know how
   much to trust the rest of the report.
2. **Per-slice dispatches** — spawn activity grouped by slice, where
   determinable.
3. **Per-agent activity** — spawn/completion counts and status per agent.
4. **Tier & cost proxy** — tier distribution and a cost-proxy total, with
   every number source-labeled `default` / `observed` / `decided` (see
   below).
5. **Routing-discipline coverage %** — the fraction of layer-(b) spawns that
   have a matching layer-(c) logged decision.
6. **Recommendations** — heuristic notes (e.g., "N `deep`-tier spawns had no
   logged rationale — check whether adaptive-model-routing is being
   applied").

## Reading the "cost proxy" honestly

`governance/model-routing.yaml` defines `cost_weights` — `deep: 5.0`,
`standard: 1.0`, `light: 0.25` — used to compute a relative cost figure per
tier. **These are not dollar amounts.** They're coarse proxies for the
relative per-token price of the tier's resolved model on the harness in
question, meant for relative comparison ("this quarter routed noticeably
more `deep`-tier work than last quarter") not absolute accounting. Tune them
per organization if your actual per-tier pricing ratio differs.

The report labels each figure by source so you know exactly what grounds it:

- **`default`** — no spawn/routing telemetry available for this agent; the
  figure falls back to the agent's static `capability_tier` from its
  frontmatter.
- **`observed`** — layer (b) spawn events exist for this agent (we know it
  ran, and possibly at what model), but no layer (c) routing decision was
  logged to explain the tier choice.
- **`decided`** — a matching layer (c) routing decision exists; this is the
  most complete/trustworthy figure — it tells you not just what happened,
  but why.

## Where reports land

`.project/telemetry/reports/routing-report-<YYYY-MM-DD>.md` (or your `--out`
path). Nothing auto-deletes old reports — treat them like ADRs: keep them,
diff them quarter over quarter to see whether tier usage is drifting.

## See also

- `references/factory-metrics-schema.md` — full schema for all telemetry
  shapes (markdown records + both JSONL files), plus worked examples.
- [`docs/model-routing.md`](model-routing.md) — what the tiers mean and how
  the routing decision gets made in the first place; this page is about
  measuring what already happened.
- `skills/adaptive-model-routing/SKILL.md` — the rubric the delivery-lead
  applies before each spawn, which is what layer (c) is recording.
- `PLAYBOOK.md` §7.5–7.6 — the per-session and weekly telemetry-review
  cadences in the operating guide.
