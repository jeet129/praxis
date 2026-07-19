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
[[ -f "$PLUGIN/hooks/hooks.json" ]] || fail "missing packaged hooks/hooks.json"
grep -q '"hooks"' "$PLUGIN/.codex-plugin/plugin.json" || fail "packaged plugin.json missing \"hooks\" key"

# Codex hook-event vocabulary. Codex has NO `SessionEnd` (its turn-scoped
# `Stop` is the analog); shipping an unsupported event name in the Codex
# package is a silent no-op that would drop end-of-session token capture.
# Allowlist per the Codex hooks reference; reject anything outside it, and
# require `Stop` (so token capture is actually wired for Codex).
python3 - "$PLUGIN/hooks/hooks.json" <<'PY'
import json, sys
supported = {
    "SessionStart", "SubagentStart", "PreToolUse", "PermissionRequest",
    "PostToolUse", "PreCompact", "PostCompact", "UserPromptSubmit",
    "SubagentStop", "Stop",
}
events = set(json.load(open(sys.argv[1])).get("hooks", {}))
bad = sorted(events - supported)
if bad:
    raise SystemExit(
        "packaged hooks/hooks.json registers Codex-unsupported event(s): "
        + ", ".join(bad)
        + " (Codex has no SessionEnd — use Stop). Rebuild via scripts/build-codex-plugin.sh."
    )
if "Stop" not in events:
    raise SystemExit(
        "packaged hooks/hooks.json missing the `Stop` event — Codex end-of-turn "
        "token capture is not wired. Rebuild via scripts/build-codex-plugin.sh."
    )
PY

# No fabricated `codex --agent` invocation syntax anywhere in the packaged
# skills/codex-agents or the source overlay — Codex has no such flag.
for scan_dir in "$PLUGIN/skills" "$PLUGIN/codex-agents" "$ROOT/codex-plugin-assets"; do
  if [[ -d "$scan_dir" ]] && grep -rq -- 'codex --agent ' "$scan_dir" 2>/dev/null; then
    fail "fabricated 'codex --agent' syntax found under $scan_dir"
  fi
done

# governance/autonomy.yaml codex harness must declare real-usage-capture keys.
AUTONOMY_YAML="$ROOT/governance/autonomy.yaml"
[[ -f "$AUTONOMY_YAML" ]] || fail "missing $AUTONOMY_YAML"
awk '
  /^  codex:/ { in_codex=1; next }
  in_codex && /^  [a-zA-Z0-9_-]+:/ { in_codex=0 }
  in_codex && /json_output_flag:/ { have_flag=1 }
  in_codex && /usage_parse:[[:space:]]*codex-json/ { have_parse=1 }
  END {
    if (!have_flag) { print "governance/autonomy.yaml codex harness missing json_output_flag"; exit 1 }
    if (!have_parse) { print "governance/autonomy.yaml codex harness missing usage_parse: codex-json"; exit 1 }
  }
' "$AUTONOMY_YAML" || fail "governance/autonomy.yaml codex harness real-usage-capture keys check failed"

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
  praxis-intake \
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

# Respect TMPDIR; fall back to /tmp only when it's writable, else a repo-local
# scratch dir — hardcoding /tmp breaks on sandboxes where /tmp is locked.
SKILL_VAL_OUT="$(mktemp "${TMPDIR:-/tmp}/praxis-codex-skill-validation.XXXXXX" 2>/dev/null \
  || mktemp "$ROOT/.praxis-codex-skill-validation.XXXXXX")"
trap 'rm -f "$SKILL_VAL_OUT"' EXIT
bash "$ROOT/scripts/validate-skills.sh" "$PLUGIN" >"$SKILL_VAL_OUT"
ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f) }' "$PLUGIN"/workflows/*.yaml "$PLUGIN"/governance/*.yaml

# Generated-package freshness (the stale-mirror class the reviewer hit):
# key canonical files must be present in the mirror AND byte-identical.
[[ -f "$PLUGIN/references/phase-gates.md" ]] || fail "mirror is stale: references/phase-gates.md missing from plugins/praxis-codex/ — run scripts/build-codex-plugin.sh"
for _f in scripts/praxis-drive.sh skills/autonomous-drive/SKILL.md references/loop-contracts.md; do
  if [[ -f "$ROOT/$_f" ]]; then
    diff -q "$ROOT/$_f" "$PLUGIN/$_f" >/dev/null 2>&1 \
      || fail "mirror is stale/diverged: $_f differs from canonical — run scripts/build-codex-plugin.sh and commit the result"
  fi
done

[[ -f "$ROOT/.claude-plugin/plugin.json" ]] || fail "Claude plugin manifest was removed"
[[ -d "$ROOT/.claude/commands" ]] || fail "Claude commands directory was removed"
[[ -d "$ROOT/commands" ]] || fail "root commands directory was removed"

cat "$SKILL_VAL_OUT"
echo "Codex plugin validation passed."
