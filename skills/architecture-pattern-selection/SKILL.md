---
name: architecture-pattern-selection
description: Choose the macro-architecture for a project from the requirements + NFR register + team composition + scale targets. Modular monolith, microservices, event-driven, serverless, layered/hexagonal — each has trade-offs and a sweet spot. Defaults to the **simplest pattern that meets the NFRs** — KISS/YAGNI applied to architecture.
---

# Architecture Pattern Selection


<!-- praxis:description:full -->
## Full description

Choose the macro-architecture for a project from the requirements + NFR register + team composition + scale targets. Modular monolith, microservices, event-driven, serverless, layered/hexagonal — each has trade-offs and a sweet spot. Defaults to the **simplest pattern that meets the NFRs** — KISS/YAGNI applied to architecture. Produces an architecture decision with explicit alternatives rejected, a C4 component diagram, and the ADR that locks the choice. Use whenever a project enters the design phase, or a slice introduces architectural divergence from the existing pattern. Architecture Challenger fires against this skill's output.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: active
dependencies:
 - requirements-elicitation
 - nfr-definition
 - product-discovery
triggers:
 - "entering architecture phase"
 - "selecting macro-architecture pattern"
 - "a slice requires architectural extension or change"
 - "evaluating whether to extract a microservice"
 - "deciding between monolith vs distributed"
outputs:
 - architecture decision (chosen pattern + rationale)
 - C4 component diagram (context + container + component views)
 - rejected alternatives with rationale
 - ADR
 - input to Architecture Challenger (which runs sub-personas against this)
consumers:
 - solution-architect (primary author)
 - architecture-challenger (consumes for adversarial review)
 - delivery-planner (uses chosen pattern to calibrate workflow)
 - all developers (consume the architecture as design context)
 - architecture-documentation (keeps living docs)
