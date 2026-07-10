---
name: adaptive-model-routing
description: "Routes tasks to the right reasoning-effort tier (high / medium / low — the Codex resolution of Praxis capability tiers deep / standard / light per governance/model-routing.yaml) based on task complexity, novelty, stakes, and interdependency. Prevents wasteful high-reasoning consumption on tasks medium handles equally well, and prevents quality failures from routing complex tasks to low reasoning. The Delivery Lead runs this SKILL every time it opens a new specialist session. Use whenever an agent session is about to be launched, when selecting a model_reasoning_effort for the current session, or when a prior attempt failed and escalation is being considered."
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
  - "about to launch a specialist Codex session — which reasoning effort should it use?"
  - "starting a new session — which model_reasoning_effort should I launch on?"
  - "prior attempt failed — should I escalate the reasoning tier?"
  - "deciding whether this task needs high reasoning or medium is enough"
  - "API spend running high — can I safely use medium reasoning here?"
  - "complex architecture decision coming — what reasoning tier?"
  - "entering a new workflow phase — should the reasoning tier change?"
outputs:
  - reasoning-effort selection (per session or specialist launch)
  - complexity score + rationale
  - escalation recommendation (when prior attempt fails)
  - routing log entry at .project/telemetry/model-routing.jsonl
consumers:
  - delivery-lead (primary — runs this SKILL before every specialist launch)
  - using-praxis (consumes routing decision when selecting reasoning effort for orchestration)
  - agentic-architecture (session-as-agent configuration)
references:
  - llm-cost-optimization.md
