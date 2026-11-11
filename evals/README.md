# Praxis evaluation suite

These cases check behaviour, not file layout: does the right skill load for a
realistic request, do trivial requests stay free of ceremony, and does the
agent refuse to call unverified work done.

| Folder prefix | What it checks | Grader |
|---|---|---|
| `trigger-*` | A plain-language request loads the matching Tier A skill | `tool_used: Skill` (display-only under ablation) plus an `llm` grader |
| `negative-*` | A trivial request loads no skill | `tool_used: Skill` with `max: 0` plus an `llm` answer check |
| `e2e-*` | A behaviour Praxis exists to enforce | `llm` |

## Claude Code

```bash
claude plugin eval . --tag trigger --runs 3 --max-cost-usd 5      # trigger accuracy
claude plugin eval . --ablation with-without --max-cost-usd 10    # full suite, with and without Praxis
```

`claude plugin eval` runs real model sessions on your account. It is not part
of CI; CI only checks the suite is well formed (`scripts/validate-evals.py`).
Run it before a release and whenever skill descriptions change, and keep the
report from `evals/results/` with the release notes.

## Codex and Antigravity

```bash
python3 scripts/eval-harness-triggers.py --harness codex --project-dir <a Praxis project>
python3 scripts/eval-harness-triggers.py --harness antigravity --project-dir <a Praxis project>
```

Runs every `trigger-*` and `negative-*` case once and grades it from evidence,
not from the reply text:

| Result | Meaning |
|---|---|
| `LOADED` | Codex: a shell command read `<skill>/SKILL.md`. Antigravity: the Praxis telemetry hook logged a tool call naming the skill. Pass. |
| `MENTIONED` | The reply names the skill but nothing shows it was read. Fail; look at it. |
| `MISS` | No sign of the skill. Fail. |
| `CLEAN` / `LOADED_A_SKILL` | Negative cases: pass only when no skill was read. |

Needs a logged-in `codex` or `agy` and spends real tokens. For Antigravity
also run `agy plugin validate --strict plugins/praxis-antigravity` once, and
check by hand that `touch .project/STOP` makes the next tool call fail.

## Adding a case

Create `evals/<name>/prompt.md` (frontmatter + the user request) and at least
one grader under `evals/<name>/graders/`. `claude plugin eval init` can
interview you for one. Every Tier A skill has a trigger case; `scripts/validate-evals.py` reports any that lose theirs.