references: []
```
<!-- praxis:metadata:end -->

The single most consequential decision in a project. Get the macro-architecture right and the rest of the design is constrained productively; get it wrong and you spend the project fighting the architecture.

This skill's default bias is **simplicity**. The right architecture is the simplest one that meets the NFRs. A modular monolith almost always beats microservices for projects under ~10 engineers; serverless beats containers for spiky workloads with no warm-state needs; event-driven beats request/response when temporal decoupling is the actual requirement.

## When this skill fires

- A new project transitions from requirements to design. SA runs this skill.
- A slice within an existing project introduces a workload the existing architecture can't handle gracefully (e.g., adding a real-time matching engine to a request/response service). The skill is run scoped to that workload's architectural needs.
- An architecture review (Steward + Curator) revisits the choice based on factory-evaluation signals.

## The selection procedure

### 1. Read the inputs

- `.project/working/requirements-brief.md` — what the system does.
- `.project/semantic/nfr-register.md` — quality targets.
- `.project/semantic/opportunity.md` — JTBD + sizing.
- `team-composition` (from project metadata) — how many people, what skills.
- Mode flag — greenfield vs. brownfield.

For brownfield, also: `.repo-intel/` from `codebase-comprehension` — the existing architecture is a strong default.

### 2. Eliminate patterns that can't meet the NFRs

Run the candidate patterns against the NFR register. Eliminate those that structurally cannot meet the targets:

- **Pure monolith** (deployable unit = entire system, single DB): eliminate if scale targets > a few thousand QPS or if independent deployment of subsystems is a real need.
- **Modular monolith** (single deployable, internal module boundaries, possibly DB-per-module): viable up to surprisingly large scale; team < ~10–15; latency-sensitive intra-module calls are free.
- **Microservices**: each service deploys independently; team-per-service alignment ideal. Eliminate when team is < 5 (overhead dominates), or when transactional consistency across services is a hard requirement (sagas / 2PC add complexity).
- **Event-driven**: temporal decoupling is the requirement; eventual consistency is acceptable. Eliminate when strict consistency is required or when debugging async flows is unaffordable.
- **Serverless (FaaS)**: spiky workloads, no warm state, fast cold-start is acceptable or warm pools justify the cost. Eliminate for high-throughput steady-state workloads (FaaS economics break down) or low-latency-with-cold-start sensitivity.
- **Layered (n-tier)**: stable, comfortable, often *the* default — but mostly an implementation pattern that lives *inside* one of the macro patterns, not a competitor to them.
- **Hexagonal / ports-and-adapters**: implementation pattern, not macro architecture; combines with any of the above.

### 3. Score the survivors against KISS/YAGNI

For each surviving candidate:

- **Operational cost** — how much ops work does this pattern impose? Microservices imply service mesh, distributed tracing, per-service deploys. Monolith implies less.
- **Team fit** — does the team have the skills to operate this pattern? A 3-person team running 12 microservices is a disaster waiting to happen.
- **Future-flexibility cost** — how locked in is the team to this choice? Modular monolith → microservices is a well-trodden migration; microservices → modular monolith is harder.
- **Time to first slice** — how fast can the walking skeleton ship in this pattern? Faster is better; KISS rewards velocity.

The winner is typically the simplest pattern in the surviving set — unless an NFR specifically demands the more complex one.

### 4. Locate the components

For the chosen pattern, sketch the components:

- **Bounded contexts** from `domain-discovery` become components (in a microservices model) or modules (in a modular monolith). Read `.project/semantic/bounded-contexts.md` if it exists.
- **External integrations** are explicit components — third-party APIs, payment gateways, identity providers.
- **Data stores** are components — one per bounded context typically, polyglot persistence if NFRs justify it.
- **Messaging / event backbone** is a component if the pattern is event-driven.
- **Caches and queues** are components if NFRs require them.

Produce **C4 diagrams**:

- **Context** — the system + its users + external systems.
- **Container** — major deployable units (services, databases, queues, etc.).
- **Component** — within each container, the major internal pieces.
- **Code level (optional)** — only for components with non-obvious internal structure.

### 5. Identify the failure-mode design

For each component, the SA pre-answers (handed to Challenger to attack):

- What's the failure mode? (Component down, slow, returning bad data, partial outage.)
- What does the system do when it fails? (Fallback, circuit-break, queue, fail-fast, retry.)
- Which `resilience-patterns` apply? (Circuit breaker, bulkhead, retry-with-jitter, idempotency, saga.)

This is where `distributed-systems-patterns` becomes a key reference for any pattern with multiple components.

### 6. Write the ADR

The architecture decision goes into an ADR (via `adr-decision-records`). Mandatory sections:

- **Decision** — the chosen pattern, named.
- **Context** — the NFRs and constraints that drove the choice.
- **Options considered** — at least three; the surviving candidates from step 2.
- **Why we rejected each alternative** — concrete, NFR-tied.
- **Consequences** — positives, negatives, debts taken on.
- **Failure modes** — the design's known weak points.

### 7. Hand to Architecture Challenger

The chosen architecture is the input to `architecture-challenger`'s five sub-personas (`scale`, `security`, `cost`, `operations`, `reliability`). The planner selects the relevant subset based on the NFR register and project characteristics. The Challenger produces a severity-tagged challenge report; the SA either incorporates findings or documents the override (override = new ADR).

## Default biases

When the inputs are ambiguous and no NFR forces a hand:

- **Modular monolith** for teams under 10.
- **One database**, internally partitioned by bounded context, until an NFR forces split.
- **Synchronous request/response** until temporal decoupling is the actual requirement.
- **Containers on K8s** (per the cloud decision) over FaaS for steady-state workloads.
- **Polyglot only when NFRs demand it** (don't run Redis + Postgres + MongoDB + ElasticSearch on day one).

These biases are KISS/YAGNI made concrete. A project that picks all the *complex* options on day one is almost always over-engineering against assumed-future-state. Future state earns its complexity later via explicit ADRs.

## Patterns the chosen architecture composes with

Macro architecture sets the *shape*; patterns from `patterns/` fill in the *moves* within that shape:

- Modular monolith composes naturally with hexagonal, repository, CQRS-light.
- Microservices compose with API Gateway, Saga, Outbox, Event Sourcing (selectively), Circuit Breaker.
- Event-driven composes with Outbox, Saga, Event Sourcing, CQRS.
- Serverless composes with event-driven and with managed-service-heavy data designs.

The SA references `patterns/` for the specific patterns being applied; this skill doesn't reproduce them.

## Mode handling (G/B)

**Greenfield.** Full procedure as above.

**Brownfield.** The existing architecture is the strong default. Reframe the question as: "Does this slice fit the existing pattern, or does it warrant divergence?" Divergence is the exception and requires an explicit ADR. Strangler-fig migrations *are* divergence done deliberately — and they get their own pattern from `patterns/strangler-fig.md`.

## What this skill does not do

- Functional design — that's done within the chosen pattern by the SA and developers.
- API design — separate skill (`api-design`, not but on the roadmap).
- Data modeling — separate skill (`data-modeling`).
- Implementation — developers handle that with the chosen pattern as context.

## Verification

You are done when:

- [ ] At least 2 architecture patterns were considered (e.g., monolith vs services; sync vs event-driven; SQL vs NoSQL).
- [ ] Selection rationale ties to NFRs from `nfr-definition` register, not "best practice."
- [ ] Trade-offs documented per axis (scale, security, cost, operations, reliability).
- [ ] ADR exists at `.project/decision/` with: context, options, decision, consequences, status.
- [ ] Architecture Challenger has run all 5 sub-personas against the selection.
- [ ] At least one "what would change our mind" condition documented (when to revisit).
- [ ] Per-store data-consistency model decided (per `distributed-systems-patterns` if applicable).

Evidence to check:
- A new joiner can read the ADR and answer "why this pattern, not another?"
- The pattern's known weaknesses are matched against mitigations.
- Future change cost is acknowledged ("if we outgrow X, the migration looks like Y").

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Microservices because it's modern." | Microservices solve a specific problem (independent deployment for independent teams). Without that problem, you're paying cost without benefit. |
| "Event-driven because it scales." | Sync also scales when bottlenecks aren't the request path. Event-driven adds ordering / idempotency / observability complexity. Choose for the right reason. |
| "We picked Kafka because we'll need it." | YAGNI applies to architecture too. Pick the simplest pattern that meets known NFRs; revisit when NFRs change. |
| "The pattern is obvious from the requirements." | The pattern is a trade-off. "Obvious" usually means "I haven't considered alternatives." Document at least 2. |
| "We'll refactor the pattern later if needed." | Pattern changes are 100x more expensive than data-model changes. Pick deliberately. |
| "The team knows X; we'll use X." | Familiarity is a real input, but not the only one. If X mis-fits the problem, the team's familiarity is wasted on incidents. |
| "Polyglot persistence — use the right tool for each subsystem." | Each new data store is operational overhead, monitoring overhead, expertise overhead. Default to one until the cost of bending it exceeds the cost of a second. |

## Anti-patterns

- "Microservices because it's modern." Microservices solve a specific problem (independent deployment for independent teams); using them without that problem is taking on cost without benefit.
- Choosing the architecture before reading the NFRs. The NFRs are the deciders; everything else is preference.
- Architecture that "scales to a billion users" for a product with 100 expected users. YAGNI is a virtue.

## Sign-off

Architecture decision + ADR + Challenger report together gate the **architecture_sign_off** approval per the governance matrix.
