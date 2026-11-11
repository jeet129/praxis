#!/usr/bin/env python3
"""validate-evals.py — structural check of the evals/ suite (no model calls).

Each case needs prompt.md with frontmatter and a non-empty body, and at least
one grader with a known type. A `tool_used: Skill` grader with input_match must
name a skill that exists. Tier A skills without a trigger case are reported as
warnings.
"""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
evals, skills = root / "evals", root / "skills"
TYPES = {"tool_used", "file_exists", "llm", "baseline"}
errors, warnings, covered, cases = [], [], set(), 0


def front(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, m.group(2)


if not evals.is_dir():
    print("evals/ missing"); sys.exit(1)
for case in sorted(p for p in evals.iterdir() if p.is_dir() and p.name != "results"):
    cases += 1
    prompt = case / "prompt.md"
    if not prompt.is_file():
        errors.append(f"{case.name}: prompt.md missing"); continue
    fm, body = front(prompt)
    if fm is None or not body.strip():
        errors.append(f"{case.name}: prompt.md needs frontmatter and a body")
    graders = sorted((case / "graders").glob("*.md")) if (case / "graders").is_dir() else []
    if not graders:
        errors.append(f"{case.name}: no graders")
    for g in graders:
        gfm, gbody = front(g)
        if gfm is None:
            errors.append(f"{case.name}/{g.name}: no frontmatter"); continue
        if gfm.get("type") not in TYPES:
            errors.append(f"{case.name}/{g.name}: unknown grader type {gfm.get('type')!r}")
        if gfm.get("type") == "llm" and not gbody.strip():
            errors.append(f"{case.name}/{g.name}: llm grader has no criteria")
        if gfm.get("type") == "tool_used" and gfm.get("input_match"):
            skill = gfm["input_match"]
            if not (skills / skill / "SKILL.md").is_file():
                errors.append(f"{case.name}/{g.name}: skill {skill!r} does not exist")
            covered.add(skill)
            if "Skill" not in (fm or {}).get("allowed_tools", ""):
                errors.append(f"{case.name}: tool_used Skill grader but Skill not in allowed_tools")
for skill_md in sorted(skills.glob("*/SKILL.md")):
    if re.search(r"^listing_tier:\s*A\b", skill_md.read_text(), re.M) and skill_md.parent.name not in covered:
        warnings.append(skill_md.parent.name)
if warnings:
    print(f"note: {len(warnings)} Tier A skills have no trigger case yet: {', '.join(warnings)}")
for e in errors:
    print(f"ERROR: {e}")
print(f"{cases} eval cases, {len(covered)} skills with a trigger case, {len(errors)} errors")
sys.exit(1 if errors else 0)
