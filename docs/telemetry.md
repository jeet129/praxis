# Telemetry

Praxis captures three layers of telemetry, with deliberately different
reliability guarantees. Read this before trusting a number from a report —
one layer is agent-written but mandatory (near-100% capture because it's a
required workflow output, not a tool-event side effect); one is hook/runner-
written and deterministic; the third is a thin stub layer that no longer
carries the weight it used to. The report tools label every figure by which
layer it came from so you're never guessing.

## The three layers

### Layer (a) — checkpoint records (primary usage source; mandatory, not hook-triggered)

**What:** One structured episodic entry per closure boundary — slice close,
requirements_freeze, architecture_sign_off, ideation convergence, spike
disposition, release, expedited retro, steward review, or any other
gate/phase/slice/loop/disposition/workflow-end boundary. Frontmatter carries
`agents_dispatched`, `skills_consumed`, `artifacts_produced`, `cost_proxy`,
`human_touchpoints`, and `deviations` accumulated since the previous
checkpoint, plus a few lines of prose on what closed and what carries
forward.

**Path:** `.project/episodic/checkpoint-<YYYYMMDD-HHMM>-<label>.md`.

**How it's written:** delivery-lead (single writer) at the AOP Document step
of every closure boundary, per `references/factory-metrics-schema.md`
("Checkpoint records"). This is *agent-written*, not hook-fired — but unlike
the retired read/preload stubs, it isn't optional instrumentation riding on
a tool event that may or may not fire. It's a required output of the
workflow itself, costing a few dozen tokens per phase, not per event.

**Reliability:** Near-100% capture in a workflow that's actually being
followed, because skipping it means skipping a mandatory AOP step — but it
is still discipline-dependent in the sense that a delivery-lead who
short-circuits the AOP can skip it. This replaced an earlier tool-event
capture approach (hook-fired stubs for every SKILL read/preload/session)
that measured out at roughly 5% real-world capture — plugin-injected skills
never fire a `Read` event, and main-session orchestration produces no `Task`
event. Checkpoints don't have that gap because they're not watching for a
tool event; they're a workflow deliverable.

**Read by:** `scripts/factory-usage-report.py` — the primary usage-analytics
tool. See "Running the reports" below.

### Layer (b) — structured JSONL streams (hook/runner-written, deterministic)

**What:** Four append-only, one-JSON-object-per-line files under
`.project/telemetry/`:

```jsonc
// agent-spawns.jsonl — spawn, written when a sub-agent is launched
{"ts": "2026-06-28T09:15:00Z", "event": "spawn", "session": "8f3c-a1b2", "agent": "solution-architect", "model": null}

// agent-spawns.jsonl — complete, written when a sub-agent finishes
{"ts": "2026-06-28T09:42:00Z", "event": "complete", "session": "8f3c-a1b2", "agent": "solution-architect", "status": "success", "input_tokens": null, "output_tokens": null}

// model-routing.jsonl — the delivery-lead's routing-decision rationale
{"ts": "2026-06-28T09:14:00Z", "agent": "solution-architect", "default_tier": "standard", "chosen_tier": "deep", "score": 8, "reason": "payment + compliance + cross-cutting = deep tier"}

// drive.jsonl — one line per scripts/praxis-drive.sh iteration
{"ts":"2026-07-10T12:00:00Z","run_id":"drive-20260710-1200","iteration":4,"slice":"S9","task":"S9-T2","agent":"backend-developer","tier":"standard","outcome":"done","ledger_hash":"a1b2c3","stop_flags":[],"cost_proxy":1.0}

// sessions.jsonl — one line per session boundary
{"ts": "2026-06-28T09:00:00Z", "event": "session_start", "session": "8f3c-a1b2"}
```

**Paths:** `.project/telemetry/agent-spawns.jsonl`, `model-routing.jsonl`,
`drive.jsonl`, `sessions.jsonl`.

**How it's written:** `hooks/tap.sh` fires on the `Task` (spawn) and
`SubagentStop` (completion) hook events for `agent-spawns.jsonl`, and on
`SessionStart`/`SessionEnd` for `sessions.jsonl` — no agent cooperation
needed, same deterministic guarantee either way. `scripts/praxis-drive.sh`
appends to `drive.jsonl` once per iteration it runs, also deterministic
(runner-written, not agent-written). **`model-routing.jsonl` is the one
exception in this layer**: the delivery-lead writes it itself, per
`skills/adaptive-model-routing/SKILL.md`, before each spawn — it is
discipline, not hook-enforced automation. If the delivery-lead skips logging
a decision, there's no lower-level mechanism catching the gap; treat that
one stream with appropriate skepticism even though it lives alongside three
deterministic ones.

