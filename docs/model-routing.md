# Model Routing — Operator Guide

How Praxis decides which concrete model runs a given agent, why it's a
one-file edit to change vendors, and how to adjust it for your own project.
This is the operator-facing companion to `skills/adaptive-model-routing/SKILL.md`
(the rubric an agent applies) — read this page for the mechanics; read that
SKILL for the scoring logic itself.

## Tier semantics

Agents don't hardcode a model. Each `agents/<name>.md` declares an abstract
`capability_tier` in its frontmatter:

| Tier | Use for | Not for |
|---|---|---|
| **deep** | Adversarial judgment, novel architecture decisions, security threat modeling, high-stakes gates, cross-cutting ADRs, tasks where a prior standard-tier attempt already failed. Misses here are expensive — buy the strongest reasoning available. | Routine implementation, formulaic output. |
| **standard** | Implementation, test authoring against an existing plan, artifact generation, the large majority of production work. The thinking is carried by the implementation packet; generation quality at this tier is sufficient and much cheaper. | Novel/adversarial reasoning, mechanical scaffolding. |
| **light** | Mechanical, formulaic work — scaffolding, doc drafts, formatting, classification, pre-flight checks, telemetry digests. Cheapest tier. | Anything with real judgment content. |

Current roster: 6 agents default `deep`, 10 default `standard`, 1 defaults
`light` (see each agent's `capability_tier:` field in `agents/*.md`).

## `governance/model-routing.yaml` anatomy

This is the **single file in the repo that names concrete models.** Everything
else — agent frontmatter, Codex TOML — is derived from it.

```yaml
version: 1
tiers: [deep, standard, light]

harnesses:
  claude-code:
    field: model                    # written into agents/*.md frontmatter
    map: { deep: opus, standard: sonnet, light: haiku }
  codex:
    field: model_reasoning_effort   # written into codex-plugin-assets/codex-agents/*.toml
    map: { deep: high, standard: medium, light: low }
  gemini-cli:
    field: model
    map: { deep: gemini-2.5-pro, standard: gemini-2.5-flash, light: gemini-2.5-flash-lite }

overrides:
  force_tier: null                  # set to a tier name to pin every agent to it

escalation:
  on_gate_failure: promote_one_tier_and_retry_once   # then escalate to human
  demotion_allowed: true                             # trivial tasks may run one tier lower
  log_routing_decisions_to: .project/telemetry/model-routing.jsonl

cost_weights:                       # relative proxies, NOT dollar figures
  deep: 5.0
  standard: 1.0
  light: 0.25
```

- **`harnesses`** — one block per supported harness. `field` is the
  frontmatter/TOML key the applier writes into; `map` resolves each tier to
  that harness's concrete model setting.
- **`overrides.force_tier`** — governance escape hatch. Set to `deep` (or any
  tier name) to force every agent to that tier regardless of its declared
  default — e.g., a compliance-critical engagement that mandates the
  strongest tier everywhere. Leave `null` for normal per-agent tiering.
- **`escalation`** — the policy `delivery-lead` follows when a gate fails:
  promote one tier and retry once, then stop and escalate to a human rather
  than loop indefinitely. `demotion_allowed: true` also permits routing
  trivial tasks one tier below an agent's default.
- **`cost_weights`** — coarse relative cost proxies per tier, consumed by
  `scripts/factory-routing-report.py` to compute a cost figure when the
  harness doesn't expose real token pricing. Tune per organization; they are
  **not** dollar amounts (see `docs/telemetry.md` for how the report labels
  and uses these).

## One-edit model change workflow

To move to a new model family (e.g., a vendor ships a new flagship), you edit
**one file**:

```bash
# 1. Edit the map for the harness(es) affected
$EDITOR governance/model-routing.yaml
# e.g. change claude-code.map.deep from "opus" to the new model name

# 2. Apply — rewrites agents/*.md frontmatter + codex TOML
python3 scripts/apply-model-routing.py

# 3. Verify nothing is left stale (CI runs this same check)
python3 scripts/apply-model-routing.py --check
```

No agent file, no SKILL, no workflow changes. `apply-model-routing.py`
rewrites the `model:` (or `model_reasoning_effort:`) field in every
`agents/*.md` and `codex-plugin-assets/codex-agents/*.toml` to match the new
map. Never hand-edit a `model:` field directly — `--check` in CI will flag it
as drifted from the routing table and fail the build.

## Runtime ±1 adjustment + gate-failure escalation

The static tier in `model-routing.yaml` is a **default, not a ceiling.**
Before each sub-agent spawn, `delivery-lead` runs the rubric in
`skills/adaptive-model-routing/SKILL.md`:

- Scores the task on 5 signals (novelty, interdependency, stakes, ambiguity,
  prior failure), each 0–2.
- The total score maps to a tier, but fast-path rules can override the score
  outright (e.g., "Architecture Challenger adversarial pass" is always
  `deep`; "implementing a slice with a clear spec" is always `standard`).
- The result is at most a **±1 shift** from the agent's declared default tier
  — this is deliberately narrow; it's tuning, not a free-for-all.

**On gate failure:** per the `escalation.on_gate_failure` policy, delivery-lead
promotes one tier and retries once (e.g., a `standard`-tier implementation
attempt that fails code review gets retried at `deep`). If the retry also
fails, it stops and escalates to the human principal rather than looping.

**Force override:** if `overrides.force_tier` is set to a tier name in
`model-routing.yaml`, every agent runs at that tier regardless of its default
or the rubric — used for blanket governance requirements (e.g., "everything
in this compliance-critical engagement runs at `deep`").

## Telemetry feedback loop

Every routing decision — default tier, chosen tier, score, and a short
rationale — gets logged to `.project/telemetry/model-routing.jsonl`:

```jsonc
{"ts": "2026-06-28T09:14:00Z", "agent": "solution-architect", "default_tier": "standard", "chosen_tier": "deep", "score": 8, "reason": "payment + compliance + cross-cutting = deep tier"}
```

`scripts/factory-routing-report.py` cross-references this against the
deterministic spawn/completion events in `.project/telemetry/agent-spawns.jsonl`
and the per-invocation usage records under
`.project/operational/factory-metrics/`, producing a report with tier & cost
proxy breakdowns and a "routing-discipline coverage %" — how much of actual
spawn volume has a matching logged routing decision. Low coverage means
delivery-lead is routing without recording why, which is a signal for the
next quarterly steward review. Full detail on all three telemetry layers:
[`docs/telemetry.md`](telemetry.md).

## Adding a new harness

To wire up a harness Praxis doesn't yet support:

1. **Add a block to `harnesses:` in `governance/model-routing.yaml`** — pick
   the frontmatter/config `field` name the new harness expects (e.g., a new
   tool might use `model_tier` or a nested config path), and map all three
   tiers to that harness's concrete model identifiers.
2. **Extend `scripts/apply-model-routing.py`** to know how to write that
   field into the new harness's agent-definition format (it currently
   handles Markdown frontmatter for Claude Code / Gemini CLI and TOML for
   Codex — add a writer function following the existing `process_agents` /
   `process_codex` pattern).
3. **Add an `install.sh --tool=<name>` layout** if the harness needs its own
   directory structure (see `docs/<tool>-setup.md` for the pattern other
   tools follow) — this is a separate concern from routing but usually goes
   together.
4. **Run `apply-model-routing.py --check`** to confirm the new harness's
   agent files are in sync, and add the harness to CI's validator run.
5. **Document it** — add a `docs/<harness>-setup.md` and a row to the tool
   compatibility table in `README.md`.

## See also

- `skills/adaptive-model-routing/SKILL.md` — the full rubric, fast-path
  rules, and phase-level defaults an agent applies before each spawn.
- `docs/telemetry.md` — what gets measured, the three telemetry layers, and
  how to read the routing/cost report.
- `PLAYBOOK.md` §7.5 — the per-session operating cadence for model routing.
- `CONTRIBUTING.md` — "Generated surfaces" section, on why you never
  hand-edit a `model:` field.

## Per-project overrides

`governance/model-routing.yaml` and `governance/autonomy.yaml` ship inside
the plugin. On Claude Code, the SessionStart hook seeds copies into your
project at `.project/governance/` automatically (once, if missing), and
`/start` asks whether you want to tune them for the engagement. On other
harnesses — or if the hook hasn't run yet — seed them manually:

```bash
mkdir -p .project/governance
cp "$PRAXIS_ROOT/governance/model-routing.yaml" .project/governance/
cp "$PRAXIS_ROOT/governance/autonomy.yaml"      .project/governance/
```

Never edit the installed plugin's own copies — updates overwrite them.

Resolution order (consumed by `praxis-drive.sh`, `factory-routing-report.py`,
and the delivery-lead's runtime routing): `.project/governance/<file>` if
present, else the plugin's copy. Typical per-project tunings: `force_tier`
for compliance-critical engagements, `cost_weights` for your org's actual
model pricing, `stop_after` and `run_budget` for drive-mode autonomy.

## Routing the router (per-iteration model selection)

The orchestrator itself is routed, not pinned. In drive mode the runner
resolves each iteration's model from the TASK's tier (`model_flag` per
harness in `governance/autonomy.yaml` + the tier map): a light-tier task's
entire iteration — including the delivery-lead protocol execution — runs on
the light model, recorded as `iteration_model` in `drive.jsonl`.
Interactively, open orchestration sessions on the standard tier and reserve
deep-tier sessions for architecture phases, re-plans, and judgment-heavy
gate evaluations (see delivery-lead's "Your own tier" discipline).
delivery-lead's static default is `standard`; deep is an escalation, never
a resting state.
