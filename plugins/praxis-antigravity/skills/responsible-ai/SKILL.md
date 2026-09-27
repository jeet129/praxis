---
name: responsible-ai
description: "Fairness, robustness, transparency, and safety practices for ML and AI systems. Bias audits per protected slice, robustness checks (adversarial / distribution shift), explainability (SHAP / LIME / feature attribution), model cards and datasheets, human-in-the-loop policy, escalation on harm signals. HARD GATE — not optional for models that affect people, decisions, or regulated surfaces. Fires for both traditional ML and agentic AI / LLMs . ML/AI Engineer co-runs with Security Reviewer; PM contributes the harm-scenario definitions; compliance-privacy consumes outputs for regulated regimes."
---

# Responsible AI

<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: ml
state: active
dependencies:
 - ml-problem-framing
 - ml-training-evaluation
 - ml-monitoring-drift
 - threat-modeling
 - compliance-privacy
triggers:
 - "model affects people or decisions; fairness must be audited"
 - "preparing the responsible-AI evidence pack for production_go_live"
 - "investigating a fairness regression in production"
 - "adversarial robustness check before release"
 - "explainability required for regulated regime or customer-facing decisions"
 - "harm-signal escalation from production monitoring"
outputs:
 - fairness audit (per protected slice; with metric + threshold + finding)
 - model card (per `ml-training-evaluation`; this skill verifies it's complete)
 - datasheet for the training data (provenance + composition + known biases)
 - human-in-the-loop policy (where humans review / override; cadence; criteria)
 - harm-signal escalation runbook
 - explainability evidence (per prediction or aggregate; tool-specific)
consumers:
 - ml-ai-engineer (primary co-author with Security Reviewer)
 - security-reviewer (audits responsible-AI posture)
 - compliance-privacy (consumes for regulated-regime evidence)
 - product-manager (consumes for harm-scenario design)
 - production-release.yaml workflow (consumes responsible_ai_review gate evidence)
references:
  - worked-examples.md
```
<!-- praxis:metadata:end -->

The discipline that asks the questions ML and AI projects often skip: *who is affected, how could this go wrong, what controls prevent that?* For models that affect people's lives — credit, employment, healthcare, content moderation, search ranking — responsible-AI is non-negotiable. For agentic AI / LLM features, the same discipline applies with content-safety and prompt-injection added.

The principle: **fairness, robustness, transparency, and safety are properties, not afterthoughts. They are designed in, audited, monitored, and gated.**

## When this skill fires

- A model is in design and the harm scenarios need definition (per `ml-problem-framing`'s risk log).
- A trained model is being evaluated for responsible-AI properties before release.
- An LLM / agent feature is being designed (Chunk B ) — applies with content-specific extensions.
- The production_go_live gate requires `responsible_ai_review` evidence per `governance.yaml`.
- A fairness regression is detected in production via `ml-monitoring-drift`.
- A regulated regime requires explainability or audit (per `compliance-privacy`).

## The four pillars

### 1. Fairness

Does the model perform equally well across groups, especially protected classes? Disparate impact is the test:

| Class of metric | What it measures |
|---|---|
| **Demographic parity** | Predicted positive rate equal across groups. |
| **Equal opportunity** | Recall equal across groups (when target is binary). |
| **Equalized odds** | Both recall and false-positive rate equal across groups. |
| **Calibration parity** | Predicted probabilities calibrated within each group. |

No single metric captures fairness perfectly; the metrics conflict in many situations. The team **picks the relevant metric explicitly per problem** and documents the choice in the model card.

Implementation: per-slice metrics from `ml-training-evaluation`, audited against thresholds, with disparate-impact findings flagged. Load `references/worked-examples.md` for a full worked fairness-audit excerpt (Hiring Resume Screening Model, equal-opportunity metric, per-group TPR table, findings, mitigations, residual risk).

Fairness audits are uncomfortable. The discomfort is the work — it surfaces what would otherwise stay hidden until lawsuit or news story.

### 2. Robustness

Does the model perform reliably under realistic perturbations?

- **Distribution shift** — model performance under feature distribution changes (per `ml-monitoring-drift`).
- **Adversarial robustness** — model behavior under adversarial inputs (perturbations designed to fool the model).
- **Sub-population robustness** — performance on long-tail or under-represented groups (related to fairness).
- **Temporal robustness** — performance stable over time (related to drift).

Tools and methods:

- **Adversarial example generation** — FGSM, PGD for vision; TextAttack for NLP.
- **Robustness benchmarks** — standardized perturbed test sets.
- **Slice analysis** — performance on hard sub-populations.

Robustness findings inform retraining priorities and serving-time defenses (input validation, sanity checks).

### 3. Transparency / explainability

Can the model's decision be explained?

- **Global explainability** — what features matter overall? (Feature importance, SHAP summary plots.)
- **Local explainability** — why this specific prediction? (LIME, SHAP per instance.)
- **Mechanistic** — what's the model actually doing internally? (Hard for deep learning; easier for linear/tree models.)

Required when:

- **Regulation demands it** — EU AI Act, fair lending laws, etc.
- **Customer demands it** — "why was I declined?"
- **Internal stakeholders need it** — to trust + improve the system.

Tools:

- **SHAP** — game-theoretic; broadly applicable.
- **LIME** — local approximations; framework-agnostic.
- **Captum** (PyTorch) — attribution methods built-in.
- **InterpretML** — Microsoft's explainability toolkit.

Explainability has limits. Deep models often resist clean explanation; document what's possible and what's not.

### 4. Safety + harm prevention

What's the worst this model can do? What controls prevent it?

- **Harm scenarios** — defined at framing time (per `ml-problem-framing`); refreshed per release.
- **Human-in-the-loop** — where humans review or override. High-stakes decisions usually require it.
- **Escalation paths** — when the model is uncertain or the input is unusual, escalate to humans.
- **Audit trail** — every consequential decision logged with model version, inputs, prediction, and human override (if any).
- **Kill switch** — ability to disable the model instantly when harm signal triggers.

The human-in-the-loop policy is explicit per model (mandatory-review triggers, optional-review defaults, audit logging, override handling). Load `references/worked-examples.md` for a full worked HITL policy (Loan Approval Model v3.0).

## Datasheet for the training data

A **datasheet** documents the training data with the same rigor as a model card documents the model, per Gebru et al.'s *Datasheets for Datasets* (motivation, composition, collection process, preprocessing, uses, distribution, known biases, maintenance). Load `references/worked-examples.md` for a full worked datasheet (Resume Screening Training Data v3.2). The datasheet is required output; consumed by `compliance-privacy` for regulated regimes.

## The responsible-AI gate

Per `governance.yaml`, the `production_go_live` evidence package includes `responsible_ai_review` for models that affect people / decisions. The evidence:

1. **Fairness audit** — per-slice metrics; thresholds; findings + mitigations.
2. **Robustness check** — adversarial / distribution / sub-population.
3. **Explainability evidence** — required per regime; sample explanations.
4. **Model card** — complete (per `ml-training-evaluation`).
5. **Datasheet for the training data** — complete.
6. **Human-in-the-loop policy** — defined and configured.
7. **Harm-signal escalation runbook** — defined and rehearsed.

ML/AI Engineer assembles; Security Reviewer audits; PM signs off on the policy choices. The gate doesn't clear without all seven items.

## Continuous monitoring (handoff to `ml-monitoring-drift`)

Responsible-AI is continuous, not one-time:

- **Per-slice production performance** — `ml-monitoring-drift` instruments the per-slice metrics; fairness regressions trigger investigation.
- **Override pattern analysis** — humans overriding the model systematically indicate fairness or robustness issues.
- **Harm signals** — user complaints, regulatory inquiries, news mentions — escalation runbook triggers.

## Outputs

| Output | Location |
|---|---|
| Fairness audit | `.project/operational/ml-models/{model}-fairness-audit-{date}.md` |
| Robustness check | `.project/operational/ml-models/{model}-robustness-{date}.md` |
| Explainability evidence | `.project/operational/ml-models/{model}-explainability/` |
| Datasheet for training data | `.project/semantic/ml-datasheets/{dataset}.md` |
| Human-in-the-loop policy | `.project/procedural/hitl-policy-{model}.md` |
| Harm-signal escalation runbook | `.project/operational/runbooks/harm-signal-{model}.md` |
| Responsible-AI evidence pack | `.project/operational/ml-models/{model}-responsible-ai-{release}.md` |

## Mode handling (G/B)

**Greenfield.** Build responsible-AI in from problem framing. Risk log + fairness criteria explicit before training.

**Brownfield.** Audit existing models. Common findings: no fairness audit; no datasheet; no harm-signal escalation; "the model works" because no one's measuring fairness. Prioritize models that affect people first; non-customer-facing internal models later.

## What this skill does not do

- Train models — that's `ml-training-evaluation`.
- Serve models — that's `ml-serving-deployment`.
- Monitor drift — that's `ml-monitoring-drift` (this skill defines fairness criteria; that skill instruments the monitoring).
- General security — that's `threat-modeling` + `secure-coding`.
- LLM-specific safety (jailbreak, content filtering) — that's `llm-safety` ; this skill is the broader responsible-AI framework that includes it.

## Verification

You are done when:

- [ ] Fairness audit complete with per-slice metrics + thresholds + findings.
- [ ] Robustness check: adversarial + distribution-shift + sub-population.
- [ ] Explainability evidence (SHAP / LIME / feature attribution OR agent decision trace).
- [ ] Human-in-the-loop policy documented + configured.
- [ ] Harm-signal escalation runbook documented + rehearsed.
- [ ] Model card (for traditional ML) OR agent architecture + safety design (for agentic AI).
- [ ] Datasheet for training data (traditional ML) OR eval suite pass (agentic AI).
- [ ] Responsible-AI evidence pack assembled for the `responsible_ai_review` gate.
- [ ] Continuous monitoring wired (per `ml-monitoring-drift` per-slice metrics).

Evidence to check:
- An auditor can reproduce the fairness finding from the artifacts.
- Last harm-signal simulation triggered the runbook correctly.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We don't use protected attributes — no fairness audit needed." | Proxies (zip code → race; school → SES). Fairness shows up even when protected attributes aren't features. |
| "Our model is just a recommender; low stakes." | Recommenders shape what people see and choose. Fairness regressions hit at scale silently. |
| "We'll audit fairness if regulation requires it." | Regulation lags incidents. Audit before deployment; the cheap moment is now. |
| "Explainability isn't possible for deep models." | Partial explainability (SHAP, feature attribution) is. Document what's possible and what isn't. |
| "Move fast; we'll add HITL later." | Once auto-decisions are deployed, retrofitting HITL means re-architecting the request flow. Design HITL in. |
| "The model card is paperwork." | The model card is the artifact that surveys, audits, and post-incident analyses use. It's not paperwork; it's the record. |

## Anti-patterns

- Fairness audit skipped because "we don't use protected attributes" (proxies and indirect effects matter).
- Single fairness metric optimized; others ignored (fairness metrics conflict; choice must be explicit).
- Datasheet skipped (training-data biases hidden).
- Human-in-the-loop policy ad-hoc (not documented; not auditable).
- Harm-signal escalation untested.
- Explainability claimed but never demonstrated.
- Continuous fairness monitoring skipped (snapshot at release; no monitoring after).
- "Move fast" used to skip responsible-AI for stakes that warrant it.
- Responsible-AI seen as compliance paperwork (it's engineering work; do it well or the paperwork doesn't matter).
- LLM features deployed without applying the same discipline (Chunk B covers LLM-specific; the discipline is universal).
