#!/usr/bin/env bash
# Build the Codex plugin package from canonical Praxis content.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/plugins/praxis-codex"
SRC="$ROOT/codex-plugin-assets"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: missing Codex source directory: $SRC" >&2
  exit 2
fi

if [[ -e "$OUT" && ! -f "$OUT/.generated-by-praxis-codex-build" ]]; then
  if [[ -d "$OUT/.codex-plugin" || "$OUT" == "$ROOT/plugins/praxis-codex" ]]; then
    echo "WARN: replacing interrupted Codex plugin package: $OUT" >&2
  else
    echo "ERROR: refusing to replace non-generated directory: $OUT" >&2
    exit 3
  fi
fi

python3 - "$ROOT" "$SRC" "$OUT" <<'PY'
import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = Path(sys.argv[2])
out = Path(sys.argv[3])

# The generated Codex package is a PUBLIC artifact. Correctness beats sandbox
# convenience: this build refreshes every file in place, then reconciles OUT
# against the exact set of files it produced and REMOVES anything left over.
# If a stale file cannot be removed (e.g. a delete-restricted filesystem), the
# build FAILS rather than publish a mirror that still contains a since-deleted
# skill/hook. (The authoritative build runs in pre-commit/CI on an unrestricted
# filesystem; there the removal always succeeds.)
expected = set()  # POSIX-rel paths, from OUT, that this build intends to exist


def place_tree(source: Path, dest: Path):
    """Copy source -> dest (overwriting file contents in place, which is
    allowed even where unlink is blocked) and record every file it places
    relative to OUT, so reconciliation below knows exactly what belongs."""
    for p in source.rglob("*"):
        if p.name == ".DS_Store" or p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue  # never ship python bytecode
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
(out / ".codex-plugin").mkdir(exist_ok=True)

for name in ("skills", "agents", "workflows", "governance", "references", "patterns", "scripts", "hooks"):
    source = root / name
    if source.exists():
        place_tree(source, out / name)

command_skills = src / "skills"
if command_skills.exists():
    for skill in command_skills.iterdir():
        if skill.is_dir():
            place_tree(skill, out / "skills" / skill.name)

codex_agents = src / "codex-agents"
if codex_agents.exists():
    place_tree(codex_agents, out / "codex-agents")

# Harness-correct the mirror's hook events. Codex's hook vocabulary has NO
# `SessionEnd` (verified against the Codex hooks reference); its turn-scoped
# `Stop` event is the analog. The canonical hooks.json is Claude-shaped
# (SessionEnd fires once for Claude), so for the MIRROR only we: drop the
# Codex-unsupported `SessionEnd`, and add `Stop` routed to the same tap.sh
# handler. tap.sh's capture is an upsert keyed by session id (Stop is turn-
# scoped and may fire per turn), so this cannot double-count. Every other event
# kept here (SessionStart, PostToolUse, UserPromptSubmit, SubagentStart,
# SubagentStop) is in Codex's supported set.
hooks_json = out / "hooks" / "hooks.json"
if hooks_json.exists():
    data = json.loads(hooks_json.read_text())
    hooks = data.get("hooks", {})
    hooks.pop("SessionEnd", None)   # Codex has no SessionEnd
    tap_cmd = 'TAP="${CLAUDE_PLUGIN_ROOT}/hooks/tap.sh"; [ -f "$TAP" ] && bash "$TAP" Stop || true'
    hooks["Stop"] = [{"hooks": [{"type": "command", "command": tap_cmd}]}]
    # Env robustness for the MIRROR: the canonical commands resolve tap.sh via
    # ${CLAUDE_PLUGIN_ROOT}; if the Codex runtime exposes a different var the
    # [ -f "$TAP" ] guard silently no-ops every hook. Rewrite all commands to a
    # fallback chain so either var works.
    chain = "${CLAUDE_PLUGIN_ROOT:-${CODEX_PLUGIN_ROOT:-}}"
    def _rewrite(node):
        if isinstance(node, dict):
            if isinstance(node.get("command"), str):
                node["command"] = node["command"].replace("${CLAUDE_PLUGIN_ROOT}", chain)
            for v in node.values():
                _rewrite(v)
        elif isinstance(node, list):
            for v in node:
                _rewrite(v)
    _rewrite(hooks)
    data["hooks"] = hooks
    hooks_json.write_text(json.dumps(data, indent=2) + "\n")

# Generated files (also part of the expected set).
manifest = out / ".codex-plugin" / "plugin.json"
manifest.write_text(json.dumps({
    "name": "praxis-codex",
    "version": "0.1.0",
    "description": "Praxis for Codex: agentic development platform for end-to-end software and product delivery.",
    "skills": "./skills/",
    "hooks": "./hooks/hooks.json",
}, indent=2) + "\n")
record(manifest)
readme = out / "README.md"
readme.write_text(
    "# Praxis Codex Plugin\n\n"
    "**GENERATED PACKAGE — DO NOT EDIT. Edit the repository root and rebuild.**\n\n"
    "Generated package for installing Praxis as a Codex plugin.\n\n"
    "Source of truth lives at the repository root. Rebuild this package with:\n\n"
    "```bash\nscripts/build-codex-plugin.sh\n```\n"
)
record(readme)
marker = out / ".generated-by-praxis-codex-build"
marker.write_text("")
record(marker)

# Reconcile: remove any file in OUT this build did not produce. Fail loudly if
# a stale file cannot be removed — never silently ship an orphan.
stale = []
for p in sorted(out.rglob("*"), key=lambda x: len(x.parts), reverse=True):
    if p.is_file():
        if p.suffix == ".pyc" or "__pycache__" in p.parts:
            continue  # bytecode is gitignored cruft, not a tracked orphan
        if p.relative_to(out).as_posix() not in expected:
            stale.append(p)
failed = []
for p in stale:
    try:
        p.unlink()
    except OSError:
        failed.append(p)
# Best-effort prune of now-empty directories (ignore failures — empty dirs are
# harmless; a leftover orphan FILE is the real hazard and is handled above).
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
        "ERROR: build-codex-plugin cannot remove stale file(s) from the mirror "
        "on this filesystem; refusing to publish a dirty package. Rebuild on an "
        "unrestricted filesystem (pre-commit/CI does this). Offending files:\n"
        + "\n".join("  " + str(p) for p in failed) + "\n"
    )
    sys.exit(4)
PY

echo "Built Codex plugin package: $OUT"
