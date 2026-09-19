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
# `name:`. Assert no commands/ dir, and that the 12 workflow commands were
# emitted as nested name-bearing <name>/SKILL.md skills (agy discovers nested).
[[ ! -d "$PLUGIN/commands" ]] || fail "package must not contain a commands/ dir (Antigravity uses nested skills/<name>/SKILL.md)"
n_cmd=0
for base in start intake discover refine-idea architect slice review audit release steward factory-record drive; do
  f="$PLUGIN/skills/$base/SKILL.md"
  [[ -f "$f" ]] || fail "missing command-skill: skills/$base/SKILL.md"
  grep -q "^name: $base$" "$f" || fail "skills/$base/SKILL.md missing 'name: $base' frontmatter"
  n_cmd=$((n_cmd+1))
done
[[ "$n_cmd" == "12" ]] || fail "expected 12 nested command-skills, found $n_cmd"

# Front-door skill + a spot-check of agents present.
[[ -f "$PLUGIN/skills/using-praxis/SKILL.md" ]] || fail "missing front-door skill using-praxis"
n_agents=$(ls "$PLUGIN"/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
[[ "$n_agents" == "18" ]] || fail "expected 18 markdown agents, found $n_agents"

# Antigravity honors no per-agent model (subagents inherit the session model;
# hooks cannot set one; the SDK config has no model field). The build strips the
# Claude `model:`/`effort:` frontmatter from the agy agents, leaving the
# harness-agnostic `capability_tier:`. Assert that held: every agy agent must
# declare a tier and must NOT re-introduce a model/effort line (which would
# advertise a model agy cannot use). See docs/antigravity-setup.md.
for af in "$PLUGIN"/agents/*.md; do
  grep -qE '^capability_tier:' "$af" || fail "agy agent $(basename "$af") missing capability_tier"
  if grep -qE '^(model|effort):' "$af"; then
    fail "agy agent $(basename "$af") carries model:/effort: frontmatter — agy honors no per-agent model; rebuild (scripts/build-antigravity-plugin.sh) to strip it"
  fi
done

# Freshness: canonical files copied as-is must be byte-identical in the mirror.
for f in skills/using-praxis/SKILL.md governance/governance.yaml; do
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
overlay = {p.parent.name for p in pathlib.Path(sys.argv[2]).glob("*/SKILL.md")}
missing = sorted(canon - overlay)
extra = sorted(overlay - canon)
if missing:
    raise SystemExit("overlay is missing command-skill(s) for canonical command(s): "
                     + ", ".join(missing) + " (add <name>/SKILL.md to antigravity-plugin-assets/skills/)")
if extra:
    raise SystemExit("overlay has command-skill(s) with no canonical command: "
                     + ", ".join(extra) + " (remove or align antigravity-plugin-assets/skills/)")
PYCHK

# No Claude-isms may leak into the packaged command-skills.
if grep -rEn 'Task\(\{|CLAUDE_PLUGIN_ROOT|--tool[[:space:]]+claude-code|~/\.claude' "$PLUGIN"/skills/{start,intake,discover,refine-idea,architect,slice,review,audit,release,steward,factory-record,drive}/SKILL.md >/dev/null 2>&1; then
  fail "packaged command-skills contain Claude-specific content (Task()/CLAUDE_PLUGIN_ROOT/claude-code/~/.claude) — fix the overlay and rebuild"
fi

# Lifecycle hooks: the telemetry manifest must exist AND be in agy's real format
# (top-level named hooks; only the five agy events). This guards against the
# Claude-format leak ({"hooks": {SessionStart|UserPromptSubmit|Subagent*...}})
# that agy counts as "1 processed" but silently drops every handler.
[[ -f "$PLUGIN/hooks.json" ]] || fail "missing hooks.json (agy telemetry manifest) at package root"
[[ -f "$OVERLAY/hooks.json" ]] || fail "missing hand-authored antigravity-plugin-assets/hooks.json (build source)"
diff -q "$OVERLAY/hooks.json" "$PLUGIN/hooks.json" >/dev/null 2>&1 \
  || fail "mirror stale: plugins/praxis-antigravity/hooks.json differs from antigravity-plugin-assets/hooks.json — rebuild"
python3 - "$PLUGIN/hooks.json" <<'PYHOOK'
import json, sys
ALLOWED = {"PreToolUse", "PostToolUse", "PreInvocation", "PostInvocation", "Stop"}
GROUPED = {"PreToolUse", "PostToolUse"}
# Claude Code events that agy does NOT support; their presence is the exact bug
# that makes agy count the hook but register no handlers.
CLAUDE = {"SessionStart", "SessionEnd", "UserPromptSubmit", "SubagentStart",
          "SubagentStop", "Notification", "PreCompact", "Stop"} - ALLOWED
d = json.load(open(sys.argv[1]))
if not isinstance(d, dict) or not d:
    raise SystemExit("hooks.json must be a non-empty object of named hooks")
if "hooks" in d and isinstance(d["hooks"], dict) and set(d["hooks"]) & (ALLOWED | {"SessionStart"}):
    raise SystemExit('hooks.json uses the Claude {"hooks": {events}} wrapper; agy '
                     'expects TOP-LEVEL NAMED hooks (e.g. {"praxis-telemetry": {...}})')
seen_events = set()
for name, spec in d.items():
    if not isinstance(spec, dict):
        raise SystemExit(f'named hook "{name}" must map to an event object')
    for ev, handlers in spec.items():
        if ev == "enabled":
            continue
        if ev not in ALLOWED:
            raise SystemExit(f'named hook "{name}" declares unsupported event "{ev}" '
                             f'(agy supports only {sorted(ALLOWED)})')
        seen_events.add(ev)
        if not isinstance(handlers, list):
            raise SystemExit(f'"{name}.{ev}" must be a list')
        for h in handlers:
            if ev in GROUPED:
                if "matcher" not in h or "hooks" not in h:
                    raise SystemExit(f'"{name}.{ev}" (grouped) needs matcher + hooks wrapper')
                inner = h["hooks"]
            else:
                inner = [h]  # flat: handler objects directly
            for hh in inner:
                if hh.get("type", "command") != "command":
                    raise SystemExit('only type:"command" hooks are supported by agy')
                if not hh.get("command"):
                    raise SystemExit(f'"{name}.{ev}" handler missing command')
if not seen_events:
    raise SystemExit("hooks.json registers no agy events")
print(f"hooks.json ok: named hooks {sorted(d)}, events {sorted(seen_events)}")
PYHOOK

echo "Antigravity plugin validation passed."
