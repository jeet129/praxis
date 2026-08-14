#!/usr/bin/env bash
# install.sh — Praxis installer
#
# Installs the library into a target project for any supported AI coding tool.
# 91 SKILLs · 17 agents · 9 workflows · 12 slash commands · governance · hooks · validator.
#
# Usage:
#   ./install.sh [TARGET]                       # default: claude-code into current dir
#   ./install.sh --tool=<name> [TARGET]         # tool: claude-code | codex | cursor | gemini | opencode | copilot | kiro | antigravity | all
#   ./install.sh --user                         # user-global Claude Code install (~/.claude/)
#   ./install.sh --dry-run [TARGET]             # preview without doing anything
#   ./install.sh --force [TARGET]               # overwrite existing install
#   ./install.sh --help
#
# Examples:
#   ./install.sh ~/dev/my-project                       # Claude Code (default)
#   ./install.sh --tool=cursor ~/dev/my-project         # Cursor
#   ./install.sh --tool=gemini ~/dev/my-project         # Gemini CLI
#   ./install.sh --tool=all ~/dev/my-project            # Every supported tool
#   ./install.sh --dry-run --tool=copilot ~/dev/proj    # Preview Copilot install

set -euo pipefail

# ----------------------------------------------------------------------
# Defaults + arg parsing
# ----------------------------------------------------------------------

TOOL="claude-code"
SCOPE="project"
TARGET=""
DRY_RUN=0
FORCE=0
SKIP_MEMORY=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBRARY_ROOT="$SCRIPT_DIR"

VALID_TOOLS=(claude-code codex cursor gemini opencode copilot kiro antigravity all)

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool=*)         TOOL="${1#--tool=}" ;;
    --tool)           shift; TOOL="$1" ;;
    --codex)          TOOL="codex" ;;             # legacy alias
    --both)           TOOL="all" ;;               # legacy alias (now "all")
    --user)           SCOPE="user"; TOOL="claude-code" ;;
    --dry-run)        DRY_RUN=1 ;;
    --force)          FORCE=1 ;;
    --skip-memory)    SKIP_MEMORY=1 ;;
    --help|-h)        usage ;;
    --*)              echo "Unknown flag: $1" >&2; exit 2 ;;
    *)                TARGET="$1" ;;
  esac
  shift
done

# Validate tool
tool_ok=0
for t in "${VALID_TOOLS[@]}"; do [[ "$t" == "$TOOL" ]] && tool_ok=1; done
if [[ $tool_ok -eq 0 ]]; then
  echo "ERROR: unknown tool: $TOOL" >&2
  echo "Valid: ${VALID_TOOLS[*]}" >&2
  exit 2
fi

# ----------------------------------------------------------------------
# Resolve target
# ----------------------------------------------------------------------

if [[ "$SCOPE" == "user" ]]; then
  TARGET="$HOME"
elif [[ -z "$TARGET" ]]; then
  TARGET="$(pwd)"
fi

if [[ ! -d "$TARGET" ]]; then
  echo "ERROR: target directory does not exist: $TARGET" >&2
  exit 2
fi

# Validate library root
for required in agents skills workflows governance; do
  if [[ ! -d "$LIBRARY_ROOT/$required" ]]; then
    echo "ERROR: $LIBRARY_ROOT doesn't look like the library root (missing $required/)" >&2
    exit 2
  fi
done

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

say() { echo "  $*"; }
hdr() { echo; echo "==> $*"; }

