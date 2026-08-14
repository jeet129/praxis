# Adaptive Model Routing (Codex) — worked examples and tables

Extracted from the Codex variant SKILL.md; load on demand.

## 2026-07-02 — requirements-elicitation for payments feature
- First attempt: medium reasoning
- Failure: Missed 4 compliance NFRs; scope too broad; output not actionable
- Escalation: high reasoning with failure context and compliance mandate
- Outcome: high-reasoning session produced complete NFR register; passed requirements_freeze gate
- Learning: requirements-elicitation with compliance scope → always high
```

Escalation logs feed the fast-path rules above. Three escalations on the same task type → promote it to "Always high" in this project's local fast-path override.

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

