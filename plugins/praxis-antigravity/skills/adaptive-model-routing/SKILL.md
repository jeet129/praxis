---
name: adaptive-model-routing
description: "Routes tasks to the right abstract capability tier (deep vs standard vs light) based on task complexity, novelty, stakes, and interdependency; tiers resolve to concrete harness-native models via `governance/model-routing.yaml`. Prevents wasteful deep-tier consumption on tasks the standard tier handles equally well, and prevents quality failures from routing complex tasks to cheaper tiers. The Delivery Lead runs this SKILL every time it spawns a sub-agent. Use whenever an agent is about to be spawned, when selecting a tier for a session, or when a prior attempt failed and escalation is being considered."
---

# Adaptive Model Routing

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - using-praxis
  - llm-cost-optimization
  - agentic-architecture
triggers:
  - "about to spawn a sub-agent — which model should it use?"
  - "starting a new session — which model should I open with?"
  - "prior attempt failed — should I escalate the model?"
  - "deciding whether this task needs the deep tier or the standard tier"
  - "running low on deep-tier budget — can I safely use the standard tier here?"
  - "complex architecture decision coming — what model?"
  - "entering a new workflow phase — should the model change?"
outputs:
  - model selection decision (per agent spawn)
  - complexity score + rationale
  - escalation recommendation (when prior attempt fails)
  - routing log entry at .project/telemetry/model-routing.jsonl
consumers:
  - delivery-lead (primary — runs this SKILL before every agent spawn)
  - using-praxis (consumes routing decision when selecting model for orchestration)
  - agentic-architecture (agent spawn configuration)
references:
  - llm-cost-optimization.md
  - routing-examples.md
