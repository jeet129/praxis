# Cost playbooks

Worked examples and templates supporting `llm-cost-optimization`. Load this file when you need the full artifact behind a SKILL.md pointer.

## Routing policy — worked YAML example

```yaml
routing:
  - condition: "intent == 'classify'"
    model: fast/cheap
    reason: "Classification doesn't need a frontier model."

  - condition: "intent == 'extract' AND input_tokens < 1000"
    model: fast/cheap
    reason: "Extraction is constrained; small model suffices."

  - condition: "intent == 'generate' AND complexity == 'simple'"
    model: general
    reason: "Default for generation."

  - condition: "intent == 'generate' AND complexity == 'complex'"
    model: frontier
    reason: "Hard generation needs frontier."

  - condition: "previous_attempt_failed_eval"
    model: frontier
    escalate_from: general
```

## Token budgets — worked YAML example

```yaml
budgets:
  simple_query:
    max_input_tokens: 2000
    max_output_tokens: 500
    expected_cost: $0.002 per request

  rag_answer:
    max_input_tokens: 10000
    max_output_tokens: 800
    expected_cost: $0.025 per request

  long_conversation:
    max_input_tokens: 30000
    max_output_tokens: 1500
    expected_cost: $0.10 per request
```

## Sample cost dashboard

```markdown
# LLM Cost Dashboard

## This month (so far)
- Total: $32,450 (budget: $50,000) — on track.
- Top feature: Customer Support Chat — $18,200.
- Top tenant: Acme Corp — $4,500.
- Top model: Claude Sonnet 4.6 — $19,800.

## Trends
- Day-over-day cost: +12% (investigate spike on 2026-11-14).
- Cache hit rate: 67% (target: 70%).
- Avg input tokens per request: 4,200 (last week: 3,100 — investigate).
```

## Self-hosted vs managed — full comparison table

For predictable load + sensitive data + cost predictability:

| | Managed (OpenAI, Anthropic, Google) | Self-hosted (vLLM + Llama / Mistral / etc.) |
|---|---|---|
| **Per-token cost** | Pay-per-use; transparent. | Compute + ops cost; fixed. |
| **Scaling** | Effortless. | Operational. |
| **Latency** | Predictable; managed. | Tunable; can be lower. |
| **Quality** | Frontier available. | Open-source models; gap shrinking. |
| **Data control** | Sent to provider (with API terms). | On-prem / VPC. |
| **Break-even** | High variable; low fixed. | High fixed; low variable. |

## Cost-vs-quality trade-off — worked writeup

```markdown
# Cost-vs-Quality — Customer Support Chat

## Current configuration
- Model: Claude Sonnet 4.6 for all requests.
- Cost: $0.025 per request.
- Quality eval: 0.89.

## Alternative considered
- Routing: Haiku for classification + simple queries; Sonnet for complex.
- Estimated cost: $0.012 per request (-52%).
- Quality eval: 0.86 (-3 points).
- Decision: ADOPT. The 3-point quality regression is acceptable per the eval slice analysis (regression is on edge cases; common queries unaffected). Cost savings projected $130K/year.

## Future option (not yet)
- Self-hosted Llama 3.x for high-volume queries.
- Estimated infra: $40K/month + ops.
- Break-even at 200K requests/month (currently 80K).
```
