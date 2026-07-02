---
name: adaptive-model-routing
description: "Routes tasks to the right Claude model (Opus vs Sonnet vs Haiku) based on task complexity, novelty, stakes, and interdependency. Prevents wasteful Opus consumption on tasks Sonnet handles equally well, and prevents quality failures from routing complex tasks to cheaper models. The Delivery Lead runs this SKILL every time it spawns a sub-agent. Use whenever an agent is about to be spawned, when selecting a model for a session, or when a prior attempt failed and escalation is being considered."
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
  - "deciding whether this task needs Opus or Sonnet"
  - "running out of Opus quota — can I safely use Sonnet here?"
  - "complex architecture decision coming — what model?"
  - "entering a new workflow phase — should the model change?"
outputs:
  - model selection decision (per agent spawn)
  - complexity score + rationale
  - escalation recommendation (when prior attempt fails)
  - routing log entry at .project/working/model-routing-log.yaml
consumers:
  - delivery-lead (primary — runs this SKILL before every agent spawn)
  - using-praxis (consumes routing decision when selecting model for orchestration)
  - agentic-architecture (agent spawn configuration)
references:
  - llm-cost-optimization.md
```
<!-- praxis:metadata:end -->

The discipline that keeps Opus quota for tasks that actually need it. Opus and Sonnet are not interchangeable — Opus has meaningfully stronger multi-step reasoning and novel synthesis; Sonnet handles the large majority of production work at 1/5 the cost and quota burn.

The principle: **default to Sonnet; escalate to Opus only when specific complexity signals are present; never use Opus for tasks a competent Sonnet run completes correctly.**

---

## Model tier reference

| Model | String | Use for |
|---|---|---|
| **Opus** | `claude-opus-4-8` | Novel architecture decisions, complex multi-step reasoning, high-stakes gates, adversarial review, tasks where prior Sonnet attempt failed |
| **Sonnet** | `claude-sonnet-4-6` | Default for almost everything — implementation, standard SKILLs, summarization, documentation, extraction, routine orchestration |
| **Haiku** | `claude-haiku-4-5-20251001` | Classification, intent detection, simple extraction, routing decisions with structured inputs, pre-flight checks |

**Default: Sonnet.** Upgrade to Opus only when the routing rubric says so.

---

## Routing rubric

Score the task on five signals. Each signal is 0–2. Total score determines the model.

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| **Novelty** | Established pattern in codebase or skill | First time in this project; some unknowns | Genuinely first-of-kind; no prior art |
| **Interdependency** | Single concern, one domain | 2–3 concerns; some cross-cutting | Many cross-cutting concerns; global impact |
| **Stakes** | Reversible; no user or prod impact | Limited prod impact; rollback available | Security, compliance, prod go/no-go, data loss risk |
| **Ambiguity** | Spec is clear and complete | Some scope gaps; clarifiable | High ambiguity; major assumptions required |
| **Prior failure** | No prior attempt | Prior attempt marginal | Prior Sonnet attempt failed; escalation triggered |

**Score → model:**

| Total | Model | Rationale |
|---|---|---|
| 0–3 | **Sonnet** | Routine work; Sonnet handles it well |
| 4–6 | **Sonnet** (with care) | Moderate complexity; Sonnet capable; flag if output needs review |
| 7–8 | **Opus** | High complexity; use Opus |
| 9–10 | **Opus** | Critical task; Opus required |

---

## Task-type fast path

Before scoring, check these fast-path rules. If a rule matches, it overrides the score.

### Always Sonnet (regardless of score)
- Implementing a slice with a clear spec from the Lead Developer
- Writing code that follows an established pattern already in the codebase
- Applying a praxis SKILL where the application is routine (cicd-pipeline, containerization, observability wiring)
- Producing documentation, release notes, runbook templates
- Summarizing, extracting, or classifying structured content
- Routine gate checks (evidence package assembly for production release)
- Frontend component implementation per design system spec

### Always Opus (regardless of score)
- Solution Architect producing the primary architecture decision (`architecture-pattern-selection`) for a system with > 2 capability flags active
- Architecture Challenger adversarial sub-personas (`doubt-driven-decisions` pattern applied to architecture)
- Security threat model (`threat-modeling` SKILL — stakes are always 2)
- Requirements elicitation with a vague brief (`requirements-interrogation` KUACQ pass on a genuinely ambiguous scope)
- Cross-cutting ADR with > 3 affected services or teams
- Production incident post-mortem for a P0/P1
- Any task that explicitly failed a prior Sonnet run (escalation is non-negotiable)

### Consider Haiku
- Intent classification before routing to the right agent
- Pre-flight checks (does this file exist? is the spec complete?)
- Structured extraction from well-defined inputs (extract key fields from an NFR register)
- Routing decisions where the input is already structured

---

## Phase-level defaults (workflow integration)

If you're inside a workflow, the phase has a default model that applies until an escalation trigger or fast-path rule overrides it:

| Phase | Default | Rationale |
|---|---|---|
| `pre` (codebase-comprehension, brownfield) | Sonnet | Heavy-read task; Sonnet handles it; escalate impact-analysis if system is large |
| `A` (discovery + requirements) | Sonnet | Structured elicitation; escalate on vague brief per fast-path rule |
| `B` (architecture) | **Opus** | Architecture-pattern-selection + architecture-challenger are Always Opus |
| `C` (implementation slice) | Sonnet | Execution against an approved architecture |
| `D` (release gate review) | Opus | The go/no-go decision is high-stakes; scored task fires the "high stakes" trigger |
| `D` (release execution) | Sonnet | Deploy, config, mechanical steps |
| Post-release ops | Sonnet | Incident triage escalates per fast-path (P0/P1 → Opus) |

Per-agent defaults ship in each agent's frontmatter (`model:` field). This SKILL overrides at spawn time when the task warrants.

---

## Per-agent default assignments

Each agent has a `model:` in its frontmatter. Delivery Lead uses this as the spawn default; this SKILL overrides for specific tasks.

| Agent | Default | Why |
|---|---|---|
| delivery-lead | Opus | Orchestration routing compounds; wrong routes waste hours |
| product-manager | Sonnet | Structured elicitation is mechanical after first pass |
| solution-architect | Opus | Architecture decisions are irreversible |
| architecture-challenger | Opus | Adversarial depth is the role's value |
| lead-developer | Sonnet | Task decomposition against defined spec is execution |
| backend-developer | Sonnet | Implementation is pattern-matching |
| frontend-developer | Sonnet | Same |
| data-engineer | Sonnet | Pipeline implementation is mostly mechanical |
| ml-ai-engineer | Opus | Research-heavy, novel problems, eval design |
| code-reviewer | Opus | Missing a bug in review is expensive |
| security-reviewer | Opus | Adversarial + high-stakes; false negatives catastrophic |
| qa-engineer | Sonnet | Test writing is mechanical translation |
| tech-writer | Sonnet | Translation task |
| platform-sre | Sonnet | Mostly execution; escalate for incidents |
| ux-designer | Sonnet | Structured design |
| system-steward | Opus | Library evolution decisions across projects |

Result: 7 Opus / 9 Sonnet. Opus concentrated where irreversibility and adversarial depth matter.

---

## Agent spawn configuration

When the Delivery Lead spawns a sub-agent (via the Agent tool), pass the `model` field:

```
Agent({
  subagent_type: "solution-architect",
  model: "claude-opus-4-8",        # or "claude-sonnet-4-6" or "claude-haiku-4-5-20251001"
  prompt: "..."
})
```

The routing decision is made BEFORE the spawn. Log it:

```yaml
# .project/working/model-routing-log.yaml (append each entry)
- timestamp: 2026-07-02T10:00:00
  agent: solution-architect
  task: "architecture-pattern-selection for payment service"
  score: 8
  signals:
    novelty: 2        # First payment system in this project
    interdependency: 2 # Touches auth, fraud, ledger, notifications
    stakes: 2         # Financial data; compliance required
    ambiguity: 1      # Scope mostly clear; some NFR gaps
    prior_failure: 0  # First attempt
  model: claude-opus-4-8
  rationale: "Score 7+; payment + compliance + cross-cutting = Opus"
