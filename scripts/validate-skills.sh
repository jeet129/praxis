#!/usr/bin/env bash
# validate-skills.sh — structural validator for the Praxis library
#
# Each SKILL.md has:
#   - YAML frontmatter with ONLY name + description
#     (this is what Claude Code's plugin loader accepts; extra fields break it)
#   - A `<!-- praxis:metadata:begin --> ... <!-- praxis:metadata:end -->` block
#     in the body containing a YAML code fence with the orchestration metadata
#     (capability, domain, state, dependencies, triggers, outputs, consumers, references)
#
# Why two-tier: Claude Code's plugin skill loader silently rejects SKILLs whose
# frontmatter contains unknown fields. Praxis's internal skill-registry needs
# extended metadata. The body block carries it without breaking the loader.
#
# Usage:
#   ./scripts/validate-skills.sh           # validate this repo's skills/
#   ./scripts/validate-skills.sh /path     # validate a specific library root
#   VERBOSE=1 ./scripts/validate-skills.sh # show warnings too
#
# Exits non-zero if any skill fails validation. Suitable for CI.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBRARY_ROOT="${1:-$SCRIPT_DIR/..}"
SKILLS_DIR="$LIBRARY_ROOT/skills"

if [[ ! -d "$SKILLS_DIR" ]]; then
  echo "ERROR: skills directory not found: $SKILLS_DIR" >&2
  exit 2
fi

# Required frontmatter fields (Claude Code-compatible)
FM_REQUIRED=(name description)

# Required metadata fields (in the body's yaml block)
META_REQUIRED=(capability domain state)

# Recommended metadata fields (warn if missing)
META_RECOMMENDED=(dependencies triggers outputs consumers references)

# Valid state values
VALID_STATES=(experimental active deprecated merged removed)

# Counters
N_TOTAL=0
N_PASS=0
N_FAIL=0
N_WARN=0
N_REMOVED=0      # tombstones (state: removed)
N_ACTIVE=0       # what counts toward 70-90 health band
N_COMMAND_ADAPTERS=0  # capability: command entry points; excluded from the band
FAILURES=()
WARNINGS=()
LINE_BUDGET_WARNINGS=()

echo "Praxis — skill validator"
echo "======================================="
echo "Library: $LIBRARY_ROOT"
echo ""

