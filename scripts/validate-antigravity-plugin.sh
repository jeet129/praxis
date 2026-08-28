#!/usr/bin/env bash
# Validate the generated Praxis Antigravity plugin package.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="$ROOT/plugins/praxis-antigravity"

fail() { echo "ERROR: $*" >&2; exit 1; }

OVERLAY="$ROOT/antigravity-plugin-assets"

[[ -d "$PLUGIN" ]] || fail "missing plugin directory: $PLUGIN"
[[ -f "$PLUGIN/plugin.json" ]] || fail "missing Antigravity manifest at package root"
[[ -f "$PLUGIN/.generated-by-praxis-antigravity-build" ]] || fail "missing generated marker (edit source + rebuild, do not hand-edit the package)"
[[ -d "$PLUGIN/skills" ]] || fail "missing skills/ directory"
[[ -d "$PLUGIN/agents" ]] || fail "missing agents/ directory"
[[ -d "$PLUGIN/workflows" ]] || fail "missing workflows/ directory"
[[ -d "$PLUGIN/governance" ]] || fail "missing governance/ directory"

# Antigravity manifest must be the MINIMAL documented schema: name required,
# $schema recommended, and must NOT carry Claude's arrays (skills[]/agents[]/
# commands) — those are a Claude-format leak that would signal a wrong build.
python3 - "$PLUGIN/plugin.json" <<'PY'
import json, sys, re
m = json.load(open(sys.argv[1]))
if m.get("name") != "praxis":
    raise SystemExit('plugin.json name must be "praxis"')
if not re.match(r'^[a-zA-Z0-9_-]+$', m["name"]):
    raise SystemExit('plugin.json name must match ^[a-zA-Z0-9-_]+$')
if "antigravity.google/schemas" not in m.get("$schema", ""):
    raise SystemExit('plugin.json should declare the Antigravity $schema')
leaked = [k for k in ("commands",) if k in m]
for k in ("skills", "agents"):
    if isinstance(m.get(k), list):
        leaked.append(k)
if leaked:
    raise SystemExit("plugin.json carries Claude-format key(s) not in Antigravity's schema: "
                     + ", ".join(leaked) + " (rebuild via scripts/build-antigravity-plugin.sh)")
PY

# Antigravity has NO commands/ dir — slash commands come from skills/*.md with
# `name:`. Assert the package does not ship a commands/ dir, and that the 12
# workflow commands were emitted as name-bearing cmd-*.md skills.
[[ ! -d "$PLUGIN/commands" ]] || fail "package must not contain a commands/ dir (Antigravity uses skills/*.md with name:)"
n_cmd=$(ls "$PLUGIN"/skills/cmd-*.md 2>/dev/null | wc -l | tr -d ' ')
[[ "$n_cmd" == "12" ]] || fail "expected 12 cmd-*.md command-skills, found $n_cmd"
for base in start intake discover refine-idea architect slice review audit release steward factory-record drive; do
  f="$PLUGIN/skills/cmd-$base.md"
  [[ -f "$f" ]] || fail "missing command-skill: cmd-$base.md"
  grep -q "^name: $base$" "$f" || fail "cmd-$base.md missing injected 'name: $base' frontmatter"
done

# Front-door skill + a spot-check of agents present.
[[ -f "$PLUGIN/skills/using-praxis/SKILL.md" ]] || fail "missing front-door skill using-praxis"
n_agents=$(ls "$PLUGIN"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
[[ "$n_agents" == "18" ]] || fail "expected 18 markdown agents, found $n_agents"

# Freshness: canonical files copied as-is must be byte-identical in the mirror.
for f in skills/using-praxis/SKILL.md agents/solution-architect.md governance/governance.yaml; do
  if [[ -f "$ROOT/$f" ]]; then
    diff -q "$ROOT/$f" "$PLUGIN/$f" >/dev/null 2>&1 \
      || fail "mirror stale/diverged: $f differs from canonical — run scripts/build-antigravity-plugin.sh and commit"
  fi
done

# YAML parses.
if command -v ruby >/dev/null 2>&1; then
  ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f) }' "$PLUGIN"/workflows/*.yaml "$PLUGIN"/governance/*.yaml
fi

# NON-CONFLICT: the other harnesses' artifacts must still exist untouched.
[[ -f "$ROOT/.claude-plugin/plugin.json" ]] || fail "Claude plugin manifest missing — Antigravity build must not disturb it"
[[ -d "$ROOT/plugins/praxis-codex" ]] || fail "Codex package missing — Antigravity build must not disturb it"
# And Antigravity must NOT be registered in the Codex/Gemini marketplace (that
# file is consumed by Codex — an entry there would surface an Antigravity
# package to Codex users; keep the two publish paths separate).
if [[ -f "$ROOT/.agents/plugins/marketplace.json" ]]; then
  if grep -q "praxis-antigravity" "$ROOT/.agents/plugins/marketplace.json"; then
    fail "praxis-antigravity must NOT appear in the Codex marketplace.json (cross-harness conflict)"
  fi
fi

# Overlay is the authoritative command source (the Antigravity analog of
# codex-plugin-assets/). It must exist and cover every canonical command.
[[ -d "$OVERLAY/skills" ]] || fail "missing hand-authored overlay: antigravity-plugin-assets/skills/"
python3 - "$ROOT/.claude/commands" "$OVERLAY/skills" <<'PYCHK'
import sys, pathlib
canon = {p.stem for p in pathlib.Path(sys.argv[1]).glob("*.md")}
overlay = {p.name[len("cmd-"):-len(".md")] for p in pathlib.Path(sys.argv[2]).glob("cmd-*.md")}
missing = sorted(canon - overlay)
extra = sorted(overlay - canon)
if missing:
    raise SystemExit("overlay is missing command-skill(s) for canonical command(s): "
                     + ", ".join(missing) + " (add cmd-<name>.md to antigravity-plugin-assets/skills/)")
if extra:
    raise SystemExit("overlay has command-skill(s) with no canonical command: "
                     + ", ".join(extra) + " (remove or align antigravity-plugin-assets/skills/)")
PYCHK

# No Claude-isms may leak into the packaged command-skills.
if grep -rEn 'Task\(\{|CLAUDE_PLUGIN_ROOT|--tool[[:space:]]+claude-code|~/\.claude' "$PLUGIN"/skills/cmd-*.md >/dev/null 2>&1; then
  fail "packaged command-skills contain Claude-specific content (Task()/CLAUDE_PLUGIN_ROOT/claude-code/~/.claude) — fix the overlay and rebuild"
fi

echo "Antigravity plugin validation passed."
