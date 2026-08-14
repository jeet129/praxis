# Reference — Evaluation Engineering Worked Examples

Loaded by `evaluation-engineering` for the full text of the LLM-judge prompt template, the generic CI regression gate, and the slice-based eval table referenced from the main skill.

## LLM-judge prompt template

```
You are evaluating an AI assistant's response. Score on 4 dimensions:

1. Groundedness (0-5): Are claims supported by the retrieved context?
2. Relevance (0-5): Does the answer address the question?
3. Completeness (0-5): Is the answer complete?
4. Tone (0-5): Is the tone appropriate?

Question: {question}
Retrieved context: {context}
Answer: {answer}

Output: structured JSON with per-dimension scores + brief justification.
```

## Regression eval in CI (generic gate)

Per `cicd-pipeline`'s gate discipline applied to AI:

```yaml
# Eval gate in CI
- name: Run eval on golden dataset
  run: |
    python eval/run_eval.py \
      --golden-dataset eval/golden-v3.jsonl \
      --output eval/results.json

- name: Check regression vs baseline
  run: |
    python eval/check_regression.py \
      --current eval/results.json \
      --baseline eval/baseline.json \
      --threshold -0.02  # allow 2pt regression
```

PRs that regress eval scores by more than threshold fail the build. Threshold is project-specific:
- Tight (-0.5pt) for production-critical use cases.
- Loose (-2pt) for experimental features.

Baselines are updated when intentional changes improve scores. Baseline updates are reviewed PRs.

See `references/promptfoo.md` for a promptfoo-specific version of this same CI gate.

## Slice-based eval table

Per `ml-training-evaluation` discipline applied here. Aggregate eval scores hide per-cohort regression:

```markdown
| Slice | Score | Volume | vs Baseline |
|---|---|---|---|
| Overall | 0.84 | 1000 | +0.02 |
| English | 0.86 | 700 | +0.03 |
| Spanish | 0.81 | 200 | +0.01 |
| Other languages | 0.62 | 100 | **-0.08** |  ← regression
| Easy queries | 0.92 | 600 | +0.02 |
| Hard queries | 0.71 | 400 | **-0.01** |
| With RAG hits | 0.88 | 800 | +0.02 |
| Without RAG hits | 0.65 | 200 | +0.00 |
```

The overall score improved; the team would ship — but a slice regressed silently. Slice-eval catches this.
