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
│   │   └── 000-ai-delivery-platform.md    ← always-active rule pointing to library
│   └── praxis/              ← library content
│       ├── agents/, skills/, workflows/, governance/, references/, patterns/
│       └── README.md, PLAYBOOK.md
└── .project/                              ← project memory tree
```

## How Cursor finds the library

The rule at `.cursor/rules/000-ai-delivery-platform.md` is auto-loaded by Cursor on every interaction. It points at the library content at `.cursor/praxis/`.

## Sanity check

In Cursor's chat:
```
"Confirm you can see the Praxis per .cursor/rules/000-ai-delivery-platform.md.
Read the front-door SKILL at .cursor/praxis/skills/using-praxis/SKILL.md
and summarize the intent routing tree."
```

## Tips

- Reference any SKILL directly: `@.cursor/praxis/skills/threat-modeling/SKILL.md`
- The rule is short to keep context costs low; the SKILL files load on demand.

## Verify your install

```bash
ls .cursor/rules/000-ai-delivery-platform.md
find .cursor/praxis/skills -name SKILL.md | wc -l    # expect 88
ls .cursor/praxis/agents | wc -l                      # expect 17
```

Then run the sanity-check prompt above. You should see Cursor confirm the rule loaded and summarize the intent-routing tree from `using-praxis/SKILL.md`. If the counts are off, re-run `./install.sh --tool=cursor --dry-run` and compare.