N_AGENTS=$(find "$LIBRARY_ROOT/agents" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')
# Count ACTIVE skills (skip tombstones — SKILL.md files with state: removed)
N_SKILLS=$(grep -L '^state: removed' "$LIBRARY_ROOT/skills"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
N_REMOVED=$(grep -l '^state: removed' "$LIBRARY_ROOT/skills"/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
N_WORKFLOWS=$(find "$LIBRARY_ROOT/workflows" -name '*.yaml' | wc -l | tr -d ' ')

# Copy a list of subdirectories from library to dest. Args: dest, then list.
# Special handling for 'skills/': skips tombstones (state: removed).
copy_subs() {
  local dest="$1"; shift
  for sub in "$@"; do
    if [[ -d "$LIBRARY_ROOT/$sub" ]]; then
      if [[ "$sub" == "skills" ]]; then
        # Filtered copy: skip tombstones
        local skipped=0
        mkdir -p "$dest/skills"
        for skill_dir in "$LIBRARY_ROOT/skills"/*/; do
          local skill_md="$skill_dir/SKILL.md"
          if [[ -f "$skill_md" ]] && grep -q '^state: removed' "$skill_md" 2>/dev/null; then
            skipped=$((skipped + 1))
            continue
          fi
          cp -R "$skill_dir" "$dest/skills/"
        done
        if [[ $skipped -gt 0 ]]; then
          say "✓ copied skills/ ($N_SKILLS active; skipped $skipped tombstones)"
        else
          say "✓ copied skills/"
        fi
      else
        cp -R "$LIBRARY_ROOT/$sub" "$dest/"
        say "✓ copied $sub/"
      fi
    fi
  done
}

# Copy a list of files from library to dest. Args: dest, then list.
copy_files() {
  local dest="$1"; shift
  for f in "$@"; do
    if [[ -f "$LIBRARY_ROOT/$f" ]]; then
      cp "$LIBRARY_ROOT/$f" "$dest/"
      say "✓ copied $f"
    fi
  done
}

check_exists_or_force() {
  local p="$1"
  if [[ -e "$p" && $FORCE -eq 0 ]]; then
    echo "ERROR: $p already exists. Re-run with --force to overwrite." >&2
    exit 3
  fi
}

# ----------------------------------------------------------------------
# Per-tool installers
# ----------------------------------------------------------------------

install_claude_code() {
  local dest="$TARGET/.claude"
  hdr "Installing Claude Code layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest with full library + slash commands + hooks + scripts"; return; fi
  check_exists_or_force "$dest"
  rm -rf "$dest"
  mkdir -p "$dest"
  copy_subs "$dest" agents skills workflows governance patterns references hooks scripts
  copy_files "$dest" README.md PLAYBOOK.md INSTALLATION.md
  # slash commands land at <dest>/commands/ (Claude Code's .claude/commands/)
  if [[ -d "$LIBRARY_ROOT/.claude/commands" ]]; then
    cp -R "$LIBRARY_ROOT/.claude/commands" "$dest/"
    say "✓ copied slash commands ($(ls "$dest/commands" | grep -c '\.md$'): /start /discover /refine-idea /architect /slice /review /release /audit /steward /factory-record)"
  fi
  # .claude-plugin for marketplace installation
  if [[ -d "$LIBRARY_ROOT/.claude-plugin" ]]; then
    cp -R "$LIBRARY_ROOT/.claude-plugin" "$dest/"
    say "✓ copied plugin manifests"
  fi
}

install_codex() {
  local dest="$TARGET/.team"
  hdr "Installing Codex layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest + AGENTS.md at repo root"; return; fi
  check_exists_or_force "$dest"
  rm -rf "$dest"
  mkdir -p "$dest"
  copy_subs "$dest" agents skills workflows governance patterns references hooks scripts
  copy_files "$dest" README.md PLAYBOOK.md INSTALLATION.md
  # AGENTS.md at repo root
  cat > "$TARGET/AGENTS.md" <<'EOF'
# Agents and Skills Index — Praxis

This repo ships the Praxis at `.team/`. Codex / OpenCode / Cursor / Antigravity should consult these files.

## Where things live
- Role agents:    `.team/agents/` (17 agents)
- Skills:         `.team/skills/<skill-name>/SKILL.md` (91 skills)
- Workflows:      `.team/workflows/` (9 workflows)
- Governance:     `.team/governance/governance.yaml`
- References:    `.team/references/`

## Routing by task type
| Task type | Start here |
|---|---|
| Bootstrap new project | `.team/skills/delivery-planner/SKILL.md` |
| New API service | `.team/workflows/greenfield-api-service.yaml` |
| New SaaS product | `.team/workflows/greenfield-saas.yaml` |
| Enhance existing system | `.team/workflows/brownfield-enhancement.yaml` |
| Per-slice implementation | `.team/workflows/implementation-slice.yaml` |
| Release to production | `.team/workflows/production-release.yaml` |
| Quarterly library review | `.team/agents/system-steward.md` |
| ANY non-trivial task | `.team/skills/using-praxis/SKILL.md` (front-door) |

## Project memory
All artifacts under `.project/` per the six-type taxonomy.

## Activation flags
See `.project/semantic/project-charter.md`. If absent, project not bootstrapped.

## Governance
All gates per `.team/governance/governance.yaml`. Solo mode routes to principal.

## Documentation
- `.team/README.md` — library overview
- `.team/PLAYBOOK.md` — operating playbook
EOF
  say "✓ wrote AGENTS.md (repo root)"
}

install_cursor() {
  local dest="$TARGET/.cursor/rules"
  hdr "Installing Cursor layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest with rule pointing to praxis/"; return; fi
  mkdir -p "$dest"
  # Copy our cursor rule
  if [[ -f "$LIBRARY_ROOT/.cursor/rules/000-ai-delivery-platform.md" ]]; then
    cp "$LIBRARY_ROOT/.cursor/rules/000-ai-delivery-platform.md" "$dest/"
    say "✓ wrote cursor rule"
  fi
  # Copy the library to .cursor/praxis/
  local lib_dest="$TARGET/.cursor/praxis"
  check_exists_or_force "$lib_dest"
  rm -rf "$lib_dest"
  mkdir -p "$lib_dest"
  copy_subs "$lib_dest" agents skills workflows governance patterns references
  copy_files "$lib_dest" README.md PLAYBOOK.md
}

install_gemini() {
  local dest="$TARGET/.gemini"
  hdr "Installing Gemini CLI layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest + GEMINI.md at repo root"; return; fi
  check_exists_or_force "$dest"
  rm -rf "$dest"
  mkdir -p "$dest/skills" "$dest/commands"
  # Skills
  if [[ -d "$LIBRARY_ROOT/skills" ]]; then
    cp -R "$LIBRARY_ROOT/skills/." "$dest/skills/"
    say "✓ copied skills/"
  fi
  # Mirror commands
  if [[ -d "$LIBRARY_ROOT/.gemini/commands" ]]; then
    cp -R "$LIBRARY_ROOT/.gemini/commands/." "$dest/commands/"
    say "✓ copied slash commands"
  fi
  # Other content under .gemini for reference
  copy_subs "$dest" agents workflows governance references patterns
  copy_files "$dest" README.md PLAYBOOK.md INSTALLATION.md
  # GEMINI.md at repo root
  if [[ -f "$LIBRARY_ROOT/GEMINI.md" ]]; then
    cp "$LIBRARY_ROOT/GEMINI.md" "$TARGET/"
    say "✓ wrote GEMINI.md (repo root)"
  fi
}

install_opencode() {
  local dest="$TARGET/.opencode"
  hdr "Installing OpenCode layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest + AGENTS.md at repo root (shared with Codex pattern)"; return; fi
  check_exists_or_force "$dest"
  rm -rf "$dest"
  mkdir -p "$dest"
  # OpenCode uses the same AGENTS.md as Codex if not already there
  if [[ ! -f "$TARGET/AGENTS.md" ]]; then
    install_codex  # writes AGENTS.md + .team/
  fi
  copy_files "$dest" /dev/null  # placeholder; copy config below
  if [[ -f "$LIBRARY_ROOT/.opencode/config.json" ]]; then
    cp "$LIBRARY_ROOT/.opencode/config.json" "$dest/"
    say "✓ wrote .opencode/config.json"
  fi
}

install_copilot() {
  local dest="$TARGET/.github"
  hdr "Installing GitHub Copilot layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would write $dest/copilot-instructions.md + agents/"; return; fi
  mkdir -p "$dest/agents"
  # Copy copilot-instructions.md
  if [[ -f "$LIBRARY_ROOT/.github/copilot-instructions.md" ]]; then
    cp "$LIBRARY_ROOT/.github/copilot-instructions.md" "$dest/"
    say "✓ wrote .github/copilot-instructions.md"
  fi
  # Agent personas as Copilot personas
  if [[ -d "$LIBRARY_ROOT/agents" ]]; then
    cp -R "$LIBRARY_ROOT/agents/." "$dest/agents/"
    say "✓ copied agent personas to .github/agents/"
  fi
  # Copy library to .github/praxis/ for skill content access
  local lib_dest="$TARGET/.github/praxis"
  rm -rf "$lib_dest"
  mkdir -p "$lib_dest"
  copy_subs "$lib_dest" skills workflows governance patterns references
  copy_files "$lib_dest" README.md PLAYBOOK.md
}

install_kiro() {
  local dest="$TARGET/.kiro"
  hdr "Installing Kiro layout → $dest"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $dest/skills + AGENTS.md at repo root"; return; fi
  check_exists_or_force "$dest"
  rm -rf "$dest"
  mkdir -p "$dest"
  copy_subs "$dest" skills agents workflows governance patterns references
  copy_files "$dest" README.md PLAYBOOK.md INSTALLATION.md
  # Kiro also supports AGENTS.md
  if [[ ! -f "$TARGET/AGENTS.md" ]]; then
    install_codex  # writes AGENTS.md
  fi
}

install_antigravity() {
  hdr "Installing Antigravity layout → $TARGET"
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would copy library + plugin.json at root"; return; fi
  # Antigravity uses plugin.json at repo root
  if [[ -f "$LIBRARY_ROOT/plugin.json" ]]; then
    cp "$LIBRARY_ROOT/plugin.json" "$TARGET/"
    say "✓ wrote plugin.json (repo root)"
  fi
  # Library lands at root subdirs (skills/, agents/, etc.) — same as Antigravity expects
  for sub in agents skills workflows governance patterns references; do
    if [[ -d "$LIBRARY_ROOT/$sub" && ! -d "$TARGET/$sub" ]]; then
      cp -R "$LIBRARY_ROOT/$sub" "$TARGET/"
      say "✓ copied $sub/"
    fi
  done
  # Antigravity uses commands/ at repo root
  if [[ -d "$LIBRARY_ROOT/.claude/commands" && ! -d "$TARGET/commands" ]]; then
    cp -R "$LIBRARY_ROOT/.claude/commands" "$TARGET/"
    say "✓ copied commands/"
  fi
  copy_files "$TARGET" README.md PLAYBOOK.md
}

# ----------------------------------------------------------------------
# Memory tree (project-scope only)
# ----------------------------------------------------------------------

create_memory_tree() {
  if [[ $SKIP_MEMORY -eq 1 ]] || [[ "$SCOPE" == "user" ]]; then return; fi

  local project_dir="$TARGET/.project"
  hdr "Creating project memory tree → $project_dir"

  if [[ -d "$project_dir" && $FORCE -eq 0 ]]; then
    say "(already exists; leaving in place)"
    return
  fi
  if [[ $DRY_RUN -eq 1 ]]; then say "[dry-run] would create $project_dir (17 subdirs)"; return; fi

  local dirs=(
    "$project_dir/semantic" "$project_dir/episodic" "$project_dir/procedural"
    "$project_dir/decision" "$project_dir/working" "$project_dir/working/architecture"
    "$project_dir/operational" "$project_dir/operational/runbooks"
    "$project_dir/operational/releases" "$project_dir/operational/ml-models"
    "$project_dir/operational/impact-analyses" "$project_dir/operational/factory-metrics"
    "$project_dir/operational/library-evolution" "$project_dir/operational/risk-acceptances"
    "$project_dir/operational/doc-audit" "$project_dir/operational/modernization"
    "$project_dir/operational/architecture-reconciliation"
  )
  for d in "${dirs[@]}"; do mkdir -p "$d"; done
  touch "$project_dir/decision/INDEX.md" "$project_dir/operational/debt-register.md"
  say "✓ memory tree created (17 directories)"
}

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

echo "Praxis — installer"
echo "================================="
say "library root:  $LIBRARY_ROOT"
say "agents:        $N_AGENTS"
say "skills:        $N_SKILLS"
say "workflows:     $N_WORKFLOWS"
say "target:        $TARGET"
say "tool:          $TOOL"
say "scope:         $SCOPE"
[[ $DRY_RUN -eq 1 ]] && say "*** DRY RUN ***"
[[ $FORCE -eq 1 ]] && say "*** FORCE (will overwrite) ***"

case "$TOOL" in
  claude-code)  install_claude_code ;;
  codex)        install_codex ;;
  cursor)       install_cursor ;;
  gemini)       install_gemini ;;
  opencode)     install_opencode ;;
  copilot)      install_copilot ;;
  kiro)         install_kiro ;;
  antigravity)  install_antigravity ;;
  all)
    install_claude_code
    install_codex
    install_cursor
    install_gemini
    install_opencode
    install_copilot
    install_kiro
    install_antigravity
    ;;
esac

create_memory_tree

# ----------------------------------------------------------------------
# Next steps
# ----------------------------------------------------------------------

hdr "Done."

if [[ $DRY_RUN -eq 1 ]]; then
  say "Dry run complete. Re-run without --dry-run to actually install."
  exit 0
fi

cat <<EOF

Next steps:

1. Open the project in your tool:
EOF

case "$TOOL" in
  claude-code|all)  echo "   • Claude Code:  cd $TARGET && claude" ;;
esac
case "$TOOL" in
  codex|all)        echo "   • Codex:        cd $TARGET && codex" ;;
esac
case "$TOOL" in
  cursor|all)       echo "   • Cursor:       cd $TARGET && cursor ." ;;
esac
case "$TOOL" in
  gemini|all)       echo "   • Gemini CLI:   cd $TARGET && gemini" ;;
esac
case "$TOOL" in
  opencode|all)     echo "   • OpenCode:     cd $TARGET && opencode" ;;
esac
case "$TOOL" in
  copilot|all)      echo "   • GitHub Copilot: open the repo in your IDE; Copilot reads .github/copilot-instructions.md automatically" ;;
esac
case "$TOOL" in
  kiro|all)         echo "   • Kiro:         cd $TARGET && kiro" ;;
esac
case "$TOOL" in
  antigravity|all)  echo "   • Antigravity:  cd $TARGET && agy" ;;
esac

cat <<EOF

2. Sanity check (paste into the assistant):

   "Confirm you can see the Praxis. Then read
    skills/using-praxis/SKILL.md (the front-door)
    and summarize active governance gates."

3. Bootstrap the project (run once):

   /start  (Claude Code, Gemini, Antigravity slash command)

   OR paste:
   "Run delivery-planner. Capture the charter at
    .project/semantic/project-charter.md."

4. Full operating guide: PLAYBOOK.md in the install destination.

5. Per-tool setup notes: docs/<tool>-setup.md

EOF
