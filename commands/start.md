---
description: "Bootstrap a new project: run delivery-planner, set the charter, establish the architecture-doc skeleton."
---

Bootstrap a new project at this repo.

Step 1 — Run `delivery-planner`. Capture the project charter at `.project/semantic/project-charter.md` covering:
- mode (G = greenfield / B = brownfield)
- has_data_plane (true if non-trivial data workloads)
- has_ml (true if ML model training/serving)
- has_agentic_ai (true if LLM/agent features)
- compliance_regimes (list or "none")
- scale_target_qps + availability_target
- is_multi_tenant
- preferred stack(s) + cloud

Step 2 — Establish the architecture-documentation skeleton per `architecture-documentation`:
- `.project/working/architecture/overview.md` (with TODO placeholders)
- `.project/decision/INDEX.md`

Step 3 — Read `governance/governance.yaml` and tell me which gates apply per the charter flags. Distinguish always-on vs conditional.

Step 4 — Confirm the Praxis is loaded: 17 agents, 88 SKILLs, 6 workflows.

Then route automatically per `using-praxis` intent routing: proceed into `/discover` for greenfield or `/audit` for brownfield, announcing the transition — pause only if the mode is ambiguous or I object.
