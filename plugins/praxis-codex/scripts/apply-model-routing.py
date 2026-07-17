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
    """Minimal parser for the known structure of model-routing.yaml.

    Additive: also reads `effort_field`/`effort_map` (claude-code) and
    `model_field`/`model_map` (codex) alongside the original `field`/`map`.
    A harness missing these keys behaves exactly as before (backward-compat).
    """
    harnesses: dict[str, dict] = {}
    force_tier = None
    current_harness = None
    active_map = None  # which dict the indent-6 lines populate: "map" | "effort_map" | "model_map"
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
            active_map = None
            if section == "overrides":
                pass
            continue
        if section == "harnesses":
            if indent == 2:
                current_harness = key
                harnesses[current_harness] = {
                    "field": None, "map": {},
                    "effort_field": None, "effort_map": {},
                    "model_field": None, "model_map": {},
                }
                active_map = None
            elif indent == 4 and current_harness:
                if key == "field":
                    harnesses[current_harness]["field"] = val
                elif key == "map":
                    active_map = "map"
                elif key == "effort_field":
                    harnesses[current_harness]["effort_field"] = val
                elif key == "effort_map":
                    active_map = "effort_map"
                elif key == "model_field":
                    harnesses[current_harness]["model_field"] = val
                elif key == "model_map":
                    active_map = "model_map"
                else:
                    active_map = None
            elif indent == 6 and current_harness and active_map:
                harnesses[current_harness][active_map][key] = val
        elif section == "overrides" and key == "force_tier":
            force_tier = None if val in ("null", "~", "") else val
    return {"harnesses": harnesses, "force_tier": force_tier}


def frontmatter_span(text: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    return m


def process_agents(cfg: dict, check: bool) -> tuple[list[str], dict[str, str], list[str]]:
    """Returns (changed_files, agent->tier map, errors).

    Additive: alongside `model:` (from `field`/`map`), also writes/updates
    `effort:` (from `effort_field`/`effort_map`) when the harness config
    declares them. A map value of `auto` OMITS that field entirely (removes
    any existing line rather than writing `effort: auto` / `model: auto`).
    Harnesses without effort_field/effort_map behave exactly as before.
    """
    harness = cfg["harnesses"]["claude-code"]
    field, mapping = harness["field"], harness["map"]
    effort_field = harness.get("effort_field")
    effort_map = harness.get("effort_map") or {}
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

        if effort_field and effort_map:
            effort_target = effort_map.get(tier)
            has_effort_line = re.search(rf"^{effort_field}:\s*.*$", new_fm, re.M) is not None
            if effort_target and effort_target != "auto":
                if has_effort_line:
                    new_fm = re.sub(
                        rf"^{effort_field}:\s*.*$", f"{effort_field}: {effort_target}", new_fm, flags=re.M
                    )
                else:
                    new_fm = re.sub(
                        rf"^({field}:.*)$",
                        rf"\1\n{effort_field}: {effort_target}",
                        new_fm,
                        count=1,
                        flags=re.M,
                    )
            elif has_effort_line:
                # auto (or unmapped) => omit the field entirely.
                new_fm = re.sub(rf"^{effort_field}:\s*.*\n", "", new_fm, flags=re.M)

        if new_fm != fm.group(1):
            changed.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(text[: fm.start(1)] + new_fm + text[fm.end(1):])
    return changed, tiers, errors


def process_codex(cfg: dict, tiers: dict, check: bool) -> tuple[list[str], list[str]]:
    """Additive: alongside `model_reasoning_effort` (`field`/`map`), also
    writes/updates `model` (`model_field`/`model_map`) when the harness
    config declares them and the mapped value != auto. `auto` OMITS the
    `model =` line entirely (removes an existing one, writes none new)."""
    harness = cfg["harnesses"]["codex"]
    field, mapping = harness["field"], harness["map"]
    model_field = harness.get("model_field")
    model_map = harness.get("model_map") or {}
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

        if model_field and model_map:
            model_target = model_map.get(tier)
            has_model_line = re.search(rf'^{model_field}\s*=\s*".*"$', new_text, re.M) is not None
            if model_target and model_target != "auto":
                if has_model_line:
                    new_text = re.sub(
                        rf'^{model_field}\s*=\s*".*"$',
                        f'{model_field} = "{model_target}"',
                        new_text,
                        flags=re.M,
                    )
                else:
                    new_text = re.sub(
                        r'^(name\s*=.*)$',
                        rf'\1\n{model_field} = "{model_target}"',
                        new_text,
                        count=1,
                        flags=re.M,
                    )
            elif has_model_line:
                new_text = re.sub(rf'^{model_field}\s*=\s*".*"\n', "", new_text, flags=re.M)

        if new_text != text:
            changed.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(new_text)
    return changed, errors


def validate_effort_pairing(cfg: dict) -> list[str]:
    """FAIL if a claude-code tier has a concrete model but no effort mapped
    for the same tier — both should be set together (job 5). A tier whose
    model is 'auto'/unset is exempt (nothing to pair)."""
    errors = []
    harness = cfg["harnesses"].get("claude-code") or {}
    mapping = harness.get("map") or {}
    effort_field = harness.get("effort_field")
    effort_map = harness.get("effort_map") or {}
    for tier in VALID_TIERS:
        model_val = mapping.get(tier)
        if not model_val or model_val == "auto":
            continue
        effort_val = effort_map.get(tier)
        if not effort_field or not effort_val:
            errors.append(
                f"governance/model-routing.yaml: claude-code tier '{tier}' has model "
                f"'{model_val}' but no paired effort_map entry — set both together"
            )
    return errors


def validate_pin_comment_context(routing_path: Path) -> list[str]:
    """WARN (not fail) if the routing table pins concrete claude models
    without the 'current-best-known/override-friendly' comment context that
    documents what a pin means (job 5, light-touch — text presence only)."""
    warnings = []
    text = routing_path.read_text()
    if "current-best-known" not in text or "override-friendly" not in text:
        warnings.append(
            f"{routing_path}: pins concrete models without documenting the "
            "'current-best-known / override-friendly' comment context — see docs/model-routing.md"
        )
    return warnings


def main() -> int:
    check = "--check" in sys.argv
    cfg = parse_routing(ROUTING)
    for h in ("claude-code", "codex"):
        if h not in cfg["harnesses"]:
            print(f"ERROR: harness '{h}' missing from {ROUTING}", file=sys.stderr)
            return 2
    changed_a, tiers, errs_a = process_agents(cfg, check)
    changed_c, errs_c = process_codex(cfg, tiers, check)
    errs_pairing = validate_effort_pairing(cfg)
    warnings = validate_pin_comment_context(ROUTING)
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    errors = errs_a + errs_c + errs_pairing
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
