---
name: praxis-intake
description: Use when a new requirement arrives in steady state (story, epic, ticket, stakeholder ask, or change request) after the initial discover/architect rounds are done. The single front door — triage, right-size, and route it via requirements-intake so the user never picks a workflow by hand. Triggers on "new story", "new requirement", "intake this", "we got a ticket", "add this feature".
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [requirements-intake, impact-analysis, adaptive-model-routing]
triggers: [praxis intake, new requirement, new story, new epic, intake this, we have a ticket, new change request]
outputs: [inbox_entry, triage_decision, routed_work]
consumers: [praxis-slice, praxis-discover, praxis-architect, praxis-drive]
references: [../../skills/requirements-intake, ../../skills/impact-analysis]
```
<!-- praxis:metadata:end -->

# Praxis Intake

The ONE command to run when a new requirement arrives after the initial discovery + architecture rounds are complete — a story, epic, ticket, stakeholder ask, bug-disguised-as-feature, or change request. Do NOT decide the workflow yourself and do NOT jump straight to coding; run the `requirements-intake` discipline (`../../skills/requirements-intake`) and let it right-size the ask.

## Steps

1. **Capture.** Append the incoming ask to `.project/working/inbox.md` (append-only queue).
2. **Triage.** Decide size (one slice | several slices | needs architecture), blast radius (which modules `impact-analysis` must cover), and owner. Record in `.project/working/inbox-decisions.md`.
3. **Right-size and route — pick the LIGHTEST safe path:**
   - Small, well-understood, low blast radius, clear AC → have `delivery-lead` → `lead-developer` produce a slice ledger and hand to drive (`$praxis-drive`). No full ceremony.
   - Touches load-bearing / existing behavior → run `impact-analysis` FIRST, then slice.
   - Large or cross-cutting (new subsystem, schema change, new NFR) → group with related items into a mini intake brief → `$praxis-discover` → `$praxis-architect` (gated) → `project-phasing` → slices.
   - Feasibility genuinely unknown → spike.
   - P0/P1 production break → expedited-change.
4. **Report and proceed.** State the routing decision + WHY in one or two lines, then proceed — stopping only at the one human gate the chosen route requires (architecture_sign_off, spike_disposition, production_go_live, etc.).

## What you must not do

- Do NOT ask the user to choose the workflow — intake decides; that is the point.
- Do NOT give a one-line ask full discovery + architecture ceremony (FIFO churn).
- Do NOT let an ask touching existing behavior skip `impact-analysis` because it "looks obvious" (impulse coding).
- Do NOT start coding before the ask is captured and triaged.

## Reference

Intake discipline and the two failure modes it prevents: `../../skills/requirements-intake`. Blast-radius analysis: `../../skills/impact-analysis`. For the very first requirements of a brand-new project, use `$praxis-discover` instead — intake is for steady state.
