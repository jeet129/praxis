#!/usr/bin/env python3
"""Resolve a capability tier to the harness-native model + reasoning effort.

The SINGLE SOURCE OF TRUTH for "which model does tier T run on", reading the
EFFECTIVE routing table with the SAME precedence the drive runner uses:
  --routing PATH                                   (explicit), else
  <project-dir>/.project/governance/model-routing.yaml   (project override), else
  <plugin>/governance/model-routing.yaml                 (plugin default).

This is what makes NO-DRIVE routing identical to DRIVE routing: Delivery Lead
calls this before spawning a sub-agent so an interactive spawn resolves the
exact model/effort the drive runner would pick for the same tier — honoring a
project-level override, not the plugin-baked agent frontmatter.

Parsing is delegated to apply-model-routing.py so there is one parser, and the
axis resolution (model axis = the map whose field is named `model`; effort axis
= the map whose field name contains `effort`) matches scripts/praxis-drive.sh.

Usage:
  resolve-model.py --harness claude-code --tier deep [--project-dir .]
  resolve-model.py --harness codex --tier standard --field effort
Default output: `model: <name|inherit>` and `effort: <level|inherit>` (plus a
`# source:` line). `inherit` means the table maps this tier to `auto` (omit the
pin; the harness/session default is used). `--field model|effort` prints one
bare value for scripting.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALID_TIERS = ("deep", "standard", "light")

# Reuse the plugin's routing parser (one parser, no third copy of the logic).
_spec = importlib.util.spec_from_file_location("_amr", ROOT / "scripts" / "apply-model-routing.py")
_amr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_amr)


def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def effective_routing(project_dir, explicit) -> Path:
    if explicit:
        return Path(explicit)
    if project_dir:
        cand = Path(project_dir) / ".project" / "governance" / "model-routing.yaml"
        if cand.exists():
            return cand
    return ROOT / "governance" / "model-routing.yaml"


def resolve(cfg: dict, harness: str, tier: str):
    """Return (model, effort) for the tier; None means 'auto' (omit/inherit).
    force_tier override honored, same as the rest of the toolchain."""
    h = cfg["harnesses"].get(harness, {}) or {}
    if cfg.get("force_tier"):
        tier = cfg["force_tier"]
    axis = []
    for fkey, mkey in (("field", "map"), ("effort_field", "effort_map"), ("model_field", "model_map")):
        fname = h.get(fkey)
        tmap = h.get(mkey) or {}
        if isinstance(fname, str) and fname and isinstance(tmap, dict):
            axis.append((fname, tmap))

    def pick(pred):
        for fname, tmap in axis:
            if pred(fname):
                return tmap
        return {}

    m = pick(lambda f: f == "model").get(tier)
    e = pick(lambda f: "effort" in f).get(tier)
    model = None if (not m or m == "auto") else m
    effort = None if (not e or e == "auto") else e
    return model, effort


def main() -> int:
    harness = _arg("--harness")
    tier = _arg("--tier")
    field = _arg("--field")
    if not harness or tier not in VALID_TIERS:
        sys.stderr.write(
            "usage: resolve-model.py --harness H --tier deep|standard|light "
            "[--project-dir D | --routing FILE] [--field model|effort]\n"
        )
        return 2
    path = effective_routing(_arg("--project-dir"), _arg("--routing"))
    if not path.exists():
        sys.stderr.write(f"resolve-model: routing file not found: {path}\n")
        return 2
    if harness not in _amr.parse_routing(path)["harnesses"]:
        sys.stderr.write(f"resolve-model: harness '{harness}' not in {path}\n")
        return 2
    model, effort = resolve(_amr.parse_routing(path), harness, tier)
    if field == "model":
        print(model or "inherit")
        return 0
    if field == "effort":
        print(effort or "inherit")
        return 0
    print(f"model: {model or 'inherit'}")
    print(f"effort: {effort or 'inherit'}")
    print(f"# source: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
