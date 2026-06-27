#!/usr/bin/env bash
# validate-skills.sh — structural validator for the Praxis library
#
# Verifies every SKILL.md has the full 8-field frontmatter the platform
# expects: name, description, capability, domain, state, dependencies,
# triggers, outputs, consumers, references.
#
# Usage:
#   ./scripts/validate-skills.sh           # validate this repo's skills/
#   ./scripts/validate-skills.sh /path     # validate a specific library root
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

# Required frontmatter fields
REQUIRED_FIELDS=(name description capability domain state)

# Recommended (warn if missing, don't fail)
RECOMMENDED_FIELDS=(dependencies triggers outputs consumers references)

# Valid state values
VALID_STATES=(experimental active deprecated merged removed)

# Counters
N_TOTAL=0
N_PASS=0
N_FAIL=0
N_WARN=0
N_REMOVED=0      # tombstones (state: removed) — not counted in active total
N_ACTIVE=0       # active total — what counts toward 70-90 health band
FAILURES=()
WARNINGS=()

echo "Praxis — skill validator"
echo "======================================="
echo "Library: $LIBRARY_ROOT"
echo ""

for skill_md in "$SKILLS_DIR"/*/SKILL.md; do
  N_TOTAL=$((N_TOTAL + 1))
  skill_name=$(basename "$(dirname "$skill_md")")
  skill_failed=0
  skill_warned=0

  # Extract frontmatter (between --- markers)
  frontmatter=$(awk '/^---$/{flag=!flag; if(!flag)exit; next} flag' "$skill_md")

  if [[ -z "$frontmatter" ]]; then
    FAILURES+=("$skill_name: no frontmatter found")
    N_FAIL=$((N_FAIL + 1))
    continue
  fi

  # Check required fields
  for field in "${REQUIRED_FIELDS[@]}"; do
    if ! echo "$frontmatter" | grep -q "^$field:"; then
      FAILURES+=("$skill_name: missing required field '$field'")
      skill_failed=1
    fi
  done

  # Check name matches directory
  declared_name=$(echo "$frontmatter" | grep "^name:" | head -1 | sed 's/^name: *//' | tr -d '"')
  if [[ -n "$declared_name" && "$declared_name" != "$skill_name" ]]; then
    FAILURES+=("$skill_name: declared name '$declared_name' doesn't match directory")
    skill_failed=1
  fi

  # Check state is valid
  declared_state=$(echo "$frontmatter" | grep "^state:" | head -1 | sed 's/^state: *//' | tr -d '"')
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

  # Tombstones (state: removed) — count separately, skip recommended-field checks
  if [[ "$declared_state" == "removed" ]]; then
    N_REMOVED=$((N_REMOVED + 1))
    if [[ $skill_failed -eq 0 ]]; then
      N_PASS=$((N_PASS + 1))
    else
      N_FAIL=$((N_FAIL + 1))
    fi
    continue
  fi

  # Past this point, the skill is active (or experimental/deprecated) — counts toward health band
  N_ACTIVE=$((N_ACTIVE + 1))

  # Check recommended fields (warnings only)
  for field in "${RECOMMENDED_FIELDS[@]}"; do
    if ! echo "$frontmatter" | grep -q "^$field:"; then
      WARNINGS+=("$skill_name: missing recommended field '$field'")
      skill_warned=1
    fi
  done

  # Description quality: should contain "Use when" trigger phrase
  declared_desc=$(echo "$frontmatter" | grep "^description:" | head -1)
  if ! echo "$declared_desc" | grep -qi "use when\|use whenever"; then
    WARNINGS+=("$skill_name: description lacks 'Use when' trigger phrase")
    skill_warned=1
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

# Exit code
if [[ $N_FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
