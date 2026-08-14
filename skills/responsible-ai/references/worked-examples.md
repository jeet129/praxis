# Worked examples

Worked artifacts supporting `responsible-ai`. Load this file when you need the full example behind a SKILL.md pointer.

## Fairness audit — worked example

```markdown
# Fairness Audit — Hiring Resume Screening Model v2.1

## Protected attributes (per legal review)
- Gender (inferred from name + signals; itself problematic)
- Race (inferred from school + location; itself problematic)
- Age (from graduation year)

## Metric: equal opportunity (since we care about not missing qualified candidates)

| Group | TPR (recall) | Volume | Threshold (0.7 ± 5%) |
|---|---|---|---|
| Gender: Male | 0.73 | 50,000 | within |
| Gender: Female | 0.71 | 35,000 | within |
| Race: White | 0.74 | 60,000 | within |
| Race: Black | 0.62 | 8,000 | **OUT (4.5% below floor)** |
| Race: Hispanic | 0.69 | 12,000 | within |
| Race: Asian | 0.75 | 10,000 | within |
| Age: 22-30 | 0.75 | 40,000 | within |
| Age: 31-45 | 0.72 | 30,000 | within |
| Age: 46+ | 0.65 | 10,000 | **OUT (5% below floor)** |

## Findings
- Recall significantly lower for Black candidates and 46+ candidates.
- Root cause investigation: training data underrepresents both groups in successful-hire labels (selection bias — past hiring practices).

## Mitigations applied
- Threshold tuning per group to equalize recall (controversial; documented).
- Additional training data sourcing from non-traditional channels.
- Human review mandatory for borderline cases in underrepresented groups.

## Residual risk
- Threshold tuning may itself be problematic per emerging regulation.
- Continuous monitoring required.
- Annual third-party fairness audit.
```

## Human-in-the-loop policy — worked example

```markdown
# Human-in-the-Loop Policy — Loan Approval Model v3.0

## Mandatory review (model decision → human approves before action)
- All denials.
- All approvals above $50K loan amount.
- All applications flagged by adversarial-input detector.
- Random 1% sample (audit + monitoring purposes).

## Optional review (model decision auto-applied; human reviews later)
- All approvals below $50K.
- Discretionary: random 5% sample for ongoing quality assurance.

## Audit
- All model decisions logged with version + input + prediction + threshold.
- Monthly review of model decisions on protected-class boundary cases.

## Override
- Loan officers can override approvals (require documented reason).
- Underwriting can override denials (require documented reason).
- Override patterns monitored for systematic disagreement (signal of model drift or fairness issue).
```

## Datasheet for training data — worked example

Per Gebru et al.'s *Datasheets for Datasets*:

```markdown
# Datasheet — Resume Screening Training Data v3.2

## Motivation
- Built to train the resume screening model.
- Created by: Hiring data team.
- Funding: Internal product budget.

## Composition
- 100K resumes from past 3 years of hiring.
- Labels: hired (positive) vs not hired (negative).
- Selection: all applicants to engineering roles.

## Collection process
- Sourced from ATS system.
- No explicit consent for ML use (raised as compliance issue; deferred to legal).

## Preprocessing / cleaning
- PII removed (names, contact info, addresses).
- Demographics inferred for fairness audit; not used as model input.

## Uses
- Resume screening model training.
- NOT intended for: candidate ranking, hiring quotas, downstream HR decisions.

## Distribution
- Internal only.
- Not shared externally.

## Known biases
- Reflects past hiring practices; if past hiring was biased, training data is biased.
- Under-represents successful candidates from non-traditional backgrounds.
- Geographic bias toward our existing office locations.

## Maintenance
- Refresh quarterly with new hires.
- Bias audit annually.
- Sunset criteria: regulatory change OR major business pivot.
```
