#!/usr/bin/env bash
# uninstall.sh — Praxis uninstaller
#
# Removes the library from a target. Preserves .project/ memory by default
# (use --purge-memory to also delete it — irreversible).
#
# Usage:
#   ./uninstall.sh                   # → from current dir, Claude Code layout
#   ./uninstall.sh /path/to/repo     # → from that repo
#   ./uninstall.sh --user            # → from ~/.claude/
#   ./uninstall.sh --codex /path     # → Codex layout (removes .team/ + AGENTS.md)
#   ./uninstall.sh --both /path      # → Both layouts
#   ./uninstall.sh --purge-memory /path  # → Also delete .project/ (irreversible)
#   ./uninstall.sh --dry-run /path   # → Print what would happen

set -euo pipefail

MODE="claude-code"
SCOPE="project"
TARGET=""
DRY_RUN=0
PURGE_MEMORY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)           SCOPE="user" ;;
    --codex)          MODE="codex" ;;
    --both)           MODE="both" ;;
    --dry-run)        DRY_RUN=1 ;;
    --purge-memory)   PURGE_MEMORY=1 ;;
    --help|-h)        sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --*)              echo "Unknown flag: $1" >&2; exit 2 ;;
    *)                TARGET="$1" ;;
  esac
  shift
done

if [[ "$SCOPE" == "user" ]]; then
  TARGET="$HOME"
fi
if [[ -z "$TARGET" ]]; then
  TARGET="$(pwd)"
fi

say() { echo "  $*"; }
hdr() { echo; echo "==> $*"; }

rm_path() {
  local p="$1"
  if [[ ! -e "$p" ]]; then
    say "(not present) $p"
    return
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    say "[dry-run] would remove $p"
  else
    rm -rf "$p"
    say "✓ removed $p"
  fi
}

echo "Praxis — uninstaller"
echo "==================================="
say "target: $TARGET"
say "mode:   $MODE"
[[ $DRY_RUN -eq 1 ]] && say "*** DRY RUN ***"
[[ $PURGE_MEMORY -eq 1 ]] && say "*** WILL DELETE .project/ MEMORY ***"

case "$MODE" in
  claude-code|both)
    hdr "Removing Claude Code layout"
    rm_path "$TARGET/.claude"
    ;;
esac
case "$MODE" in
  codex|both)
    hdr "Removing Codex layout"
    rm_path "$TARGET/.team"
    rm_path "$TARGET/AGENTS.md"
    ;;
esac

if [[ $PURGE_MEMORY -eq 1 && "$SCOPE" != "user" ]]; then
  hdr "Purging .project/ memory (irreversible)"
  rm_path "$TARGET/.project"
fi

echo
echo "Done."
