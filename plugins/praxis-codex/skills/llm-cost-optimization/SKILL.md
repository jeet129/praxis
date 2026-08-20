---
name: llm-cost-optimization
description: "Production economics for LLM features. Model selection per task (capability-vs-cost tiering), prompt-cache + KV-cache utilization, semantic caching, batching, smaller-model routing for the common case, token budgets per request, observability of cost as a first-class signal. LLM cost is the silent project killer — features that work in development can be unaffordable at scale. ML/AI Engineer owns the design; Platform/SRE wires the cost monitoring; `cost-finops` treats LLM cost as a category. Use whenever a new LLM feature is being designed, when investigating cost growth, when setting token budgets, or when designing model-routing policy."
---

# LLM Cost Optimization

<!-- praxis:metadata:begin -->
```yaml
capability: agentic-ai
domain: ml
state: active
dependencies:
  - agentic-architecture
  - cost-finops
  - nfr-definition
  - observability
triggers:
  - "designing cost model for a new LLM feature"
  - "investigating LLM cost growth"
  - "setting token budgets per request / per use case"
  - "designing model-routing (cheap → expensive escalation)"
  - "wiring prompt cache or semantic cache"
  - "evaluating self-hosted vs managed LLM options"
outputs:
  - cost model per feature (per request × volume)
  - routing policy (model tier selection per request type)
  - caching strategy (prompt cache + semantic cache + KV cache hits)
  - token-budget defaults per use case
  - cost dashboard (per feature, per tenant, per model)
  - cost-vs-quality trade-off documentation
consumers:
  - ml-ai-engineer (primary author)
  - cost-finops (consumes LLM cost as a category)
  - platform-sre (wires monitoring + budget alerts)
  - product-manager (cost-vs-quality trade-off decisions)
  - agentic-architecture (consumes routing decisions for call graph)
references:
  - litellm.md
  - portkey.md
  - helicone.md
  - cost-playbooks.md
```
<!-- praxis:metadata:end -->

The discipline that keeps LLM features financially viable. LLM API costs scale with usage, often dramatically; a feature that costs cents in dev can cost six figures at scale. Without cost discipline, projects either don't ship to scale (too expensive) or ship and burn cash silently.

The principle: **cost is a first-class NFR for LLM features. Measure per request; budget; optimize continuously.**

## When this skill fires

- A new LLM feature is being designed; cost model needed before commit.
- Cost growth concerns surface (monthly LLM bill exceeds plan).
- Token budget per request / per use case is being set.
- Model-routing policy is being designed (cheap → expensive escalation).
- Prompt cache or semantic cache is being wired.
- Self-hosted vs managed LLM decision.

## The cost categories

Per LLM call:

- **Input tokens × cost per input token** — usually the larger cost (RAG + long context).
- **Output tokens × cost per output token** — typically 3-5x input cost per token.
- **Tool-use overhead** — each tool call may be a separate LLM round-trip.
- **Cache hits / misses** — cached input tokens are much cheaper (or free).

Per request, sum all rounds (agent loop, tool calls, classifier calls). At scale, observability per-request cost is the only way to actually understand the bill.

## Model tiering

Different models have different cost / capability trade-offs:

| Tier | Examples (2026) | Cost | Use for |
|---|---|---|---|
| **Frontier** | Claude Opus 4.6, GPT-4.x successors, Gemini 2.x | Highest | Hard tasks; complex reasoning; final answer. |
| **General** | Claude Sonnet 4.6, GPT-4o-class | Medium | Default for most LLM features. Strong; affordable. |
| **Fast / cheap** | Claude Haiku 4.5, GPT-4o-mini, Gemini Flash | Low | Classification, extraction, simple routing, summarization. |
| **Self-hosted** | Llama 3.x, Mistral, Qwen | Compute-cost only | Predictable load; sensitive data; cost predictability. |

The decision tree:

- Can a smaller model handle this task adequately? Use it.
- Does the task have a clear structure (extraction, classification, routing)? Smaller model.
- Is creativity / complex reasoning needed? Larger model.
- Is the task common but each request cheap? Smaller model + bulk evaluation to confirm quality.

**Default for new features: General-tier model.** Move down to fast/cheap when the task allows; up to frontier when accuracy demands it.

## Routing strategy

For systems handling diverse requests, route per-condition (e.g., classification/extraction → fast/cheap; simple generation → general; complex generation → frontier; failed-eval retries → escalate to frontier). Load `references/cost-playbooks.md` for a worked routing-policy YAML example. Implementations: LiteLLM, Portkey, OpenRouter all provide routing infrastructure.

