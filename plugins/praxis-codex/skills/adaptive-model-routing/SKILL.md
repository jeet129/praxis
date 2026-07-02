---
name: adaptive-model-routing
description: "Routes tasks to the right OpenAI model (flagship vs mid-tier vs fast) based on task complexity, novelty, stakes, and interdependency. Prevents wasteful high-tier token spend on tasks the mid-tier handles equally well, and prevents quality failures from routing complex tasks to cheaper models. The Delivery Lead runs this SKILL every time it opens a new sub-session or spawns a specialist. Use whenever an agent session is about to be opened, when selecting a model for the current session, or when a prior attempt failed and escalation is being considered."
---

# Adaptive Model Routing (Codex variant)

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
  - "about to open a specialist sub-session — which model should it use?"
  - "starting a new session — which model should I launch?"
  - "prior attempt failed — should I escalate the model?"
  - "deciding whether this task needs the flagship model or the mid-tier"
  - "API spend running high — can I safely use the mid-tier here?"
  - "complex architecture decision coming — what model?"
  - "entering a new workflow phase — should the model change?"
outputs:
  - model selection decision (per session or specialist spawn)
  - complexity score + rationale
  - escalation recommendation (when prior attempt fails)
  - routing log entry at .project/working/model-routing-log.yaml
consumers:
  - delivery-lead (primary — runs this SKILL before every specialist session)
  - using-praxis (consumes routing decision when selecting model for orchestration)
  - agentic-architecture (session-as-agent configuration)
references:
  - llm-cost-optimization.md
