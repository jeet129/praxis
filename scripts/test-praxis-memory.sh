#!/usr/bin/env bash
# Contract tests for the v0.3.0 storage layout and memory tooling:
# hooks/praxis_project.py (ensure, map, fingerprints), scripts/praxis-verify.py
# (runner, legacy log capture, worktree-shared evidence), hooks/praxis_commit_trailer.py,
# and scripts/praxis-memory.py (index, check, migrate-local, consolidate). No model calls.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PPY="$ROOT/hooks/praxis_project.py"; V="$ROOT/scripts/praxis-verify.py"; M="$ROOT/scripts/praxis-memory.py"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
pass=0; fail=0
ok()  { pass=$((pass+1)); }
bad() { fail=$((fail+1)); echo "FAIL: $1"; echo "      got: $2"; }
expect()   { case "$2" in *"$3"*) ok ;; *) bad "$1" "$2" ;; esac; }
expect_no(){ case "$2" in *"$3"*) bad "$1" "$2" ;; *) ok ;; esac; }
export PRAXIS_NESTED=""; unset PRAXIS_NESTED

P="$T/p"; mkdir -p "$P/.project/working" "$P/src" "$P/.project/operational/reviews" "$P/.project/episodic" "$P/.project/semantic"
cd "$P" && git init -q && git config user.email t@t && git config user.name t
echo 'a=1' > src/a.py
cat > .project/working/slice-001-tasks.yaml <<'Y'
slice: "001"
state: closed
tasks:
  - id: T1
    verify: "echo '5 passed in 0.2s' > .project/working/verify-T1.log; echo 0 > .project/working/verify-T1.exit"
    status: done
Y
cat > .project/working/slice-002-tasks.yaml <<'Y'
slice: "002"
tasks:
  - id: U1
    verify: "echo 'Tests:       2 passed, 2 total'"
    status: in_progress
Y
echo "notes" > .project/working/slice-001-notes.md
echo "live" > .project/working/slice-002-notes.md
for i in 1 2 3; do echo log > ".project/working/verify-X$i.log"; done
mkdir -p .project/working/4c-run-final && echo '<testsuite/>' > .project/working/4c-run-final/junit.owner.xml
echo "data" > .project/working/notes-ish.txt
printf -- '---\ntype: episodic\ndate: 2026-09-01\nsource: test\n---\n# Close\nSee [x](../semantic/missing.md)\n' > .project/episodic/2026-09-01-slice-001-close.md
echo "# no frontmatter" > .project/semantic/glossary.md
for r in "2026-09-11-adr-nf-054-challenge-round-1" "2026-09-12-adr-nf-054-challenge-round-2" "2026-09-13-adr-nf-054-challenge-round-3"; do
  echo "# $r" > ".project/operational/reviews/$r.md"; done
echo 'pytest output' > .project/operational/reviews/pytest.log
mkdir -p .project/telemetry && echo '{}' > .project/telemetry/guard.jsonl
cat > .project/working/inbox.md <<'Y'
# Requirements Inbox

## R-1: first  [arrived 2026-08-20]
- **Status:** shipped 2026-09-01.

## R-2: second  [arrived 2026-08-21]
- **Status:** open.

## R-3: third  [arrived 2026-08-22]
- **Status:** shipped for approval 2026-09-11
Y
git add -A && git commit -qm init

# ── ensure: layout, gitignore, shims, hook; idempotent ──
out=$(python3 "$PPY" ensure "$P" --plugin-root "$ROOT")
expect "ensure reports ok" "$out" '"ok": true'
[ -x .project/local/bin/praxis-verify ] && ok || bad "shim created" "missing"
expect "gitignore has managed block" "$(cat .project/.gitignore)" 'praxis-managed'
python3 "$PPY" ensure "$P" --plugin-root "$ROOT" >/dev/null
[ "$(grep -c 'praxis-managed (praxis' .project/.gitignore)" = 1 ] && ok || bad "gitignore block not duplicated" "$(cat .project/.gitignore)"
expect "commit hook installed" "$(cat .git/hooks/prepare-commit-msg)" 'praxis-managed'
echo '#!/bin/sh' > "$T/foreign"; cp "$T/foreign" .git/hooks/prepare-commit-msg
expect "foreign hook is never replaced" "$(python3 "$PPY" ensure "$P" --plugin-root "$ROOT")" 'skipped'
rm .git/hooks/prepare-commit-msg; python3 "$PPY" ensure "$P" --plugin-root "$ROOT" >/dev/null
[ -f .project/governance/memory-layout.yaml ] && ok || bad "layout seeded" "missing"
expect "git ignores local/" "$(git check-ignore -v .project/local/evidence/x 2>&1)" 'local/'

# ── runner: legacy self-logging command, counts, worktree sharing ──
.project/local/bin/praxis-verify T1 >/dev/null; rc=$?
[ "$rc" = 0 ] && ok || bad "runner exit code" "$rc"
[ ! -e .project/working/verify-T1.log ] && ok || bad "legacy log moved out of working/" "still there"
S=$(ls .project/operational/verification/T1--*.json | head -1)
expect "summary has counts from the legacy log" "$(cat "$S")" '"passed": 5'
expect "summary records the tree" "$(cat "$S")" '"tree_before"'
.project/local/bin/praxis-verify U1 >/dev/null
expect "jest-style counts" "$(cat .project/operational/verification/U1--*.json)" '"passed": 2'
expect "unknown task is a usage error" "$(.project/local/bin/praxis-verify NOPE 2>&1; echo rc=$?)" 'rc=2'
git add -A >/dev/null; git commit -qm "with layout"
git worktree add -q "$T/wt" -b lane >/dev/null 2>&1
mkdir -p "$T/wt/.project/working" && cp .project/working/slice-002-tasks.yaml "$T/wt/.project/working/"
(cd "$T/wt" && python3 "$V" U1 >/dev/null)
expect "lane evidence lands in the main checkout's store" "$(ls .project/local/evidence/U1 | wc -l | tr -d ' ')" '2'
git worktree remove --force "$T/wt" >/dev/null 2>&1

