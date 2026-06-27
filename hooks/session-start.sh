#!/usr/bin/env bash
# session-start.sh — Praxis session-start hook
#
# Surfaces the project context at session start. Fires when Claude Code
# opens a session in a directory where this hook is installed.
#
# Output is written to stderr (per Claude Code hook contract); appears in
# the user's session prelude.

set -u

# ----------------------------------------------------------------------
# Locate the project root + the platform install
# ----------------------------------------------------------------------

PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
PROJECT_DIR="$PROJECT_ROOT/.project"

# Find the library install (either project-local or user-global)
LIBRARY_ROOT=""
if [[ -d "$PROJECT_ROOT/.claude/skills" ]]; then
  LIBRARY_ROOT="$PROJECT_ROOT/.claude"
elif [[ -d "$HOME/.claude/skills" ]]; then
  LIBRARY_ROOT="$HOME/.claude"
fi

# ----------------------------------------------------------------------
# Output banner
# ----------------------------------------------------------------------

{
  echo "================================================================"
  echo "  Praxis — session start"
  echo "================================================================"
} >&2

# Charter
if [[ -f "$PROJECT_DIR/semantic/project-charter.md" ]]; then
  {
    echo ""
    echo "Project charter (from .project/semantic/project-charter.md):"
    head -40 "$PROJECT_DIR/semantic/project-charter.md" | sed 's/^/  /'
  } >&2
else
  {
    echo ""
    echo "⚠️  No project charter found. Run /start to bootstrap."
  } >&2
fi

# Active workflow
if [[ -f "$PROJECT_DIR/working/active-workflow.md" ]]; then
  {
    echo ""
    echo "Active workflow:"
    head -10 "$PROJECT_DIR/working/active-workflow.md" | sed 's/^/  /'
  } >&2
fi

# Library counts (only if library is installed)
if [[ -n "$LIBRARY_ROOT" ]]; then
  N_SKILLS=$(find "$LIBRARY_ROOT/skills" -name SKILL.md 2>/dev/null | wc -l | tr -d ' ')
  N_AGENTS=$(find "$LIBRARY_ROOT/agents" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  N_WORKFLOWS=$(find "$LIBRARY_ROOT/workflows" -name '*.yaml' 2>/dev/null | wc -l | tr -d ' ')
  {
    echo ""
    echo "Library loaded: $N_SKILLS skills · $N_AGENTS agents · $N_WORKFLOWS workflows"
    echo "  (target health band: 70-90 skills; review at 91+; consolidate at 101+)"
  } >&2
fi

# Recent ADRs (last 5)
if [[ -d "$PROJECT_DIR/decision" ]]; then
  RECENT=$(ls -t "$PROJECT_DIR/decision/"*.md 2>/dev/null | head -5)
  if [[ -n "$RECENT" ]]; then
    {
      echo ""
      echo "Recent decisions (ADRs):"
      echo "$RECENT" | xargs -I{} basename {} | sed 's/^/  · /'
    } >&2
  fi
fi

# Open debt items (count)
if [[ -f "$PROJECT_DIR/operational/debt-register.md" ]]; then
  N_DEBT=$(grep -c "^## DEBT-" "$PROJECT_DIR/operational/debt-register.md" 2>/dev/null || echo 0)
  if [[ "$N_DEBT" -gt 0 ]]; then
    {
      echo ""
      echo "Debt register: $N_DEBT items (per tech-debt-management)"
    } >&2
  fi
fi

# Quarterly steward cadence check
if [[ -d "$PROJECT_DIR/operational/factory-metrics" ]]; then
  LATEST_FACTORY=$(ls -t "$PROJECT_DIR/operational/factory-metrics/"*.md 2>/dev/null | head -1)
  if [[ -n "$LATEST_FACTORY" ]]; then
    AGE_DAYS=$(( ( $(date +%s) - $(stat -f %m "$LATEST_FACTORY" 2>/dev/null || stat -c %Y "$LATEST_FACTORY" 2>/dev/null) ) / 86400 ))
    if [[ "$AGE_DAYS" -gt 90 ]]; then
      {
        echo ""
        echo "⚠️  Quarterly steward cadence overdue ($AGE_DAYS days since last factory report). Run /steward."
      } >&2
    fi
  fi
fi

# Slash command reminder
{
  echo ""
  echo "Slash commands: /start  /discover  /architect  /slice  /release  /audit  /steward"
  echo "Front-door SKILL: using-praxis"
  echo "================================================================"
  echo ""
} >&2

exit 0
