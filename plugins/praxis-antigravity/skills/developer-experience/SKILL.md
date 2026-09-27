---
name: developer-experience
description: "Local development environment and onboarding discipline: one-command setup, dev/prod parity (containers, seeded data), fast feedback loops (test-speed budgets, hot reload), an onboarding doc that's actually tested by onboarding someone with it, and pre-commit hooks that mirror CI so checks are never discovered for the first time in a pipeline. Use whenever a project's local setup is being scaffolded, a new developer's onboarding is taking longer than a day, the local/CI toolchain has drifted apart, or the local feedback loop (test/build/reload time) has become a visible drag on delivery speed. Distinct from `environments` (deployed dev/staging/prod environments) and `cicd-pipeline` (the pipeline itself; this skill is about the laptop and the inner loop that feeds it)."
---

# Developer Experience

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: experimental
dependencies:
  - environments
  - engineering-standards
  - cicd-pipeline
triggers:
  - "scaffolding local dev setup for a new project"
  - "a new developer's onboarding is taking longer than a day"
  - "local and CI toolchains have drifted apart"
  - "local feedback loop (test/build/reload) has become a visible drag"
  - "writing or updating the onboarding doc"
outputs:
  - one-command setup script (make/task/devcontainer)
  - onboarding doc, tested by an actual onboarding run
  - pre-commit hook config mirroring CI checks
  - test-speed budget per test layer
  - scripts-to-rule-them-all convention (`script/setup`, `script/test`, `script/server`, ...)
consumers:
  - backend-developer (primary daily user of the inner loop)
  - frontend-developer (primary daily user of the inner loop)
  - lead-developer (owns onboarding time as a delivery metric)
  - cicd-pipeline (pre-commit hooks mirror what CI enforces)