**Reliability:** Deterministic for `agent-spawns.jsonl`, `drive.jsonl`, and
`sessions.jsonl` (the fact of the event, and any fields the harness
exposes — `model`/`input_tokens`/`output_tokens` are `null`, never a
guessed zero, when the harness doesn't expose them). Discipline-dependent
for `model-routing.jsonl`. delivery-lead also embeds the same routing
decision in every `.project/working/routing-*.md` frontmatter (`routing:`
block) as a fallback the report tools recover as an equivalent "decided"
record when the JSONL append was skipped.

**Read by:** `scripts/factory-routing-report.py` (routing/cost/drive
aggregation) and `scripts/factory-usage-report.py` (sessions, plus
`routing-*.md` for dispatch/skill evidence).

### Layer (c) — stub layer (commands + human observations only; supplementary)

**What:** One markdown file per event, written under
`.project/operational/factory-metrics/<type>s/<name>/<date>-<rand>.md`.

**What's still written:** `command` stubs (`UserPromptSubmit` parsed for
`/praxis:<cmd>` or `/cmd`) and human-authored `/praxis:factory-record`
observations. Both remain live.

**What's retired, and why:** `skill`-read, `agent`-preload, and per-session
stub types used to be written on `PostToolUse(Read)`, `SubagentStart`
(preload-mapping lookup), and `SessionStart`/`SessionEnd`. They're retired —
measured real-world capture was ~5%, because plugin-injected skills are
never `Read` into context as a discrete tool call, and main-session
orchestration (no sub-agent spawned) never fires a `Task` event either. Any
skill/agent/hook/workflow/gate/reference stub files still on disk predate
the slimdown; the report tools count them under a "legacy stub layer" label
for continuity but don't treat them as current usage evidence. Skill/agent
usage now comes from layer (a).