```
<!-- praxis:metadata:end -->

The Codex variant of `adaptive-model-routing`. Same underlying routing rubric as the Claude Code version; different model strings, different spawn pattern, different quota semantics.

**How Codex differs from Claude Code:**

| Aspect | Claude Code | Codex |
|---|---|---|
| Sub-agent spawn | `Agent({ subagent_type, model, prompt })` — in-session, per-spawn model | Session-as-agent: each specialist is a separate CLI session launched with `--model <tier>` |
| Model switch mid-session | `/model <name>` slash command | Not supported — restart the session with a different `--model` flag |
| Model tiers | Opus / Sonnet / Haiku | Flagship / Mid-tier / Fast (verify current tier names below) |
| Quota model | Weekly rate limits per plan | API-based per-token billing + org-wide rate limits |
| Delivery Lead's role | Spawns sub-agents in-process | Opens new CLI sessions per specialist; routing decision is a `--model` flag choice |

**What stays the same:** the 5-signal rubric, fast-path rules, phase-level defaults, per-agent assignments, escalation protocol, anti-rationalization table, red flags. Those are model-agnostic engineering discipline.

The principle: **default to the mid-tier; escalate to the flagship only when specific complexity signals are present; never use the flagship for tasks a competent mid-tier run completes correctly.**

---

## Model tier reference

> **Note:** Codex/OpenAI model names evolve. Verify the exact strings against the deployed CLI version before wiring into workflows. The examples below use placeholder-plus-candidates format.

| Tier | Candidate model strings (verify current) | Use for |
|---|---|---|
| **Flagship** (Opus-equivalent) | `gpt-5`, or the current reasoning-strongest model (o-series if available) | Novel architecture decisions, complex multi-step reasoning, high-stakes gates, adversarial review, tasks where prior mid-tier attempt failed |
| **Mid-tier** (Sonnet-equivalent) | `gpt-5-mini`, `gpt-4.1`, or the current default coding model | Default for almost everything — implementation, standard SKILLs, summarization, documentation, extraction, routine orchestration |
| **Fast** (Haiku-equivalent) | `gpt-5-nano`, `gpt-4o-mini`, or the current fastest small model | Classification, intent detection, simple extraction, routing decisions with structured inputs, pre-flight checks |

**Default: Mid-tier.** Upgrade to Flagship only when the routing rubric says so.

If your Codex CLI is bound to a specific model per session, this SKILL's output tells you which model to launch the next session on — not a runtime switch.

---

## Routing rubric

Score the task on five signals. Each signal is 0–2. Total score determines the model tier.

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| **Novelty** | Established pattern in codebase or skill | First time in this project; some unknowns | Genuinely first-of-kind; no prior art |
| **Interdependency** | Single concern, one domain | 2–3 concerns; some cross-cutting | Many cross-cutting concerns; global impact |
| **Stakes** | Reversible; no user or prod impact | Limited prod impact; rollback available | Security, compliance, prod go/no-go, data loss risk |
| **Ambiguity** | Spec is clear and complete | Some scope gaps; clarifiable | High ambiguity; major assumptions required |
| **Prior failure** | No prior attempt | Prior attempt marginal | Prior mid-tier attempt failed; escalation triggered |

**Score → tier:**

| Total | Tier | Rationale |
|---|---|---|
| 0–3 | **Mid-tier** | Routine work; mid-tier handles it well |
| 4–6 | **Mid-tier** (with care) | Moderate complexity; mid-tier capable; flag output for review |
| 7–8 | **Flagship** | High complexity; use flagship |
| 9–10 | **Flagship** | Critical task; flagship required |

---

## Task-type fast path

Before scoring, check these fast-path rules. If a rule matches, it overrides the score.

### Always Mid-tier (regardless of score)
- Implementing a slice with a clear spec from the Lead Developer
- Writing code that follows an established pattern already in the codebase
- Applying a praxis SKILL where the application is routine (cicd-pipeline, containerization, observability wiring)
- Producing documentation, release notes, runbook templates
- Summarizing, extracting, or classifying structured content
- Routine gate checks (evidence package assembly for production release)
- Frontend component implementation per design system spec

### Always Flagship (regardless of score)
- Solution Architect producing the primary architecture decision (`architecture-pattern-selection`) for a system with > 2 capability flags active
- Architecture Challenger adversarial sub-personas (`doubt-driven-decisions` pattern applied to architecture)
- Security threat model (`threat-modeling` SKILL — stakes are always 2)
- Requirements elicitation with a vague brief (`requirements-interrogation` KUACQ pass on genuinely ambiguous scope)
- Cross-cutting ADR with > 3 affected services or teams
- Production incident post-mortem for a P0/P1
- Any task that explicitly failed a prior mid-tier run (escalation is non-negotiable)

### Consider Fast tier
- Intent classification before routing to the right agent
- Pre-flight checks (does this file exist? is the spec complete?)
- Structured extraction from well-defined inputs (extract key fields from an NFR register)
- Routing decisions where the input is already structured

---

## Phase-level defaults (workflow integration)

If you're inside a workflow, the phase has a default tier that applies until an escalation trigger or fast-path rule overrides it:

| Phase | Default | Rationale |
|---|---|---|
| `pre` (codebase-comprehension, brownfield) | Mid-tier | Heavy-read task; mid-tier handles it; escalate impact-analysis if system is large |
| `A` (discovery + requirements) | Mid-tier | Structured elicitation; escalate on vague brief per fast-path rule |
| `B` (architecture) | **Flagship** | Architecture-pattern-selection + architecture-challenger are Always Flagship |
| `C` (implementation slice) | Mid-tier | Execution against an approved architecture |
| `D` (release gate review) | Flagship | The go/no-go decision is high-stakes |
| `D` (release execution) | Mid-tier | Deploy, config, mechanical steps |
| Post-release ops | Mid-tier | Incident triage escalates per fast-path (P0/P1 → Flagship) |

Per-agent defaults are captured in each agent's file. This SKILL overrides at session-launch time when the task warrants.

---

## Per-agent default assignments

Each agent has a canonical model tier. In Codex, the Delivery Lead launches specialist sessions on that tier by default.

| Agent | Default tier | Why |
|---|---|---|
| delivery-lead | Flagship | Orchestration routing compounds; wrong routes waste hours |
| product-manager | Mid-tier | Structured elicitation is mechanical after first pass |
| solution-architect | Flagship | Architecture decisions are irreversible |
| architecture-challenger | Flagship | Adversarial depth is the role's value |
| lead-developer | Mid-tier | Task decomposition against defined spec is execution |
| backend-developer | Mid-tier | Implementation is pattern-matching |
| frontend-developer | Mid-tier | Same |
| data-engineer | Mid-tier | Pipeline implementation is mostly mechanical |
| ml-ai-engineer | Flagship | Research-heavy, novel problems, eval design |
| code-reviewer | Flagship | Missing a bug in review is expensive |
| security-reviewer | Flagship | Adversarial + high-stakes; false negatives catastrophic |
| qa-engineer | Mid-tier | Test writing is mechanical translation |
| tech-writer | Mid-tier | Translation task |
| platform-sre | Mid-tier | Mostly execution; escalate for incidents |
| ux-designer | Mid-tier | Structured design |
| system-steward | Flagship | Library evolution decisions across projects |

Result: 7 Flagship / 9 Mid-tier. Flagship concentrated where irreversibility and adversarial depth matter.

Since Codex uses session-as-agent, this table drives the `--model` flag for each specialist's session launch.

---

## Session launch configuration

When the Delivery Lead opens a new specialist session:

```bash
# Launch solution-architect on the flagship for a real architecture call
codex --agent solution-architect --model gpt-5 --prompt "..."

