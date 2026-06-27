# The Project Lifecycle

How a typical project flows through the Praxis.

For the interactive visualization, ask Claude Code to render the lifecycle diagram. The flow below is the text reference.

## Six phases at a glance

```
Phase 1     Phase 2          Phase 3            Phase 4            Phase 5         Phase 6
Bootstrap → Discovery     → Architecture     → Slice loop       → Release       → Steward (quarterly)
/start      /discover        /architect        /slice (×N)        /release        /steward
            ⇣                ⇣                 ⇣                  ⇣               ⇣
            requirements_    architecture_     slice DoD          production_      steward_
            freeze gate      sign_off gate     (Code/Sec/QA)      go_live gate     promotion gate
```

For brownfield projects, `/audit` (codebase comprehension + arch reconciliation + debt audit + impact analysis) runs before Phase 2 Discovery.

## Phase-by-phase

### Phase 1 — Bootstrap (`/start`)

**Lead:** Delivery Lead activates the Delivery Planner.

**What happens:**
- ~10 questions about the project: mode (G/B), data plane, ML, agentic AI, compliance regimes, scale target, availability target, multi-tenancy, stack, cloud.
- `.project/semantic/project-charter.md` is written with all activation flags.
- Architecture documentation skeleton established (`.project/working/architecture/overview.md`, `.project/decision/INDEX.md`).
- Governance gates that apply per the charter are surfaced.

**Output:** Project charter + governance scope. Every other agent reads these.

### Phase 2 — Discovery (`/discover`)

**Lead:** Product Manager.

**Skills:**
- `product-discovery` — JTBD framing, persona surfacing, value hypothesis.
- `requirements-elicitation` — INVEST-compliant user stories + acceptance criteria + scope boundary.
- `requirements-interrogation` — KUACQ block (Knowns / Unknowns / Assumptions / Conflicts / Questions). **Stops here for your input.**
- `nfr-definition` — measurable quality-attribute register tied to user stories.

**Closes at:** `requirements_freeze` gate. Evidence pack: requirements brief, user stories, scope boundary, NFR register, assumptions register, open questions log.

### Phase 3 — Architecture (`/architect`)

**Lead:** Solution Architect.

**Skills:**
- `architecture-pattern-selection` — monolith vs services vs event-driven; CAP / PACELC; per-store consistency.
- `api-design` — OpenAPI / GraphQL / gRPC contracts.
- `data-modeling` — schema with multi-tenant scoping if applicable.
- `resilience-patterns` — circuit breaker, retry, bulkhead per NFR availability.
- `distributed-systems-patterns` — idempotency, saga, outbox (if distributed).
- `multi-tenancy` — if `is_multi_tenant == true`.
- `threat-modeling` — STRIDE + trust boundaries + data flows.
- `project-phasing` — phased roadmap.

Then **Architecture Challenger** reviews with all 5 sub-personas (scale / security / cost / operations / reliability).

**Closes at:** `architecture_sign_off` gate. Evidence: architecture decision + ADR + C4 diagrams + challenge report (mandatory) + phased roadmap.

### Phase 4 — Slice loop (`/slice`, repeated)

**Lead:** Lead Developer decomposes; specialists implement.

**Per slice (2-5 days):**
- Slice opens; implementation packet prepared.
- Specialist (BE / FE / Data / ML-AI) implements per their stack pack + relevant SKILLs.
- For SaaS: BE + FE run in parallel.
- Code Review (7-dimension review).
- Security Review (deep security on PRs touching auth, data, public surface).
- QA Engineer verifies acceptance.
- Slice DoD checked; slice closes.

**Repeats** for each slice in `project_phasing`'s output. Typical: 8-30 slices for an MVP.

**Conditional augmentations** per charter flags:
- `has_data_plane == true`: Data Engineer joins the parallel branch.
- `has_ml == true OR has_agentic_ai == true`: ML/AI Engineer joins; `responsible_ai_review` gate added.
- `is_multi_tenant == true`: `tenant_isolation_review` gate added.

### Phase 5 — Release (`/release`)

**Lead:** Platform / SRE.

**Workflow:** `production-release.yaml` assembles the 10-item evidence pack:

**Always required (Wave 3 baseline):**
1. All pre-prod gates cleared.
2. DR drill recent pass.
3. Capacity sizing verified.
4. SLO observability live.
5. Rollback plan documented.

**Conditional (per change characteristics):**
6. Chaos engineering pass recent.
7. Performance test soak pass.
8. Compliance evidence complete (if regulated).
9. Threat model updated (if architecture changed).
10. Supply chain attestation verified.

If `has_ml` or `has_agentic_ai`: also `responsible_ai_review` evidence pack (5 always + 5 conditional items).

**Closes at:** `production_go_live` gate. Principal reviews + approves. Deploy executes. Release notes generated.

### Phase 6 — Steward (`/steward`, quarterly)

**Lead:** System Steward.

**Cadence:** Every 90 days (the SessionStart hook reminds you when overdue).

**What happens:**
- `factory-evaluation` produces the quarterly report (currently from your observations; future: from telemetry).
- System Steward drafts the quarterly report: library health, findings, proposals (lifecycle changes, trigger tunings, reference / pattern additions, consolidations).
- Routes through `steward_promotion` gate; you approve / reject per proposal.
- Approved changes are applied to the library.

This is the self-improvement loop. **Today it's a structured manual review, not autopilot** — see [`INSTALLATION.md`](../INSTALLATION.md#7-what-about-the-self-evolving-claim) for the honest reset.

## Operating cadences (running parallel)

| Cadence | What runs | Trigger |
|---|---|---|
| **Per slice** (2-5 days) | `implementation-slice.yaml` + 3 review gates | `/slice` |
| **Per release** | `production-release.yaml` + `production_go_live` | `/release` |
| **Monthly** | Architecture-doc reconciliation; runbook freshness; ADR walk | Manual via PLAYBOOK §7.4 |
| **Quarterly** | `factory-evaluation` → Steward report → `steward_promotion` | `/steward` |

## Gates summary

| Gate | When fires | Closes with |
|---|---|---|
| `requirements_freeze` | End of Discovery | PM evidence pack approved |
| `architecture_sign_off` | End of Architecture | SA + Challenger evidence approved |
| `production_go_live` | Each release | 10-item evidence pack approved |
| `responsible_ai_review` | If ML / agentic AI | 5 always + 5 conditional items |
| `steward_promotion` | Quarterly | Per-proposal evidence packs |
| `tenant_isolation_review` | If multi-tenant | Tenancy model + isolation evidence |
| `hipaa_control_review` / `pci_scope_review` | Per regime | Regime-specific control matrices |
| `capacity_stress_test` | If high QPS / availability | Load test + bottleneck analysis |

Plus per-slice quality gates (Code Review, Security Review, QA) — these don't have evidence packs at the same level; they're verdicts that gate merge.

## What you (as principal) actually do

The agents do the writing; you do the judgment. Concretely:

- **Paste slash commands** at phase transitions.
- **Answer KUACQ blocks** when interrogation surfaces unknowns.
- **Review evidence packs** when gates fire — approve, reject, or send back with reason.
- **Make calls** the agents escalate (NFR trade-offs, architecture overrides, security risk acceptances).
- **Run quarterly steward review** to keep the library sharp.

The agents handle: discovery synthesis, NFR articulation, architecture documentation, ADR drafting, threat model writing, slice decomposition, implementation, review, evidence pack assembly, release coordination.

Together: you get a documented, governed, evidence-based delivery without doing every artifact by hand.
