# Gemini Routing for Praxis

This repository ships the Praxis. Gemini CLI should consult these files when assisting:

## Where things live
- Role agents: `agents/`
- Skills: `skills/<skill-name>/SKILL.md` (91 SKILLs)
- Workflows: `workflows/`
- Governance: `governance/governance.yaml`
- Slash commands: `.gemini/commands/`
- References: `references/`

## How to discover the right skill
Read `skills/using-praxis/SKILL.md` — the front-door SKILL with intent → workflow → agent → skill routing.

## Project memory
All artifacts under `.project/` (semantic / episodic / procedural / decision / operational / working).

## Activation flags
Read `.project/semantic/project-charter.md` for the planner's flags. If absent, the project hasn't been bootstrapped.

## Governance
All gates per `governance/governance.yaml`. Solo mode routes every gate to the principal.

## Documentation
- Overview: `README.md`
- Operating playbook: `PLAYBOOK.md`
- Per-tool setup: `docs/`