# Launch backend-developer on the mid-tier for a routine slice
codex --agent backend-developer --model gpt-5-mini --prompt "..."

# Launch a pre-flight classifier on the fast tier
codex --agent intent-classifier --model gpt-5-nano --prompt "..."
```

The routing decision is made BEFORE the `codex` invocation. Log it:

```yaml
# .project/working/model-routing-log.yaml (append each entry)
- timestamp: 2026-07-02T10:00:00
  agent: solution-architect
  task: "architecture-pattern-selection for payment service"
  score: 8
  signals:
    novelty: 2         # First payment system in this project
    interdependency: 2 # Touches auth, fraud, ledger, notifications
    stakes: 2          # Financial data; compliance required
    ambiguity: 1       # Scope mostly clear; some NFR gaps
    prior_failure: 0   # First attempt
  tier: flagship
  model: gpt-5
  rationale: "Score 8; payment + compliance + cross-cutting = Flagship"
```

Log entries serve the quarterly `llm-cost-optimization` review — frequency reports show which agent types actually need the flagship vs which are habitually over-provisioned.

---

## Session-level model selection

When opening the top-level Delivery Lead session:

**Start on Mid-tier.** If the session's first task scores 7+ on the rubric, close and re-launch on Flagship. Don't pre-emptively open on Flagship for sessions that haven't been scored.

Signs that a session needs Flagship from the start:
- The session title suggests architecture, threat modeling, or cross-cutting ADR
- The user's brief contains > 2 "first-of-kind" markers
- The session is a P0 incident post-mortem

Signs that a Mid-tier session is sufficient:
- "Implement slice N" — implementation per established design
- "Review this code" — code review against known standards
- "Write the docs for X" — documentation
- "Set up CI/CD" — following `cicd-pipeline` SKILL
- "Fix this bug" — isolated, reproducible, scope clear

---

## Escalation protocol

When a mid-tier attempt is rejected or fails quality checks:

1. **Score the failure.** Add 2 to `prior_failure` signal. Re-score.
2. **Escalate to Flagship.** Always — never retry mid-tier on the same task after a failure.
3. **Give Flagship the failure context.** Include the mid-tier output, the failure reason, and what was missing. In Codex, this typically means opening the new session with a system prompt referencing the prior attempt.
4. **Log the escalation** to `.project/episodic/model-escalations.md` with the task, failure reason, and outcome.

```markdown
# Model Escalation Log

