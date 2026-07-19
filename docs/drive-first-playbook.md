# Praxis in practice — a drive-first scenario playbook

A single product's life — from a rough idea to launch, and then the **ongoing
sprint-by-sprint steady state** (§9) where new epics and stories keep arriving —
told through every Praxis workflow, with an explicit call on **when to run drive
mode and when to stay interactive**. Commands are shown for both harnesses:
Claude Code `/command` · Codex `$praxis-command`.
Workflows without a dedicated command (spike, expedited-change, modernization)
are entered by describing the intent.

---

## Read this first: the drive rule

**Drive mode = the runner iterates between human touchpoints instead of you
advancing each step.** Two altitudes:

- **slice-drive** — `/drive` (`$praxis-drive`) loops a slice's *task ledger*
  (`.project/working/slice-<id>-tasks.yaml`): take the next ready task, run it on
  its tier's model, verify, update status, repeat.
- **workflow-drive** — `/drive --workflow` loops a *workflow's steps*
  (`.project/working/workflow-state.yaml`), each on its phase-tier model.

**The autonomous zone is C→D (implementation → release).** Discovery (A) and
architecture (B) are high-judgment and stay interactive/human-gated — you cannot
drive them, because that's where the machine-checkable exits are *created*. Any
step outside the ledger's `autonomy_zone` is never driven. Governance gates
always stop, regardless of the dial.

**The dial (`governance/autonomy.yaml` → `stop_after`), least to most autonomous:**

| Setting | Stops after every… | Use when |
|---|---|---|
| `task` | task | building trust in a new workflow; first slice of a phase |
| `slice` | slice close | you want to review each slice before the next |
| `phase` | phase boundary | you trust slices but want phase checkpoints |
| `gate` | only real stops (gates, decisions, budget/stall) | you trust the loop — **the drive-first default** |

Three stops are **non-negotiable** even at `stop_after: gate`: decision points,
governance gates, and budget/stall/exhaustion.

**The heuristic for "should I drive this?"** — if the exit is
**machine-verifiable** (tests pass, a validator exits 0, evidence file exists) →
**drive it**. If the exit is a **judgment call** (is this the right design? is
this idea good enough? is this incident really a P0?) → stay interactive. Praxis
is built so the machine-checkable work is exactly the work drive runs.

---

## Meet the product: "Kanso"

Kanso is a new multi-tenant SaaS for small-team retrospectives. We'll follow it
from a rough idea to production and beyond, and every Praxis workflow will show
up naturally.

---

## 1. The idea is rough — `ideation-refinement-loop`

**Situation:** you have a one-paragraph pitch for Kanso and want it sharpened
before spending discovery effort on it.

**Run:** `/refine-idea` (`$praxis-refine-idea`).

**How it drives:** this workflow is a **self-driving bounded loop** — a
creator/reviewer/enhancer cycle with an arbiter that scores convergence, now
machine-checked (the arbiter writes `recommended_disposition: converged` and the
loop exits via `check: status_field`). So it iterates *itself* to convergence
without you advancing each pass. You don't need `/drive` here; the loop is the
drive.

**Stops at:** `ideation_refinement_approval` — a human sign-off on the converged
artifact before it enters discovery.

**Recommendation:** let the loop run; review only at the approval gate. Cap
passes via the loop's `max_iterations` if you want a tighter box.

---

## 2. Build Kanso from scratch — `greenfield-saas`

**Situation:** the idea is approved; build the product.

This is the full lifecycle. It's where the interactive-vs-drive split is
clearest, so it's worth walking phase by phase.

**A — Discovery (interactive).** `/start` (`$praxis-start`) to bootstrap the
charter (multi-tenant: yes, has data plane, scale target, compliance), then
`/discover` (`$praxis-discover`). PM + requirements skills produce the KUACQ
block and stop for you. **Do not drive** — requirements are judgment. Gate:
`requirements_freeze`.

**B — Architecture (interactive).** `/architect` (`$praxis-architect`): Solution
Architect proposes the design, the **Architecture Challenger** attacks it
adversarially, ADRs capture decisions. **Do not drive** — this is where the
checkable exits for C are born. Gate: `architecture_sign_off`.

