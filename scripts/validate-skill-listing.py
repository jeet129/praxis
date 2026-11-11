#!/usr/bin/env python3
"""validate-skill-listing.py — keep skill descriptions inside each harness's
skill-listing budget.

Every harness shows the model a one-line-per-skill menu (name + description)
and trims it when it overflows:

  * Claude Code: budget = context window (tokens) x 4 chars x 1%  -> 8,000
    chars on a 200k model, 40,000 on a 1M model; least-used descriptions are
    dropped first (code.claude.com/docs/en/skills, "Skill descriptions are cut
    short").
  * Codex: budget = 2% of the context window in tokens (bytes/4), i.e. 5,440
    tokens on a 272k model; each description is cut at 1,024 chars, then
    descriptions are shortened and skills omitted (openai/codex
    codex-rs/ext/skills/src/render.rs).
  * Antigravity: description must be 1-1,024 chars (antigravity.google/docs/
    build-plugins).

Praxis therefore keeps two tiers, declared as `listing_tier:` in each skill's
praxis:metadata block:

  A  front-door skills a user or orchestrator asks for by intent: <= 160 chars,
     and the description says when to use it.
  B  reference skills an agent already knows to open by name: <= 60 chars.

Exit 1 on any violation. Usage: validate-skill-listing.py [library_root]
"""
import pathlib
import re
import sys

TIER_LIMIT = {"A": 160, "B": 60}
HARD_LIMIT = 1024               # Agent Skills spec / Codex / Antigravity
COMMAND_LIMIT = 160             # command-adapter skills in the overlays
CLAUDE_LISTING_MAX_CHARS = 12_000
# Codex's default budget on a 272k-token model is 5,440 tokens, and about half
# of the catalog is skill PATHS, which Praxis cannot shorten. The catalog lands
# just above that default, so $praxis-setup-subagents writes
# `[skills] max_context_tokens = 8000` into the project's Codex config. Without
# it Codex trims the longest descriptions slightly; nothing is dropped.
CODEX_CATALOG_MAX_TOKENS = 6_000
CODEX_PATH_ESTIMATE = 96           # typical installed SKILL.md path length

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent)
errors = []


def parse(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        errors.append(f"{path}: no frontmatter")
        return None
    fm, body = m.group(1), m.group(2)
    name = (re.search(r"^name:\s*(.+)$", fm, re.M) or [None, path.parent.name])[1].strip()
    dm = re.search(r"^description:\s*(.*?)\s*$", fm, re.M | re.S)
    desc = dm.group(1).strip() if dm else ""
    if desc.startswith(('"', "'")) and desc.endswith(desc[0]):
        desc = desc[1:-1]
    elif ": " in desc:
        errors.append(f"{path.parent.name}: description contains an unquoted ': ' "
                      "(invalid for strict YAML parsers) — wrap it in double quotes")
    tm = re.search(r"^listing_tier:\s*(\S+)", body, re.M)
    return name, desc, (tm.group(1) if tm else None)


claude_chars = 0
canon = {}
for p in sorted((root / "skills").glob("*/SKILL.md")):
    r = parse(p)
    if not r:
        continue
    name, desc, tier = r
    canon[name] = desc
    claude_chars += len(name) + len(desc) + 4
    if tier not in TIER_LIMIT:
        # Generated packages mix in harness command skills (praxis-*, overlay
        # copies) that carry no tier; they follow the command limit instead.
        if (root / "codex-plugin-assets").is_dir():
            errors.append(f"{name}: metadata block needs `listing_tier: A` or `listing_tier: B`")
        elif len(desc) > 160:
            errors.append(f"{name}: command skill description is {len(desc)} chars (limit 160)")
        continue
    if len(desc) > TIER_LIMIT[tier]:
        errors.append(f"{name}: tier {tier} description is {len(desc)} chars (limit {TIER_LIMIT[tier]})")
    if tier == "A" and not re.search(r"\buse\b", desc, re.I):
        errors.append(f"{name}: tier A description must say when to use the skill")

overlays = {}
for overlay in ("codex-plugin-assets", "antigravity-plugin-assets"):
    d = root / overlay / "skills"
    overlays[overlay] = {}
    if not d.is_dir():
        continue
    for p in sorted(d.glob("*/SKILL.md")):
        r = parse(p)
        if not r:
            continue
        name, desc, _ = r
        overlays[overlay][name] = desc
        if len(desc) > COMMAND_LIMIT:
            errors.append(f"{overlay}/{name}: description is {len(desc)} chars (limit {COMMAND_LIMIT})")

for name, desc in canon.items():
    if len(desc) > HARD_LIMIT:
        errors.append(f"{name}: description exceeds the {HARD_LIMIT}-char hard limit")

codex = dict(canon)
codex.update(overlays["codex-plugin-assets"])
codex_tokens = sum(len(n) + len(d) + CODEX_PATH_ESTIMATE + 8 for n, d in codex.items()) // 4

if claude_chars > CLAUDE_LISTING_MAX_CHARS:
    errors.append(f"Claude Code listing is {claude_chars} chars (limit {CLAUDE_LISTING_MAX_CHARS})")
if codex_tokens > CODEX_CATALOG_MAX_TOKENS:
    errors.append(f"Codex catalog is ~{codex_tokens} tokens (limit {CODEX_CATALOG_MAX_TOKENS})")

print(f"Skill listing: {len(canon)} skills, Claude Code listing {claude_chars} chars "
      f"(limit {CLAUDE_LISTING_MAX_CHARS}; 8,000 fits a 200k model, 40,000 a 1M model), "
      f"Codex catalog ~{codex_tokens} tokens for {len(codex)} skills (limit {CODEX_CATALOG_MAX_TOKENS}).")
if errors:
    print("Skill-listing failures:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
print("✓ Skill listing within budget.")