```
<!-- praxis:metadata:end -->

The Codex variant of `adaptive-model-routing`. Same underlying routing rubric as the Claude Code version; adapted to Codex CLI's `model_reasoning_effort` parameter and session-as-agent spawn pattern.

## What differs from the Claude Code variant

| Aspect | Claude Code | Codex |
|---|---|---|
| Tier parameter | `model:` frontmatter (opus / sonnet / haiku) | `model_reasoning_effort` in `codex-agents/*.toml` (high / medium / low) |
| Sub-agent spawn | `Agent({ subagent_type, model, prompt })` — in-process, per-spawn model | Session-as-agent: launch a new Codex CLI session with the specialist's TOML config |
| Model switch mid-session | `/model <name>` slash command | Not supported — restart the session with the new agent config |
| Quota model | Weekly rate limits per plan | Per-token API cost + org rate limits |
| Model itself | Distinct models per tier (Opus / Sonnet / Haiku) | Typically ONE base model; `reasoning_effort` is what tunes cost + quality |

**What stays the same:** the 5-signal rubric, fast-path rules, phase-level defaults, per-agent assignments, escalation protocol, anti-rationalization table, red flags. Those are model-agnostic engineering discipline.

The principle: **default to medium reasoning; escalate to high only when specific complexity signals are present; never use high for tasks a competent medium-reasoning run completes correctly.**

---

## Reasoning-effort tier reference

Codex agent TOMLs declare `model_reasoning_effort = "high" | "medium" | "low"`. This SKILL routes tasks to the right value.

| Reasoning effort | Use for | Cost multiplier |
|---|---|---|
| **high** | Novel architecture decisions, complex multi-step reasoning, high-stakes gates, adversarial review, tasks where prior medium attempt failed | ~3-5x medium |
| **medium** | Default for almost everything — implementation, standard SKILLs, summarization, documentation, extraction, routine orchestration | baseline |
| **low** | Classification, intent detection, simple extraction, routing decisions with structured inputs, pre-flight checks | ~0.2-0.5x medium |

**Default: medium.** Upgrade to high only when the routing rubric says so.

---

## Routing rubric

Score the task on five signals. Each signal is 0–2. Total score determines the reasoning effort.

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| **Novelty** | Established pattern in codebase or skill | First time in this project; some unknowns | Genuinely first-of-kind; no prior art |
| **Interdependency** | Single concern, one domain | 2–3 concerns; some cross-cutting | Many cross-cutting concerns; global impact |
| **Stakes** | Reversible; no user or prod impact | Limited prod impact; rollback available | Security, compliance, prod go/no-go, data loss risk |
| **Ambiguity** | Spec is clear and complete | Some scope gaps; clarifiable | High ambiguity; major assumptions required |
| **Prior failure** | No prior attempt | Prior attempt marginal | Prior medium-reasoning attempt failed; escalation triggered |

**Score → tier:**

| Total | Tier | Rationale |
|---|---|---|
| 0–3 | **medium** | Routine work; medium reasoning handles it well |
| 4–6 | **medium** (with care) | Moderate complexity; medium capable; flag output for review |
| 7–8 | **high** | High complexity; escalate |
| 9–10 | **high** | Critical task; high required |

---

## Task-type fast path

Before scoring, check these fast-path rules. If a rule matches, it overrides the score.

### Always medium (regardless of score)
- Implementing a slice with a clear spec from the Lead Developer
- Writing code that follows an established pattern already in the codebase
- Applying a praxis SKILL where the application is routine (cicd-pipeline, containerization, observability wiring)
- Producing documentation, release notes, runbook templates
- Summarizing, extracting, or classifying structured content
- Routine gate checks (evidence package assembly for production release)
- Frontend component implementation per design system spec

### Always high (regardless of score)
- Solution Architect producing the primary architecture decision (`architecture-pattern-selection`) for a system with > 2 capability flags active
- Architecture Challenger adversarial sub-personas
- Security threat model (`threat-modeling` SKILL — stakes are always 2)
- Requirements elicitation with a genuinely vague brief (`requirements-interrogation` KUACQ pass on ambiguous scope)
- Cross-cutting ADR with > 3 affected services or teams
- Production incident post-mortem for a P0/P1
- Any task that explicitly failed a prior medium-reasoning run (escalation is non-negotiable)

### Consider low
- Intent classification before routing to the right agent
- Pre-flight checks (does this file exist? is the spec complete?)
- Structured extraction from well-defined inputs
- Routing decisions where the input is already structured

---

## Phase-level defaults (workflow integration)

If you're inside a workflow, the phase has a default reasoning tier that applies until an escalation trigger or fast-path rule overrides it:

| Phase | Default | Rationale |
|---|---|---|
| `pre` (codebase-comprehension, brownfield) | medium | Heavy-read task; medium handles it; escalate impact-analysis if system is large |
| `A` (discovery + requirements) | medium | Structured elicitation; escalate on vague brief per fast-path rule |
| `B` (architecture) | **high** | Architecture-pattern-selection + architecture-challenger are Always high |
| `C` (implementation slice) | medium | Execution against an approved architecture |
| `D` (release gate review) | high | The go/no-go decision is high-stakes |
| `D` (release execution) | medium | Deploy, config, mechanical steps |
| Post-release ops | medium | Incident triage escalates per fast-path (P0/P1 → high) |

Per-agent defaults are captured in each specialist's `codex-agents/<name>.toml` file via `model_reasoning_effort`. This SKILL overrides at session-launch time when the task warrants.

---

## Per-agent default assignments

Each Codex agent profile in `codex-agents/<name>.toml` carries a `model_reasoning_effort` GENERATED from the canonical agent's `capability_tier` via `governance/model-routing.yaml`:

| Agent | Tier | `model_reasoning_effort` | Why |
|---|---|---|---|
| delivery-lead | deep | high | Orchestration routing compounds; wrong routes waste hours |
| product-manager | standard | medium | Structured elicitation is mechanical after first pass; escalate on vague briefs per fast-path |
| solution-architect | deep | high | Architecture decisions are irreversible |
| architecture-challenger | deep | high | Adversarial depth is the role's value |
| lead-developer | standard | medium | Task decomposition against defined spec is execution |
| backend-developer | standard | medium | Implementation is pattern-matching against the packet |
| frontend-developer | standard | medium | Same |
| mobile-developer | standard | medium | Same — implementation against the packet and stack-flutter |
| data-engineer | standard | medium | Pipeline implementation is mostly mechanical; escalate high-blast-radius designs |
| ml-ai-engineer | deep | high | Research-heavy, novel problems, eval design |
| code-reviewer | deep | high | Missing a bug in review is expensive |
| security-reviewer | deep | high | Adversarial + high-stakes; false negatives catastrophic |
| qa-engineer | standard | medium | Test code is mechanical; test design stays standard |
| tech-writer | light | low | Translation/formatting task; promote for novel architecture docs |
| platform-sre | standard | medium | Mostly execution; escalate for incidents per fast-path |
| ux-designer | standard | medium | Structured design |
| system-steward | standard | medium | Digest + proposal work; promotions are human-gated anyway |

Result: **6 high / 10 medium / 1 low** — identical tier assignments to every other harness, resolved from each agent's `capability_tier` by `scripts/apply-model-routing.py`. Do not edit `codex-agents/*.toml` reasoning efforts by hand; change the tier in the canonical agent or the mapping in `governance/model-routing.yaml` and re-run the script.

---

## Session launch configuration

When the Delivery Lead opens a new specialist session in Codex:

```bash
# Launch solution-architect on high reasoning for a real architecture call
codex --agent codex-agents/solution-architect.toml

# Launch backend-developer on medium for a routine slice
codex --agent codex-agents/backend-developer.toml

# For an ad-hoc override (task warrants higher tier than the agent's default):
codex --agent codex-agents/backend-developer.toml --model-reasoning-effort high
```

The routing decision is made BEFORE the `codex` invocation. Log it:

```yaml
# .project/telemetry/model-routing.jsonl (append each entry)
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
  reasoning_effort: high
  rationale: "Score 8; payment + compliance + cross-cutting = high reasoning"
```

Log entries serve the quarterly `llm-cost-optimization` review — frequency reports show which agent types actually need high reasoning vs which are habitually over-provisioned.

---

## Session-level model selection

When opening the top-level Delivery Lead session, follow the routing rubric on the session's first task. Signs that the session needs high reasoning from launch:
- The session title suggests architecture, threat modeling, or cross-cutting ADR
- The user's brief contains > 2 "first-of-kind" markers
- The session is a P0 incident post-mortem

Signs that medium is sufficient:
- "Implement slice N" — implementation per established design
- "Review this code" — code review against known standards
- "Write the docs for X" — documentation
- "Set up CI/CD" — following `cicd-pipeline` SKILL
- "Fix this bug" — isolated, reproducible, scope clear

---

## Escalation protocol

When a medium-reasoning attempt is rejected or fails quality checks:

1. **Score the failure.** Add 2 to `prior_failure` signal. Re-score.
2. **Escalate to high.** Always — never retry medium on the same task after a failure.
3. **Give the high-reasoning session the failure context.** Include the medium output, the failure reason, and what was missing. Prepend the new session's prompt with a "Prior attempt failed because…" block.
4. **Log the escalation** to `.project/episodic/model-escalations.md`.

```markdown
# Model Escalation Log

## 2026-07-02 — requirements-elicitation for payments feature
- First attempt: medium reasoning
- Failure: Missed 4 compliance NFRs; scope too broad; output not actionable
- Escalation: high reasoning with failure context and compliance mandate
- Outcome: high-reasoning session produced complete NFR register; passed requirements_freeze gate
- Learning: requirements-elicitation with compliance scope → always high
```

Escalation logs feed the fast-path rules above. Three escalations on the same task type → promote it to "Always high" in this project's local fast-path override.

---

## Cost management heuristics

Codex API cost scales roughly linearly with reasoning effort. When API spend is running high:

1. Audit what's been using high. Check `.project/telemetry/model-routing.jsonl`.
2. Identify tasks that could have been medium (score ≤ 6 that were routed to high by habit).
3. Tighten the default: treat score 7 as "medium with elevated review" rather than automatic high, reserving high for 8+.
4. **Never downgrade these regardless of cost:** threat-modeling, architecture sign-off for systems > 2 flags, P0 post-mortems, escalations after medium failure.
5. For cheap classifications and pre-flight checks, drop to low — often 5-10× cheaper than medium.

The goal is never quality regression — cost management is about eliminating high on tasks that don't need it, not downgrading tasks that genuinely do.

---

## Anti-rationalization

The reason this discipline holds is that both directions are seductive — high feels safer, medium feels cheaper.

| Shortcut you'll be tempted to take | Why it's tempting | What actually happens | Hold the line |
|---|---|---|---|
| "Use high by default; it's better" | Zero cognitive overhead | Monthly API spend blows past budget; ops questions your ROI | The 5-second scoring cost pays back 10x by preserving high for when it matters |
| "Use medium for everything to save cost" | Feels frugal | Medium writes a subtle bug in the migration script; multi-day cleanup dwarfs the token savings | If a mistake costs > 1 day, that's not a medium task regardless of visible complexity |
| "High is stuck, retry with more context" | Sunk cost fallacy | High loops on the same wrong hypothesis; wastes 2x tokens | If medium is stuck, clarify the problem first. Ambiguity ≠ complexity |
| "This is architectural, must be high" | Nominal category match | The "architectural" task is renaming a class; judgment already happened | Look at what the task actually requires, not what it's labeled |
| "Medium is fine, it's just implementation" | It IS implementation | The implementation touches auth, cross-tenant boundaries, or migration | "Implementation" that touches load-bearing modules is high-worthy regardless of task label |
| "Leave session on high, cheaper than relaunching" | Session restart feels like friction | Every message on high that could be on medium burns API budget | In Codex, session restart IS the pattern — no cost to relaunching |
| "Re-try medium on a failed task" | Might work this time | Same reasoning tier + same task rarely fixes the failure | Escalate with failure context, per escalation protocol |
| "Skip the routing log — I'll remember" | Log feels bureaucratic | Steward can't tell what actually needed high; can't tighten routing rules | The log is 10 seconds; the quarterly cost audit needs it |
| "Downgrade threat-modeling to save cost" | Cost pressure | Security corners cut for budget; incident 6 months later | Threat-modeling is never downgraded — cost is not an excuse |
| "Escalate preemptively before any medium attempt" | Feels safer | High produces marginal answer to ambiguous problem; you burn budget on a bad question | Try medium first with explicit failure criteria; escalate only on evidence |

---

## Red flags during routing

- **High session running > 2 hours on a single problem.** Either escalate the problem (break it up, get help) or restart on medium — this is the "stuck in a loop" signal.
- **Medium asked to make a decision without context.** Escalation is wrong response; clarify the decision criteria first.
- **High used for a mechanical task > 3 times in a week.** Update routing table — habit forming.
- **Medium used for a review that later missed a bug.** Update escalation trigger table — this class of PR is high-worthy.
- **Never varying reasoning tier across sessions.** Different tasks warrant different tiers; sticking to one is either underspending or overspending.

---

## Integration with using-praxis routing

In the `using-praxis` intent → workflow routing tree, each `agent_invocation` step carries a reasoning hint:

```yaml
- id: architecture
  type: agent_invocation
  agent: solution-architect
  skill: architecture-pattern-selection
  reasoning: adaptive  # Delivery Lead runs adaptive-model-routing before launching
  inputs:
    from: requirements_brief
```

When `reasoning: adaptive` is set on a workflow step, the Delivery Lead evaluates this SKILL before launching the specialist session. The routing log entry is produced; the session is opened with the selected `model_reasoning_effort` override.

Steps where reasoning tier is always fixed (no evaluation needed):
- `agent: architecture-challenger` → always high
- `agent: code-reviewer` (standard slice review) → always medium (with escalation triggers for cross-cutting PRs)
- `agent: platform-sre` (CI/CD, IaC wiring) → always medium

---

## Outputs

| Output | Location |
|---|---|
| Per-session routing decision | `.project/telemetry/model-routing.jsonl` |
| Escalation log | `.project/episodic/model-escalations.md` |
| Fast-path overrides (project-local) | `.project/procedural/model-routing-overrides.md` |

---

## Verification

Before ending a routing decision as final:

- [ ] The task has been scored on all five signals (or a fast-path rule matched).
- [ ] The rationale is stated in 1-2 sentences (not "vibes").
- [ ] The reasoning tier is selected and recorded.
- [ ] The session launch command includes the correct `model_reasoning_effort` (via TOML or `--model-reasoning-effort` flag override).
- [ ] The routing log entry is appended.
- [ ] If this is an escalation: the failure context is passed to the new session; the escalation log is updated.
- [ ] For phase transitions: any per-project override in `.project/procedural/model-routing-overrides.md` is reviewed.

---

## Mode handling (G/B)

**Greenfield.** Architecture phases score high on novelty → high expected for Phase B. Implementation slices score low → medium default throughout. Ratio after a full project run: roughly 15–20% high, 75–80% medium, 5% low.

**Brownfield.** Brownfield `codebase-comprehension` is a heavy read task — medium handles it. Impact analysis may score 7+ if the system is large and the change is cross-cutting → high. Architecture reconciliation against existing system: medium unless NFR violations are found, then high for remediation ADRs.

---

## What this SKILL does not do

- Execute the task — it only selects the reasoning tier.
- Override OpenAI's model availability or rate limits — if capacity is constrained, sessions block; this SKILL flags the situation but cannot provision more.
- Switch reasoning tier mid-session — Codex CLI doesn't support this; the output is a recommendation for the next session launch.
- Track cost in dollars — that's `llm-cost-optimization`.
- Modify the underlying model — Codex CLI is typically bound to one base model per install; this SKILL tunes reasoning effort within that model.

---

## Build integration

This SKILL is the Codex-specific overlay applied by `scripts/build-codex-plugin.sh`. It replaces the canonical `skills/adaptive-model-routing/SKILL.md` in the generated Codex package.

Do NOT edit `plugins/praxis-codex/skills/adaptive-model-routing/SKILL.md` directly — that file is generated and will be overwritten on next build. Edit this file (`codex-plugin-assets/skills/adaptive-model-routing/SKILL.md`) instead, then run:

```bash
scripts/build-codex-plugin.sh
```

To keep the Claude Code and Codex variants in sync when you change the routing rubric, edit both:
- `skills/adaptive-model-routing/SKILL.md` (canonical, Claude Code-shaped)
- `codex-plugin-assets/skills/adaptive-model-routing/SKILL.md` (Codex overlay, this file)

The scoring rubric and anti-rationalization should stay identical between the two; only tier names, spawn syntax, and cost model differ.
