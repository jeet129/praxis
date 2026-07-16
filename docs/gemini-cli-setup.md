# Gemini CLI Setup

Status: adapter shipped, structurally validated, not yet exercised
end-to-end on a real engagement — expect rough edges; issues welcome.

## Install

```bash
./install.sh --tool=gemini /path/to/your-project
```

## What lands

```
your-project/
├── .gemini/
│   ├── skills/             90 SKILLs
│   ├── commands/           11 slash commands
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

Same 11 as Claude Code, mirrored at `.gemini/commands/`:
`/start /discover /architect /audit /slice /release /review /steward /refine-idea /factory-record /drive`

## Verify your install

Type:
```
"Read GEMINI.md and confirm you can navigate to .gemini/skills/ and .gemini/agents/.
List the 17 agents and the 90 SKILLs."
```

You should see: 17 agents, 90 SKILLs listed by name. If the count is off, re-run `./install.sh --tool=gemini --dry-run` and compare.
