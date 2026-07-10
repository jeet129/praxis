# Roadmap

Honest, non-binding view of what's next. Praxis is alpha; this list reflects
priority and intent, not committed dates. Items move between buckets as
real-project use (or the lack of it) reprioritizes them. See
[`CHANGELOG.md`](CHANGELOG.md) for what's already shipped and
[`README.md`](README.md#roadmap) / [`PLAYBOOK.md`](PLAYBOOK.md) for how the
library is meant to be used today.

---

## Near-term

Work that's scoped, mostly mechanical, and blocks or de-risks everything else.

- ~~**Loop engineering for autonomous drive.**~~ **Shipped.** The outer
  drive loop is real: `scripts/praxis-drive.sh` (fresh-context harness
  invocations against the task ledger until a stop), the autonomy dial +
  run budgets + stall detection in `governance/autonomy.yaml`, the loop
  contract + task ledger schemas in `references/loop-contracts.md`, the
  `skills/autonomous-drive` delivery-lead protocol, the `/drive` command,
  drive telemetry at `.project/telemetry/drive.jsonl` feeding
  `scripts/factory-routing-report.py`, and slice-close async summaries at
  `.project/telemetry/summaries/`. Operator guide:
  [`docs/autonomous-drive.md`](docs/autonomous-drive.md). Follow-ons below.
- ~~**Modernization workflow (strangler-fig legacy replacement).**~~ **Shipped.**
  `workflows/modernization.yaml` — deep comprehension + seam identification,
  target architecture + migration strategy sign-off (`modernization_strategy_sign_off`),
  a per-seam increment loop (characterization tests → `implementation-slice`
  sub-workflow → parallel-run comparison telemetry → `parallel_run_verification`
  gate → traffic shift), and a gated legacy decommission phase
  (`legacy_decommission_approval`). Alongside two other new workflows —
  `expedited-change.yaml` (P0/P1 emergency fix, compressed gates + mandatory
  retroactive review) and `spike.yaml` (time-boxed feasibility exploration;
  spike code never merges) — plus six new conditional governance gates. Routed
  from `skills/using-praxis/SKILL.md`'s intent tree; see
  [`docs/scenarios.md`](docs/scenarios.md) Scenarios 8, 14, 15.
- **Deterministic workflow linter.** Today, `workflows/*.yaml` are declarative
  specs interpreted by the `delivery-lead` agent — an LLM, not a deterministic
  engine. Decision-node predicates (`nfr_satisfied`, `requirements_complete`,
  `slice_acceptance_met`, `production_ready`, ...) and gate wiring are enforced
  by agent discipline plus the governance gates, not by a parser. A linter that
  statically validates workflow YAML (step references resolve, decision nodes
  reference real predicates, gates referenced in `governance.yaml` actually
  exist, no orphaned steps) would catch authoring mistakes before they reach an
  agent at runtime.
- **`scripts/build-registry.py --check` in CI, fully wired.** Keep agent/skill/
  workflow counts and cross-references accurate automatically instead of by
  hand-editing README prose on every change.
- **Remaining reference backlog — high-priority items first.** Per
  `references/MISSING-INVENTORY.md`, roughly 98 cited references are still
  missing; write the `high`-priority ones next:
  `api-design/references/rest-openapi.md`,
  `compliance-privacy/references/{hipaa,pci-dss}.md`,
  `deploy-release/references/{kubernetes-rollouts,argo-rollouts}.md`,
  `ml-feature-engineering/references/feast.md`,
  `ml-monitoring-drift/references/evidently.md`,
  `ml-serving-deployment/references/{kserve,batch-online-streaming}.md`,
  `performance-testing/references/k6.md`,
  `rag-design/references/qdrant.md`,
  `secrets-config/references/{k8s-external-secrets,hashicorp-vault}.md`.
- **Test the library on real projects.** At least 3 real greenfield projects
  and 2 brownfield engagements — the single highest-value validation activity,
  and the gate everything else (trigger tuning, skill slimming, reference
  priority) should ultimately be driven by.
- **Model-routing telemetry review.** Now that routing decisions log to
  `.project/telemetry/model-routing.jsonl`, do at least one real pass
  correlating tier choices against gate-failure/escalation rates before
  claiming the ±1-tier adaptive routing is well-calibrated.
- **Codex/Gemini drive parity hardening.** `governance/autonomy.yaml`
  declares headless invocation commands for all three harnesses
  (`claude-code`, `codex`, `gemini-cli`), but only the Claude Code path has
  real mileage. Exercise `scripts/praxis-drive.sh` against `codex exec` and
  `gemini -p` on a real slice, confirm budget-flag behavior where the
  harness doesn't natively support `--max-budget-usd` (currently `null` for
  both), and fix any harness-specific stop-condition or ledger-parsing gaps
  found along the way.

