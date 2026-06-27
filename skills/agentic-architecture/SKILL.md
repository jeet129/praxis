---
name: agentic-architecture
description: Macro-design for LLM-powered features and agent systems. Choose between single-agent / multi-agent / planner-executor / supervisor topologies; design tool-use surfaces and tool schemas; choose memory systems (short-term / episodic / semantic / shared); place LLM calls relative to deterministic logic; decide when to use streaming / function calling / structured outputs. The FE of agentic AI architecture — what RAG (`rag-design`), evaluation (`evaluation-engineering`), safety (`llm-safety`), and cost (`llm-cost-optimization`) hang off of. ML/AI Engineer + SA co-design. Use whenever an LLM / agent feature is being designed, when choosing agent topology, when designing tool-use, or when deciding where deterministic logic vs LLM calls belong.
---

# Agentic Architecture


<!-- praxis:metadata:begin -->
```yaml
capability: agentic-ai
domain: ml
state: active
dependencies:
  - architecture-pattern-selection
  - resilience-patterns
  - distributed-systems-patterns
  - nfr-definition
  - ml-problem-framing
triggers:
  - "designing a new LLM-powered feature"
  - "choosing agent topology (single / multi / planner-executor / supervisor)"
  - "designing tool-use surfaces and tool schemas"
  - "deciding memory architecture (short-term / episodic / semantic)"
  - "placing LLM calls relative to deterministic logic"
  - "choosing structured-output / function-calling / streaming patterns"
outputs:
  - agent topology decision + ADR
  - tool catalog (per tool: schema, side effects, idempotency, authn/authz)
  - memory architecture (which memory types; storage; retrieval)
  - LLM-vs-deterministic boundary diagram (call graph)
  - structured-output / function-calling design
  - failure-mode catalog (what does the system do when the LLM is wrong / slow / unavailable)
consumers:
  - ml-ai-engineer (primary author)
  - solution-architect (co-designs system architecture)
  - rag-design (consumes when retrieval-augmented)
  - llm-safety (consumes for guardrail placement)
  - llm-cost-optimization (consumes for cost-routing decisions)
  - evaluation-engineering (consumes for what to evaluate)
references: []
```
<!-- praxis:metadata:end -->

The macro-design layer for LLM-powered features. Done right, it sets up `rag-design`, `evaluation-engineering`, `llm-safety`, and `llm-cost-optimization` to do their jobs. Done poorly, the system is a chatbot wrapped around a single API call with no story for failure, no story for evaluation, and no story for cost.

The principle: **LLMs are non-deterministic components within a deterministic system. Architect the system; the LLM is one (important) part.**

## When this skill fires

- A new LLM-powered feature is being designed.
- Agent topology is being chosen (single-agent, multi-agent, planner-executor, supervisor).
- Tool-use surfaces are being designed (what the agent can call).
- Memory architecture is being chosen.
- The boundary between LLM calls and deterministic logic is being placed.
- Structured-output / function-calling patterns are being decided.

## Topology choice

The single most consequential decision.

| Topology | When |
|---|---|
| **Single agent** | One LLM call (or a short bounded loop) handles the request. Default for most features. Cheapest, simplest, easiest to evaluate. |
| **Planner-executor** | LLM plans steps; deterministic code executes each step. Plan once; execute reliably. Good for predictable task structure with variable inputs. |
| **Supervisor / orchestrator** | One LLM coordinates multiple sub-agents (often specialized). Strong when sub-tasks are heterogeneous (research + write + critique). |
| **Multi-agent (peer)** | Multiple agents work in parallel or in dialogue. Used for debate, ensemble, role-play. Often *too complex* for production value. |
| **Tool-using single agent** | Single agent with rich tool access; can call out to many APIs / functions. Most common production pattern in 2026. |

**Default for production features: tool-using single agent OR planner-executor.** Multi-agent dialogue is researchy; reach for it only when the problem genuinely demands it.

Topology decision goes in an ADR:

```markdown
## Decision
Use a tool-using single agent with a bounded loop (max 8 tool calls).

## Why not multi-agent?
- The task decomposition is consistent across requests.
- Multi-agent adds latency + cost + harder evaluation.
- Tool-using single agent handles the variation via tool selection.

## Why not planner-executor?
- The plan is typically 1-3 steps; planner overhead exceeds the benefit.
- A bounded-loop single agent achieves the same outcome with less complexity.

## Loop bound
- 8 tool calls max per request.
- If unresolved after 8: graceful escalation to human / fallback response.
```

## Tool design

Tools are how the agent affects the world. Each tool's design is critical.

### Tool schema

