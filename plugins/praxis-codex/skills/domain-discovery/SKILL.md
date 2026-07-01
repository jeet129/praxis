---
name: domain-discovery
description: "Lightweight domain modeling using event-storming-style techniques to find bounded contexts, the ubiquitous language, and the candidate aggregates BEFORE choosing an architecture or designing data. Establishes the shared semantic foundation that every downstream skill consumes. The Solution Architect runs this once for a new product and lightly per slice that introduces new domain concepts. Output lives in `.project/semantic/` and becomes the project's persistent semantic memory."
---

# Domain Discovery

<!-- praxis:metadata:begin -->
```yaml
capability: architecture
domain: cross-cutting
state: active
dependencies:
  - product-discovery
  - requirements-elicitation
triggers:
  - "modeling a new domain for the first time"
  - "a slice introduces new domain concepts not in the existing model"
  - "bounded-context boundaries are unclear"
  - "the team is using inconsistent terminology"
  - "defining the ubiquitous language for a project"
outputs:
  - bounded-context map (`.project/semantic/bounded-contexts.md`)
  - ubiquitous-language glossary (`.project/semantic/glossary.md`)
  - candidate aggregates per context (`.project/semantic/aggregates-{context}.md`)
  - context-relationship map (which contexts integrate, how)
consumers:
  - solution-architect (uses contexts as the architecture's organizing primitive)
  - data-modeling (uses aggregates to define schema boundaries)
  - api-design (uses contexts to define service boundaries)
  - all developer agents (use the glossary for naming)
references: []
```
<!-- praxis:metadata:end -->

The semantic foundation. Every subsequent design decision — architecture, data model, API, naming — refers back to the bounded contexts and the ubiquitous language this skill produces. Done right, downstream conflicts evaporate; done sloppily, the team argues about names and boundaries for the life of the project.

This is *not* a deep domain-driven-design exercise. It's a lightweight, ~2-hour activity per new product or major feature area, focused on getting *just enough* shared language and boundary clarity to ground the architecture.

## When this skill fires

- A new product is in design and there's no existing semantic memory.
- A slice introduces domain concepts the existing model doesn't cover (e.g., adding subscriptions to a transactional-orders product).
- The team is using inconsistent terminology and confusion is showing up in PRs and stand-ups — that's the symptom of a domain-language gap.
- Bounded-context boundaries are unclear and the SA can't draw the architecture without first agreeing where the lines are.

## The procedure

### 1. List the domain events

Without code, without architecture — just the *things that happen* in the domain, written in past tense, in domain language:

- `Order placed`
- `Payment authorized`
- `Inventory reserved`
- `Shipment dispatched`
- `Customer onboarded`
- `Subscription renewed`
- `Refund issued`

Aim for 20–50 events for a new product. The PM and any domain experts contribute; the SA hosts. Time-boxed at 30 minutes.

### 2. Cluster events into bounded contexts

Group events that *belong together* — that change together, that share vocabulary, that one team would own. The clusters are candidate bounded contexts:

```
Ordering:
  - Order placed
  - Order paid
  - Order shipped
  - Order cancelled
  - Order returned

Billing:
  - Invoice generated
  - Payment authorized
  - Payment captured
  - Payment refunded
  - Subscription renewed

Inventory:
  - Item received
  - Item reserved
  - Item shipped
  - Stock counted

Customer:
  - Customer onboarded
  - Customer profile updated
  - Customer suspended

Notification:
  - Email sent
  - SMS sent
  - Push notification delivered
```

Each context has a name, a one-sentence purpose, and the events it owns.

### 3. Identify integration points

Where do contexts interact? List them explicitly:

- **Ordering → Inventory**: Ordering asks Inventory to reserve items.
- **Ordering → Billing**: Ordering asks Billing to authorize payment.
- **Billing → Notification**: Billing tells Notification to send receipts.
- **Customer → all contexts**: Customer state is read across contexts (typically via context-specific projection or via shared identity service).

Each integration is a *relationship* with a direction (who calls whom) and a style (synchronous request/response, async event, shared database — avoid).

### 4. Build the ubiquitous language glossary

The terms that appear in events become the glossary. Pin definitions explicitly:

```
Order: A customer's request to purchase one or more items at agreed prices.
  An Order has a unique identifier, a status, and one or more LineItems.

LineItem: A single SKU and quantity within an Order, with the price at time of order.

Payment: An attempt to capture funds against a customer for a specific Order.
  A Payment has a state machine: authorized → captured → settled (or failed/refunded).

Shipment: The fulfillment vehicle for one or more Orders. May span multiple
  Orders (consolidated shipment) or be one-per-Order (direct shipment).
```

Discipline:
- One term, one meaning. If "Customer" means different things in Ordering and Billing, name them differently (BillingCustomer vs OrderingCustomer) or merge the contexts.
- Avoid generic terms ("Item," "Record," "Entity") in the domain language.
- Define terms by what they *are* in the domain, not by what data they hold.

### 5. Identify candidate aggregates per context

Within each bounded context, find the aggregate roots — the entities with identity that own a transactional boundary. The aggregate root is what changes together; everything inside the aggregate changes in a single transaction.