```

Log entries serve the quarterly `llm-cost-optimization` review — frequency reports can show which agent types actually need Opus vs which are habitually over-provisioned.

---

## Session-level model selection

When opening a new Cowork / Claude Code session (not just spawning sub-agents), advise:

**Start on Sonnet.** If the session's first task scores 7+ on the rubric, re-open on Opus. Don't pre-emptively open Opus for sessions that haven't been scored.

Signs that a session needs Opus from the start:
- The session title suggests architecture, threat modeling, or cross-cutting ADR
- The user's brief contains > 2 "first-of-kind" markers
- The session is a P0 incident post-mortem

Signs that a Sonnet session is sufficient:
- "Implement slice N" — implementation per established design
- "Review this code" — code review against known standards
- "Write the docs for X" — documentation
- "Set up CI/CD" — following `cicd-pipeline` SKILL
- "Fix this bug" — isolated, reproducible, scope clear

---

## Escalation protocol

When a Sonnet attempt is rejected or fails quality checks:

1. **Score the failure.** Add 2 to `prior_failure` signal. Re-score.
2. **Escalate to Opus.** Always — never retry Sonnet on the same task after a failure.
3. **Give Opus the failure context.** Include the Sonnet output, the failure reason, and what was missing. Don't let Opus start cold.
4. **Log the escalation** to `.project/episodic/model-escalations.md` with the task, failure reason, and outcome.

```markdown
# Model Escalation Log