**C — Implementation (DRIVE).** Now the ledgers exist and every task has a
`verify`. This is drive's home. Two ways:
- Per slice: `/slice` to open, then `/drive` — slice-drive runs the tasks.
- Whole implementation→release span: `/drive --workflow` with the workflow-step
  ledger — workflow-drive runs phases C→D, each on its phase-tier model.

**D — Release (drive to the gate).** Drive carries through to
`production_go_live`, then hard-stops for the human.

**Recommendation:** run A and B interactively; then **`/drive --workflow` with
`stop_after: gate`** for C→D. It will implement slice after slice, run reviews,
and halt at `production_go_live`. Reserve `stop_after: phase` if you want a
checkpoint at each phase boundary the first time through.

*(Variant: `greenfield-api-service` — identical spine without the UX phase, for
a service with no first-party UI.)*

---

## 3. The unit of work — `implementation-slice`

**Situation:** one bounded piece of Kanso — say the "create retro board"
endpoint + UI.

**Run:** `/slice` (`$praxis-slice`) to decompose and open the ledger, then
`/drive` (`$praxis-drive`).

**How it drives:** slice-drive is *literally* built for this — Lead Developer
decomposes into tasks with `verify` commands; drive runs each, executes verify,
updates status, and at drain runs Code Review + Security Review + QA before
closing.

**Stops at:** the per-slice review verdicts are part of the **drain**, not human
gates — drive runs them. It stops only at a real governance gate, a decision
point, or budget/stall.

**Recommendation:** **strongest drive recommendation of all.** `/drive` with
`stop_after: gate`. Use `stop_after: task` only for the very first slice while
you calibrate trust, then move the dial to `gate`.

---

## 4. Ship it — `production-release`

**Situation:** a slice (or a set) is ready for production.

**Run:** `/release` (`$praxis-release`).

**How it drives:** the release *execution* is machine-checkable — assemble the
evidence pack, run capacity verification, execute the deploy strategy with
rollback armed, run post-deploy verification. Drive can carry all of that up to
the gate.

**Stops at:** `production_go_live` — always a human stop. Nothing machine-clears
a go-live.

**Recommendation:** **drive up to the gate.** Under `/drive --workflow` the
release phase runs its verification steps autonomously and halts at
`production_go_live` for your approval; post-deploy verification then runs on the
far side.

---

## 5. "Can we even do X?" — `spike`

**Situation:** before committing Kanso to real-time collaborative editing, you
need to know if the approach is feasible.

**Run:** describe it — "prove real-time editing is feasible, time-box 3 days."

**How it drives:** the build-to-learn loop is a bounded loop, so it *can* be
driven — but the output is **evidence, not production code** (spike code never
merges), and the value is in what you learn, so tighter oversight pays off.

**Stops at:** `spike_disposition` — a human call to archive the report or promote
it into discovery.

**Recommendation:** drive the build loop with a **tighter dial (`stop_after:
slice` or `phase`)** so you review the learning as it accrues, and keep the
disposition human. Drive here is a convenience for the mechanical build cycles,
not an autopilot for the judgment.

---

## 6. Change the shipped product — `brownfield-enhancement`

**Situation:** Kanso is live; now add SSO/SAML login to an existing auth module.

**Run:** `/audit` (`$praxis-audit`) first — comprehension → architecture
reconciliation → tech-debt → **impact analysis** (names the blast radius before
you touch anything). Then slices.

**How it drives:** `/audit` is a read-and-assess review — **interactive, don't
drive** (its value is your judgment on the findings). Once impact analysis has
scoped the change and the slice ledgers exist, the implementation is **drive
territory** exactly like greenfield's C phase.

**Stops at:** `architecture_sign_off` if the change needs design work;
per-governance gates on release.

**Recommendation:** audit interactively; then `/drive` the enhancement slices
(`stop_after: gate`). Brownfield's only extra discipline is that impact analysis
runs *before* any modification — let it, then drive.

---

## 7. Replace the legacy monolith — `modernization`

**Situation:** Kanso's original monolith can't scale; replace it incrementally
without a big-bang rewrite.

**Run:** describe it — "modernize the Kanso monolith via strangler-fig."

**How it drives:** comprehension and **target architecture + migration strategy
are sign-off gated before any seam is touched** (interactive). But then each
increment carves one seam, builds its replacement **as an `implementation-slice`
sub-workflow** (drive territory), runs old and new in parallel with comparison
telemetry, and shifts traffic — a naturally loopable, machine-verifiable cycle.

