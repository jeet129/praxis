# Codex drive controller contract

This extension applies only to the Codex package. The canonical Praxis ledger
and Claude runner are unchanged.

## Lane scheduling

`scripts/codex_drive.py` reads each `.project/working/slice-*-tasks.yaml` and
runs the packaged `praxis-drive.sh` for one task or drain iteration at a time.
It keeps the current lane until closure, local acceptance, a reached gate, a
stall, or an exhausted budget. Other lanes are considered only at that
boundary. To cross a gate on slice A, slice B must declare its cross-slice
dependencies explicitly, for example:

```yaml
depends_on_slices: []       # B is independent of A
```

If B depends on A, use `depends_on_slices: [A]`; B stays blocked while A is
gated. An absent field means independence is unknown at a gate reached by the
lane this run, so the controller will not infer it. Historical gated ledgers
remain visible but do not freeze every other lane at startup. `gate_reached`,
`decision_required`, and technical blockers stop their slice lane.
`budget_exceeded` stops the whole controller. A future
`governance_gate_pending` flag is informational while work or review remains;
new ledgers should put future gates under `gates`, not `stop_flags`.

The controller reads unknown statuses without guessing and reports affected
tasks. On a live run it migrates only unambiguous aliases (`pending` to `open`,
`completed` to `done`, and similar aliases) after saving a
`.yaml.codex-pre-migration.bak` file. Run `--audit` for a read-only lane report.

## Closeout evidence

New Codex ledgers set `schema_version: 2`. They retain the canonical task
fields and add file paths under `closeout_evidence`:

```yaml
gates:
  code_review: pass
  security_review: n/a
  visual_review: n/a
  qa: pass
closeout_evidence:
  code_review: .project/working/code-review-S1.md
  qa: .project/working/qa-acceptance-S1.md
  tests: .project/working/tests-S1.md
  acceptance: .project/episodic/slice-S1-acceptance.md
  summary: .project/telemetry/summaries/slice-S1-summary.md
```

Add `security_review` and `visual_review` evidence when those gates apply.
The controller counts a slice as closed only when all tasks are done, the
packet exists, required verdicts pass, and every required evidence file
exists. Each review, test, and acceptance file starts with an explicit
`verdict: PASS` or `verdict: ACCEPTED` header; a bare file or conflicting
`verdict: FAIL` is insufficient. It gives one bounded repair pass if a newly closed ledger lacks
evidence; it never invents a verdict. Local acceptance uses the same checks
except the final slice-close summary and is reported separately from merged
or released status. Legacy closed ledgers remain recorded as historical
closures with `legacy_unverified` in the compact index; the controller does
not rewrite them or silently claim they meet the new bar.

## Recovery and visibility

The controller holds `.project/working/codex-controller.lock`, writes
`.project/telemetry/codex-controller.json` atomically, and refreshes its
heartbeat while an iteration runs. On restart it checks whether the previous
child process is still alive before resuming an interrupted in-progress task.
The task owner inspects partial work and verifies it before marking done.
The short `codex-active-index.json` is the first read for routing; load only
the chosen task's ledger, packet, and named dependencies next. Full Codex JSONL
stays in `drive.jsonl` and temporary usage logs; the terminal shows concise
events. The complete skill library remains in the package's `skills/` for
on-demand reads; the manifest advertises only `codex-skills/` to reduce
session startup context.
