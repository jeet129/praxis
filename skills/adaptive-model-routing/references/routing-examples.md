# Routing examples

Worked examples supporting `adaptive-model-routing`. Load this file when you need the full artifact behind a SKILL.md pointer.

## Worked routing-log entry

```yaml
# .project/telemetry/model-routing.jsonl — one JSON object per line;
# fields shown here in YAML for readability
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
  tier: deep
  resolved_model: <per governance/model-routing.yaml>
  rationale: "Score 7+; payment + compliance + cross-cutting = deep tier"
```

## Worked escalation-log entry

```markdown
# Model Escalation Log

## 2026-07-02 — requirements-elicitation for payments feature
- First attempt: standard tier
- Failure: Missed 4 compliance NFRs; scope too broad; output not actionable
- Escalation: deep tier with failure context and compliance mandate
- Outcome: deep-tier run produced complete NFR register; passed requirements_freeze gate
- Learning: requirements-elicitation with compliance scope → always deep tier
```

## Anti-rationalization — full table

The reason this discipline holds is that both directions are seductive — the deep tier feels safer, the standard tier feels cheaper. Real failure modes below.

| Shortcut you'll be tempted to take | Why it's tempting | What actually happens | Hold the line |
|---|---|---|---|
| "Use the deep tier by default; it's better" | Zero cognitive overhead | Deep-tier budget exhausts mid-week; forced onto the standard tier for the Friday architecture call that actually needed deep | The 5-second scoring cost pays back 10x by preserving the deep tier for when it matters |
| "Use the standard tier for everything to save budget" | Feels frugal | The standard tier writes a subtle bug in the migration script; multi-day cleanup dwarfs the token savings | If a mistake costs > 1 day, that's not a standard-tier task regardless of visible complexity |
| "Deep tier is stuck, retry with more context" | Sunk cost fallacy | The deep-tier run loops on the same wrong hypothesis; wastes 2x tokens | If the standard tier is stuck, clarify the problem first. Ambiguity ≠ complexity |
| "This is architectural, must be deep tier" | Nominal category match | The "architectural" task is renaming a class; judgment already happened | Look at what the task actually requires, not what it's labeled |
| "Standard tier is fine, it's just implementation" | It IS implementation | The implementation touches auth, cross-tenant boundaries, or migration | "Implementation" that touches load-bearing modules is deep-tier-worthy regardless of task label |
| "Leave the session on the deep tier, cheaper than switching" | Switching feels like friction | Every message on the deep tier that could be on standard burns budget for the next real deep-tier task | Switch at phase boundaries; ~3-5 switches per day |
| "Re-try the standard tier on a failed task" | Might work this time | Same tier + same task rarely fixes the failure | Escalate to the deep tier with failure context, per escalation protocol |
| "Skip the routing log — I'll remember" | Log feels bureaucratic | Steward can't tell what actually needed the deep tier; can't tighten routing rules | The log is 10 seconds; the quarterly cost audit needs it |
| "Downgrade threat-modeling to save budget" | Budget pressure | Security corners cut for budget; incident 6 months later | Threat-modeling is never downgraded — budget is not an excuse |
| "Escalate preemptively before any standard-tier attempt" | Feels safer | The deep tier produces a marginal answer to an ambiguous problem; you burn budget on a bad question | Try the standard tier first with explicit failure criteria; escalate only on evidence |
| "Delivery Lead's decisions are always deep tier" | Orchestration feels important | Most orchestration is mechanical routing; deep tier for every message is waste | Score the specific routing decision — most are 3-5 (standard) |
| "The user asked for the deep tier" | User authority | User may not know the task doesn't need it; help them decide | Suggest the standard tier with rationale if the task warrants it; user can override |