# ── fingerprints never grow the repository's object store ──
echo "untracked scratch" > notes-untracked.txt
before=$(git count-objects -v | awk '/^count:/{print $2}')
.project/local/bin/praxis-verify U1 >/dev/null
after=$(git count-objects -v | awk '/^count:/{print $2}')
[ "$before" = "$after" ] && ok || bad "fingerprint objects stay in .project/local/git-objects" "$before -> $after"
rm -f notes-untracked.txt

# ── commit trailer ──
echo 'a=2' > src/a.py; .project/local/bin/praxis-verify U1 >/dev/null
git add src/a.py && git commit -qm "verified change"
expect "verified commit gets verify trailer" "$(git log -1 --format=%B)" 'Praxis-Verified: verify (U1)'
echo 'a=3' > src/a.py; git add src/a.py && git commit -qm "unverified change"
expect "unverified commit says none" "$(git log -1 --format=%B)" 'Praxis-Verified: none'
git commit -q --allow-empty -m "manual" -m "Praxis-Verified: review"
[ "$(git log -1 --format=%B | grep -c Praxis-Verified)" = 1 ] && ok || bad "existing trailer kept" "$(git log -1 --format=%B)"

# ── map ──
mp=$(python3 "$PPY" map "$P")
expect "map lists active ledger" "$mp" 'slice-002-tasks.yaml (1 open)'
[ "$(printf '%s\n' "$mp" | wc -l)" -le 40 ] && ok || bad "map within 40 lines" "$(printf '%s\n' "$mp" | wc -l)"

# ── layout override ──
sed -i.bak 's#^  adr: .project/decision#  adr: docs/adr#' .project/governance/memory-layout.yaml
expect "where resolves an override" "$(python3 "$M" where adr)" 'docs/adr'
expect "map shows overrides" "$(python3 "$PPY" map "$P")" 'adr=docs/adr'
mv .project/governance/memory-layout.yaml.bak .project/governance/memory-layout.yaml

# ── migrate-local ──
dry=$(python3 "$M" migrate-local)
expect "dry run says so" "$dry" 'dry run'
expect "finds the run directory" "$dry" '4c-run-final/'
expect "finds review logs" "$dry" 'operational/reviews'
expect "untracks raw telemetry" "$dry" 'tracked files now gitignored:   1'
expect "keeps an unclear txt as uncertain" "$dry" 'notes-ish.txt'
[ -e .project/working/verify-X1.log ] && ok || bad "dry run changed nothing" "file moved"
python3 "$M" migrate-local --apply >/dev/null
[ ! -e .project/working/verify-X1.log ] && [ -e .project/local/evidence/legacy/working/verify-X1.log ] && ok || bad "apply moved logs to legacy store" "$(ls .project/working)"
expect "apply untracked them" "$(git status --short)" 'D  .project/working/verify-X1.log'
expect_no "telemetry stays on disk" "$(ls .project/telemetry)" 'No such'
ls .project/operational/memory-maintenance/*-migrate-local.md >/dev/null 2>&1 && ok || bad "maintenance note" "missing"
git add -A >/dev/null; git commit -qm migrate

# ── consolidate ──
touch -d '40 days ago' .project/operational/reviews/2026-09-1*-adr-nf-054-challenge-round-[12].md 2>/dev/null || \
  touch -t 202609010000 .project/operational/reviews/2026-09-1*-adr-nf-054-challenge-round-[12].md
cd=$(python3 "$M" consolidate)
expect "closed slice notes proposed" "$cd" 'slice-001-notes.md'
expect_no "open slice notes untouched" "$(printf '%s' "$cd" | grep -A4 'closed slices')" 'slice-002-notes.md'
expect "two earlier review rounds proposed" "$cd" '     2  earlier review rounds'
expect "one closed inbox entry (shipped for approval stays)" "$cd" '     1  closed inbox entries'
python3 "$M" consolidate --apply >/dev/null
[ -e .project/episodic/archive/slices/001/slice-001-notes.md ] && ok || bad "slice note archived" "$(find .project/episodic)"
[ -e .project/working/slice-002-notes.md ] && ok || bad "open slice note kept" "moved"
expect "inbox keeps open entries" "$(cat .project/working/inbox.md)" 'R-2'
expect_no "inbox drops closed entry" "$(cat .project/working/inbox.md)" 'R-1:'
expect "closed entry archived" "$(cat .project/episodic/archive/inbox-closed.md)" 'R-1: first'
expect "newest review round kept" "$(ls .project/operational/reviews)" 'round-3'
expect "tracked moves use git mv" "$(git status --short)" 'R  .project/working/slice-001-notes.md -> .project/episodic/archive/slices/001/slice-001-notes.md'
expect "prompt available" "$(python3 "$M" consolidate --print-prompt)" 'injected'

# ── index + check ──
python3 "$M" index >/dev/null
expect "index counts episodic" "$(cat .project/INDEX.yaml)" 'episodic:'
[ -f .project/index/review.yaml ] && ok || bad "per-kind index" "missing"
ck=$(python3 "$M" check)
expect "check finds the broken link" "$ck" 'broken links'
expect "check warns on missing frontmatter" "$ck" 'no frontmatter'
expect "strict check fails on errors" "$(python3 "$M" check --strict >/dev/null; echo rc=$?)" 'rc=1'

echo "praxis-memory tests: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
