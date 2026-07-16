# Antigravity CLI Setup

Status: adapter shipped, structurally validated, not yet exercised
end-to-end on a real engagement — expect rough edges; issues welcome.

## Install

```bash
./install.sh --tool=antigravity /path/to/your-project
```

## What lands

```
your-project/
├── plugin.json             ← Antigravity manifest at repo root
├── agents/, skills/, workflows/, governance/, references/, patterns/, commands/
├── README.md, PLAYBOOK.md
└── .project/               ← project memory tree
```

Antigravity expects the library to live at repo root (with `plugin.json` as the manifest) — install.sh handles this layout.

## Plugin install (native)

When published to a repo:

```bash
agy plugin install https://github.com/your-org/praxis.git
```

From a local clone:

```bash
agy plugin install ./praxis
```

## Slash commands

Same 11 as Claude Code, copied to `commands/` at repo root:
`/start /discover /architect /audit /slice /release /review /steward /refine-idea /factory-record /drive`

## Verify your install

Type:
```
"Confirm plugin.json is loaded and the Praxis is available.
Read skills/using-praxis/SKILL.md and summarize the routing tree."
```

You should see: a routing summary mapping intents to workflows, agents, and skills. List `commands/` — you should see 11 `.md` files. If `plugin.json` isn't picked up, confirm it's at repo root next to `agents/`, `skills/`, `commands/`.
