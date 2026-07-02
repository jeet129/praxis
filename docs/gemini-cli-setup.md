# Gemini CLI Setup

## Install

```bash
./install.sh --tool=gemini /path/to/your-project
```

## What lands

```
your-project/
├── .gemini/
│   ├── skills/             84 SKILLs
│   ├── commands/           8 slash commands
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

Same 7 as Claude Code, mirrored at `.gemini/commands/`:
`/start /discover /architect /slice /release /audit /steward`

## Sanity check

```
"Read GEMINI.md and confirm you can navigate to .gemini/skills/ and .gemini/agents/.
List the 16 agents and the 84 SKILLs."
```
