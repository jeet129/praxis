#!/usr/bin/env bash
# Build the Antigravity plugin package from canonical Praxis content.
#
# Antigravity's plugin format (antigravity.google/docs/cli/plugins) is its own:
#   • plugin.json at the package ROOT — MINIMAL: $schema + name (required) +
#     optional description/version. NOT Claude's arrays, NOT Codex's schema.
#   • Slash commands come from nested skills/<name>/SKILL.md dirs that carry a
#     `name:` frontmatter key (no commands/ dir; agy discovers nested
#     skills/<name>/SKILL.md and ignores flat skills/*.md). The 12 workflow
#     command-skills are HAND-AUTHORED in antigravity-plugin-assets/skills/<name>/
#     SKILL.md (the Antigravity analog of
#     codex-plugin-assets/) — harness-correct: prose delegation instead of Claude's
#     Task() API, and no Claude-specific paths.
#   • Agents are markdown (no TOML transform — unlike Codex).
#   • Installed/auto-discovered under .agents/plugins/<name>/ (workspace) or
#     ~/.gemini/antigravity-cli/plugins/ (global).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/plugins/praxis-antigravity"
SRC="$ROOT/antigravity-plugin-assets"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: missing Antigravity source overlay: $SRC" >&2
  exit 2
fi

if [[ -e "$OUT" && ! -f "$OUT/.generated-by-praxis-antigravity-build" ]]; then
  if [[ "$OUT" == "$ROOT/plugins/praxis-antigravity" ]]; then
    echo "WARN: replacing interrupted Antigravity plugin package: $OUT" >&2
  else
    echo "ERROR: refusing to replace non-generated directory: $OUT" >&2
    exit 3
  fi
fi

python3 - "$ROOT" "$OUT" "$SRC" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
out = Path(sys.argv[2])
src = Path(sys.argv[3])

# The generated package is a PUBLIC artifact. This build refreshes every file in
# place, then reconciles OUT against the exact set of files it produced and
# REMOVES anything left over. If a stale file cannot be removed (delete-restricted
# filesystem), the build FAILS rather than publish a mirror with an orphan.
expected = set()


def place_tree(source: Path, dest: Path):
    for p in source.rglob("*"):
        if p.name == ".DS_Store" or p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(source)
        target = dest / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
            expected.add(target.relative_to(out).as_posix())


def record(target: Path):
    expected.add(target.relative_to(out).as_posix())


out.mkdir(parents=True, exist_ok=True)

# Canonical library the assistant reads. Antigravity consumes markdown agents
# directly (no TOML transform), so agents/ is copied as-is.
for name in ("skills", "agents", "workflows", "governance", "references", "patterns"):
    source = root / name
    if source.exists():
        place_tree(source, out / name)

# Antigravity honors NO per-agent model selection: subagents inherit the session
# model, hooks cannot set a model, and the SDK config exposes no model field
# (see docs/antigravity-setup.md, "Cache-aware routing on Antigravity"). The
# canonical agents carry Claude `model:`/`effort:` frontmatter as Claude Code's
# static default; shipping those verbatim in the agy package advertises models
# agy can never use. Strip them from the agy agents, keeping the harness-agnostic
# `capability_tier:` — the real routing signal, resolved by hand via `/model` per
# the advisory tier map. Canonical agents/ are untouched (Claude Code needs them).
import re as _re
for _ap in sorted((out / "agents").glob("*.md")):
    _txt = _ap.read_text()
    _m = _re.match(r"^(---\n)(.*?)(\n---\n)(.*)$", _txt, _re.S)
    if not _m:
        continue
    _fm = _m.group(2)
    _fm2 = "\n".join(l for l in _fm.split("\n")
                      if not _re.match(r"\s*(model|effort)\s*:", l))
    if _fm2 != _fm:
        _ap.write_text(_m.group(1) + _fm2 + _m.group(3) + _m.group(4))

# Antigravity command-skills come from the hand-authored overlay
# (antigravity-plugin-assets/skills/) — harness-correct <name>/SKILL.md with `name:`
# frontmatter, prose delegation, and no Claude-specific paths. This is the
# Antigravity analog of codex-plugin-assets/; the build copies them in as-is.
overlay_skills = src / "skills"
if overlay_skills.exists():
    place_tree(overlay_skills, out / "skills")

# Lifecycle hooks: the agy telemetry manifest ships at the package root. It is
# self-contained (inline commands, no sibling script to copy), so it survives
# `agy plugin install` regardless of which files agy propagates. agy exposes no
# token/cost/cache or subagent-spawn data, so it logs only what is real:
# model-per-step (routing), tool activity, and session stops, under the
# workspace's .project/telemetry/.
hooks_manifest = src / "hooks.json"
if hooks_manifest.exists():
    shutil.copy2(hooks_manifest, out / "hooks.json")
    record(out / "hooks.json")

# Minimal Antigravity manifest at package root.
manifest = out / "plugin.json"
manifest.write_text(json.dumps({
    "$schema": "https://antigravity.google/schemas/v1/plugin.json",
    "name": "praxis",
    "version": "0.1.0",
    "description": (
        "Praxis — production-grade skill library + agents + workflows + "
        "governance for AI-augmented software delivery. 91 skills, 18 agents, "
        "9 workflows, 19 governance gates."
    ),
}, indent=2) + "\n")
record(manifest)

readme = out / "README.md"
readme.write_text(
    "# Praxis Antigravity Plugin\n\n"
    "**GENERATED PACKAGE — DO NOT EDIT. Edit the repository root and rebuild.**\n\n"
    "Generated package for installing Praxis as a Google Antigravity (`agy`) plugin.\n\n"
    "Install into a global `agy`:\n\n"
    "```bash\nagy plugin install ./plugins/praxis-antigravity\n```\n\n"
    "Or let a project auto-discover it via `.agents/plugins/praxis/` "
    "(`./install.sh --tool=antigravity <project>`).\n\n"
    "Source of truth lives at the repository root. Rebuild this package with:\n\n"
    "```bash\nscripts/build-antigravity-plugin.sh\n```\n"
)
record(readme)

marker = out / ".generated-by-praxis-antigravity-build"
marker.write_text("")
record(marker)

# Reconcile: remove any file in OUT this build did not produce.
stale = []
for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
    if p.is_file():
        if p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue
        if p.relative_to(out).as_posix() not in expected:
            stale.append(p)
failed = []
for p in stale:
    try:
        p.unlink()
    except OSError:
        failed.append(p)
for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
    if p.is_dir():
        try:
            next(p.iterdir())
        except StopIteration:
            try:
                p.rmdir()
            except OSError:
                pass
if failed:
    sys.stderr.write(
        "ERROR: build-antigravity-plugin cannot remove stale file(s) on this "
        "filesystem; refusing to publish a dirty package. Rebuild on an "
        "unrestricted filesystem (pre-commit/CI does this). Offending files:\n"
        + "\n".join("  " + str(p) for p in failed) + "\n"
    )
    sys.exit(4)
PY

echo "Built Antigravity plugin package: $OUT"