```
<!-- praxis:metadata:end -->

The discipline that keeps deep-tier budget for tasks that actually need it. The deep and standard tiers are not interchangeable — deep has meaningfully stronger multi-step reasoning and novel synthesis; standard handles the large majority of production work at a fraction of the cost and budget burn.

The principle: **default to standard; escalate to deep only when specific complexity signals are present; never use the deep tier for tasks a competent standard-tier run completes correctly.**

---

## Capability-tier reference

Praxis routes by **abstract capability tier**, not by model name. Concrete models are resolved per harness by `governance/model-routing.yaml` — the *only* file in the repo that names models. When a vendor ships a new family, edit that table and run `scripts/apply-model-routing.py`; nothing in this skill or any agent changes.

| Tier | Use for | Resolves to (examples, per routing table) |
|---|---|---|
| **deep** | Novel architecture decisions, complex multi-step reasoning, high-stakes gates, adversarial review, tasks where a prior standard-tier attempt failed | Claude: Opus · Codex: `model_reasoning_effort=high` |
| **standard** | Default for almost everything — implementation, test authoring against a designed plan, standard SKILLs, summarization, extraction, routine orchestration | Claude: Sonnet · Codex: `medium` |
| **light** | Classification, intent detection, simple extraction, doc formatting, scaffolding, routing decisions with structured inputs, pre-flight checks | Claude: Haiku · Codex: `low` |

**Default: standard.** Upgrade to deep only when the routing rubric says so.

---

## Routing rubric

Score the task on five signals. Each signal is 0–2. Total score determines the model.

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| **Novelty** | Established pattern in codebase or skill | First time in this project; some unknowns | Genuinely first-of-kind; no prior art |
| **Interdependency** | Single concern, one domain | 2–3 concerns; some cross-cutting | Many cross-cutting concerns; global impact |
| **Stakes** | Reversible; no user or prod impact | Limited prod impact; rollback available | Security, compliance, prod go/no-go, data loss risk |
| **Ambiguity** | Spec is clear and complete | Some scope gaps; clarifiable | High ambiguity; major assumptions required |
| **Prior failure** | No prior attempt | Prior attempt marginal | Prior standard-tier attempt failed; escalation triggered |

**Score → tier:**

| Total | Tier | Rationale |
|---|---|---|
| 0–3 | **standard** (demotable to **light** for mechanical tasks against an existing packet) | Routine work |
| 4–6 | **standard** (with care) | Moderate complexity; flag if output needs review |
| 7–8 | **deep** | High complexity |
| 9–10 | **deep** | Critical task; strongest tier required |

---

## Task-type fast path

Before scoring, check these fast-path rules. If a rule matches, it overrides the score.

### Always standard (regardless of score)
- Implementing a slice with a clear spec from the Lead Developer
- Writing code that follows an established pattern already in the codebase
- Applying a praxis SKILL where the application is routine (cicd-pipeline, containerization, observability wiring)
- Producing documentation, release notes, runbook templates
- Summarizing, extracting, or classifying structured content
- Routine gate checks (evidence package assembly for production release)
- Frontend component implementation per design system spec

### Always deep (regardless of score)
- Solution Architect producing the primary architecture decision (`architecture-pattern-selection`) for a system with > 2 capability flags active
- Architecture Challenger adversarial sub-personas (`doubt-driven-decisions` pattern applied to architecture)
- Security threat model (`threat-modeling` SKILL — stakes are always 2)
- Requirements elicitation with a vague brief (`requirements-interrogation` KUACQ pass on a genuinely ambiguous scope)
- Cross-cutting ADR with > 3 affected services or teams
- Production incident post-mortem for a P0/P1
- Any task that explicitly failed a prior standard-tier run (escalation is non-negotiable)

### Consider light
- Intent classification before routing to the right agent
- Pre-flight checks (does this file exist? is the spec complete?)
- Structured extraction from well-defined inputs (extract key fields from an NFR register)
- Routing decisions where the input is already structured

---

## Phase-level defaults (workflow integration)

If you're inside a workflow, the phase has a default model that applies until an escalation trigger or fast-path rule overrides it:

| Phase | Default | Rationale |
|---|---|---|
| `pre` (codebase-comprehension, brownfield) | standard | Heavy-read task; standard tier handles it; escalate impact-analysis if system is large |
| `A` (discovery + requirements) | standard | Structured elicitation; escalate on vague brief per fast-path rule |
| `B` (architecture) | **deep** | Architecture-pattern-selection + architecture-challenger are Always deep |
| `C` (implementation slice) | standard | Execution against an approved architecture |
| `D` (release gate review) | deep | The go/no-go decision is high-stakes; scored task fires the "high stakes" trigger |
| `D` (release execution) | standard | Deploy, config, mechanical steps |
| Post-release ops | standard | Incident triage escalates per fast-path (P0/P1 → deep) |

Per-agent defaults ship in each agent's frontmatter (`capability_tier:`, resolved to the harness-native model field by `scripts/apply-model-routing.py`). This SKILL overrides at spawn time when the task warrants.

---

## Per-agent default assignments

Each agent declares a `capability_tier:` in its frontmatter; `scripts/apply-model-routing.py` resolves it to the harness-native model field. Delivery Lead uses the tier as the spawn default; this SKILL adjusts ±1 tier for specific tasks.

| Agent | Tier | Why |
|---|---|---|
| delivery-lead | standard | Routine orchestration is mechanical; deep moments (re-plans, ambiguous decision nodes) escalate per session/spawn — measured evidence: routing sessions were the largest deep-tier cost center |
| product-manager | standard | Structured elicitation is mechanical after first pass |
| solution-architect | deep | Architecture decisions are irreversible |
| architecture-challenger | deep | Adversarial depth is the role's value |
| lead-developer | standard | Task decomposition against defined spec is execution |
| backend-developer | standard | Implementation is pattern-matching against the packet |
| frontend-developer | standard | Same |
| mobile-developer | standard | Same — implementation against the packet and stack-flutter |
| data-engineer | standard | Pipeline implementation is mostly mechanical |
| database-engineer | standard | Non-trivial OLTP only (RLS/grants, zero-downtime live migrations, indexing/partitioning/replication); routine schema stays with backend-developer; escalate to deep for security-sensitive or destructive changes |
| ml-ai-engineer | deep | Research-heavy, novel problems, eval design |
| code-reviewer | deep | Missing a bug in review is expensive |
| security-reviewer | deep | Adversarial + high-stakes; false negatives catastrophic |
| qa-engineer | standard | Test *code* is mechanical; test *design* stays standard |
| tech-writer | light | Translation/formatting task; promote for novel architecture docs |
| platform-sre | standard | Mostly execution; escalate for incidents |
| ux-designer | standard | Structured design |
| system-steward | standard | Digest + proposal work; promotions are human-gated anyway |

Result: 5 deep / 11 standard / 1 light. Deep concentrated where irreversibility and adversarial depth matter; generation work runs on cheaper tiers because the thinking is carried by the implementation packet.

---

## Agent spawn configuration

**One routing rule for every spawn — drive or no-drive.** The model + effort a
sub-agent runs on is `resolve(tier, harness)` against the **effective** routing
table: `.project/governance/model-routing.yaml` if the project has one, else the
plugin default. This is the SAME table and precedence the drive runner uses, so
an interactive (no-drive) spawn routes exactly as the drive loop would for the
same tier — a project override wins in both. Do NOT resolve against the plugin
file directly, and do NOT rely on the baked frontmatter alone (that is only the
fallback default).

**Cache-aware down-routing.** A tier switch that changes the underlying model
forfeits prompt-cache prefix reuse — the lower tier can't read the orchestrator's
or a prior spawn's cached prefix. When the tier's price gap is smaller than the
cache-read discount (~10×) — as it currently is for most Claude Code tier steps,
and always for Codex effort-only steps on one base model — that miss can exceed
the tier saving. So for a context-heavy sub-task reusing a large cached prefix,
prefer dropping *effort* within the same model over switching model; reserve
model-down moves for output-heavy or large-gap tasks. Ratios are per-harness
(`governance/model-routing.yaml`); see `llm-cost-optimization` →
"Cache economics vs model routing."

**Enforce it with the pre-flight guardrail (do not rely on judgment alone).**
Before you dispatch any tier DOWN-route, run the deterministic check — it applies
the cache-aware decision for you and logs the rationale:

```bash
scripts/routing-preflight.py --from-tier <current> --to-tier <proposed> \
  --project-dir . --session "$SESSION" --agent <agent> [--slice <s>] [--task <t>]