references: []
```
<!-- praxis:metadata:end -->

The inner loop — clone, set up, run, test, iterate — is where developers spend most of their day. Friction here compounds across every developer, every day, for the life of the project. This skill treats local setup and onboarding as a maintained product, not a one-time README someone wrote and never revisited.

## When this skill fires

- A new project is being scaffolded and needs a local dev setup from the start.
- Onboarding a new developer is taking longer than a day, or requires tribal knowledge not in any doc.
- Local tooling and CI have drifted — a check passes locally but fails in CI, or vice versa.
- The local feedback loop (test run time, build time, hot-reload latency) has degraded enough to be a visible complaint.
- A postmortem or retro surfaces "I didn't know that check existed until CI failed" as a root cause.

## One-command setup

A fresh clone to a running local environment is one command — `make setup`, `task setup`, or opening a devcontainer. That one command:

- Installs the correct language/runtime versions (via a version manager or devcontainer, not "install Node however you like").
- Installs dependencies.
- Provisions local infra (DB, cache, queue) via containers, not by requiring the developer to install and configure them natively.
- Seeds the database with representative data — enough to exercise real flows, not an empty schema.
- Ends in a state where `make server` (or equivalent) starts the app successfully, with no manual follow-up steps.

If setup takes more than one command, or requires reading multiple docs to assemble the sequence, it's not done. Every additional manual step is a place onboarding silently breaks when the environment shifts underneath the doc.

## Parity with prod

Local environments should match production's shape closely enough that "works on my machine" failures are rare:

- **Containers** for the app and its dependencies — the same base images (or close variants) used in deployed environments, not a hand-installed local stack that drifts from what `environments` runs.
- **Seeded data** that resembles production data shape (realistic volumes of representative records, not three hardcoded rows) — catches pagination, N+1, and empty-state bugs before they reach staging.
- **Config parity** — local config is derived from the same schema/validation as deployed config (see `environments`), with safe local defaults, not a separate ad hoc `.env.example` that's gone stale.
- Full production-scale parity isn't the goal (that's wasteful) — the goal is that the *shape* of the environment doesn't hide bugs that only show up later.

## Fast feedback loops

Set explicit speed budgets per test layer and treat budget breaches as a defect in the test suite, not an accepted cost:

| Layer | Typical budget | Why it matters |
|---|---|---|
| Unit tests (full suite) | Under ~2 minutes | Run on every save/pre-commit; slower and developers stop running them |
| Fast integration subset | Under ~5 minutes | Run before push; catches wiring issues without full E2E cost |
| Hot reload / dev server restart | Under a few seconds | Anything slower breaks the edit-see-result loop developers rely on constantly |
| Full CI suite | Minutes, not tens of minutes | Long CI queues delay merge and encourage batching risky changes together |

When a budget is breached: parallelize, split slow tests into a separate tier that doesn't block the fast loop, or fix the underlying slowness (test isolation via containers instead of shared state, mocking slow externals) — don't just let the suite get slower every quarter.

## Onboarding doc, tested by onboarding

The onboarding doc is only trustworthy if it's been executed recently by someone unfamiliar with the project:

- Every new developer's first day is, in effect, a test run of the onboarding doc. Track how long it actually took and what steps needed help outside the doc — that's the doc's bug report.
- Fix the doc immediately when a gap surfaces, in the same week, not "next time someone has bandwidth" — the gap will bite the next new hire identically.
- The doc covers: setup, running the app, running tests, the branch/PR workflow, where to find the architecture overview, and who to ask for what.
- Stale docs are worse than no docs — they cost trust and time simultaneously. Periodically re-run the doc from scratch (a clean clone, ideally by someone who didn't write it) to catch drift.

## Golden-path docs

Beyond onboarding, maintain a small set of "golden path" docs for the most common tasks (add an endpoint, add a migration, add a test, deploy a hotfix) — a working example plus the exact commands, not prose explaining general theory. New contributors copy the golden path rather than reverse-engineering conventions from scattered existing code.

## Pre-commit hooks matching CI

CI should never be the first place a check runs. Pre-commit (or pre-push) hooks run the fast subset of what CI enforces:

- Linting, formatting, type-checking — always in pre-commit; these are fast and deterministic.
- Fast unit tests — in pre-commit if the budget allows; otherwise pre-push.
- The exact same tool versions and config CI uses — a local linter running a different version than CI's is worse than no local linter, because it produces false confidence.
- Slow checks (full test suite, security scans, build) stay in CI, but their *rules* (the linter config, the type-checker strictness) must match what pre-commit already ran, so CI failures are never a surprise about a rule the developer didn't know existed.

## Scripts-to-rule-them-all convention

Standardize a small set of entry points, regardless of the underlying stack, so switching between projects doesn't require re-learning tooling:

| Script | Purpose |
|---|---|
| `script/setup` (or `make setup`) | One-command environment bring-up |
| `script/server` | Start the app locally |
| `script/test` | Run the test suite (or `script/test fast` for the quick subset) |
| `script/lint` | Run linters/formatters, matching pre-commit and CI |
| `script/update` | Bring an existing checkout up to date after a pull (migrations, new deps) |

Every project uses the same names for the same purposes. A developer moving between projects should never need to read a project-specific README to know how to start it.

## Mode handling (G/B)

**Greenfield.** Build the one-command setup, devcontainer, and scripts-to-rule-them-all convention from the first commit — retrofitting them onto an established project is far more expensive than starting with them.

**Brownfield.** Audit current onboarding time and pain points first (ask the most recently onboarded developer what actually happened, not what the README claims). Prioritize fixing the worst friction point rather than a wholesale rewrite of tooling; a working-but-imperfect local setup that's incrementally improved beats a stalled "someday we'll containerize everything" rewrite. Document known parity gaps (e.g., "local uses SQLite, prod uses Postgres") explicitly rather than silently, so bugs caused by the gap are recognized faster.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "The README is basically accurate, we don't need to re-test it." | "Basically accurate" is exactly the failure mode — dependencies and steps drift silently. Re-run it from a clean clone periodically. |
| "New devs can just ask in Slack if something's unclear." | Ad hoc tribal knowledge doesn't scale and isn't discoverable by the next person. Fold the answer back into the doc immediately. |
| "Pre-commit hooks slow down commits, let's skip them." | The alternative is discovering the same failure in CI, later, at higher cost, and repeatedly across the team. |
| "Local doesn't need to match prod exactly, we have staging for that." | Staging catches drift late and expensively. Local parity catches the cheap, common bugs before they leave the laptop. |
| "Test suite is a bit slow but it still passes." | A slow suite gets run less often, which is the actual damage — feedback delayed is feedback avoided. |

## Verification

You are done when:

- [ ] A fresh clone reaches a running local environment via one command.
- [ ] Local infra runs in containers with seeded, representative data.
- [ ] Test-speed budgets are defined per layer and currently met (or a fix is tracked if breached).
- [ ] The onboarding doc has been executed by someone unfamiliar with the project within the last quarter, and gaps found were fixed.
- [ ] Pre-commit hooks run the same lint/type/format rules as CI, using the same tool versions.
- [ ] The scripts-to-rule-them-all set (`setup`, `server`, `test`, `lint`, `update`) exists and is documented.

Evidence to check:
- A new developer's actual time-to-first-successful-run is tracked and trending flat or down.
- No CI failure category exists that pre-commit hooks don't already catch locally, for the fast-enough-to-run-locally checks.

## Anti-patterns

- An onboarding doc that hasn't been executed by anyone since it was written.
- Local setup requiring undocumented tribal knowledge ("oh yeah, you also need to run this one extra script").
- Pre-commit hooks that check different rules, or different tool versions, than CI.
- Letting test suite runtime creep upward release after release with no budget or ownership.
- Local environment using a fundamentally different data store or infra shape than production, with the gap undocumented.

## What this SKILL does NOT do

- Manage deployed dev/staging/prod environments — that's `environments`; this skill is strictly the developer's own laptop and the inner loop.
- Define or run the CI pipeline itself — that's `cicd-pipeline`; this skill ensures pre-commit hooks mirror what that pipeline checks.
- Set coding standards or review criteria — that's `engineering-standards`; this skill ensures those standards are enforced as early (and as fast) as possible, locally.
- Provision cloud infrastructure or IaC — that's `iac`; local containers here are for developer convenience, not a deployment target.
