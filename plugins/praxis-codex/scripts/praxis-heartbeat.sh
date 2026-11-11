#!/usr/bin/env bash
# praxis-heartbeat.sh — schedule praxis-drive.sh so a project keeps moving
# without anyone starting it. One crontab line per project; safe to re-run.
#
#   praxis-heartbeat.sh install [--project-dir DIR] [--every MINUTES] [--harness claude-code|codex] [--window "1-5"]
#   praxis-heartbeat.sh remove  [--project-dir DIR]
#   praxis-heartbeat.sh status  [--project-dir DIR]
#   praxis-heartbeat.sh run     [--project-dir DIR] [--harness H]     (what cron calls)
#
# `run` takes a lock so two beats never overlap, skips while .project/STOP
# exists, then starts one praxis-drive.sh run. Every drive run starts from the
# files under .project/, so a beat that crashed is picked up by the next one.
# --window is the cron day-of-week field (default "*", every day).
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SELF="$SCRIPT_DIR/$(basename "${BASH_SOURCE[0]}")"
CMD="${1:-}"; shift || true
PROJECT="$PWD"; EVERY=30; HARNESS="claude-code"; WINDOW="*"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir) PROJECT="$2"; shift 2 ;;
    --every) EVERY="$2"; shift 2 ;;
    --harness) HARNESS="$2"; shift 2 ;;
    --window) WINDOW="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
PROJECT="$(cd "$PROJECT" 2>/dev/null && pwd)" || { echo "project dir not found" >&2; exit 2; }
TAG="# praxis-heartbeat:$PROJECT"

# PRAXIS_HEARTBEAT_CRONTAB_FILE lets tests (and cautious users) use a file
# instead of the real crontab.
cron_read()  { if [[ -n "${PRAXIS_HEARTBEAT_CRONTAB_FILE:-}" ]]; then cat "$PRAXIS_HEARTBEAT_CRONTAB_FILE" 2>/dev/null; else crontab -l 2>/dev/null; fi; true; }
cron_write() { if [[ -n "${PRAXIS_HEARTBEAT_CRONTAB_FILE:-}" ]]; then cat > "$PRAXIS_HEARTBEAT_CRONTAB_FILE"; else crontab -; fi; }

case "$CMD" in
  install)
    [[ -d "$PROJECT/.project" ]] || { echo "no .project/ in $PROJECT — run /start first" >&2; exit 2; }
    [[ "$EVERY" =~ ^[0-9]+$ ]] && (( EVERY >= 5 && EVERY <= 1440 )) || { echo "--every must be 5..1440 minutes" >&2; exit 2; }
    case "$HARNESS" in claude-code|codex) ;; *) echo "--harness must be claude-code or codex (Antigravity: use its own /schedule)" >&2; exit 2 ;; esac
    if (( EVERY < 60 )); then SCHED="*/$EVERY * * * $WINDOW"; else SCHED="0 */$(( EVERY / 60 )) * * $WINDOW"; fi
    LINE="$SCHED /bin/bash \"$SELF\" run --project-dir \"$PROJECT\" --harness $HARNESS >> \"$PROJECT/.project/telemetry/heartbeat.log\" 2>&1 $TAG"
    mkdir -p "$PROJECT/.project/telemetry"
    CURRENT="$(cron_read | grep -vF "$TAG" || true)"   # read fully before writing
    { [[ -n "$CURRENT" ]] && printf '%s\n' "$CURRENT"; echo "$LINE"; } | cron_write
    echo "heartbeat installed: every $EVERY min, harness $HARNESS"
    echo "  log:    $PROJECT/.project/telemetry/heartbeat.log"
    echo "  pause:  touch $PROJECT/.project/STOP      remove: $SELF remove --project-dir $PROJECT"
    ;;
  remove)
    CURRENT="$(cron_read | grep -vF "$TAG" || true)"
    if [[ -n "$CURRENT" ]]; then printf '%s\n' "$CURRENT" | cron_write; else : | cron_write; fi
    echo "heartbeat removed for $PROJECT"
    ;;
  status)
    if cron_read | grep -qF "$TAG"; then
      echo "installed: $(cron_read | grep -F "$TAG" | sed 's/ \/bin\/bash.*//')"
    else
      echo "not installed"
    fi
    [[ -e "$PROJECT/.project/STOP" ]] && echo "paused: .project/STOP exists"
    [[ -f "$PROJECT/.project/telemetry/heartbeat.log" ]] && { echo "last beats:"; grep "^\[heartbeat\]" "$PROJECT/.project/telemetry/heartbeat.log" | tail -3; }
    true
    ;;
  run)
    STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    if [[ -e "$PROJECT/.project/STOP" ]]; then echo "[heartbeat] $STAMP skipped: kill switch"; exit 0; fi
    LOCK="$PROJECT/.project/working/.heartbeat.lock"
    mkdir -p "$PROJECT/.project/working"
    if ! mkdir "$LOCK" 2>/dev/null; then
      OLD="$(cat "$LOCK/pid" 2>/dev/null || true)"
      if [[ -n "$OLD" ]] && kill -0 "$OLD" 2>/dev/null; then echo "[heartbeat] $STAMP skipped: previous beat (pid $OLD) still running"; exit 0; fi
      rm -rf "$LOCK"; mkdir "$LOCK" || exit 0      # stale lock from a crashed beat
    fi
    echo $$ > "$LOCK/pid"
    trap 'rm -rf "$LOCK"' EXIT
    DRIVE="${PRAXIS_HEARTBEAT_DRIVE:-$SCRIPT_DIR/praxis-drive.sh}"
    echo "[heartbeat] $STAMP start ($HARNESS)"
    bash "$DRIVE" --project-dir "$PROJECT" --harness "$HARNESS"; RC=$?
    echo "[heartbeat] $(date -u +%Y-%m-%dT%H:%M:%SZ) end exit=$RC"
    exit 0
    ;;
  *) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