## Caching

Cache hits dramatically reduce cost.

### Prompt caching (provider-side)

Modern LLM APIs offer prompt caching:

- **Cached input tokens cost ~10% of full price** (provider-dependent).
- **TTL is typically minutes** (e.g., 5 minutes).
- **Cache key includes the prompt prefix**; identical prefixes get hits.

Design implications:

- Put stable content (system prompt, RAG corpus excerpts, examples) first.
- Put variable content (user query) last.
- Structure prompts to maximize prefix reuse across requests.

A well-structured system prompt + few-shot examples + variable user input = 80%+ of input tokens cached after the first hit.

### Semantic caching

Cache full request/response pairs by *semantic similarity* of the query:

- Embed incoming query.
- Search cache for similar prior queries (vector similarity above threshold).
- If hit: return cached response.
- If miss: query LLM; cache the response.

Tools: GPTCache, Helicone, custom (Redis + embeddings).

Semantic caching works when:

- Queries have natural-language variation but semantic equivalence ("What is your refund policy?" vs "How do refunds work?").
- Stale answers are OK for cache TTL.

Doesn't work when:

- Personalized responses required.
- Real-time information needed.
- Even small variation matters.

### KV-cache (inference-side)

For self-hosted models or providers that expose KV-cache reuse:

- Inference engines cache the attention key-value computations for the prompt prefix.
- Subsequent requests with the same prefix skip re-computing.
- Major latency + cost savings.

vLLM, TensorRT-LLM, SGLang all support KV-cache reuse.

### Cache economics vs model routing (the interaction)

Caching and model-tier routing are usually optimized separately — but they interact, and the interaction often flips the naive answer. This is **provider- and harness-agnostic**; only the numbers change. The prompt-cache read discount is large (commonly ~10×; cached input ≈ 0.1× full input), and it is frequently **larger than the price gap between adjacent capability tiers**. When that holds, a **cache-warm higher tier can be cheaper than a cache-cold lower tier on shared context** — routing *down* to save money can cost more once the cached prefix is lost. Always derive the actual per-tier ratios for your harness from `governance/model-routing.yaml` cost weights and compare them against your provider's cache-read multiplier before down-routing.

As one concrete example, current Claude Code tier gaps are ≈1.67× (deep→standard) and ≈5× (deep→light), both under the ~10× cache discount — so a cached deep-tier input (~$0.50/Mtok) undercuts an uncached light-tier input (~$1.00) and an uncached standard-tier input (~$3.00) on the shared prefix. Other harnesses differ in kind, not just degree: on Codex the tiers are often reasoning-effort levels of the *same* base model, so there is no per-token price step to capture by down-routing at all — the cache is almost always worth preserving; Gemini has its own Pro/Flash/Flash-Lite spread. Run the check per harness.

Decompose every delegated sub-task's tokens into three buckets and route each on its own economics:

1. **Shared cacheable prefix** (system prompt, library/skill content, repeated project context) — cheapest on the model that already has it cached; a model switch forfeits the ~10× discount here, so down-routing *loses*.
2. **Task-unique input** — no cache either way; cheapest on the smallest capable model.
3. **Output / thinking tokens** — never cached; cheapest on the smallest capable model.

A model-down route saves the tier ratio on (2)+(3) but forfeits the cache on (1); the crossover is the token mix — big reused context + short output favors keeping the model, small context + large output favors down-routing.

**Corollary: the reasoning-effort lever is cache-preserving; a model-family switch is not.** When a large cached prefix is in play, prefer effort-down on the same model — it captures the output/thinking savings without a cache miss. Reserve model-down moves for output-heavy, low-shared-context, or large-gap tasks. Validate before trusting a model-down policy: correlate `factory-token-report.py`'s cache-hit ratio with `factory-routing-report.py`'s per-tier escalation rate — a high cache-hit ratio plus escalations on a down-routed tier means that route is net-negative.

## Token budgets

Per use case, set explicit budgets (max input tokens, max output tokens, expected cost per request). Load `references/cost-playbooks.md` for a worked token-budgets YAML example across simple-query / RAG-answer / long-conversation use cases.

Budgets enforced:

- **Hard truncation** at max input tokens (truncate context).
- **Output limits** in API call.
- **Per-user / per-session budgets** to prevent runaway costs from one user.

Per `multi-tenancy`, per-tenant budgets prevent one tenant from consuming the LLM bill.

## Cost observability

Per `observability`, treat cost as a first-class signal:

- **Per-request cost** logged with the request.
- **Cost dashboard** per feature, per tenant, per model.
- **Anomaly detection** on cost trends (sudden spike → investigate).
- **Budget alerts** per feature monthly cost.

Load `references/cost-playbooks.md` for a sample cost-dashboard markdown template. Cost regressions are caught quickly with dashboards + alerts.

## Self-hosted vs managed

For predictable load + sensitive data + cost predictability, weigh managed (pay-per-use, effortless scaling, frontier quality, data sent to provider, low fixed/high variable cost) against self-hosted (fixed compute + ops cost, operational scaling, tunable latency, on-prem data control, high fixed/low variable cost). Load `references/cost-playbooks.md` for the full comparison table.

Self-hosting becomes economic above some volume threshold. The threshold depends on the model:

- Frontier-equivalent self-hosting is rarely cheaper at any volume (the gap is wide).
- General-tier self-hosting can break even at meaningful volume.
- Fast/cheap self-hosting (small models) breaks even at modest volume.

Plus operational considerations: self-hosting LLMs is its own infra problem (GPUs, autoscaling, monitoring, model updates).

Default: **managed for new projects**; revisit at meaningful scale.

## Cost-vs-quality trade-offs

Document explicitly: current configuration + cost + quality eval, the alternative considered (cost delta, quality delta, adopt/reject decision with rationale), and future options not yet taken with their break-even conditions. Load `references/cost-playbooks.md` for a worked Cost-vs-Quality writeup. Trade-offs documented per ADR. Reviewed quarterly.

## Tool / library refs

- **LiteLLM** — multi-provider routing + unified API.
- **Portkey** — managed LLM gateway with routing + caching + observability.
- **Helicone** — LLM observability + caching.

## Outputs

| Output | Location |
|---|---|
| Cost model per feature | `.project/operational/llm-cost-model.md` |
| Routing policy | `.project/decision/adr-NNN-llm-routing.md` + implementation |
| Caching strategy | `.project/operational/llm-caching.md` |
| Token budgets | `.project/procedural/llm-token-budgets.md` |
| Cost dashboard | provisioned per `observability` |
| Cost-vs-quality trade-offs | per-feature ADR |

## Mode handling (G/B)

**Greenfield.** Cost model from day one. Routing + budgets configured before first production traffic.

**Brownfield.** Audit existing LLM costs. Common findings: all requests on frontier model; no caching; no routing; per-tenant cost opaque. Quick wins available from routing + caching.

## What this skill does not do

- Build the feature — `agentic-architecture` + application.
- Generic FinOps — `cost-finops` (this skill is LLM-specific).
- Eval — `evaluation-engineering` (used to verify routing doesn't regress quality).
- Safety — `llm-safety`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Use frontier model for everything; simpler." | Paying 5-10x for tasks a general model handles. Route by task class. |
| "Caching is later optimization." | Prompt caching is 10x cost reduction on stable prefixes. Free if structured correctly. |
| "Per-request cost is unknown; we'll see at the bill." | The bill is the lagging indicator. Per-request instrumentation is the leading one. |
| "Token budgets feel arbitrary." | They prevent runaway requests. Set defaults per use case; enforce. |
| "Routing is overkill." | One model for all is overkill the other way — paying premium for simple tasks. |
| "Self-host because it's cheaper." | At small scale, ops cost > savings. Compute break-even before switching. |

## Verification

You are done when:

- [ ] Cost model per feature (per request × volume = monthly).
- [ ] Model tiering applied: frontier / general / fast-cheap / self-hosted per task.
- [ ] Routing policy documented + implemented.
- [ ] Caching strategy: prompt cache + semantic cache + KV cache where applicable.
- [ ] Token budgets defined per use case; enforced.
- [ ] Cost dashboard per feature / tenant / model.
- [ ] Cost regression caught (anomaly detection + budget alerts).
- [ ] Cost-vs-quality trade-offs documented as ADRs.

Evidence to check:
- Per-request cost telemetry surfaces a recent optimization opportunity.
- Cache hit rate meets target.

## Anti-patterns

- One model for all requests (no tiering).
- No caching (cheap wins left on the table).
- Token budgets undefined (runaway requests possible).
- Per-request cost not measured (the bill is the only signal).
- "We'll optimize after launch" (often the bill kills the project before optimization).
- Self-hosting prematurely (ops overhead exceeds savings at small scale).
- Frontier model when general suffices (paying 5-10x for 1-2pt quality).
- No per-tenant cost attribution (can't tell who's expensive).
- Cost dashboards absent ("the bill last month was..." → too late).
- Routing decisions without eval (cheaper model might regress quality on important slices).
