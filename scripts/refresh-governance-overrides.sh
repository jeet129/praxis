#!/usr/bin/env bash
# Refresh a project's governance overrides against the current plugin defaults.
#
# `.project/governance/model-routing.yaml` and `autonomy.yaml` are seeded once
# and then win over the plugin's copies (so per-engagement tuning survives
# plugin updates) — which means new default KEYS from a plugin update don't
# reach an existing project on their own. This helper closes that gap
# non-destructively: it reports the drift, and with --apply merges the new keys
# in while KEEPING your tuned values (changed defaults are surfaced, never
# silently overwritten).
#
# Usage:
#   scripts/refresh-governance-overrides.sh [PROJECT_DIR]            # report only
#   scripts/refresh-governance-overrides.sh --apply [PROJECT_DIR]    # merge (backs up first)
#
# PROJECT_DIR defaults to the current directory.

set -euo pipefail

APPLY=0
PROJECT_DIR=""
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) PROJECT_DIR="$arg" ;;
  esac
done
PROJECT_DIR="${PROJECT_DIR:-$PWD}"

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$PLUGIN_ROOT/scripts/governance-overrides.py"
GOV_DIR="$PROJECT_DIR/.project/governance"

if ! command -v python3 >/dev/null 2>&1; then
  echo "refresh-governance-overrides: python3 not found — cannot diff/merge." >&2
  exit 2
fi
[[ -f "$ENGINE" ]] || { echo "refresh-governance-overrides: missing $ENGINE" >&2; exit 2; }

any_drift=0
for gf in model-routing.yaml autonomy.yaml; do
  plugin_f="$PLUGIN_ROOT/governance/$gf"
  proj_f="$GOV_DIR/$gf"
  [[ -f "$plugin_f" ]] || continue
  if [[ ! -f "$proj_f" ]]; then
    echo "· $gf: no project override yet (seeded on next session) — nothing to refresh."
    continue
  fi

  echo "==> $gf"
  if python3 "$ENGINE" diff "$plugin_f" "$proj_f"; then
    echo "  ✓ in sync with plugin defaults."
    continue
  fi
  # diff exited 3 = drift (plugin has keys your copy lacks)
  any_drift=1
  if (( APPLY == 1 )); then
    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    cp "$proj_f" "$proj_f.bak-$ts"
    tmp="$(mktemp "${TMPDIR:-/tmp}/praxis-gov.XXXXXX")"
    if python3 "$ENGINE" merge "$plugin_f" "$proj_f" >"$tmp"; then
      mv "$tmp" "$proj_f"
      echo "  ✓ merged new keys into $proj_f (backup: $(basename "$proj_f.bak-$ts")). Review any '~ default changed' above."
    else
      rm -f "$tmp"
      echo "  ✗ merge failed; your file is unchanged (backup left at $proj_f.bak-$ts)." >&2
    fi
  fi
done

if (( any_drift == 1 && APPLY == 0 )); then
  echo
  echo "Run with --apply to merge the new keys in (your tuned values are kept; a .bak is written)."
fi
