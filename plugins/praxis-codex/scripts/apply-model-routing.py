#!/usr/bin/env python3
"""Resolve abstract capability tiers to harness-native model settings.

Reads governance/model-routing.yaml, then:
  * agents/*.md            — rewrites the `model:` frontmatter line from `capability_tier:`
  * codex-plugin-assets/codex-agents/*.toml — rewrites `model_reasoning_effort` using the
    capability_tier of the same-named canonical agent.

Usage:
  scripts/apply-model-routing.py           # apply (rewrites files in place)
  scripts/apply-model-routing.py --check   # CI mode: exit 1 if any file is out of sync

Zero dependencies: parses the strict YAML subset used by model-routing.yaml.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTING = ROOT / "governance" / "model-routing.yaml"
AGENTS = ROOT / "agents"
CODEX_AGENTS = ROOT / "codex-plugin-assets" / "codex-agents"
VALID_TIERS = ("deep", "standard", "light")


def parse_routing(path: Path) -> dict:
    """Minimal parser for the known structure of model-routing.yaml."""
    harnesses: dict[str, dict] = {}
    force_tier = None
    current_harness = None
    in_map = False
    section = None
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        key_val = line.strip().split(":", 1)
        key = key_val[0].strip()
        val = key_val[1].strip() if len(key_val) > 1 else ""
        if indent == 0:
            section = key
            current_harness = None
            in_map = False
            if section == "overrides":
                pass
            continue
        if section == "harnesses":
            if indent == 2:
                current_harness = key
                harnesses[current_harness] = {"field": None, "map": {}}
                in_map = False
            elif indent == 4 and current_harness:
                if key == "field":
                    harnesses[current_harness]["field"] = val
                elif key == "map":
                    in_map = True
            elif indent == 6 and current_harness and in_map:
                harnesses[current_harness]["map"][key] = val
        elif section == "overrides" and key == "force_tier":
            force_tier = None if val in ("null", "~", "") else val
    return {"harnesses": harnesses, "force_tier": force_tier}


def frontmatter_span(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    return m


def process_agents(cfg: dict, check: bool) -> tuple[list[str], dict[str, str], list[str]]:
    """Returns (changed_files, agent->tier map, errors)."""
    harness = cfg["harnesses"]["claude-code"]
    field, mapping = harness["field"], harness["map"]
    force = cfg["force_tier"]
    changed, tiers, errors = [], {}, []
    for path in sorted(AGENTS.glob("*.md")):
        text = path.read_text()
        fm = frontmatter_span(text)
        if not fm:
            errors.append(f"{path}: no frontmatter")
            continue
        tier_m = re.search(r"^capability_tier:\s*(\S+)\s*$", fm.group(1), re.M)
        if not tier_m:
            errors.append(f"{path}: missing capability_tier")
            continue
        tier = force or tier_m.group(1)
        if tier not in VALID_TIERS:
            errors.append(f"{path}: invalid capability_tier '{tier}'")
            continue
        tiers[path.stem] = tier
        target = mapping[tier]
        new_fm, n = re.subn(
            rf"^{field}:\s*.*$", f"{field}: {target}", fm.group(1), flags=re.M
        )
        if n == 0:  # insert model line after capability_tier
            new_fm = re.sub(
                r"^(capability_tier:.*)$",
                rf"\1\n{field}: {target}",
                fm.group(1),
                flags=re.M,
            )
        if new_fm != fm.group(1):
            changed.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(text[: fm.start(1)] + new_fm + text[fm.end(1):])
    return changed, tiers, errors


def process_codex(cfg: dict, tiers: dict, check: bool) -> tuple[list[str], list[str]]:
    harness = cfg["harnesses"]["codex"]
    field, mapping = harness["field"], harness["map"]
    changed, errors = [], []
    if not CODEX_AGENTS.exists():
        return changed, errors
    for path in sorted(CODEX_AGENTS.glob("*.toml")):
        tier = tiers.get(path.stem)
        if tier is None:
            errors.append(f"{path}: no canonical agent '{path.stem}' with a capability_tier")
            continue
        target = mapping[tier]
        text = path.read_text()
        new_text, n = re.subn(
            rf'^{field}\s*=\s*".*"$', f'{field} = "{target}"', text, flags=re.M
        )
        if n == 0:  # insert after description line
            new_text = re.sub(
                r'^(description\s*=.*)$',
                rf'\1\n{field} = "{target}"',
                text,
                count=1,
                flags=re.M,
            )
        if new_text != text:
            changed.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(new_text)
    return changed, errors


def main() -> int:
    check = "--check" in sys.argv
    cfg = parse_routing(ROUTING)
    for h in ("claude-code", "codex"):
        if h not in cfg["harnesses"]:
            print(f"ERROR: harness '{h}' missing from {ROUTING}", file=sys.stderr)
            return 2
    changed_a, tiers, errs_a = process_agents(cfg, check)
    changed_c, errs_c = process_codex(cfg, tiers, check)
    errors = errs_a + errs_c
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    changed = changed_a + changed_c
    if check:
        if changed:
            print("Out of sync with governance/model-routing.yaml:")
            for f in changed:
                print(f"  {f}")
            return 1
        if errors:
            return 1
        print(f"OK: {len(tiers)} agents in sync with routing table.")
        return 0
    for f in changed:
        print(f"updated: {f}")
    if not changed:
        print("All files already in sync.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