## 2026-07-02 — requirements-elicitation for payments feature
- First attempt: Mid-tier (gpt-5-mini)
- Failure: Missed 4 compliance NFRs; scope too broad; output not actionable
- Escalation: Flagship (gpt-5) with failure context and compliance mandate
- Outcome: Flagship produced complete NFR register; passed requirements_freeze gate
- Learning: requirements-elicitation with compliance scope → always Flagship
```

Escalation logs feed the fast-path rules above. Three escalations on the same task type → promote it to "Always Flagship" in this project's local fast-path override.

---

## Cost management heuristics

Codex API cost is per-token, not weekly-quota-limited. When your API spend is running high (org rate limits, budget alerts):

1. Audit what's been using Flagship. Check `.project/working/model-routing-log.yaml`.
2. Identify tasks that could have been Mid-tier (score ≤ 6 that were routed to Flagship by habit).
3. Tighten the default: treat score 7 as "Mid-tier with elevated review" rather than automatic Flagship, reserving Flagship for 8+.
4. **Never downgrade these regardless of cost:** threat-modeling, architecture sign-off for systems > 2 flags, P0 post-mortems, escalations after mid-tier failure.
5. For very cheap classifications and pre-flight checks, drop to the Fast tier — often 10-20× cheaper.

The goal is never quality regression — cost management is about eliminating Flagship on tasks that don't need it, not downgrading tasks that genuinely do.

---

## Anti-rationalization

The reason this discipline holds is that both directions are seductive — Flagship feels safer, Mid-tier feels cheaper.

| Shortcut you'll be tempted to take | Why it's tempting | What actually happens | Hold the line |
|---|---|---|---|
| "Use Flagship by default; it's better" | Zero cognitive overhead | Monthly API spend blows past budget; ops questions your ROI | The 5-second scoring cost pays back 10x by preserving Flagship for when it matters |
| "Use Mid-tier for everything to save cost" | Feels frugal | Mid-tier writes a subtle bug in the migration script; multi-day cleanup dwarfs the token savings | If a mistake costs > 1 day, that's not a Mid-tier task regardless of visible complexity |
| "Flagship is stuck, retry with more context" | Sunk cost fallacy | Flagship loops on the same wrong hypothesis; wastes 2x tokens | If Mid-tier is stuck, clarify the problem first. Ambiguity ≠ complexity |
| "This is architectural, must be Flagship" | Nominal category match | The "architectural" task is renaming a class; judgment already happened | Look at what the task actually requires, not what it's labeled |
| "Mid-tier is fine, it's just implementation" | It IS implementation | The implementation touches auth, cross-tenant boundaries, or migration | "Implementation" that touches load-bearing modules is Flagship-worthy regardless of task label |
| "Leave session on Flagship, cheaper than relaunching" | Session restart feels like friction | Every message on Flagship that could be on Mid-tier burns API budget for no reason | In Codex, session restart IS the pattern — no cost to relaunching on a different tier |
| "Re-try Mid-tier on a failed task" | Might work this time | Same model + same task rarely fixes the failure | Escalate with failure context, per escalation protocol |
| "Skip the routing log — I'll remember" | Log feels bureaucratic | Steward can't tell what actually needed Flagship; can't tighten routing rules | The log is 10 seconds; the quarterly cost audit needs it |
| "Downgrade threat-modeling to save cost" | Cost pressure | Security corners cut for budget; incident 6 months later | Threat-modeling is never downgraded — cost is not an excuse |
| "Escalate preemptively before any Mid-tier attempt" | Feels safer | Flagship produces marginal answer to ambiguous problem; you burn budget on a bad question | Try Mid-tier first with explicit failure criteria; escalate only on evidence |
| "The user asked for Flagship" | User authority | User may not know task doesn't need it; help them decide | Suggest Mid-tier with rationale if task warrants it; user can override |

---

## Red flags during routing

- **Flagship session running > 2 hours on a single problem.** Either escalate the problem (break it up, get help) or restart on Mid-tier — this is the "stuck in a loop" signal.
- **Mid-tier asked to make a decision without context.** Escalation is wrong response; clarify the decision criteria first.
- **Flagship used for a mechanical task > 3 times in a week.** Update routing table — habit forming.
- **Mid-tier used for a review that later missed a bug.** Update escalation trigger table — this class of PR is Flagship-worthy.
- **Never varying model tier across sessions.** Different tasks warrant different tiers; sticking to one is either underspending or overspending.

---

## Integration with using-praxis routing

In the `using-praxis` intent → workflow routing tree, each `agent_invocation` step carries a model hint:

```yaml
- id: architecture
  type: agent_invocation
  agent: solution-architect
  skill: architecture-pattern-selection
  model: adaptive  # Delivery Lead runs adaptive-model-routing before spawning
  inputs:
    from: requirements_brief
