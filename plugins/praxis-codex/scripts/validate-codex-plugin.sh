#!/usr/bin/env bash
# Validate the generated Praxis Codex plugin package.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN="$ROOT/plugins/praxis-codex"
MARKETPLACE="$ROOT/.agents/plugins/marketplace.json"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ -f "$MARKETPLACE" ]] || fail "missing marketplace: $MARKETPLACE"
[[ -d "$PLUGIN" ]] || fail "missing plugin directory: $PLUGIN"
[[ -f "$PLUGIN/.codex-plugin/plugin.json" ]] || fail "missing Codex plugin manifest"
[[ -d "$PLUGIN/skills" ]] || fail "missing plugin skills directory"
[[ -d "$PLUGIN/workflows" ]] || fail "missing plugin workflows directory"
[[ -d "$PLUGIN/codex-agents" ]] || fail "missing plugin codex-agents directory"

python3 - "$MARKETPLACE" "$PLUGIN/.codex-plugin/plugin.json" "$PLUGIN/codex-agents" <<'PY'
import json
import pathlib
import sys

marketplace_path = pathlib.Path(sys.argv[1])
plugin_json_path = pathlib.Path(sys.argv[2])
agents_dir = pathlib.Path(sys.argv[3])

marketplace = json.loads(marketplace_path.read_text())
plugins = marketplace.get("plugins", [])
entry = next((p for p in plugins if p.get("name") == "praxis-codex"), None)
if not entry:
    raise SystemExit("marketplace missing praxis-codex entry")
if entry.get("source", {}).get("path") != "./plugins/praxis-codex":
    raise SystemExit("marketplace praxis-codex source.path must be ./plugins/praxis-codex")
if entry.get("policy", {}).get("installation") != "AVAILABLE":
    raise SystemExit("marketplace praxis-codex policy.installation must be AVAILABLE")
if entry.get("policy", {}).get("authentication") != "ON_INSTALL":
    raise SystemExit("marketplace praxis-codex policy.authentication must be ON_INSTALL")
if not entry.get("category"):
    raise SystemExit("marketplace praxis-codex category is required")

manifest = json.loads(plugin_json_path.read_text())
for field in ("name", "version", "description", "skills"):
    if not manifest.get(field):
        raise SystemExit(f"plugin manifest missing {field}")
if manifest["name"] != "praxis-codex":
    raise SystemExit("plugin manifest name must be praxis-codex")

required_agents = {
    "product-manager",
    "solution-architect",
    "architecture-challenger",
    "delivery-lead",
    "lead-developer",
    "backend-developer",
    "frontend-developer",
    "mobile-developer",
    "data-engineer",
    "ml-ai-engineer",
    "platform-sre",
    "qa-engineer",
    "code-reviewer",
    "security-reviewer",
    "tech-writer",
    "ux-designer",
    "system-steward",
}
for name in sorted(required_agents):
    path = agents_dir / f"{name}.toml"
    if not path.exists():
        raise SystemExit(f"missing Codex agent profile: {path}")
    text = path.read_text()
    for field in ("name", "description", "developer_instructions"):
        if f"{field} =" not in text:
            raise SystemExit(f"{path} missing {field}")
PY

for skill in \
  praxis-start \
  praxis-discover \
  praxis-architect \
  praxis-audit \
  praxis-slice \
  praxis-release \
  praxis-steward \
  praxis-review \
  praxis-setup-subagents
do
  [[ -f "$PLUGIN/skills/$skill/SKILL.md" ]] || fail "missing Codex command skill: $skill"
done

bash "$ROOT/scripts/validate-skills.sh" "$PLUGIN" >/tmp/praxis-codex-skill-validation.out
ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f) }' "$PLUGIN"/workflows/*.yaml "$PLUGIN"/governance/*.yaml

[[ -f "$ROOT/.claude-plugin/plugin.json" ]] || fail "Claude plugin manifest was removed"
[[ -d "$ROOT/.claude/commands" ]] || fail "Claude commands directory was removed"
[[ -d "$ROOT/commands" ]] || fail "root commands directory was removed"

cat /tmp/praxis-codex-skill-validation.out
echo "Codex plugin validation passed."