for skill_md in "$SKILLS_DIR"/*/SKILL.md; do
  N_TOTAL=$((N_TOTAL + 1))
  skill_name=$(basename "$(dirname "$skill_md")")
  skill_failed=0
  skill_warned=0

  # 0. Line budget: SKILL.md over 460 lines is an error (too large to load
  #    efficiently as context), over 300 is a warning worth trimming.
  line_count=$(wc -l < "$skill_md" | tr -d ' ')
  if [[ "$line_count" -gt 460 ]]; then
    FAILURES+=("$skill_name: SKILL.md is $line_count lines (over the 460-line hard limit)")
    skill_failed=1
  elif [[ "$line_count" -gt 300 ]]; then
    WARNINGS+=("$skill_name: SKILL.md is $line_count lines (over the 300-line soft budget)")
    LINE_BUDGET_WARNINGS+=("$skill_name: SKILL.md is $line_count lines (over the 300-line soft budget)")
    skill_warned=1
  fi

  # Extract frontmatter (between first two --- markers)
  frontmatter=$(awk '/^---$/{flag=!flag; if(!flag)exit; next} flag' "$skill_md")

  if [[ -z "$frontmatter" ]]; then
    FAILURES+=("$skill_name: no frontmatter found")
    N_FAIL=$((N_FAIL + 1))
    continue
  fi

  # 1. Frontmatter validation: must have ONLY name + description
  fm_keys=$(echo "$frontmatter" | grep -E "^[a-zA-Z_][a-zA-Z0-9_-]*:" | sed 's/:.*//' | sort -u)
  for required in "${FM_REQUIRED[@]}"; do
    if ! echo "$fm_keys" | grep -qx "$required"; then
      FAILURES+=("$skill_name: frontmatter missing required field '$required'")
      skill_failed=1
    fi
  done

  # Reject any non-allowed frontmatter keys (Claude Code rejects them silently)
  while read -r key; do
    [[ -z "$key" ]] && continue
    case "$key" in
      name|description) ;;
      *)
        FAILURES+=("$skill_name: frontmatter has disallowed field '$key' (move to body metadata block)")
        skill_failed=1
        ;;
    esac
  done <<< "$fm_keys"

  # 2. Name matches directory
  declared_name=$(echo "$frontmatter" | grep "^name:" | head -1 | sed 's/^name: *//' | tr -d '"')
  if [[ -n "$declared_name" && "$declared_name" != "$skill_name" ]]; then
    FAILURES+=("$skill_name: declared name '$declared_name' doesn't match directory")
    skill_failed=1
  fi

  # 3. Extract body metadata YAML block (between the markers)
  metadata=$(awk '
    /<!-- praxis:metadata:begin -->/{flag=1; next}
    /<!-- praxis:metadata:end -->/{flag=0; exit}
    flag {
      # strip the ```yaml and ``` fences
      if (/^```/) next
      print
    }
  ' "$skill_md")

  if [[ -z "$metadata" ]]; then
    FAILURES+=("$skill_name: no praxis:metadata block in body")
    skill_failed=1
  else
    # 4. Check required metadata fields
    for required in "${META_REQUIRED[@]}"; do
      if ! echo "$metadata" | grep -q "^$required:"; then
        FAILURES+=("$skill_name: metadata block missing required field '$required'")
        skill_failed=1
      fi
    done

    # 5. Validate state
    declared_state=$(echo "$metadata" | grep "^state:" | head -1 | sed 's/^state: *//' | tr -d '"')
    if [[ -n "$declared_state" ]]; then
      state_ok=0
      for s in "${VALID_STATES[@]}"; do
        [[ "$s" == "$declared_state" ]] && state_ok=1
      done
      if [[ $state_ok -eq 0 ]]; then
        FAILURES+=("$skill_name: invalid state '$declared_state' (must be one of: ${VALID_STATES[*]})")
        skill_failed=1
      fi
    fi

    # Tombstone handling (shouldn't appear in skills/ anymore; archived to archive/skills/)
    if [[ "$declared_state" == "removed" ]]; then
      N_REMOVED=$((N_REMOVED + 1))
      WARNINGS+=("$skill_name: tombstone (state: removed) found inside skills/ — should live in archive/skills/")
      skill_warned=1
      if [[ $skill_failed -eq 0 ]]; then
        N_PASS=$((N_PASS + 1))
      else
        N_FAIL=$((N_FAIL + 1))
      fi
      N_WARN=$((N_WARN + skill_warned))
      continue
    fi

    # Command-entry adapter skills (capability: command — e.g. the Codex
    # $praxis-* commands) are validated like any skill but do NOT count
    # toward the 70-90 knowledge-skill health band: they are thin entry
    # points, not knowledge, and scale with harness count by design.
    if echo "$metadata" | grep -q "^capability: command$"; then
      N_COMMAND_ADAPTERS=$((N_COMMAND_ADAPTERS + 1))
    else
      N_ACTIVE=$((N_ACTIVE + 1))
    fi

    # 6. Recommended metadata fields (warnings)
    for field in "${META_RECOMMENDED[@]}"; do
      if ! echo "$metadata" | grep -q "^$field:"; then
        WARNINGS+=("$skill_name: metadata missing recommended field '$field'")
        skill_warned=1
      fi
    done

    # 7. Description quality: should contain "Use when" trigger phrase
    declared_desc=$(echo "$frontmatter" | grep "^description:" | head -1)
    if ! echo "$declared_desc" | grep -qi "use when\|use whenever"; then
      WARNINGS+=("$skill_name: description lacks 'Use when' trigger phrase")
      skill_warned=1
    fi
  fi

  if [[ $skill_failed -eq 0 ]]; then
    N_PASS=$((N_PASS + 1))
  else
    N_FAIL=$((N_FAIL + 1))
  fi
  if [[ $skill_warned -eq 1 ]]; then
    N_WARN=$((N_WARN + 1))
  fi
done

# Output report
echo "Summary"
echo "-------"
echo "  Total SKILL.md files: $N_TOTAL"
echo "  Active skills:        $N_ACTIVE  (counts toward 70-90 health band)"
if [[ $N_COMMAND_ADAPTERS -gt 0 ]]; then
  echo "  Command adapters:     $N_COMMAND_ADAPTERS  (capability: command; excluded from the band)"
fi
echo "  Removed (tombstones): $N_REMOVED (not counted)"
echo "  Passed:               $N_PASS"
echo "  Failed:               $N_FAIL"
echo "  With warnings:        $N_WARN"
echo ""

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "Failures:"
  for f in "${FAILURES[@]}"; do
    echo "  ✗ $f"
  done
  echo ""
fi

if [[ ${#LINE_BUDGET_WARNINGS[@]} -gt 0 ]]; then
  echo "Line-budget warnings (>300 lines; always printed):"
  for w in "${LINE_BUDGET_WARNINGS[@]}"; do
    echo "  ⚠ $w"
  done
  echo ""
fi

if [[ ${#WARNINGS[@]} -gt 0 && "${VERBOSE:-}" == "1" ]]; then
  echo "Warnings:"
  for w in "${WARNINGS[@]}"; do
    echo "  ⚠ $w"
  done
  echo ""
fi

# Library health context — based on ACTIVE skills only
if [[ $N_ACTIVE -gt 100 ]]; then
  echo "⚠️  Library health: $N_ACTIVE active skills exceeds the 101+ mandatory-consolidation threshold."
elif [[ $N_ACTIVE -gt 90 ]]; then
  echo "⚠️  Library health: $N_ACTIVE active skills in the 91-100 review zone. Consider consolidation."
elif [[ $N_ACTIVE -lt 70 ]]; then
  echo "ℹ️  Library health: $N_ACTIVE active skills below the 70-90 target band."
else
  echo "✓ Library health: $N_ACTIVE active skills in target 70-90 band."
fi

if [[ $N_FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
