# Triage scan checklist

Companion to `triage/SKILL.md` — the concrete, scoped, quiet commands per
source. Adapt to the project's stack; keep every command quiet and capture
volume to a log (per `using-praxis` tool-output hygiene).

## 1. Git activity since last triage
```bash
# window start = timestamp of newest .project/operational/triage/*.md, else 14 days
git log --oneline --since="<window>" | head -50
git status -s
git branch --no-merged main 2>/dev/null    # unmerged work
```
Report: areas of change (dirs), unmerged branches, uncommitted work. Not full diffs.

## 2. Failing tests / CI
```bash
<project quiet test cmd> > .project/operational/triage/.scan-tests.log 2>&1; echo $?
# e.g. pytest -q --tb=no ; ./gradlew test -q --console=plain ; npm test --silent
```
Consume: exit code + failing test names (grep the log). Never the full log.
Also read any CI status file the project exposes (e.g. last workflow run summary).

## 3. Tech-debt register
Read `.project/operational/debt-register.md`. Surface: items classified
reckless (Fowler quadrant), high payoff×risk, or aged past their suggested
follow-up slice. Read-only — `tech-debt-management` owns edits.

## 4. TODO/FIXME/HACK drift
```bash
grep -rniE "TODO|FIXME|HACK|XXX" --include="*.<ext>" <src-dirs> | wc -l
grep -rniE "TODO|FIXME|HACK|XXX" --include="*.<ext>" <src-dirs> | head -30
```
Report: count + locations of markers, weighted toward ones in changed areas
(cross-reference §1). Do not dump all.

## 5. Dependency / security alerts
Project-specific, cheap surfaces only:
```bash
npm audit --audit-level=high 2>/dev/null | tail -5
pip-audit 2>/dev/null | tail -5
./gradlew dependencyCheckAnalyze -q 2>/dev/null   # if configured
```
Report: count of high/critical only, not the full advisory text.

## 6. Doc-vs-code drift
Spot-check (not exhaustive): for each ADR / architecture doc / README that
names files or contracts, confirm the named paths still exist and the
referenced contract shapes still match. Flag mismatches as needs-human
(doc-fix is judgment about which side is authoritative).

## Classification gate
For each finding, ask: **is there a runnable command that would confirm it
fixed?** Yes → auto-fixable, record the `verify` command. No → needs-human.
No machine exit is the *definition* of needs-human, not a soft signal.

## Clean up
Remove `.scan-*.log` scratch files after extracting summaries; keep only the
final `.project/operational/triage/<date>.md`.