```

When `model: adaptive` is set on a workflow step, the Delivery Lead evaluates this SKILL before launching the specialist session. The routing log entry is produced; the session is opened with the selected `--model` flag.

Steps where model tier is always fixed (no evaluation needed):
- `agent: architecture-challenger` → always Flagship
- `agent: code-reviewer` (standard slice review) → always Mid-tier
- `agent: platform-sre` (CI/CD, IaC wiring) → always Mid-tier

---

## Outputs

| Output | Location |
|---|---|
| Per-session routing decision | `.project/working/model-routing-log.yaml` |
| Escalation log | `.project/episodic/model-escalations.md` |
| Fast-path overrides (project-local) | `.project/procedural/model-routing-overrides.md` |

---

## Verification

Before ending a routing decision as final:

- [ ] The task has been scored on all five signals (or a fast-path rule matched).
- [ ] The rationale is stated in 1-2 sentences (not "vibes").
- [ ] The tier + specific model string is selected and recorded.
- [ ] The session launch command includes the correct `--model` flag.
- [ ] The routing log entry is appended.
- [ ] If this is an escalation: the failure context is passed to the new session; the escalation log is updated.
- [ ] For phase transitions: any per-project override to `.project/procedural/model-routing-overrides.md` is reviewed.

---

## Mode handling (G/B)

**Greenfield.** Architecture phases score high on novelty → Flagship expected for Phases A and B. Implementation slices score low → Mid-tier default throughout. The ratio after a full project run is roughly: 15–20% Flagship, 75–80% Mid-tier, 5% Fast.

**Brownfield.** Brownfield `codebase-comprehension` is a heavy read task — Mid-tier handles it. Impact analysis may score 7+ if the system is large and the change is cross-cutting → Flagship. Architecture reconciliation against existing system: Mid-tier unless NFR violations are found, then Flagship for remediation ADRs.

---

## What this SKILL does not do

- Execute the task — it only selects the model tier.
- Override OpenAI's model availability or rate limits — if the flagship is rate-limited, sessions block; this SKILL flags the situation but cannot provision more capacity.
- Switch the model mid-session — Codex doesn't support this; the output is a recommendation for the next session launch.
- Track cost in dollars — that's `llm-cost-optimization`.
- Guarantee current model strings — verify against the deployed Codex CLI version. The strings in this SKILL are candidates as of authoring; substitute the real ones in your project's `.project/procedural/model-routing-overrides.md`.

---

## Adaptation from Claude Code variant

This Codex variant is derived from `skills/adaptive-model-routing/SKILL.md` in the Claude Code plugin. Content that stayed the same:
- 5-signal scoring rubric
- Fast-path task-type rules
- Phase-level defaults
- Per-agent assignments (Flagship/Mid-tier maps 1:1 to Opus/Sonnet)
- Escalation protocol structure
- Anti-rationalization discipline

What changed for Codex:
- Model strings (Claude Opus → OpenAI flagship; Sonnet → mid-tier; Haiku → fast)
- Spawn pattern (in-session `Agent({...})` → session-as-agent via CLI `--model` flag)
- Quota model (weekly rate limit → per-token API cost + rate limits)
- "Switch model mid-session" is not supported — restart the session
- Explicit "verify current model strings" caveat since OpenAI's tier names evolve

If your organization is on Claude Code, use the parent SKILL. If on Codex, use this one.
