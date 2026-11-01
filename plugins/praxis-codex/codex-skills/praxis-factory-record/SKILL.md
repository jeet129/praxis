---
name: praxis-factory-record
description: Use when the user wants to record a rich factory-metrics observation for steward review — "record what we learned", "capture an observation", "factory record", "log this for the steward". Codex analogue of Claude Code's /factory-record.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [factory-evaluation]
triggers: [praxis factory record, record observation, capture what we learned, log for steward]
outputs: [factory_metrics_observation]
consumers: [praxis-steward]
references: [../../references/factory-metrics-schema.md]
```
<!-- praxis:metadata:end -->

# Praxis Factory Record

Record a rich factory-metrics observation — a human judgment about how a skill, agent, workflow, or command performed — for the System Steward's quarterly review.

## Steps

1. Ask the user (once, concisely) for anything not already clear from context: which artifact (skill/agent/workflow/command slug), what happened, and the verdict flavor (worked well | over-engineered | misfired | gap).
2. Run the recorder script from the installed plugin root:
   ```bash
   bash <plugin-root>/scripts/factory-record.sh
   ```
   (locate the plugin root by walking up from this skill until `scripts/` is present). If the script prompts interactively, relay its prompts; if invoked with arguments, pass the observation through.
3. Confirm the observation landed under `.project/operational/factory-metrics/` with the structured frontmatter per `../../references/factory-metrics-schema.md` — an observation without the frontmatter is incomplete.

## What you must not do

- Do NOT paraphrase the user's judgment into blandness — record their actual verdict, including negative ones; the steward needs honest signal.
- Do NOT skip the structured frontmatter (slug, verdict, date) — free prose alone is unusable by `factory-usage-report.py`.

## Reference

Schema: `../../references/factory-metrics-schema.md`. Consumed at `$praxis-steward` (quarterly review).
