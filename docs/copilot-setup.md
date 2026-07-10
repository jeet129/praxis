# GitHub Copilot Setup

## Install

```bash
./install.sh --tool=copilot /path/to/your-project
```

## What lands

```
your-project/
├── .github/
│   ├── copilot-instructions.md         ← system-level guidance for Copilot
│   ├── agents/                         ← agent personas usable as Copilot personas
│   └── praxis/           ← library content
│       ├── skills/, workflows/, governance/, references/, patterns/
│       └── README.md, PLAYBOOK.md
└── .project/                           ← project memory tree
```

## How Copilot finds the library

Copilot automatically reads `.github/copilot-instructions.md` for any repository it's used in. The installer writes a comprehensive instruction file that points at the library and the front-door SKILL.

## Sanity check

Open any file in the repo with Copilot Chat:

```
"Per .github/copilot-instructions.md, confirm the Praxis is loaded.
Read .github/praxis/skills/using-praxis/SKILL.md
and tell me which workflow applies to a new feature."
```

## Personas

The agent personas in `.github/agents/` can be referenced explicitly:

```
"Acting as the security-reviewer persona from .github/agents/security-reviewer.md,
audit this PR."
```

## Limitations

- Copilot doesn't have native slash commands like Claude Code; the routing happens through `copilot-instructions.md` + persona references.
- Workflows are referenced but the agent must walk them step-by-step.

## Verify your install

```bash
ls .github/copilot-instructions.md
find .github/praxis/skills -name SKILL.md | wc -l    # expect 88
ls .github/agents | wc -l                             # expect 17
```

Then run the sanity-check prompt above. You should see Copilot confirm it read `copilot-instructions.md`, list the front-door SKILL's routing, and name a workflow. If the counts are off, re-run `./install.sh --tool=copilot --dry-run` and compare.