## Mid-term

Needs the near-term groundwork (real usage, registry data) to do well.

- **`examples/` case studies.** One worked greenfield run and one worked
  brownfield run, captured end-to-end (charter → gates → release), so new
  users can see the full lifecycle instead of piecing it together from the
  playbook prompts. `examples/` currently exists as an empty extension point.
- **A recorded end-to-end driven slice in `examples/`.** Capture one real
  slice run entirely through `/drive` or `scripts/praxis-drive.sh` —
  ledger evolution, telemetry, the slice-close summary, and every stop the
  runner made — as a concrete worked example of drive mode, distinct from
  the interactive case studies above.
- **`evaluations/` — first factory-evaluation run.** The `factory-evaluation`
  skill and the telemetry stack (`factory-record.sh`, `factory-aging.sh`,
  `factory-frequency.sh`) are wired, but no full quarterly-style synthesis has
  been run yet. Running it once, on real accumulated telemetry, is the
  prerequisite for trusting the aggregation and for the System Steward's
  quarterly cadence to mean anything.
- **Wave 4 operational-hardening completion.** `production-release.yaml` and
  `implementation-slice.yaml` both reference Wave-4 items not yet feasible in
  the current gate baseline (e.g. `chaos_engineering_pass_recent` and other
  reliability/DR evidence items) — see the `Wave scope notes` sections of
  those workflow files. Land the remaining reliability, chaos, multi-tenancy,
  and cost-hardening skills so `production_go_live` can enforce the full
  Wave-4 evidence set instead of falling back to the Wave-3 baseline.
- **Wave 5/6 conditional-plane validation.** Data-plane (`Wave 5`,
  `has_data_plane`) and ML/agentic-AI-plane (`Wave 6`, `has_ml` /
  `has_agentic_ai`) branches in `implementation-slice.yaml` are currently
  `deferred_until_wave_5` / `deferred_until_wave_6` conditional activations —
  present in the workflow spec but not yet exercised on a real project with
  those flags set.
- **Remaining `medium`-priority reference backlog** from
  `references/MISSING-INVENTORY.md` (data warehouse engines, data
  orchestrators, additional compliance regimes, additional stack frameworks).
- **Patterns directory population.** `patterns/` is an extension point today;
  populate it from genuine cross-project recurrences once there are enough
  real engagements to recognize a pattern rather than guess one.

## Later

Depends on real signal that doesn't exist yet, or is explicitly opportunistic.

- **Real factory-evaluation *synthesis* pipeline.** Telemetry capture is
  automatic; the quarterly System Steward synthesis is still a manual read of
  the aggregates. Automating trend detection across quarters is worth doing
  once there are several factory-evaluation runs to compare.
- **Additional language stacks** (Go, Rust, Kotlin where Spring isn't the
  right fit) — add when a real project needs one, not speculatively.
- **New capability tiers / model families** as vendors ship them — the
  `governance/model-routing.yaml` design exists precisely so this is a
  single-file edit plus `scripts/apply-model-routing.py`, not an agent rewrite.
- **Parallel task consumption in drive mode.** Today `scripts/praxis-drive.sh`
  runs one task per iteration, strictly in `depends_on` order — deliberate,
  not an oversight. Explicitly deferred until drive telemetry
  (`.project/telemetry/drive.jsonl`, aggregated by
  `scripts/factory-routing-report.py`) shows enough queue depth (independent
  open tasks piling up within a slice) to justify the added complexity of
  concurrent ledger writes and multi-agent coordination.
- **`low`-priority reference backlog** (Jenkins, FedRAMP, Synapse, and other
  narrow-applicability items) from `references/MISSING-INVENTORY.md`.
- **Claude Code marketplace publication** and continued Codex/Gemini/other
  harness parity, once the library has enough real-project mileage to call
  itself stable rather than alpha.

---

The library intentionally does not aim to keep growing in raw skill count —
per the Knowledge Growth Policy (`agents/system-steward.md`), growth is meant
to flow into references, patterns, and examples once the core skill set is in
place, not into an ever-larger SKILL catalog. This roadmap reflects that bias.