**Reliability:** Deterministic for the fact of a command invocation (same
hook-tap mechanism as layer (b)'s deterministic streams). Discipline-
dependent for `/factory-record` observations (a human has to actually run
the command).

**Read by:** `scripts/factory-usage-report.py` (command stubs; legacy stub
count). `scripts/factory-frequency.sh` / `scripts/factory-aging.sh` still
read the full stub layer including the legacy types — see the deprecation
note at the top of each script.

## The report scripts

| Script | Primary source | What it reports |
|---|---|---|
| `scripts/factory-usage-report.py` | Layer (a) checkpoints, plus working packets/task ledgers, routing logs, command stubs, and sessions | Per-skill and per-agent usage (checkpoints/packets naming it, last-seen, never-observed list), per-workflow checkpoint/gate breakdown, per-command invocations, engagement summary (sessions, span, checkpoints, total cost proxy) |
| `scripts/factory-routing-report.py` | Layer (b) JSONL streams, plus `routing-*.md` and legacy factory-metrics records | Data coverage, per-slice dispatches, per-agent activity, tier & cost-proxy totals, routing-discipline coverage %, drive-run summaries, heuristic recommendations |
| `scripts/factory-token-report.py` | `drive.jsonl` real-usage fields + local Claude Code session transcripts | Real (not proxy) token/cost totals — per-model, per-day, per-slice (best-effort), input:output ratio, cache-hit ratio, and a proxy-calibration table against `cost_proxy`. See "Real token telemetry" below. |

Both are zero-dependency Python 3, fail-soft (a missing/malformed source
degrades that section of the report, never crashes the script), and accept
`--project-dir` (project root or a `.project` dir directly), `--format
md|json`, and `--out`.

## Running the reports

**Primary usage report (skills, agents, workflows, commands, engagement):**

```bash
python3 scripts/factory-usage-report.py --project-dir <path> --format md --out <file>
```

- `--project-dir` — the project root, or a `.project` directory directly.
  Defaults to cwd.
- `--format` — `md` (default) or `json`.
- `--out` — output path. Default for `md`:
  `.project/telemetry/reports/usage-report-<YYYY-MM-DD>.md`. Default for
  `json`: stdout unless `--out` is given.

Mines (fail-soft — every source is optional; a missing one just degrades
that section of the report, never crashes it):
- `.project/episodic/checkpoint-*.md` (layer a, primary)
- `.project/working/slice-*-packet.md` + `slice-*-tasks.yaml`
- `.project/working/routing-*.md` (layer b's prose fallback)
- `.project/operational/factory-metrics/commands/**` (layer c, commands)
- `.project/telemetry/sessions.jsonl` (layer b)
- `.project/operational/factory-metrics/{skills,agents,...}` (legacy stub
  layer — counted for continuity, labeled, not treated as evidence)

Report sections: (1) data coverage per source with honest notes; (2)
per-skill usage — checkpoints/packets naming it, last-seen, source labels,
plus a "never observed" list for steward review; (3) per-agent dispatches,
tiers seen, last active; (4) per-workflow checkpoint/gate breakdown; (5)
per-command invocations; (6) engagement summary (sessions, span,
checkpoints, total cost proxy).

**Full routing + cost report (aggregates layer b's JSONL streams):**

```bash
python3 scripts/factory-routing-report.py --project-dir <path> --format md --out <file>
```

Same `--project-dir` / `--format` / `--out` convention. Default `md` output:
`.project/telemetry/reports/routing-report-<YYYY-MM-DD>.md`.

Reads (fail-soft):
- `.project/telemetry/model-routing.jsonl` (layer b, discipline-dependent)
- `.project/telemetry/agent-spawns.jsonl` (layer b, deterministic)
- `.project/telemetry/drive.jsonl` (layer b, deterministic)
- `.project/working/routing-*.md` (layer b's prose fallback)
- `.project/operational/factory-metrics/**` (layer c, supplementary)

Report sections:

1. **Data coverage** — how much of each source is present, so you know how
   much to trust the rest of the report.
2. **Per-slice dispatches** — spawn activity grouped by slice, where
   determinable.
3. **Per-agent activity** — spawn/completion counts and status per agent.
4. **Tier & cost proxy** — tier distribution and a cost-proxy total, with
   every number source-labeled `default` / `observed` / `decided` (see
   below).
5. **Routing-discipline coverage %** — the fraction of spawn events (from
   `agent-spawns.jsonl`) that have a matching logged routing decision (from
   `model-routing.jsonl` or its `routing-*.md` frontmatter fallback).
6. **Drive-run summaries** — iterations/slices/tasks/cost per
   `scripts/praxis-drive.sh` run, stop reasons, human-touchpoint density.
7. **Recommendations** — heuristic notes (e.g., "N `deep`-tier spawns had no
   logged rationale — check whether adaptive-model-routing is being
   applied").

**Legacy stub-layer aggregation (command-stub aging; deprecated for skill/agent usage):**

```bash
scripts/factory-frequency.sh --type skill --since $(date -v-7d +%Y-%m-%d) --top 10
scripts/factory-aging.sh --strict-window 30
```

Both scripts carry a deprecation note explaining the ~5% capture ratio that
led to retiring the read/preload/session stub types they were built around.
They still work unchanged, and remain useful for command-stub aging and
auditing `/factory-record` observation coverage — just don't treat their
skill/agent numbers as the current picture; use
`scripts/factory-usage-report.py` for that.

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
- **`observed`** — `agent-spawns.jsonl` events exist for this agent (we know
  it ran, and possibly at what model), but no `model-routing.jsonl` decision
  was logged to explain the tier choice.
- **`decided`** — a matching `model-routing.jsonl` decision (or its
  `routing-*.md` frontmatter fallback) exists; this is the most
  complete/trustworthy figure — it tells you not just what happened, but
  why.

## Where reports land

`.project/telemetry/reports/usage-report-<YYYY-MM-DD>.md` and
`.project/telemetry/reports/routing-report-<YYYY-MM-DD>.md` (or your `--out`
path). Nothing auto-deletes old reports — treat them like ADRs: keep them,
diff them over time to see whether skill/agent usage and tier usage are
drifting.

## See also

- `references/factory-metrics-schema.md` — full schema for checkpoint
  records, both JSONL layers, and the legacy stub-layer markdown format,
  plus worked examples.
- [`docs/model-routing.md`](model-routing.md) — what the tiers mean and how
  the routing decision gets made in the first place; this page is about
  measuring what already happened.
- `skills/adaptive-model-routing/SKILL.md` — the rubric the delivery-lead
  applies before each spawn, which is what `model-routing.jsonl` is
  recording.
- `skills/factory-evaluation/SKILL.md` — how usage analytics feed the
  quarterly factory report and steward review.
- `PLAYBOOK.md` §7.5–7.6 — the per-session and weekly telemetry-review
  cadences in the operating guide.

## Real token telemetry

**Universal capture (every session):** at SessionEnd the hook sums the
session's own transcript into `.project/telemetry/tokens.jsonl` — one
record per session with input/output/cache tokens and per-model output.
This fires for ALL workflow executions, interactive or driven; drive runs
additionally get per-iteration usage in `drive.jsonl`.

Everything above — `cost_proxy`, tier totals, the "cost proxy" figures in
`factory-routing-report.py` — is a RELATIVE unit (`cost_weights` from
`governance/model-routing.yaml`: `deep: 5.0`, `standard: 1.0`, `light: 0.25`),
not a token count or a dollar amount. Three paths exist for actual token/cost
numbers, in decreasing order of reliability:

**1. Drive headless JSON usage (deterministic).** `scripts/praxis-drive.sh`
appends `--output-format json` to the `claude-code` harness command whenever
it doesn't already request a `--output-format` (overridable per harness via
optional `governance/autonomy.yaml` keys `harnesses.<harness>.json_output_flag`
/ `usage_parse` — not required, and not owned/edited by this doc's scope),
captures the invocation's stdout, and parses the result object's `usage`
(`input_tokens`, `output_tokens`, `cache_read_input_tokens`,
`cache_creation_input_tokens`) and `total_cost_usd` into five additive fields
on every `drive.jsonl` record — `null` when the harness doesn't expose them,
never a guessed value. This is deterministic and covers every headless drive
iteration, but ONLY headless drive iterations — interactive sessions aren't
captured this way. See `references/factory-metrics-schema.md`'s drive.jsonl
section for the full field table.

**2. Transcript mining (deterministic, interactive sessions).**
`scripts/factory-token-report.py` mines Claude Code's own per-session JSONL
transcripts (`~/.claude/projects/<munged-project-path>/<session-id>.jsonl` —
an observed, not officially pinned, path convention; the script defends
against it being wrong with a fuzzy-match fallback and an explicit
`--transcripts-dir` override) for `message.usage` on every assistant-role
line. This is the only path that covers interactive (non-headless) sessions.
It correlates mined tokens against `.project/telemetry/sessions.jsonl` (for
session-id matching where transcript filenames allow it) and
`model-routing.jsonl` / `drive.jsonl` timestamps (for best-effort per-slice
attribution via a padded time window) — both correlations are best-effort and
labeled as such in the report. Run:

```bash
python3 scripts/factory-token-report.py --project-dir <path> --format md --out <file>
# or, to bypass the ~/.claude/projects path-munge guess entirely:
python3 scripts/factory-token-report.py --project-dir <path> --transcripts-dir <exact-dir> --format md
```

Report sections: coverage (which capture path resolved, or an honest "no
transcripts found" note), totals + input:output ratio + cache-hit ratio,
per-model, per-day, per-slice (best-effort), the drive-runner real-usage
table (path 1 above, surfaced for one combined picture), and a **proxy
calibration** table comparing `cost_proxy` totals to actual mined tokens per
slice — a sanity check on whether the tier cost weights track real
consumption. Zero dependencies, fails soft, exits 0 with the "no transcripts
found" note when `~/.claude/projects` is absent (the expected CI case).

**Sub-session attribution ladder.** Below the session level, the same
"deterministic where possible, honest approximation otherwise" discipline
applies at finer grain, in decreasing order of reliability: (a) a `drive.jsonl`
task-level exact figure, when a task ran under drive (`source: exact` in
report section 9); (b) sidechain (subagent/Task-tool) per-invocation
attribution, when transcripts carry `isSidechain` — measured per assistant
message, with the invoking agent's identity itself best-effort (an
identity field on the line, else a ±3-minute match against `routing-*.md`
timestamps, else `unattributed-subagent`) — report section 8; (c) interactive
task-window attribution, when a task ledger carries `started_at`/`completed_at`
(`references/loop-contracts.md` §2) but didn't run under drive — transcript
messages falling inside the window are summed as a time-based approximation,
not a measurement, because shared context means tokens can't be cleanly
split by task (`source: window` in report section 9). Each report row is
labeled with which rung produced it — never silently blended.

**3. Tier proxy (fallback, always available).** When neither of the above
applies — no drive runs, no local transcript history — `cost_proxy` from
`factory-routing-report.py` is what's left: a coarse, tier-weighted relative
figure, useful for "did this quarter route more deep-tier work than last
quarter", not for real accounting.

**Org-scale option (OTEL):** Claude Code can also emit usage via OpenTelemetry
(`claude_code.token.usage` and related metrics) to an OTEL collector, which is
the right answer at organization scale — one pipeline aggregating usage
across every project and every developer's local sessions, rather than
per-project transcript mining. Praxis doesn't set this up or depend on it;
mentioned here as the direction to look if `factory-token-report.py`'s
single-machine transcript mining stops being enough.

## If model-routing.jsonl is empty

The JSONL is agent-written and the most commonly skipped discipline. Two
mitigations are built in: delivery-lead embeds the same decision in every
`routing-*.md` frontmatter (`routing:` block), which the report recovers as
decided records; and `hooks/session-start.sh` pre-creates
`.project/telemetry/` so appends never fail on a missing directory. Check
the report's coverage note — "recovered from routing-*.md frontmatter"
means routing is happening but the JSONL append was skipped; zero decisions
in both forms means adaptive routing is not being practiced and the
delivery-lead discipline needs attention.
