---
name: intake
description: Single entry point for any new requirement in steady state (story, epic, ticket, change request). Delegates to delivery-lead, which runs requirements-intake to triage, right-size, and route — so you never pick a workflow by hand.
---

The ONE command to run when a new requirement arrives after the initial discovery + architecture rounds are done — a story, epic, ticket, stakeholder ask, bug-disguised-as-feature, or change request. You do NOT decide which workflow it needs; the `requirements-intake` discipline does the right-sizing for you. Just drop the ask.

## What you do

Capture the incoming ask (or point me at an untriaged `.project/working/inbox.md`), then delegate the whole decision to `delivery-lead`:

Delegate to the **delivery-lead** agent — read `agents/delivery-lead.md`, adopt that role, and execute this brief:

> A new requirement has arrived in steady state. Run the requirements-intake discipline (skills/requirements-intake) — do NOT jump straight to coding.
>
> 1. Append the ask to .project/working/inbox.md (append-only queue).
> 2. Triage it: size (one slice | several slices | needs architecture), blast radius (which modules impact-analysis must cover), owner. Record in .project/working/inbox-decisions.md.
> 3. Right-size and route — pick the LIGHTEST path that is safe:
>      - Small, well-understood, low blast radius, clear AC -> have lead-developer produce a slice ledger and hand to slice-drive (/drive). Do NOT force full ceremony.
>      - Touches load-bearing / existing behavior -> run impact-analysis FIRST, then slice.
>      - Large or cross-cutting (new subsystem, schema change, new NFR) -> group with related items into a mini intake brief and route to /discover (requirements) then /architect (design increment, gated at architecture_sign_off) then project-phasing (roadmap slices).
>      - Feasibility genuinely unknown -> spike.
>      - P0/P1 production break -> expedited-change.
> 4. Tell me the routing decision and WHY in one or two lines, then proceed — stopping only at the one human gate the chosen route actually requires (architecture_sign_off, spike_disposition, production_go_live, etc.).
>
> Honor the two failure modes requirements-intake exists to prevent: FIFO churn (do NOT give every small ask full discovery+architect ceremony) and impulse coding (do NOT let a small ask skip impact-analysis and detonate a load-bearing module).

## What you do NOT do

- Do NOT ask me to choose the workflow — that is the entire point of this command; intake decides.
- Do NOT let a one-line ask trigger full discovery + architecture ceremony (FIFO churn).
- Do NOT let an ask that touches existing behavior skip `impact-analysis` because it "looks obvious" (impulse coding).
- Do NOT start coding before the ask is captured in the inbox and triaged.

## Where it routes (you run ONE command; intake picks)

| The ask is… | Intake routes it to |
|---|---|
| a small, ready story (clear AC, low blast radius) | slice ledger → `/drive` |
| a change to existing behavior | `impact-analysis` → slice → `/drive` |
| an epic / cross-cutting change | group → `/discover` → `/architect` → `project-phasing` → slices |
| an unproven approach | `spike` |
| a P0/P1 production break | `expedited-change` |

This is the steady-state front door — it fires for every new requirement once initial discovery is complete. (For the very first requirements of a brand-new project, use `/discover`.)