For Ordering:
- **Order** (aggregate root) contains LineItems (entities), Address (value object), Status (value object).
- Operations on an Order (place, cancel, ship) modify the whole aggregate atomically.

For Billing:
- **Invoice** (aggregate root) contains InvoiceLineItems (entities), PaymentAttempts (entities).
- **Subscription** is a separate aggregate (its own consistency boundary).

Aggregates inform `data-modeling`: each aggregate is typically one transactional unit, often one or a small set of related tables.

### 6. Document the model

| Output | Location | Update cadence |
|---|---|---|
| Bounded-context map | `.project/semantic/bounded-contexts.md` | Stable; updated when domain reshapes |
| Glossary | `.project/semantic/glossary.md` | Grows over project life; entries added as concepts emerge |
| Aggregates per context | `.project/semantic/aggregates-{context}.md` | One file per context |
| Context-relationship map | `.project/semantic/context-map.md` | Stable; updated on integration changes |

These files are *referenced* by all subsequent design work and are the canonical source for domain language.

## Working with the model

- Every new ADR references the bounded context(s) it impacts in its `impacted_domains` frontmatter.
- Every new user story is implicitly in a context (the PM or SA tags it explicitly).
- Every new schema design (data-modeling) maps to one or more aggregates.
- Every new API (api-design) is owned by one context.
- Every new piece of code lives in the top-level package/directory for its context (matches `engineering-standards` layout).

## Mode handling (G/B)

**Greenfield.** Run the full procedure once at the start of the project. Update the glossary as the project evolves; the contexts themselves are stable.

**Brownfield.** The existing bounded contexts are inferred from `.repo-intel/architecture-map.md` and the existing code's top-level package structure. The glossary may already exist in the codebase as comments, README sections, or implicit knowledge — extract it explicitly via this skill and put it in `.project/semantic/glossary.md`. Reshaping existing context boundaries is a substantial change (it's the heart of a re-architecture); flag it as such.

## What this skill does not do

- Design the technical architecture — that's `architecture-pattern-selection`, which *uses* this skill's output.
- Design schemas — that's `data-modeling`, which uses the aggregates from this skill.
- Implement code — developers consume the glossary for naming.
- Validate business logic — that's product discovery and user research.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "We know the domain; no need for a glossary." | Implicit knowledge produces ambiguous code. The glossary is what catches "I thought X meant Y." Cheap insurance. |
| "Bounded contexts are over-engineering for our size." | Even one-team projects benefit from clear contexts. Without them, models bleed and the codebase becomes a single tangled domain. |
| "DDD is too heavyweight." | DDD-lite (glossary + contexts + ubiquitous language) is days of work; full DDD-heavy is weeks. Don't conflate. The light version pays off in any system above trivial. |
| "We'll define terms as we go." | "As we go" means three engineers using `User` to mean three different things. Define before coding. |
| "Our domain doesn't have interesting concepts." | Every domain has terms users use that engineers misinterpret. The fact that the agent thinks the domain is boring is itself a signal that comprehension is shallow. |
| "Context map is a diagram nobody reads." | The context map is the architecture cheat-sheet for anyone joining the project. Without it, every new contributor rediscovers the boundaries. |

## Verification

You are done when:

- [ ] Glossary at `.project/semantic/glossary.md` with ≥ 10 domain terms.
- [ ] Each term has: definition + which bounded context owns it + synonyms (and what they mean elsewhere).
- [ ] Bounded contexts identified and named.
- [ ] Context map at `.project/working/architecture/context-map.md` shows: contexts as boxes + integration patterns between them (shared kernel / customer-supplier / conformist / ACL / separate ways).
- [ ] Ubiquitous language sample: 5+ phrases the team will use consistently.
- [ ] Aggregates within each context identified with their invariants.

Evidence to check:
- An engineer joining cold can read glossary + context map and pass a "what does X mean in context Y" quiz.
- Two contexts that share a term have an explicit translation (or it's the SAME term meaning the SAME thing — explicit, not assumed).
- Each aggregate has a named root and a stated invariant ("Order: total = sum(line items) - discounts").

If any item is missing, domain discovery is incomplete; do not advance to data-modeling or api-design.

## Anti-patterns

- Skipping domain discovery because "the team already knows the domain." Implicit knowledge produces ambiguous code; explicit glossary prevents it.
- Naming bounded contexts by technical layer (Frontend, Backend, Database) rather than by domain (Ordering, Billing, Inventory). Wrong abstraction.
- Generic glossary entries ("Order: a thing customers make"). Domain definitions are specific or they're useless.
- One giant "core" context containing everything. That's not a context; that's an absence of boundaries.
- Aggregate definitions that span multiple contexts. Aggregates respect context boundaries; cross-context aggregates are a smell.

## Time budget

This skill is intentionally lightweight:
- Greenfield first pass: 90–120 minutes with the PM + SA + any domain experts.
- Slice-level extension: 15–30 minutes by the SA, optionally with the PM if domain terms are at stake.

It's not an exhaustive DDD exercise. The goal is *just enough* shared language and boundary clarity that the next phases run cleanly.
