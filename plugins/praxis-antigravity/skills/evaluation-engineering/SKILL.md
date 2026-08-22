---
name: evaluation-engineering
description: 'The QA discipline for AI / agent systems. Golden datasets, LLM-judge methodology (with calibration), regression eval in CI, slice-based metrics, hallucination detection, faithfulness / groundedness scoring, human-in-the-loop review process. Without this, agentic systems regress silently — a "small prompt change" or model upgrade can degrade quality dramatically without anyone noticing. Distinct from `testing-strategy` (application code) and `ml-training-evaluation` (traditional ML model eval). ML/AI Engineer owns the eval design; QA Engineer integrates with the broader testing strategy; reviewers consume eval reports.'
---

# Evaluation Engineering

<!-- praxis:metadata:begin -->
```yaml
capability: agentic-ai
domain: ml
state: active
dependencies:
  - agentic-architecture
  - testing-strategy
  - ml-training-evaluation
triggers:
  - "designing evals for a new LLM / agent feature"
  - "investigating quality regression in production"
  - "wiring eval to CI as a release gate"
  - "designing LLM-as-judge methodology"
  - "establishing the human-review queue"
  - "regression test before prompt change or model upgrade"
outputs:
  - golden-dataset registry (per use case)
  - eval suite (offline + CI)
  - LLM-judge prompts + calibration data
  - regression dashboard (per release / per prompt change)
  - human-review queue config
  - per-slice eval metrics
consumers:
  - ml-ai-engineer (primary author)
  - qa-engineer (consumes for AI acceptance testing)
  - agentic-architecture (consumes eval-driven feedback)
  - rag-design (consumes retrieval-eval results)
  - llm-safety (consumes for safety eval; refusal and harm metrics)
  - production-release.yaml (consumes eval pass for evidence)
references:
  - langsmith.md
  - braintrust.md
  - promptfoo.md
  - deepeval.md
  - inspect-ai.md
  - eval-worked-examples.md
```
<!-- praxis:metadata:end -->

The QA discipline for AI systems. Where `testing-strategy` ensures application code is correct, this skill ensures the *AI part* is correct — that the LLM's outputs are accurate, grounded, safe, and stable across changes. Without it, "a small prompt change" silently regresses quality on the long tail; the team finds out from user complaints weeks later.

The principle: **non-determinism is not an excuse for not measuring. Measure with statistical methods; gate on the measurements.**

## When this skill fires

- Designing evals for a new LLM / agent feature.
- Investigating a quality regression in production.
- Wiring eval to CI as a release gate.
- Designing LLM-as-judge methodology (with calibration).
- Establishing the human-review queue.
- Regression-testing before a prompt change or model upgrade.

## The eval pyramid

Mirrors the test pyramid (per `testing-strategy`), adapted to AI systems:

```
                       /\
                      /  \   Human evaluation (rare; expensive; ground truth)
                     /----\
                    /      \  LLM-judge eval (medium; fast; calibrated to human)
                   /--------\
                  /          \ Programmatic eval (most; fast; deterministic checks)
                 /----------- \
                /              \ Unit tests on prompts (smoke; structure)
               /----------------\
```

Most evals are programmatic + LLM-judge. Human eval anchors the calibration.

## Golden datasets

The eval foundation. A golden dataset:

- **Curated examples** — real (or realistic) inputs the feature should handle.
- **Expected outputs or rubrics** — what good looks like for each.
- **Coverage** — happy paths, edge cases, adversarial cases, slice-representative.
- **Versioned** — golden dataset has versions; changes tracked.
- **Owned** — someone is accountable for currency.

Build by:

1. Start with 20-50 hand-curated examples covering the use case.
2. Add examples from real production logs (sanitized).
3. Add adversarial / hard examples from incidents or red-team exercises.
4. Grow steadily — golden datasets that don't grow miss new failure modes.

Per use case (Q&A, summarization, classification, agent task) — a separate golden dataset.

## Programmatic eval

Deterministic checks against outputs:

- **Schema conformance** — for structured outputs, validate against schema.
- **Format checks** — citations present? Length within range? Required sections?
- **Keyword presence / absence** — required terms appear; banned terms don't.
- **Lookup checks** — referenced product IDs exist; cited URLs resolve.
- **Length constraints** — within token budget.

Fast and cheap; ~10ms per check. Run on every eval pass.

## LLM-judge eval

Judging quality with another LLM. See `references/eval-worked-examples.md` for the full judge-prompt template.

LLM-judge is *powerful but biased*. Mitigations:

- **Calibrate against human labels** — sample LLM-judge outputs; have humans agree/disagree; tune judge prompt until human agreement > target (e.g., 80%).
- **Use a stronger judge** than the system under test (or at least different).
- **Multiple judges + majority** — variance reduction.
- **Structured output for the judge** — no free-form prose.
- **Reference-based vs reference-free** — reference-based (judge sees expected output) is easier and more reliable.

LLM-judge cost is meaningful at scale. Run nightly or per-PR; not per-request.

## Regression eval in CI

Per `cicd-pipeline`'s gate discipline applied to AI. PRs that regress eval scores by more than a threshold fail the build; threshold is project-specific (tight for production-critical use cases, loose for experimental features); baselines are updated via reviewed PRs when intentional changes improve scores. See `references/eval-worked-examples.md` for the full CI gate example, and `references/promptfoo.md` for a promptfoo-specific version.

## Slice-based eval

Per `ml-training-evaluation` discipline applied here. Aggregate eval scores hide per-cohort regression — an overall score can improve while a slice regresses silently. See `references/eval-worked-examples.md` for a worked example table.

