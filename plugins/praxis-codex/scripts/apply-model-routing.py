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


def _arg(name, default=None):
    """Value following `name` in argv, or default."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


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


def process_agents(cfg: dict, check: bool, out_dir=None) -> tuple[list[str], dict[str, str], list[str]]:
    """Returns (changed_files, agent->tier map, errors).

    Additive: alongside `model:` (from `field`/`map`), also writes/updates
    `effort:` (from `effort_field`/`effort_map`) when the harness config
    declares them. A map value of `auto` OMITS that field entirely (removes
    any existing line rather than writing `effort: auto` / `model: auto`).
    Harnesses without effort_field/effort_map behave exactly as before.

    `out_dir` (optional): write each agent to `out_dir/<name>.md` instead of
    in place — used by the setup-claude-agents install path to materialize
    project-local `.claude/agents/*.md` (which shadow the plugin agents) with
    frontmatter resolved from the EFFECTIVE routing table. The plugin's own
    agent files are never touched in this mode.
    """
    harness = cfg["harnesses"]["claude-code"]
    field, mapping = harness["field"], harness["map"]
    effort_field = harness.get("effort_field")
    effort_map = harness.get("effort_map") or {}
    force = cfg["force_tier"]
    changed, tiers, errors = [], {}, []
    if out_dir is not None:
        out_dir = Path(out_dir)
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
        has_model_line = re.search(rf"^{field}:\s*.*$", fm.group(1), re.M) is not None
        if target and target != "auto":
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
        elif has_model_line:
            # auto => omit the model line (Claude then inherits the session model)
            new_fm = re.sub(rf"^{field}:\s*.*\n", "", fm.group(1), flags=re.M)
        else:
            new_fm = fm.group(1)

        if effort_field and effort_map:
            effort_target = effort_map.get(tier)
            has_effort_line = re.search(rf"^{effort_field}:\s*.*$", new_fm, re.M) is not None
            anchor = field if re.search(rf"^{field}:.*$", new_fm, re.M) else "capability_tier"
            if effort_target and effort_target != "auto":
                if has_effort_line:
                    new_fm = re.sub(
                        rf"^{effort_field}:\s*.*$", f"{effort_field}: {effort_target}", new_fm, flags=re.M
                    )
                else:
                    new_fm = re.sub(
                        rf"^({anchor}:.*)$",
                        rf"\1\n{effort_field}: {effort_target}",
                        new_fm,
                        count=1,
                        flags=re.M,
                    )
            elif has_effort_line:
                # auto (or unmapped) => omit the field entirely.
                new_fm = re.sub(rf"^{effort_field}:\s*.*\n", "", new_fm, flags=re.M)

        new_text = text[: fm.start(1)] + new_fm + text[fm.end(1):]
        if out_dir is not None:
            dest = out_dir / path.name
            prior = dest.read_text() if dest.exists() else None
            if prior != new_text:
                changed.append(str(dest))
                if not check:
                    out_dir.mkdir(parents=True, exist_ok=True)
                    dest.write_text(new_text)
        elif new_fm != fm.group(1):
            changed.append(str(path.relative_to(ROOT)))
            if not check:
                path.write_text(new_text)
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
            try:
                rel = str(path.relative_to(ROOT))
            except ValueError:
                rel = str(path)  # target dir outside the repo (e.g. a project's .codex/agents)
            changed.append(rel)
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


def _resolve_routing() -> Path:
    """Which model-routing.yaml to apply. Precedence:
      --routing PATH                                  (explicit)
      --project-dir DIR -> DIR/.project/governance/model-routing.yaml  (if present)
      else the plugin default (ROUTING).
    This is what lets a PROJECT override drive the generated subagent profiles,
    the same file the drive loop already honors at runtime."""
    explicit = _arg("--routing")
    if explicit:
        return Path(explicit)
    project_dir = _arg("--project-dir")
    if project_dir:
        cand = Path(project_dir) / ".project" / "governance" / "model-routing.yaml"
        if cand.exists():
            return cand
    return ROUTING


def main() -> int:
    global CODEX_AGENTS
    check = "--check" in sys.argv
    routing_path = _resolve_routing()
    # Targeted install paths write the (possibly project-overridden) routing
    # into a project's agent dir instead of the plugin source, and DON'T touch
    # the plugin's own files:
    #   --codex-out DIR  -> resolve into DIR (a project's .codex/agents)
    #   --claude-out DIR -> materialize project-local .claude/agents/*.md
    #                        (they shadow the plugin agents) so no-drive Claude
    #                        spawns honor the override too.
    codex_out = _arg("--codex-out")
    claude_out = _arg("--claude-out")
    targeted = bool(codex_out or claude_out)
    if codex_out:
        CODEX_AGENTS = Path(codex_out)

    if not routing_path.exists():
        print(f"ERROR: routing file not found: {routing_path}", file=sys.stderr)
        return 2
    cfg = parse_routing(routing_path)
    for h in ("claude-code", "codex"):
        if h not in cfg["harnesses"]:
            print(f"ERROR: harness '{h}' missing from {routing_path}", file=sys.stderr)
            return 2

    # tiers always come from the canonical agents/*.md. In a codex-only targeted
    # run the claude agents are read-only (never touched); with --claude-out we
    # write them to the target dir; default writes them in place.
    if claude_out:
        changed_a, tiers, errs_a = process_agents(cfg, check, out_dir=claude_out)
    else:
        changed_a, tiers, errs_a = process_agents(cfg, check or targeted)
    changed_c, errs_c = ([], [])
    if codex_out or not targeted:
        changed_c, errs_c = process_codex(cfg, tiers, check)

    errors = list(errs_c)
    if claude_out or not targeted:
        errors += errs_a
    if not targeted:
        errors += validate_effort_pairing(cfg)
        for w in validate_pin_comment_context(routing_path):
            print(f"WARNING: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    if not targeted:
        changed = changed_a + changed_c
    elif claude_out and codex_out:
        changed = changed_a + changed_c
    elif claude_out:
        changed = changed_a
    else:
        changed = changed_c
    src_label = routing_path if routing_path != ROUTING else "governance/model-routing.yaml"
    if check:
        if changed:
            print(f"Out of sync with {src_label}:")
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
    if targeted and not errors:
        dest = claude_out if claude_out else CODEX_AGENTS
        print(f"Applied routing from {src_label} to {dest}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