**Stops at:** `modernization_strategy_sign_off` (once), `parallel_run_verification`
(per increment), `legacy_decommission_approval` (at the end).

**Recommendation:** strategy interactive; then **`/drive --workflow` the
increment loop** with `stop_after: gate` — it will build each seam's replacement,
and halt at each `parallel_run_verification` for you to confirm old/new parity
before traffic shifts. The per-increment gates are exactly the right drive
checkpoints.

---

## 8. Production is down — `expedited-change`

**Situation:** a P0 auth outage on Kanso needs a fix now.

**Run:** describe the incident and severity — the front door checks
`incident-runbook` severity first; only genuine P0/P1 (or a critical security
patch) is expedited-eligible (anything less reroutes to brownfield-enhancement).

**How it drives:** gates are compressed to what a 2 a.m. responder can clear —
blocker-only review, single-approver go-live, rollback armed. The fix-and-verify
cycle is machine-checkable and can be driven, but the **severity judgment and the
go-live approval are human**, and the compression is **repaid**: a normal-bar
review, a postmortem, and a debt entry per shortcut.

**Stops at:** `expedited_change_approval` (single approver), and the
**mandatory** `expedited_change_retro` — the retro half is not optional.

**Recommendation:** you *can* drive the fix-verify loop to move fast, but keep
the incident call and the deploy approval interactive, and **do not let drive
"finish" the workflow — the retro is a required later stop.** This is the one
place to favor a human hand on the wheel even though parts are drivable.

---

## 9. Steady state — sprint-by-sprint, new epics/stories arriving

Sections 2–8 are the *arc* of a product. But most of a product's life is **not**
a fresh lifecycle — it's a continuous stream of epics and stories landing sprint
after sprint, each a new requirement. And here's the important part: **you don't
route these by hand.** There's one command.

### Run `/intake` (`$praxis-intake`) — the steady-state front door

When any new requirement arrives — a story, epic, ticket, stakeholder ask, or
change request — run **`/intake`** and drop the ask. It fronts the
`requirements-intake` discipline, which does the right-sizing *for* you: it logs
the ask to `.project/working/inbox.md`, triages it (size + blast radius +
owner), and routes it to the lightest safe path — so you pick nothing:

| The ask is… | `/intake` routes it to |
|---|---|
| a small, ready story (clear AC, low blast radius) | slice ledger → `/drive` |
| a change to existing behavior | `impact-analysis` → slice → `/drive` |
| an epic / cross-cutting change | group → `/discover` → `/architect` → `project-phasing` → slices |
| an unproven approach | `spike` |
| a P0/P1 production break | `expedited-change` |

It exists specifically to prevent the two steady-state failure modes:
**FIFO churn** (every small ask gets full discovery+architect ceremony and the
team burns out) and **impulse coding** (a small ask skips impact-analysis and
detonates a load-bearing module). You get told the routing decision in a line or
two, and it proceeds — stopping only at the one human gate the route actually
requires.

So the whole steady-state loop collapses to: **new requirement → `/intake` → it
routes and (for the common case) hands to `/drive`.** The routing table above is
what the command decides internally; you don't work through it.

