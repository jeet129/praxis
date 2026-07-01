#!/usr/bin/env bash
# validate-manifests.sh — verify all plugin manifests are well-formed
#
# Checks all .json manifest files for:
#   - Valid JSON parse
#   - No empty-string URL fields (Claude Code's plugin validator rejects these)
#   - Required fields present (name, version, description for plugin.json)
#
# Run before `git push` to catch manifest issues that would fail at install time.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."

MANIFESTS=(
  "$ROOT/plugin.json"
  "$ROOT/.claude-plugin/plugin.json"
  "$ROOT/.claude-plugin/marketplace.json"
)

failures=0

echo "Praxis — plugin manifest validator"
echo "==================================="
echo ""

for f in "${MANIFESTS[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "  ⚠️  skipping (file not found): $f"
    continue
  fi

  rel="${f#$ROOT/}"
  echo "Checking $rel"

  # 1. JSON parses cleanly
  if ! python3 -m json.tool "$f" > /dev/null 2>&1; then
    echo "  ✗ INVALID JSON"
    failures=$((failures + 1))
    continue
  fi

  # 2. No empty-string URL fields
  empty_urls=$(python3 -c "
import json, sys
with open('$f') as fp: d = json.load(fp)
def check(obj, path=''):
    issues = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f'{path}.{k}' if path else k
            if k in ('homepage', 'url', 'documentation', 'repository') and isinstance(v, str) and v == '':
                issues.append(new_path)
            issues.extend(check(v, new_path))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            issues.extend(check(x, f'{path}[{i}]'))
    return issues
issues = check(d)
print('|'.join(issues))
")
  if [[ -n "$empty_urls" ]]; then
    echo "  ✗ empty URL fields: $empty_urls"
    echo "     (Claude Code's plugin validator rejects empty-string URLs)"
    failures=$((failures + 1))
  else
    echo "  ✓ no empty URL fields"
  fi

  # 3. Required fields per file type
  case "$rel" in
    plugin.json|.claude-plugin/plugin.json)
      missing=$(python3 -c "
import json
with open('$f') as fp: d = json.load(fp)
required = ['name', 'version', 'description']
missing = [k for k in required if k not in d or not d[k]]
print('|'.join(missing))
")
      if [[ -n "$missing" ]]; then
        echo "  ✗ missing required fields: $missing"
        failures=$((failures + 1))
      else
        echo "  ✓ required fields present (name, version, description)"
      fi
      ;;
    .claude-plugin/marketplace.json)
      missing=$(python3 -c "
import json
with open('$f') as fp: d = json.load(fp)
required = ['name', 'description', 'plugins']
missing = [k for k in required if k not in d or not d[k]]
print('|'.join(missing))
")
      if [[ -n "$missing" ]]; then
        echo "  ✗ missing required fields: $missing"
        failures=$((failures + 1))
      else
        echo "  ✓ required fields present (name, description, plugins)"
      fi
      ;;
  esac

  echo ""
done

if [[ $failures -gt 0 ]]; then
  echo "Summary: $failures manifest(s) failed validation"
  exit 1
fi

echo "✓ All manifests valid"
exit 0
