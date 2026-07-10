#!/usr/bin/env python3
"""Validate reference citations across skills/*/SKILL.md.

For each skill, collects citations from two places:
  1. Frontmatter `references:` YAML list (bare filenames, e.g. `rest-openapi.md`) —
     these resolve to skills/<skill>/references/<file>.
  2. Body mentions of the form `references/<file>.md` (own skill) or
     `<other-skill>/references/<file>.md` (cross-skill, e.g. as seen in
     engineering-standards cross-references from stack-*/ skills).

A citation is OK if:
  - the file exists under the target skill's references/ dir, or
  - the file exists under the repo-level references/ dir, or
  - the file is listed (shipping or missing) in references/MISSING-INVENTORY.md.

Also reports (as info, not an error) reference files that exist on disk under
skills/*/references/ but are not cited by that skill's frontmatter list or any
body mention — these are candidates for either citing or removing.

Exit codes:
  1 — one or more citations are neither existing on disk nor tracked in
      references/MISSING-INVENTORY.md (a truly dangling reference)
  0 — clean, or only uncited-but-existing info findings

Zero third-party dependencies.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
REPO_REFERENCES_DIR = ROOT / "references"
MISSING_INVENTORY = REPO_REFERENCES_DIR / "MISSING-INVENTORY.md"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
BODY_REF_RE = re.compile(r"(?:([a-zA-Z0-9_-]+)/)?references/([a-zA-Z0-9_.-]+\.md)")
INVENTORY_ROW_RE = re.compile(r"`([a-zA-Z0-9_-]+/references/[a-zA-Z0-9_.-]+\.md)`")


def load_inventory_tracked():
    """Returns the set of 'skill/references/file.md' paths mentioned in
    MISSING-INVENTORY.md (shipping or missing — both count as tracked)."""
    if not MISSING_INVENTORY.exists():
        return set()
    text = MISSING_INVENTORY.read_text()
    return set(INVENTORY_ROW_RE.findall(text))


def extract_frontmatter_references(text):
    """Parses the `references:` field from the praxis:metadata body block
    (a YAML list of bare filenames or `references: []`)."""
    # The metadata lives in a ```yaml fenced block between the praxis:metadata
    # markers, not in the top frontmatter (per validate-skills.sh's two-tier model).
    m = re.search(
        r"<!-- praxis:metadata:begin -->.*?```yaml\n(.*?)```.*?<!-- praxis:metadata:end -->",
        text,
        re.S,
    )
    if not m:
        return []
    meta = m.group(1)
    ref_m = re.search(r"^references:\s*(\[\s*\])?\s*$", meta, re.M)
    if not ref_m:
        return []
    if ref_m.group(1) is not None:
        return []  # references: []
    # Collect the following indented `- file.md` list lines.
    start = ref_m.end()
    rest = meta[start:]
    files = []
    for line in rest.splitlines():
        if not line.strip():
            continue
        item_m = re.match(r"^\s*-\s*([A-Za-z0-9_./-]+\.md)\s*(#.*)?$", line)
        if item_m:
            files.append(item_m.group(1))
        else:
            break  # end of the references list
    return files


def resolve_citation(citing_skill, prefix, filename):
    """Returns (target_skill, relative_path_str, exists_bool)."""
    target_skill = prefix if prefix else citing_skill
    # Cross-skill relative citations like `../engineering-standards/references/x.md`
    # resolve from the citing skill's directory.
    if "/" in filename:
        candidate = (SKILLS_DIR / citing_skill / filename).resolve()
        if candidate.exists() and candidate.is_relative_to(SKILLS_DIR.resolve()):
            rel = candidate.relative_to(SKILLS_DIR.resolve())
            return rel.parts[0], str(rel), True
    candidate = SKILLS_DIR / target_skill / "references" / filename
    if candidate.exists():
        return target_skill, f"{target_skill}/references/{filename}", True
    repo_level = REPO_REFERENCES_DIR / filename
    if repo_level.exists():
        return target_skill, f"references/{filename}", True
    return target_skill, f"{target_skill}/references/{filename}", False


def main():
    inventory_tracked = load_inventory_tracked()

    errors = []
    warnings_uncited = []
    cited_per_skill = {}  # skill_name -> set of filenames cited (own-skill citations)

    skill_dirs = sorted(p.parent for p in SKILLS_DIR.glob("*/SKILL.md"))

    for skill_dir in skill_dirs:
        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        text = skill_md.read_text()
        cited_per_skill.setdefault(skill_name, set())

        # 1. Frontmatter references: list
        for filename in extract_frontmatter_references(text):
            target_skill, rel_path, exists = resolve_citation(skill_name, None, filename)
            cited_per_skill.setdefault(target_skill, set()).add(Path(filename).name)
            if not exists and rel_path not in inventory_tracked:
                errors.append(
                    f"{skill_name}/SKILL.md: frontmatter references '{filename}' -> "
                    f"missing {rel_path} and not tracked in MISSING-INVENTORY.md"
                )

        # 2. Body mentions of references/<file>.md or <skill>/references/<file>.md
        for m in BODY_REF_RE.finditer(text):
            prefix, filename = m.group(1), m.group(2)
            target_skill, rel_path, exists = resolve_citation(skill_name, prefix, filename)
            cited_per_skill.setdefault(target_skill, set()).add(filename)
            if not exists and rel_path not in inventory_tracked:
                errors.append(
                    f"{skill_name}/SKILL.md: body cites '{rel_path}' -> "
                    f"missing and not tracked in MISSING-INVENTORY.md"
                )

    # 3. Uncited-but-existing reference files
    for skill_dir in skill_dirs:
        skill_name = skill_dir.name
        refs_dir = skill_dir / "references"
        if not refs_dir.is_dir():
            continue
        on_disk = {p.name for p in refs_dir.glob("*.md")}
        cited = cited_per_skill.get(skill_name, set())
        uncited = sorted(on_disk - cited)
        for f in uncited:
            warnings_uncited.append(f"{skill_name}/references/{f}: exists on disk but not cited by {skill_name}/SKILL.md")

    # dedupe errors while preserving order
    seen = set()
    deduped_errors = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            deduped_errors.append(e)

    print("Praxis — reference citation validator")
    print("=======================================")
    print(f"  skills scanned:         {len(skill_dirs)}")
    print(f"  inventory entries:      {len(inventory_tracked)}")
    print()

    if warnings_uncited:
        print(f"Info: {len(warnings_uncited)} reference file(s) exist but are not cited:")
        for w in warnings_uncited:
            print(f"  i {w}")
        print()

    if deduped_errors:
        print(f"Errors: {len(deduped_errors)} dangling citation(s) (not on disk, not tracked):")
        for e in deduped_errors:
            print(f"  x {e}")
        print()
        print("FAIL")
        return 1

    print("OK: all citations either exist on disk or are tracked in MISSING-INVENTORY.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