```yaml
name: search_orders
description: Search for orders by customer email, date range, or order ID. Returns up to 50 results.
inputs:
  customer_email: { type: string, format: email, optional: true }
  date_from: { type: string, format: date, optional: true }
  date_to: { type: string, format: date, optional: true }
  order_id: { type: string, optional: true }
outputs:
  orders: { type: array, items: { ... } }
  truncated: { type: boolean, description: "True if more than 50 results existed" }
side_effects: none      # read-only
idempotent: true
auth_scope: customer-service-rep
cost_class: low         # <100ms; cheap DB query
```

Tool design principles:

- **Narrow, composable tools** > broad multi-purpose tools. The LLM picks better with focused tools.
- **Side effects explicit** — tools that modify state are flagged; the agent's loop logic and the audit log treat them differently.
- **Idempotency where possible** — retries should not double-create orders.
- **Output schema strict** — structured returns the LLM can reason about.
- **Errors as data** — tools return errors as part of their output schema, not as exceptions; the LLM can decide how to handle.

### Tool catalog discipline

The set of tools an agent has access to defines its capability and its risk. Treat the catalog as a *permission boundary*:

- **Least privilege** — give the agent only the tools it needs for the slice's use case.
- **Per-user authorization** — tool calls respect the user's permissions (the agent operates with the user's authority, not the system's).
- **Audit trail** — every tool call logged with: which agent, which tool, what inputs, what output, on whose behalf, in what session.

A tool that can spend money, send messages externally, or modify customer data has a different risk class than a read-only lookup tool.

## Memory architecture

Per the round-2 R2.2 taxonomy applied to agents — agents need multiple memory types:

| Memory type | What it stores | Lifetime |
|---|---|---|
| **Working** | Current conversation / current task state | One session |
| **Short-term** | Recent context within a longer interaction | Hours to days |
| **Episodic** | What this user has previously asked / done | Months to years |
| **Semantic** | World knowledge / domain knowledge (often via RAG) | Stable; updated as docs update |
| **Procedural** | How-to knowledge (often baked into prompts) | Stable; version-controlled |
| **Shared (between agents)** | When multi-agent: what other agents have learned this session | One workflow |

Storage:
- **Working / short-term** — in the request context (chat history).
- **Episodic** — vector store + structured DB.
- **Semantic** — vector store (per `rag-design`).
- **Procedural** — system prompt + tool descriptions.
- **Shared** — orchestrator-managed state (workflow run-state per `using-praxis`).

