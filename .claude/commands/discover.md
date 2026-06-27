---
description: Phase A — Discovery + requirements + NFRs. Product Manager runs; ends at requirements_freeze gate.
---

Start Phase A. Activate the Product Manager agent. Run the discovery + requirements skill sequence per the AOP:

1. `product-discovery` — JTBD framing, persona surfacing, value hypothesis.
2. `requirements-elicitation` — user stories with acceptance criteria, scope boundary.
3. `requirements-interrogation` — produce the KUACQ block (Knowns / Unknowns / Assumptions / Conflicts / Questions). STOP here and bring questions to me.

After my answers:

4. `nfr-definition` — measurable quality-attribute register tied to the user stories.

Output artifacts to `.project/semantic/`:
- product-discovery.md
- user-stories.md
- scope-boundary.md
- nfr-register.md
- assumptions-register.md
- open-questions.md

Then prep the `requirements_freeze` gate evidence pack. Show me the pack; I approve or send back.

Per the front-door SKILL: do NOT spawn other agents within this phase. PM owns Phase A. Specialists come in Phase B+.

Common rationalizations to ignore:
- "The user said what they want; I don't need discovery." → vague-request-into-spec is the #1 failure mode. Always run discovery.
- "We'll define NFRs later." → no, NFRs drive architecture. Now.
