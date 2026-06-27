# Cursor Setup

## Install

```bash
./install.sh --tool=cursor /path/to/your-project
```

## What lands

```
your-project/
├── .cursor/
│   ├── rules/
│   │   └── 000-praxis.md    ← always-active rule pointing to library
│   └── praxis/              ← library content
│       ├── agents/, skills/, workflows/, governance/, references/, patterns/
│       └── README.md, PLAYBOOK.md
└── .project/                              ← project memory tree
```

## How Cursor finds the library

The rule at `.cursor/rules/000-praxis.md` is auto-loaded by Cursor on every interaction. It points at the library content at `.cursor/praxis/`.

## Sanity check

In Cursor's chat:
```
"Confirm you can see the Praxis per .cursor/rules/000-praxis.md.
Read the front-door SKILL at .cursor/praxis/skills/using-praxis/SKILL.md
and summarize the intent routing tree."
```

## Tips

- Reference any SKILL directly: `@.cursor/praxis/skills/threat-modeling/SKILL.md`
- The rule is short to keep context costs low; the SKILL files load on demand.
