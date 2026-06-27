#!/usr/bin/env bash
# try-as-plugin.sh — launch Claude Code with this library as a loaded plugin
#
# Path 1 from INSTALLATION.md §7: tests the library as a plugin WITHOUT
# packaging it as a .plugin file or publishing to a marketplace.
#
# Claude Code reads the directory directly; slash commands, hooks, agents,
# and skills all activate.
#
# Usage:
#   ./try-as-plugin.sh                       # launch Claude in current dir
#   ./try-as-plugin.sh /path/to/your-project # launch Claude in target dir
#   ./try-as-plugin.sh --init /path/to/proj  # init .project/ memory tree + launch
#   ./try-as-plugin.sh --dry-run /path       # show what would happen
#   ./try-as-plugin.sh --help
#
# What it does:
#   1. Locates the library directory (this script's parent).
#   2. Optionally creates the .project/ memory tree in the target.
#   3. Runs: claude --plugin-dir <library>
#      from inside the target project.
#
# Why this path:
#   - Works today with zero packaging.
#   - The library directory IS the plugin; Claude Code reads it as-is.
#   - Updates to the library propagate immediately (no reinstall).
#   - Easy to switch back; nothing was installed in the project.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBRARY_ROOT="$SCRIPT_DIR"

TARGET=""
DRY_RUN=0
INIT_MEMORY=0

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)  DRY_RUN=1 ;;
    --init)     INIT_MEMORY=1 ;;
    --help|-h)  usage ;;
    --*)        echo "Unknown flag: $1" >&2; exit 2 ;;
    *)          TARGET="$1" ;;
  esac
  shift
done

# Default target
if [[ -z "$TARGET" ]]; then
  TARGET="$(pwd)"
fi

if [[ ! -d "$TARGET" ]]; then
  echo "ERROR: target directory does not exist: $TARGET" >&2
  exit 2
fi

# Validate library root
for required in agents skills workflows governance commands .claude-plugin; do
  if [[ ! -d "$LIBRARY_ROOT/$required" ]] && [[ ! -e "$LIBRARY_ROOT/$required" ]]; then
    echo "ERROR: $LIBRARY_ROOT doesn't look like the library root (missing $required/)" >&2
    exit 2
  fi
done

# Verify claude CLI is available
if ! command -v claude &> /dev/null && [[ $DRY_RUN -eq 0 ]]; then
  echo "ERROR: 'claude' command not found in PATH." >&2
  echo "Install Claude Code first: https://docs.claude.com" >&2
  exit 2
fi

# Counts (for the banner)
N_AGENTS=$(find "$LIBRARY_ROOT/agents" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
N_SKILLS=$(grep -L '^state: removed' "$LIBRARY_ROOT/skills"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
N_WORKFLOWS=$(find "$LIBRARY_ROOT/workflows" -name '*.yaml' | wc -l | tr -d ' ')
N_COMMANDS=$(find "$LIBRARY_ROOT/commands" -name '*.toml' | wc -l | tr -d ' ')

echo "Praxis — plugin-dir test launcher"
echo "==============================================="
echo "  library:     $LIBRARY_ROOT"
echo "  target:      $TARGET"
echo "  agents:      $N_AGENTS"
echo "  skills:      $N_SKILLS"
echo "  workflows:   $N_WORKFLOWS"
echo "  commands:    $N_COMMANDS"
echo ""

# Init memory tree if requested
if [[ $INIT_MEMORY -eq 1 ]]; then
  PROJECT_DIR="$TARGET/.project"
  echo "==> Initializing .project/ memory tree → $PROJECT_DIR"
  if [[ -d "$PROJECT_DIR" ]]; then
    echo "  (already exists; leaving in place)"
  elif [[ $DRY_RUN -eq 1 ]]; then
    echo "  [dry-run] would create 17 subdirs under $PROJECT_DIR"
  else
    mkdir -p "$PROJECT_DIR"/{semantic,episodic,procedural,decision,working/architecture}
    mkdir -p "$PROJECT_DIR"/operational/{runbooks,releases,ml-models,impact-analyses,factory-metrics,library-evolution,risk-acceptances,doc-audit,modernization,architecture-reconciliation}
    touch "$PROJECT_DIR/decision/INDEX.md" "$PROJECT_DIR/operational/debt-register.md"
    echo "  ✓ memory tree created (17 directories)"
  fi
  echo ""
fi

# Launch Claude Code with plugin
echo "==> Launching Claude Code"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "  [dry-run] would run: cd $TARGET && claude --plugin-dir $LIBRARY_ROOT"
  echo ""
  echo "Dry run complete. Re-run without --dry-run to launch."
  exit 0
fi

echo "  cd $TARGET && claude --plugin-dir $LIBRARY_ROOT"
echo ""
echo "Once Claude is open, sanity-check by pasting:"
echo ""
cat <<'EOF'
   Confirm the Praxis is loaded as a plugin. Specifically:

   1. List the slash commands you see (expect 7: /start /discover /architect
      /slice /release /audit /steward).
   2. Read the front-door SKILL — using-praxis — and summarize
      the intent → workflow routing.
   3. List the 16 agents grouped by tier.

   If anything is missing, report it.
EOF
echo ""
echo "Then try /start to bootstrap the project."
echo ""

cd "$TARGET" && exec claude --plugin-dir "$LIBRARY_ROOT"
