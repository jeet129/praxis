#!/usr/bin/env bash
# Materialize project-local Claude agents that honor THIS project's routing.
#
# Claude Code loads `agents/*.md` from the plugin (shared across projects), so a
# project-level `.project/governance/model-routing.yaml` override normally can't
# change the model a subagent spawns on OUTSIDE the drive loop. This writes
# project-local `.claude/agents/*.md` — which shadow the plugin agents — with
# each agent's `model:`/`effort:` frontmatter resolved from the EFFECTIVE
# routing table (project override first, plugin default fallback). Result:
# no-drive interactive spawns route the same as the drive loop.
#
# Only needed if you keep a project-level routing override (force_tier, a custom
# tier->model map, pinned models). Without an override the plugin defaults are
# already correct and you can skip this. Re-run after changing the override.
#
# Usage: scripts/setup-claude-agents.sh [PROJECT_DIR]   (default: current dir)

set -euo pipefail

PROJECT_DIR="${1:-$PWD}"
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v python3 >/dev/null 2>&1 || { echo "setup-claude-agents: python3 required." >&2; exit 2; }

override="$PROJECT_DIR/.project/governance/model-routing.yaml"
if [[ -f "$override" ]]; then
  echo "Using project routing override: $override"
else
  echo "No project override found — resolving from plugin defaults (project-local agents will match the plugin)."
fi

python3 "$PLUGIN_ROOT/scripts/apply-model-routing.py" \
  --project-dir "$PROJECT_DIR" \
  --claude-out "$PROJECT_DIR/.claude/agents"

echo
echo "Project-local Claude agents written to $PROJECT_DIR/.claude/agents/ (they shadow the plugin agents)."
echo "Start a new Claude Code session so they load. Re-run this after editing .project/governance/model-routing.yaml."
