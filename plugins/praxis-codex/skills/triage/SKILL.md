---
name: triage
description: "On-demand discovery scan that surfaces what needs attention in a project and writes a classified triage inbox. Use when you want a scan of outstanding work — 'run triage', 'what needs attention', 'scan for work', 'what's the state of this repo', resuming a project after time away, or before planning the next slice. Reads git activity since the last triage, failing tests/CI, the tech-debt register, TODO/FIXME drift, dependency alerts, and doc-vs-code drift; classifies each finding as auto-fixable-and-machine-verifiable vs needs-human and writes .project/operational/triage/<date>.md. This is the ON-DEMAND, zero-standing-cost building block of a loop heartbeat — it runs only when invoked, never on a schedule (a scheduled version would burn tokens every cadence whether or not it finds anything; see ROADMAP). Distinct from `factory-usage-report`/`factory-routing-report` (those aggregate telemetry about the FACTORY; triage scans the PROJECT for outstanding work), from `impact-analysis` (blast radius of one proposed change), and from `tech-debt-management` (owns the debt register; triage reads it and surfaces stale items)."
---

# Triage

<!-- praxis:metadata:begin -->
```yaml
capability: maintenance
domain: cross-cutting
state: experimental
dependencies:
  - project-memory
  - tech-debt-management
  - impact-analysis
triggers:
  - "run triage"
  - "what needs attention in this repo?"
  - "scan for outstanding work"
  - "what's the state of the project?"
  - "resuming after time away — what changed and what's open?"
outputs:
  - triage inbox at .project/operational/triage/<date>.md (classified findings)
  - optional: a slice ledger seeded from auto-fixable findings (only on explicit ask)
consumers:
  - delivery-lead (runs at project resume / before planning the next slice)
  - system-steward (adjacent to the quarterly health review)
references:
  - triage-checklist.md
```
<!-- praxis:metadata:end -->

The on-demand discovery scan. Osmani's loop-engineering model puts an
*automation* — a scheduled heartbeat — at the center of a self-feeding loop.
For a solo/deliberate workflow that heartbeat is unnecessary token cost: a
scheduled scan runs every cadence whether or not there is work, and you are
already the discovery mechanism. This skill is the heartbeat's **useful
fragment without the standing cost**: the same scan, run *only when you ask*.

The scheduled version stays on the ROADMAP for teams/always-on products with
continuous inflow; do not add a scheduler here.

## When this fires

You invoke it — resuming a project after time away, before planning the next
slice, or any time you want "what needs attention?" It never runs itself.

## What it scans

Read only the named sources (scoped — never the whole tree), each quiet and
captured to a log where it produces volume (per `using-praxis` tool-output
hygiene):

1. **Git activity since last triage** — commits, changed areas, unmerged
   branches since the previous `.project/operational/triage/*.md` timestamp
   (or last N days if none). `git log --oneline`, `git status -s`.
2. **Failing tests / CI** — the project's quick test command (quiet), and any
   CI status file/log the project exposes. Consume summary + failing names
   only, never full logs.
3. **Tech-debt register** — `.project/operational/debt-register.md`: items
   marked reckless/high-priority, or aged past their suggested follow-up.
   Reads it; does not modify it (that's `tech-debt-management`).
4. **TODO/FIXME/HACK drift** — `grep -rn` for markers added since last
   triage; count and locate, do not dump.
5. **Dependency / security alerts** — lockfile advisories, outdated criticals,
   if the project surfaces them cheaply.
6. **Doc-vs-code drift** — architecture docs / ADRs / READMEs whose referenced
   files or contracts have since changed (spot-check, not exhaustive).

## What it produces

`.project/operational/triage/<YYYY-MM-DD>.md` — the inbox that survives
between sessions (the memory the loop depends on: the agent forgets, the repo
doesn't). Every finding classified into exactly one bucket:

```markdown
---
type: triage
scanned: 2026-07-16T09:00:00Z
since: 2026-07-12   # previous triage or window start
sources: [git, tests, debt-register, todos, deps, doc-drift]
---

## Auto-fixable (machine-verifiable exit exists)
- [id] <finding> — verify: <runnable command that would confirm the fix>
  # these can seed a slice ledger for /drive, on explicit ask

## Needs human (judgment / decision / no machine exit)
- [id] <finding> — why human: <ambiguous | architectural | product | risk>

## Informational (no action, recorded for awareness)
- <finding>
```

Classification rule (the load-bearing one): a finding is **auto-fixable only
if a machine-verifiable exit exists** — a failing test to make pass, a
validator to make exit 0, a lint to clear. Everything requiring judgment
(ambiguous requirements, architectural choice, product call, risk
acceptance) is **needs-human**, even if it looks small. Absence of a
machine exit is not weak evidence here — it is the definition of needs-human.

## Optional bridge to drive (only on explicit ask)

If — and only if — you ask ("open a slice from the auto-fixable items"),
seed a slice task ledger (`references/loop-contracts.md` §2) from the
auto-fixable findings, each carrying the `verify` command from its triage
line. `/drive` then executes it under the usual budgets and gates.
Never do this unprompted: triage's default output is the inbox, not action.

## Mode handling (G/B)

- **Greenfield:** git/test/todo scan; debt register and doc-drift are usually
  thin early — that's fine, report what exists.
- **Brownfield:** the full scan is most valuable here; the debt register and
  doc-vs-code drift sources carry the most signal on an inherited codebase.

## Cost posture

One invocation, scoped reads, quiet commands, a compact classified report.
No standing cost — nothing runs unless you invoke it. If you find yourself
wanting it to run on a cadence, that is the ROADMAP heartbeat, and it should
be a deliberate cost decision, not a default.

## Verification

- [ ] The report exists at `.project/operational/triage/<date>.md` with the
      three buckets and a `since` window.
- [ ] Every "auto-fixable" finding carries a runnable `verify` command; any
      finding without one is in "needs human", not "auto-fixable".
- [ ] Scan sources were scoped and quiet — no full test/CI logs pulled into
      context.
- [ ] The debt register was read, not modified.
- [ ] A slice ledger was seeded ONLY if explicitly requested.

## Anti-patterns

- Running triage on a schedule / wiring a cron here — that is the ROADMAP
  heartbeat and its standing token cost is a deliberate decision, not a
  default this skill makes.
- Classifying a judgment call as auto-fixable because it looks small — no
  machine exit ⇒ needs human, always.
- Dumping full test/CI/grep output into the report — summaries and locations
  only; the report is an index, not a log.
- Modifying the debt register, or opening slices, without being asked — the
  default deliverable is the inbox.
- Scanning the whole `.project/` or whole repo tree — scoped sources only.

## What this SKILL does NOT do

- Run itself on any schedule (ROADMAP: automation heartbeat).
- Fix anything — it surfaces and classifies; the drive loop or a human acts.
- Own the debt register (`tech-debt-management`) or aggregate factory
  telemetry (`factory-usage-report` / `factory-routing-report`).