## 2026-07-02 — requirements-elicitation for payments feature
- First attempt: Sonnet
- Failure: Missed 4 compliance NFRs; scope too broad; output not actionable
- Escalation: Opus with failure context and compliance mandate
- Outcome: Opus produced complete NFR register; passed requirements_freeze gate
- Learning: requirements-elicitation with compliance scope → always Opus
```

Escalation logs feed the fast-path rules above. Three escalations on the same task type → promote it to "Always Opus" in this project's local fast-path override.

---

## Quota management heuristics

When Opus quota is low (user signals "running out"):

1. Audit what's been using Opus. Check `.project/working/model-routing-log.yaml`.
2. Identify tasks that could have been Sonnet (score ≤ 6 that were routed to Opus by habit).
3. Tighten the default: treat score 7 as "Sonnet with elevated review" rather than automatic Opus, reserving Opus for 8+.
4. **Never downgrade these regardless of quota:** threat-modeling, architecture sign-off for systems > 2 flags, P0 post-mortems, escalations after Sonnet failure.
5. Defer non-urgent Opus tasks to the next quota window when possible.

The goal is never quality regression — Opus quota management is about eliminating Opus on tasks that don't need it, not downgrading tasks that genuinely do.

---

## Anti-rationalization

The reason this discipline holds is that both directions are seductive — Opus feels safer, Sonnet feels cheaper. Real failure modes below.

| Shortcut you'll be tempted to take | Why it's tempting | What actually happens | Hold the line |
|---|---|---|---|
| "Use Opus by default; it's better" | Zero cognitive overhead | Opus quota exhausts mid-week; forced to use Sonnet for the Friday architecture call that actually needed Opus | The 5-second scoring cost pays back 10x by preserving Opus for when it matters |
| "Use Sonnet for everything to save quota" | Feels frugal | Sonnet writes a subtle bug in the migration script; multi-day cleanup dwarfs the token savings | If a mistake costs > 1 day, that's not a Sonnet task regardless of visible complexity |
| "Opus is stuck, retry with more context" | Sunk cost fallacy | Opus loops on the same wrong hypothesis; wastes 2x tokens | If Sonnet is stuck, clarify the problem first. Ambiguity ≠ complexity |
| "This is architectural, must be Opus" | Nominal category match | The "architectural" task is renaming a class; judgment already happened | Look at what the task actually requires, not what it's labeled |
| "Sonnet is fine, it's just implementation" | It IS implementation | The implementation touches auth, cross-tenant boundaries, or migration | "Implementation" that touches load-bearing modules is Opus-worthy regardless of task label |
| "Leave session on Opus, cheaper than switching" | Switching feels like friction | Every message on Opus that could be on Sonnet burns budget for the next real Opus task | Switch at phase boundaries; ~3-5 switches per day |
| "Re-try Sonnet on a failed task" | Might work this time | Same model + same task rarely fixes the failure | Escalate to Opus with failure context, per escalation protocol |
| "Skip the routing log — I'll remember" | Log feels bureaucratic | Steward can't tell what actually needed Opus; can't tighten routing rules | The log is 10 seconds; the quarterly cost audit needs it |
| "Downgrade threat-modeling to save quota" | Quota pressure | Security corners cut for budget; incident 6 months later | Threat-modeling is never downgraded — quota is not an excuse |
| "Escalate preemptively before any Sonnet attempt" | Feels safer | Opus produces marginal answer to ambiguous problem; you burn budget on a bad question | Try Sonnet first with explicit failure criteria; escalate only on evidence |
| "Delivery Lead's decisions are always Opus" | Orchestration feels important | Most orchestration is mechanical routing; Opus for every message is waste | Score the specific routing decision — most are 3-5 (Sonnet) |
| "The user asked for Opus" | User authority | User may not know task doesn't need it; help them decide | Suggest Sonnet with rationale if task warrants it; user can override |

---

## Red flags during routing

- **Opus running > 2 hours on a single problem.** Either escalate the problem (break it up, get help) or de-escalate the model — this is the "stuck in a loop" signal.
- **Sonnet asked to make a decision without context.** Escalation is wrong response; clarify the decision criteria first.
- **Opus used for a mechanical task > 3 times in a week.** Update routing table — habit forming.
- **Sonnet used for a review that later missed a bug.** Update escalation trigger table — this class of PR is Opus-worthy.
- **Never switching models within a session.** Almost every 4-hour session has both Opus- and Sonnet-worthy moments; if you're on one model the whole time, you're either underspending or overspending.

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

Steps where model is always fixed (no evaluation needed):
- `agent: architecture-challenger` → always `claude-opus-4-8`
- `agent: code-reviewer` (standard slice review) → always `claude-sonnet-4-6`
- `agent: platform-sre` (CI/CD, IaC wiring) → always `claude-sonnet-4-6`

---

## Outputs

| Output | Location |
|---|---|
| Per-spawn routing decision | `.project/working/model-routing-log.yaml` |
| Escalation log | `.project/episodic/model-escalations.md` |
| Fast-path overrides (project-local) | `.project/procedural/model-routing-overrides.md` |

---

## Verification

Before ending an intake decision as final:

- [ ] The task has been scored on all five signals (or a fast-path rule matched).
- [ ] The rationale is stated in 1-2 sentences (not "vibes").
- [ ] The model string is selected and recorded.
- [ ] The agent spawn includes the `model:` field.
- [ ] The routing log entry is appended.
- [ ] If this is an escalation: the failure context is passed to Opus; the escalation log is updated.
- [ ] For phase transitions: any per-project override to `.project/procedural/model-routing-overrides.md` is reviewed.

---

## Mode handling (G/B)

**Greenfield.** Architecture phases score high on novelty → Opus expected for Phases A and B. Implementation slices score low → Sonnet default throughout. The ratio after a full project run is roughly: 15–20% Opus, 75–80% Sonnet, 5% Haiku.

**Brownfield.** Brownfield `codebase-comprehension` is a heavy read task — Sonnet handles it. Impact analysis may score 7+ if the system is large and the change is cross-cutting → Opus. Architecture reconciliation against existing system: Sonnet unless NFR violations are found, then Opus for remediation ADRs.

---

## What this SKILL does not do

- Execute the task — it only selects the model.
- Override Anthropic's model availability — if Opus quota is exhausted, the session blocks; this SKILL flags the situation but cannot provision more quota.
- Switch the model programmatically — Claude Code doesn't let a SKILL invoke `/model`. The output is a recommendation for the user to act on (or a spawn-time `model:` field for the Delivery Lead to pass).
- Track cost in dollars — that's `llm-cost-optimization`.