## Hallucination / groundedness detection

Specific eval class for grounded generation:

- **Answer-vs-source NLI** — natural-language inference: does the answer follow from the source?
- **Citation verification** — claims in the answer match the cited source.
- **Factual checking** — facts in the answer verifiable against the source or ground truth.

Tools: RAGAS (RAG Assessment), TruLens, or hand-rolled with LLM-judge.

Production monitoring: log groundedness scores per request; alert on aggregate degradation.

## Human review queue

Some evaluations require humans:

- **Calibration of LLM-judge** — initial setup + drift recalibration.
- **Edge-case acceptance** — when programmatic + LLM-judge disagree.
- **Sampling** — random 1% of production traffic reviewed by humans.
- **User-reported issues** — every user complaint becomes an eval entry.

Review queue infrastructure:

- **Annotators** — internal team or vendor (Labelbox, Scale AI, etc.).
- **Annotation UI** — display input + output + rubric.
- **Inter-annotator agreement** — multiple reviewers per item; measure agreement.
- **Quality control** — embed known-answer items; check annotator accuracy.

Findings flow back into the golden dataset; rare disagreements drive rubric refinement.

## Eval-driven development

For agentic systems, the discipline shifts:

1. Define the eval first (what does good look like?).
2. Build the smallest thing that might pass.
3. Run eval.
4. Iterate.

Without evals, every iteration is "I think this is better." With evals, "this is better by 3 points on the eval; we shipped."

## Tool choice

| Tool | Strength |
|---|---|
| **LangSmith** | Tight LangChain integration; rich tracing + eval; managed. |
| **Braintrust** | General-purpose eval; great UX; managed. |
| **Promptfoo** | Open-source; CI-friendly; YAML configs. |
| **DeepEval** | Open-source; pytest-style; good for unit-test-style evals. |
| **Inspect AI** | UK AISI's framework; rigorous; research-quality. |
| **Custom + LLM-judge** | Many teams build their own; LangSmith/Braintrust accelerate. |

Default for new projects: **Braintrust** (managed) or **Promptfoo** (open-source); **LangSmith** if already on LangChain.

## Outputs

| Output | Location |
|---|---|
| Golden dataset (per use case) | `eval/golden-{use-case}.jsonl` versioned in repo |
| Eval suite | `eval/` directory |
| LLM-judge prompts + calibration | inline in eval/ + `.project/operational/eval-judge-calibration.md` |
| Regression dashboard | external (managed tool) or `.project/operational/eval-results/` |
| Human-review queue config | external (Labelbox / Scale / internal tool) |
| Per-slice eval metrics | published with each eval run |

## Mode handling (G/B)

**Greenfield.** Eval from day one. First commit includes a golden dataset (even if 10 examples).

**Brownfield.** Audit existing AI features. Common findings: zero eval; "vibe testing"; quality regressions discovered from user complaints. First eval is often eye-opening — production quality is worse than the team thought.

## Verification

You are done when:

- [ ] Golden dataset versioned in repo; ≥ 20 examples covering happy + edge + adversarial cases.
- [ ] Eval suite: programmatic checks (schema / format / lookup) + LLM-judge (calibrated) + human (sampled).
- [ ] LLM-judge prompt calibrated to ≥ 80% human-agreement target on a sample.
- [ ] Slice metrics computed (per-language / per-cohort / per-difficulty) — not just aggregate.
- [ ] Regression eval wired in CI; threshold blocks merge.
- [ ] Baseline committed; updates to baseline reviewed PRs.
- [ ] Hallucination / groundedness check for grounded generation.
- [ ] Human-review queue infrastructure documented; cadence scheduled.

Evidence to check:
- A PR that intentionally regresses quality fails the eval gate.
- Sample human-review entries show inter-annotator agreement signal.
- Slice-breakdown surfaces at least one cohort the aggregate hid.

## What this skill does not do

- Run the LLM / agent — that's `agentic-architecture` + `rag-design` + the application.
- Application code testing — that's `testing-strategy`.
- Model training eval — that's `ml-training-evaluation`.
- Safety / harm specific eval — handled by `llm-safety` (consumes eval infrastructure from here).

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Vibe testing is fine for now." | Vibe testing scales like manual QA in 1995. Pre-PMF it's tolerable; post-launch it's malpractice. |
| "Golden dataset of 5 examples is enough." | Statistical signal needs sample size. 5 examples can't distinguish improvement from noise. Start at 20-50. |
| "Aggregate score went up; we shipped." | Aggregate can rise while a slice silently regresses. Per-slice always. |
| "LLM-as-judge is good enough; no human calibration needed." | The judge's biases compound silently. Sample + human-label periodically; otherwise drift is invisible. |
| "We'll add eval after launch." | After launch you're flying blind. Eval is the navigation, not the post-mortem. |
| "Hallucinations are unavoidable; can't really measure them." | They're measurable. Groundedness via NLI, citation verification, fact-check against source. Measure them. |
| "Eval gates slow CI." | Then run nightly on the golden set + per-PR for the smallest representative slice. Don't skip; right-size. |

## Anti-patterns

- "Vibe testing" — looks good, ship it.
- Eval dataset of 5 examples (no statistical signal).
- Aggregate scores only (no slices).
- LLM-judge uncalibrated to humans.
- Eval ran once at design; never again.
- Eval not gated in CI (regressions ship).
- No baseline (can't measure improvement).
- Golden dataset never grows (misses new failure modes).
- Hallucination detection skipped ("the LLM said it confidently").
- Eval gated only at release; no per-PR signal (regressions accumulate).
- Human review never done (LLM-judge drift undetected).
