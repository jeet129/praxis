#!/usr/bin/env bash
# Contract tests for praxis-heartbeat.sh. Uses a file in place of the crontab.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
H="$ROOT/scripts/praxis-heartbeat.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export PRAXIS_HEARTBEAT_CRONTAB_FILE="$T/crontab"
pass=0; fail=0
ok(){ pass=$((pass+1)); }; bad(){ fail=$((fail+1)); echo "FAIL: $1"; echo "      got: $2"; }
expect(){ case "$2" in *"$3"*) ok ;; *) bad "$1" "$2" ;; esac; }
expect_no(){ case "$2" in *"$3"*) bad "$1" "$2" ;; *) ok ;; esac; }
P="$T/proj"; mkdir -p "$P/.project/working"; P="$(cd "$P" && pwd)"
echo "0 9 * * * /usr/bin/true # someone else's job" > "$T/crontab"

expect "needs a Praxis project" "$(bash "$H" install --project-dir "$T" 2>&1)" "no .project/"
expect "rejects agy" "$(bash "$H" install --project-dir "$P" --harness antigravity 2>&1)" "must be claude-code or codex"
expect "rejects silly interval" "$(bash "$H" install --project-dir "$P" --every 1 2>&1)" "5..1440"
expect "installs" "$(bash "$H" install --project-dir "$P" --every 30 --harness codex)" "heartbeat installed"
expect "cron line written" "$(cat "$T/crontab")" "*/30 * * * *"
expect "other jobs kept" "$(cat "$T/crontab")" "someone else's job"
bash "$H" install --project-dir "$P" --every 120 --window 1-5 >/dev/null
[ "$(grep -c "praxis-heartbeat:" "$T/crontab")" = "1" ] && ok || bad "re-install replaces, never duplicates" "$(cat "$T/crontab")"
expect "hourly form + window" "$(cat "$T/crontab")" "0 */2 * * 1-5"
expect "status shows installed" "$(bash "$H" status --project-dir "$P")" "installed:"

cat > "$T/drive.sh" <<'D'
#!/usr/bin/env bash
echo "drive ran $*" >> "$(dirname "$0")/drive.calls"; sleep "${FAKE_SLEEP:-0}"
D
export PRAXIS_HEARTBEAT_DRIVE="$T/drive.sh"
expect "run starts the drive" "$(bash "$H" run --project-dir "$P" --harness codex)" "end exit=0"
expect "drive got the project and harness" "$(cat "$T/drive.calls")" "--harness codex"
[ ! -e "$P/.project/working/.heartbeat.lock" ] && ok || bad "lock released" "still there"
touch "$P/.project/STOP"
expect "kill switch skips the beat" "$(bash "$H" run --project-dir "$P")" "skipped: kill switch"
rm -f "$P/.project/STOP"
FAKE_SLEEP=3 bash "$H" run --project-dir "$P" >/dev/null & sleep 1
expect "overlapping beat is skipped" "$(bash "$H" run --project-dir "$P")" "still running"
wait
mkdir -p "$P/.project/working/.heartbeat.lock"; echo 999999 > "$P/.project/working/.heartbeat.lock/pid"
expect "stale lock is recovered" "$(bash "$H" run --project-dir "$P")" "end exit=0"
bash "$H" remove --project-dir "$P" >/dev/null
expect_no "remove deletes our line" "$(cat "$T/crontab")" "praxis-heartbeat"
expect "remove keeps other jobs" "$(cat "$T/crontab")" "someone else's job"
echo "praxis-heartbeat tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
