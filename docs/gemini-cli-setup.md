# Gemini CLI Setup

## Install

```bash
./install.sh --tool=gemini /path/to/your-project
```

## What lands

```
your-project/
├── .gemini/
│   ├── skills/             88 SKILLs
│   ├── commands/           10 slash commands
│   ├── agents/, workflows/, governance/, references/, patterns/
│   └── README.md, PLAYBOOK.md
├── GEMINI.md               ← routing file at repo root
└── .project/               ← project memory tree
```

## How Gemini finds the library

Gemini CLI reads `GEMINI.md` at the repo root. The installer writes a routing table.

Native plugin install (when published):

```bash
gemini skills install https://github.com/your-org/praxis.git --path skills
```

## Slash commands

Same 10 as Claude Code, mirrored at `.gemini/commands/`:
`/start /discover /architect /audit /slice /release /review /steward /refine-idea /factory-record`

## Verify your install

Type:
```
"Read GEMINI.md and confirm you can navigate to .gemini/skills/ and .gemini/agents/.
List the 17 agents and the 88 SKILLs."
```

You should see: 17 agents, 88 SKILLs listed by name. If the count is off, re-run `./install.sh --tool=gemini --dry-run` and compare.