```

It reads the recent cache-read share from telemetry and returns an `action`:
`apply` (take the route as requested — effort-only, up-route, cold start, or a
genuinely output-heavy task) or `enforce_effort_down` (a context-heavy model-down
that would forfeit a warm cache — **keep the current model, take only the lower
effort**). Spawn with the `model`/`effort` from the check's `applied` field, not
the raw proposed tier. The check appends a `routing_preflight` record (with
`cache_read_share`, `action`, `requested` vs `applied`, `est_saving_tokens`,
`reason`) to `.project/telemetry/model-routing.jsonl` — the same stream as the
routing decision, for later review. Config + threshold live under `preflight:` in
`governance/model-routing.yaml`. You normally do **not** call this by hand — enforcement is automatic in both
modes. In drive mode `scripts/praxis-drive.sh` runs it every iteration; in
interactive mode a `PreToolUse(Task)` hook runs it on every sub-agent spawn and
**denies** a cache-forfeiting model-down with a corrective instruction to
re-spawn using the `applied` model/effort. Invoking it yourself (above) is only
for explicitly checking a route; the guardrail fires either way, no human step.

Resolve with the shared resolver (single source of truth), then pass the result
on the spawn:

```bash
# tier decided by the rubric (may be a ±1 adjustment). Resolve from the
# EFFECTIVE table — this honors a project override, same as drive:
scripts/resolve-model.py --harness claude-code --tier deep --project-dir .
#   -> model: opus   effort: high     ('inherit' = table maps this tier to auto)
```

```
Agent({
  subagent_type: "solution-architect",
  model: <resolved model>,   # from resolve-model.py; omit / "inherit" when auto
  prompt: "..."
})
```

Harness specifics:

- **Claude Code** — pass the resolved `model:` on the Agent spawn (Claude Code's
  per-invocation model beats the frontmatter). This is how a ±1 adjustment *and*
  a project override reach an interactive spawn. For belt-and-suspenders (so a
  spawn that skips this protocol still honors the override), run
  `scripts/setup-claude-agents.sh` to materialize project-local `.claude/agents/*.md`
  whose frontmatter is resolved from the effective table — they shadow the
  plugin agents.
- **Codex** — a spawned sub-agent's model/effort come from its
  `.codex/agents/*.toml` profile, which `$praxis-setup-subagents` regenerates
  from the effective table (so the project override is baked into the profile).
  Codex has no caller-side per-spawn model override, so re-run
  `$praxis-setup-subagents` after changing the override; live ±1 at spawn isn't
  available on Codex — set the tier in the profile instead.

The routing decision is made BEFORE the spawn, and logged to `.project/telemetry/model-routing.jsonl` (timestamp, harness, agent, task, per-signal scores, tier, resolved model, rationale — include `harness` so decisions from different loop-runners stay attributable; see the canonical envelope in `docs/telemetry.md`). Load `references/routing-examples.md` for a fully worked log entry. Log entries serve the quarterly `llm-cost-optimization` review — frequency reports can show which agent types actually need the deep tier vs which are habitually over-provisioned.

---

## Session-level model selection

When opening a new Cowork / Claude Code session (not just spawning sub-agents), advise:

**Start on the standard tier.** If the session's first task scores 7+ on the rubric, re-open on the deep tier. Don't pre-emptively open on the deep tier for sessions that haven't been scored.

Signs that a session needs the deep tier from the start:
- The session title suggests architecture, threat modeling, or cross-cutting ADR
- The user's brief contains > 2 "first-of-kind" markers
- The session is a P0 incident post-mortem

Signs that the standard tier is sufficient:
- "Implement slice N" — implementation per established design
- "Review this code" — code review against known standards
- "Write the docs for X" — documentation
- "Set up CI/CD" — following `cicd-pipeline` SKILL
- "Fix this bug" — isolated, reproducible, scope clear

---

## Escalation protocol

When a standard-tier attempt is rejected or fails quality checks:

1. **Score the failure.** Add 2 to `prior_failure` signal. Re-score.
2. **Escalate to the deep tier.** Always — never retry the standard tier on the same task after a failure.
3. **Give the deep-tier run the failure context.** Include the standard-tier output, the failure reason, and what was missing. Don't let it start cold.
4. **Log the escalation** to `.project/episodic/model-escalations.md` with the task, failure reason, and outcome. Load `references/routing-examples.md` for a worked escalation-log entry.

Escalation logs feed the fast-path rules above. Three escalations on the same task type → promote it to "Always deep" in this project's local fast-path override.

---

## Quota management heuristics

When deep-tier budget is low (user signals "running out"):

1. Audit what's been using the deep tier. Check `.project/telemetry/model-routing.jsonl`.
2. Identify tasks that could have been standard tier (score ≤ 6 that were routed deep by habit).
3. Tighten the default: treat score 7 as "standard tier with elevated review" rather than automatic deep, reserving deep for 8+.
4. **Never downgrade these regardless of budget:** threat-modeling, architecture sign-off for systems > 2 flags, P0 post-mortems, escalations after standard-tier failure.
5. Defer non-urgent deep-tier tasks to the next budget window when possible.

The goal is never quality regression — deep-tier budget management is about eliminating the deep tier on tasks that don't need it, not downgrading tasks that genuinely do.

---

## Anti-rationalization

The reason this discipline holds is that both directions are seductive — the deep tier feels safer, the standard tier feels cheaper. Load `references/routing-examples.md` for the full shortcut-vs-hold-the-line table (12 rows covering default-to-deep, default-to-standard-to-save-budget, sunk-cost retries, nominal category matches, session-switching friction, log-skipping, budget-pressure downgrades, preemptive escalation, and user-authority overrides).

---

## Red flags during routing

- **Deep tier running > 2 hours on a single problem.** Either escalate the problem (break it up, get help) or de-escalate the tier — this is the "stuck in a loop" signal.
- **Standard tier asked to make a decision without context.** Escalation is the wrong response; clarify the decision criteria first.
- **Deep tier used for a mechanical task > 3 times in a week.** Update routing table — habit forming.
- **Standard tier used for a review that later missed a bug.** Update escalation trigger table — this class of PR is deep-tier-worthy.
- **Never switching tiers within a session.** Almost every 4-hour session has both deep- and standard-tier-worthy moments; if you're on one tier the whole time, you're either underspending or overspending.

---

## Integration with using-praxis routing

In the `using-praxis` intent → workflow routing tree, each `agent_invocation` step should now carry a model hint:

```yaml
- id: architecture
  type: agent_invocation
  agent: solution-architect
  skill: architecture-pattern-selection
  model: adaptive  # Delivery Lead runs adaptive-model-routing before spawning
  inputs:
    from: requirements_brief
```

When `model: adaptive` is set on a workflow step, the Delivery Lead evaluates this SKILL before spawning the agent. The routing log entry is produced; the agent is spawned with the selected model string.

Steps where the tier is always fixed (no evaluation needed):
- `agent: architecture-challenger` → always `deep`
- `agent: code-reviewer` (standard slice review) → always `standard`
- `agent: platform-sre` (CI/CD, IaC wiring) → always `standard`

---

## Outputs

| Output | Location |
|---|---|
| Per-spawn routing decision | `.project/telemetry/model-routing.jsonl` |
| Escalation log | `.project/episodic/model-escalations.md` |
| Fast-path overrides (project-local) | `.project/procedural/model-routing-overrides.md` |
| Consumer: routing/cost aggregation | `scripts/factory-routing-report.py` (reads this log plus `hooks/tap.sh`'s `agent-spawns.jsonl` and prose dispatch logs) |

---

## Verification

Before ending an intake decision as final:

- [ ] The task has been scored on all five signals (or a fast-path rule matched).
- [ ] The rationale is stated in 1-2 sentences (not "vibes").
- [ ] The model string is selected and recorded.
- [ ] The agent spawn includes the `model:` field.
- [ ] The routing log entry is appended.
- [ ] If this is an escalation: the failure context is passed to the deep-tier run; the escalation log is updated.
- [ ] For phase transitions: any per-project override to `.project/procedural/model-routing-overrides.md` is reviewed.

---

## Mode handling (G/B)

**Greenfield.** Architecture phases score high on novelty → deep tier expected for Phases A and B. Implementation slices score low → standard tier default throughout. The ratio after a full project run is roughly: 15–20% deep, 75–80% standard, 5% light.

**Brownfield.** Brownfield `codebase-comprehension` is a heavy read task — the standard tier handles it. Impact analysis may score 7+ if the system is large and the change is cross-cutting → deep tier. Architecture reconciliation against existing system: standard tier unless NFR violations are found, then deep tier for remediation ADRs.

---

## What this SKILL does not do

- Execute the task — it only selects the model.
- Override the harness's model availability — if the deep tier's budget is exhausted, the session blocks; this SKILL flags the situation but cannot provision more budget.
- Switch the model programmatically — Claude Code doesn't let a SKILL invoke `/model`. The output is a recommendation for the user to act on (or a spawn-time `model:` field for the Delivery Lead to pass).
- Track cost in dollars — that's `llm-cost-optimization`.