Memory design includes **forgetting**:
- Working memory cleared per session.
- Episodic memory subject to retention per `compliance-privacy`.
- Right-to-erasure compliance (per `data-governance`'s DSR runbook).

## LLM-vs-deterministic boundary

Decide *what is the LLM responsible for*. Common boundary patterns:

| Pattern | LLM's role |
|---|---|
| **LLM as router** | LLM picks one of N deterministic handlers. Cheap; reliable; LLM does the easy part. |
| **LLM as extractor** | LLM extracts structured data from unstructured input; deterministic logic acts on the structured data. |
| **LLM as planner** | LLM decides the steps; deterministic code executes. |
| **LLM as composer** | LLM combines deterministic-system outputs into a response (e.g., RAG + tool results → user-facing answer). |
| **LLM as endpoint** | LLM generates the entire response. Risky for production; reserved for low-stakes / human-reviewed surface. |

**Push deterministic logic out of the LLM whenever possible.** LLMs are expensive, slow, non-deterministic; deterministic code is cheap, fast, reliable. The LLM does what only it can do.

## Structured output + function calling

For production reliability:

- **Structured output** — constrain LLM output to a schema (JSON Schema, Pydantic model, etc.). Modern APIs (OpenAI, Anthropic, etc.) support guaranteed-conforming structured outputs. Use them.
- **Function calling** — the agent's tool calls are structured outputs of "what function to call with what arguments." Don't hand-roll text parsing for tool selection.
- **Streaming** — useful for chat UX; complicates parsing of structured outputs. Use for long natural-language responses; not for tool-call decisions.

The hand-rolled "ask the LLM to output JSON and hope" pattern is obsolete in 2026. Use structured output APIs.

## Failure-mode catalog

What does the system do when:

| Failure | Response |
|---|---|
| LLM is slow (> NFR latency) | Timeout per `resilience-patterns`; degrade to non-LLM path or "thinking..." response. |
| LLM is wrong (hallucinates, refuses) | Detected via `evaluation-engineering` guards (groundedness check, refusal detector). Fallback to default / human. |
| Tool call fails | Standard `resilience-patterns` — retry, circuit-break, fallback. Tool failures should not crash the agent. |
| Agent loop runs too long | Bounded by max iterations; exceeding bound = graceful escalation. |
| Prompt injection detected | Per `llm-safety` — block, log, alert. Agent does not act on injected instructions. |
| Cost spike (token usage out of budget) | Per `llm-cost-optimization` — circuit-break, fallback to cheaper model or degraded service. |
| LLM API outage | Multi-provider fallback (per `resilience-patterns` applied to LLM providers). |

Each failure mode has a documented response; no silent failures.

## NFR considerations

Per `nfr-definition`'s framework applied to agents:

- **Latency**: agentic systems are often slow. Document expected p50, p95, p99 per use case.
- **Cost per request**: a meaningful NFR for LLM features. Budget per request × volume = monthly cost.
- **Accuracy / groundedness**: measured by `evaluation-engineering`.
- **Safety**: refusal rate on harmful inputs; jailbreak resilience score.
- **Availability**: includes upstream LLM provider availability.

Most agentic NFRs are surprising the first time the team measures them. Set realistic baselines after measurement.

## Outputs

| Output | Location |
|---|---|
| Agent topology decision + ADR | `.project/decision/adr-NNN-agent-topology.md` |
| Tool catalog | `.project/semantic/tool-catalog.md` + tool specs in repo |
| Memory architecture | `.project/operational/agent-memory.md` |
| LLM-vs-deterministic call graph | `.project/operational/agent-call-graph.md` |
| Structured-output / function-calling design | inline in agent code; documented in repo |
| Failure-mode catalog | `.project/operational/agent-failure-modes.md` |

## Mode handling (G/B)

**Greenfield.** Architect from scratch using the topology + tool + memory + boundary discipline.

**Brownfield.** Audit existing LLM features. Common findings: single big prompt with everything in it; no structured output (text parsing in code); no tool catalog (everything inline); no failure modes documented. Refactor toward the discipline incrementally.

## What this skill does not do

- Implement the agent — that's done in code (per the active stack pack).
- Build the RAG retrieval — that's `rag-design`.
- Evaluate the agent — that's `evaluation-engineering`.
- Safety guardrails — that's `llm-safety`.
- Cost optimization — that's `llm-cost-optimization`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Multi-agent because it's the modern pattern." | Multi-agent adds latency, cost, harder eval. Tool-using single agent is the production default. |
| "We don't need a tool catalog." | Without one, tools accumulate ad-hoc; the agent picks badly; security boundaries blur. |
| "Memory is just chat history." | Six memory types exist (working/short-term/episodic/semantic/procedural/shared). Each has its own lifetime + storage. |
| "LLM does everything; deterministic code is legacy." | Deterministic code is faster, cheaper, more reliable. Push out anything the LLM doesn't need to do. |
| "Function calling is optional." | Hand-rolled JSON parsing for tool selection is obsolete. Use structured-output / function-calling APIs. |
| "Unbounded agent loops are fine if the agent stops eventually." | They balloon cost + latency. Bound the loop; degrade gracefully on bound hit. |
| "Failure modes don't need explicit handling." | LLMs fail silently (hallucinate, refuse, time out). Each failure has a documented response or it's a production incident. |

## Verification

You are done when:

- [ ] Agent topology chosen (single / planner-executor / supervisor / multi-agent / tool-using-single) with rationale.
- [ ] Tool catalog: each tool has schema + side-effects + idempotency + auth scope + cost class.
- [ ] Memory architecture documented (per type: storage, lifetime, retrieval).
- [ ] LLM-vs-deterministic call graph documented.
- [ ] Structured-output / function-calling configured.
- [ ] Failure-mode catalog: per failure class, a documented response.
- [ ] Bounded loop with max iterations + graceful escalation on exceed.
- [ ] NFRs: latency, cost-per-request, safety, availability targets explicit (per `nfr-definition`).

Evidence to check:
- A new joiner can read the architecture and answer "what happens when the LLM is wrong / slow / unavailable?"

## Anti-patterns

- "Just throw it all in one prompt" (no architecture).
- Multi-agent without justified value (research-y; rarely production-warranted).
- Tool that does five different things (LLM picks badly; harder to evaluate).
- No tool-call audit trail (compliance + debugging fail).
- LLM as endpoint for high-stakes decisions without human review.
- No failure-mode catalog ("hopefully it works").
- Memory architecture undefined (system forgets things it should remember; remembers things it shouldn't).
- Hand-rolled JSON parsing instead of structured-output APIs.
- Unbounded agent loops (agent reasoning itself in circles; cost balloons).
- LLM doing what deterministic code could do better (slower, more expensive, less reliable).
