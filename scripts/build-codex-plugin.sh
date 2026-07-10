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
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
src = Path(sys.argv[2])
out = Path(sys.argv[3])

if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
(out / ".codex-plugin").mkdir()

for name in ("skills", "agents", "workflows", "governance", "references", "patterns", "scripts"):
    source = root / name
    if source.exists():
        shutil.copytree(source, out / name, ignore=shutil.ignore_patterns(".DS_Store"), dirs_exist_ok=True)

command_skills = src / "skills"
if command_skills.exists():
    for skill in command_skills.iterdir():
        if skill.is_dir():
            dest = out / "skills" / skill.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(skill, dest, ignore=shutil.ignore_patterns(".DS_Store"), dirs_exist_ok=True)

codex_agents = src / "codex-agents"
if codex_agents.exists():
    shutil.copytree(codex_agents, out / "codex-agents", ignore=shutil.ignore_patterns(".DS_Store"), dirs_exist_ok=True)
PY

cat > "$OUT/.codex-plugin/plugin.json" <<'JSON'
{
  "name": "praxis-codex",
  "version": "1.0.0",
  "description": "Praxis for Codex: agentic development platform for end-to-end software and product delivery.",
  "skills": "./skills/"
}
JSON

cat > "$OUT/README.md" <<'EOF'
# Praxis Codex Plugin

**GENERATED PACKAGE — DO NOT EDIT. Edit the repository root and rebuild.**

Generated package for installing Praxis as a Codex plugin.

Source of truth lives at the repository root. Rebuild this package with:

```bash
scripts/build-codex-plugin.sh
```
EOF

touch "$OUT/.generated-by-praxis-codex-build"

echo "Built Codex plugin package: $OUT"
