#!/usr/bin/env bash
# install-git-hooks.sh — one-time setup to activate the repo-tracked pre-commit hook
#
# Points git at .githooks/ (the tracked directory) so every commit runs the
# praxis pre-commit hook. Idempotent — safe to run multiple times.
#
# Run once per clone:
#   scripts/install-git-hooks.sh

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "ERROR: not inside a git repository" >&2
  exit 1
}

cd "$REPO_ROOT"

if [[ ! -d .githooks ]]; then
  echo "ERROR: .githooks directory not found in $REPO_ROOT" >&2
  echo "       This script must be run from a checkout of the praxis repository." >&2
  exit 1
fi

# Make sure the hooks are executable (git preserves the executable bit but
# fresh clones on some file systems might not honor it)
find .githooks -type f -exec chmod +x {} \;

# Point git at the tracked hooks directory
git config core.hooksPath .githooks

echo ""
echo "✓ praxis git hooks installed."
echo ""
echo "  core.hooksPath: $(git config --get core.hooksPath)"
echo "  Hooks active:   $(ls .githooks | tr '\n' ' ')"
echo ""
echo "From now on, every commit will:"
echo "  1. Rebuild plugins/praxis-codex/ if canonical or Codex source changed."
echo "  2. Validate the rebuilt package."
echo "  3. Auto-stage regenerated files so they land atomically with the source."
echo ""
echo "To disable temporarily:"
echo "  git commit --no-verify"
echo ""
echo "To disable permanently for this clone:"
echo "  git config --unset core.hooksPath"
echo ""