**The roadmap is the backlog behind it.** Under the hood, `project-phasing`
keeps a dependency-ordered roadmap of vertical slices (re-run "when re-planning
mid-project"), so an epic *extends* the roadmap rather than starting a new
project. An **epic** is a roadmap grouping (often a phase); a **story** is one
vertical slice; a **slice** is the unit drive runs.

**Definition of ready = drive-eligible.** A story is drivable only when it has
**machine-checkable acceptance criteria and a `verify` command** — `/intake`'s
triage is what establishes that (running `requirements-interrogation` on a vague
ask before it's allowed to become a slice). "Grooming a story" *is* "making it
drive-eligible"; intake does that step so the rest can run unattended.

**A groomed sprint drives as one continuous run.** Because drive pulls the next
ledger from the roadmap at each slice close (`stop_after: gate`), a backlog of
ready, dependency-ordered slices can be driven straight through — Lead Developer
produces the next slice's ledger, drive implements it, drains it (review + QA),
and moves on — stopping only at a governance gate (e.g. the sprint's release) or
a decision point. You don't re-launch drive per story.

**Cadence mapping:**

| Sprint ritual | Praxis action | Drive? |
|---|---|---|
| A new story/epic/ticket arrives | **`/intake`** — it triages, right-sizes, and routes (you pick nothing) | It hands to `/drive` for the common case |
| Backlog grooming / sprint planning | `/intake` per item establishes AC + `verify` + sequencing; `project-phasing` extends the roadmap | No — this is the judgment that *earns* autonomy |
| Sprint execution | `/drive` the ready slices from the roadmap | **Yes** — `stop_after: slice` while calibrating, `stop_after: gate` once trusted |
| Story needing design | `/intake` escalates it → `/architect` design increment before slicing | No (architecture is B) |
| Sprint end / release | `/release` to `production_go_live` | Drive to the gate |
| Sprint retro | Notes to `.project/episodic/`; `/steward` is the *quarterly library* review, not the per-sprint retro | No |

**One-line rule for steady state:** `/intake` every new requirement — it makes
stories drive-eligible and routes them — then `/drive` the roadmap at
`stop_after: gate` and let it flow slice to slice. You run two commands, not a
decision tree.

---

## Cross-cutting — these stay interactive (not drive)

- **`/review` (`$praxis-review`)** — on-demand adversarial review of any artifact
  (Challenger + Code + Security reviewers). Judgment work; run it interactively
  whenever you want a second opinion outside a gate.
- **`/steward` (`$praxis-steward`)** — quarterly library review. Reads the
  telemetry reports and proposes skill promotions/retirements. Human cadence.
- **`/factory-record`** (Claude Code; no dedicated Codex command) — capture a
  telemetry observation. A one-shot, not a loop.

---

## Drive recommendation at a glance

| Workflow | Command | Drive it? | How | Always stops at |
|---|---|---|---|---|
| ideation-refinement-loop | `/refine-idea` | Self-driving loop | converges via arbiter | `ideation_refinement_approval` |
| greenfield-saas / -api-service | `/start`→`/discover`→`/architect`→`/slice`→`/release` | **C→D only** | `/drive --workflow`, `stop_after: gate` | `requirements_freeze`, `architecture_sign_off`, `production_go_live` |
| implementation-slice | `/slice` + `/drive` | **Yes — its home** | slice-drive, `stop_after: gate` | governance gates / decisions |
| production-release | `/release` | **Yes, to the gate** | drive runs verification steps | `production_go_live` |
| spike | *(intent)* | Yes, tighter oversight | `stop_after: slice`/`phase` | `spike_disposition` |
| brownfield-enhancement | `/audit` then `/slice`+`/drive` | **Implementation yes; audit no** | audit interactive, then slice-drive | `architecture_sign_off`, release gates |
| modernization | *(intent)* | **Increment loop yes** | `/drive --workflow`, `stop_after: gate` | strategy sign-off, per-increment `parallel_run_verification`, `legacy_decommission_approval` |
| expedited-change | *(intent, P0/P1)* | Fix loop yes, judgment no | drive fix-verify; humans on severity + go-live + retro | `expedited_change_approval`, `expedited_change_retro` |

**One-line rule:** drive the C→D machine-verifiable work at `stop_after: gate`;
keep discovery, architecture, incident judgment, and every governance gate in
human hands. If you're unsure whether a step is drivable, ask "is the exit a
test/validator/evidence check, or a judgment?" — the answer routes you.

---

## Two ways to actually launch drive

- **In-session:** `/drive` (`$praxis-drive`) — the orchestrator iterates
  continuously within the session until a stop. Convenient; good for watching it
  work.
- **Unattended (deterministic):** the runner loops in a subprocess regardless of
  the model — the reliable path for a whole slice/workflow:
  ```bash
  # Claude:  PKG=$(dirname "$(dirname "$(find ~/.claude/plugins -name praxis-drive.sh|head -1)")")
  # Codex:   PKG=$(find ~/.codex -type d -name praxis-codex|head -1)
  bash "$PKG/scripts/praxis-drive.sh" --project-dir . --harness <claude-code|codex>            # slice-drive
  bash "$PKG/scripts/praxis-drive.sh" --project-dir . --harness <claude-code|codex> --workflow  # workflow-drive
  ```
  Add `--dry-run` first to preview. The runner enforces `run_budget` caps and
  stall detection outside the agent's context — prefer it for long unattended
  runs.
