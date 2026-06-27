---
name: source-grounded-coding
description: |-
  Verify every non-trivial framework/library/tool decision against official documentation BEFORE implementing. Cite sources inline. Flag what's unverified. Reject hallucinated API surfaces. Pairs with `engineering-standards` (this skill is the active discipline; engineering-standards is the broad reference). The agent's natural failure mode is plausible-sounding API code that doesn't exist; this skill is the counter. Use when implementing against any external library/framework/tool, when answering "does X support Y?", when writing example code for unfamiliar APIs, or when adopting a new dependency.
---

# Source-Grounded Coding

<!-- praxis:metadata:begin -->
```yaml
capability: foundation
domain: cross-cutting
state: active
dependencies:
  - engineering-standards
  - codebase-comprehension
  - api-design
triggers:
  - "implementing against an external library / framework / tool"
  - "answering 'does this framework support X?'"
  - "writing example code for an unfamiliar API"
  - "adopting a new dependency or upgrading a major version"
  - "the agent is about to confidently write code citing no source"
  - "review caught hallucinated API usage"
outputs:
  - implementation code with inline source citations
  - inline verified-against notes per decision
  - unverified-needs-check flags for things that couldn't be confirmed
  - source-grounded ADR (when adopting a new library/framework)
consumers:
  - every implementation agent (backend-developer, frontend-developer, data-engineer, ml-ai-engineer)
  - code-review (consumes citations as evidence)
  - security-review (consumes for supply-chain attestation)
  - architecture-pattern-selection (consumes for framework-fit decisions)
references: []
```
<!-- praxis:metadata:end -->

The discipline that keeps the agent from making things up. LLM-generated code is **fluent** — it produces well-formed, plausible-sounding API calls. Fluent code that uses APIs that don't exist is worse than no code at all: it looks right, it compiles sometimes, and it fails at runtime in ways nobody traces back to "the agent guessed."

The principle: **fluency is not correctness. Every non-trivial framework decision must be grounded in a source the human can verify.**

## When this SKILL fires

- Implementing against an external library / framework / tool the agent isn't certain about.
- Answering "does this framework support X?"
- Writing example code for an unfamiliar API.
- Adopting a new dependency or upgrading a major version.
- The agent is about to confidently write code citing no source.
- Review caught hallucinated API usage; investigating root cause.

## The hallucination failure mode

The LLM's confidence on framework details is **not** calibrated to its actual accuracy. Common patterns:

- **Method invention** — `requests.fetch_json(url)` (doesn't exist; should be `requests.get(url).json()`).
- **Parameter invention** — `await fetch(url, { followRedirects: true })` (the option doesn't exist).
- **Version drift** — using an API that existed in v2 but was removed in v3.
- **Conflation across libraries** — borrowing axios's signature into fetch().
- **Plausible-but-wrong type signatures** — return type that's never been the return type.

The agent's training data is a snapshot. The framework's docs are current. When they disagree, the docs are right.

## The verification discipline

Four steps. Apply to every non-trivial framework decision.

### Step 1: Identify the assertion

The thing you're about to write that depends on the framework behaving a specific way:

- "Spring's `@Async` returns a `CompletableFuture`."
- "React's `useEffect` with `[]` runs once on mount."
- "Postgres's `JSONB` supports indexed containment queries via `@>`."
- "AWS SDK v3's `S3Client.send(new GetObjectCommand(...))` returns a stream you have to consume."

If you can't name the assertion compactly, you have a vibe, not a decision. Surface it before scrutinizing it.

### Step 2: Find the source

Acceptable sources, ordered by authority:

1. **Official docs** at the project's documented URL (e.g., `https://react.dev`, `https://spring.io/projects/spring-framework`).
2. **Official API reference** (Javadoc, JSDoc, godoc, intersphinx).
3. **Source code** in the repository (when behavior isn't documented but is observable).
4. **Official release notes** for version-specific behavior.
5. **Maintainer-authored blog post or RFC** when no other source covers it.

NOT acceptable as primary sources:

- Stack Overflow answers (corroborating, not primary).
- AI-generated articles.
- Third-party tutorials older than 6 months.
- The agent's own prior output.

### Step 3: Cite

Inline citation in the code comment OR in the PR description / ADR:

```python
# Per Postgres docs §8.14.4 (JSONB Indexing — GIN), the @> operator
# supports indexed containment queries when the column has a GIN index.
# https://www.postgresql.org/docs/16/datatype-json.html#JSON-INDEXING
CREATE INDEX idx_orders_meta ON orders USING GIN (meta jsonb_path_ops);
```

```typescript
// Per AWS SDK for JS v3 docs (S3 GetObjectCommand returns
// `Body: Readable | ReadableStream | Blob`), the Body must be consumed
// before the response can be discarded.
// https://docs.aws.amazon.com/AWSJavaScriptSDK/v3/latest/clients/client-s3/Class/GetObjectCommand/
const { Body } = await s3.send(new GetObjectCommand(...));
const text = await Body!.transformToString();
```

The citation does three things at once:
- Makes the assertion verifiable in 30 seconds.
- Surfaces the version (the docs URL is version-pinned).
- Becomes evidence in code review.

### Step 4: Flag what's unverified

If you can't find a source for an assertion, **don't pretend you did**. Flag it:

```javascript
// UNVERIFIED: I believe fetch() doesn't follow redirects by default in
// browser contexts but does in Node. Confirm before relying on either
// behavior. Source needed.
const response = await fetch(url);
```

Explicit "UNVERIFIED" comments give the human a list of follow-ups. Silent guessing gives them production incidents.

## The four classes of grounding

| Class | What requires citation | Example |
|---|---|---|
| **API surface** | Method names, parameter signatures, return types, async vs sync, error semantics. | "Yes, the method exists; here's the doc page." |
| **Behavior** | Side effects, ordering, retries, defaults, edge cases. | "Yes, it does Y when given Z; here's the spec section." |
| **Version-specific** | Feature availability, breaking changes, deprecations. | "This works in v17+; before that you needed X." |
| **Configuration** | What config flags do what, default values, interaction effects. | "Setting `foo: true` disables Y per docs §3." |

For trivial things — basic language constructs, well-known control flow — citation is overkill. The discipline applies to **framework / library / tool boundaries** where the agent is most likely to hallucinate.

## The doc-staleness escape hatch

Sometimes the docs are wrong. Source code is the ground truth. When docs and behavior disagree:

1. Note the discrepancy.
2. Cite both (the doc URL + the source-code line).
3. Open a tech-debt-management entry to track upstream doc bug if applicable.
4. Encode the actual behavior, not the documented behavior.

## Adopting a new dependency

When the slice introduces a new library or framework, the discipline extends:

1. **License check** — compatible with the project's license requirements (per `supply-chain-security`).
2. **Maintenance status** — last commit, open issues, release cadence, maintainer count.
3. **Security history** — known CVEs, supply-chain audits, dependency tree.
4. **Documentation quality** — can we actually verify behavior?
5. **Performance and footprint** — bundle size, runtime cost, tree-shakability.
6. **Alternatives considered** — at least 2 alternatives evaluated.

Output: an ADR per `adr-decision-records` covering the choice + alternatives + rationale + citations.

## Source-citation in PRs

PR description includes a "Sources" section for any non-trivial framework decision:

```markdown
## Sources

- React 18 `useTransition` semantics → https://react.dev/reference/react/useTransition
- Postgres GIN index for JSONB → https://www.postgresql.org/docs/16/datatype-json.html#JSON-INDEXING
- AWS SDK v3 streaming response handling → (link)

## Unverified (needs human check)

- I believe pgBouncer transaction-mode pooling preserves prepared statements
  but couldn't find a definitive doc. Verify before merging.
```

Code Reviewer can verify in minutes. Without sources, verification costs days or never happens.

## Mode handling (G/B)

**Greenfield.** Apply from the first dependency adoption. Build the citation muscle early.

**Brownfield.** Audit existing code. Common findings: framework usage with hallucinated patterns that "happen to work." Apply the discipline to NEW code and to brownfield areas touched by `impact-analysis`. Don't try to retrofit citations to the entire codebase.

## Verification

You are done when:

- [ ] Every non-trivial framework / library / tool assertion is cited inline with a source URL.
- [ ] Sources are official docs, official API reference, source code, release notes, or maintainer post.
- [ ] No citations to AI-generated articles, Stack Overflow as primary source, or agent's prior output.
- [ ] `// UNVERIFIED:` flags appear for assertions that couldn't be confirmed.
- [ ] PR description includes a "Sources" section + "Unverified" section if applicable.
- [ ] New-dependency adoptions have an ADR with: license, maintenance, security, alternatives.
- [ ] Version-specific behavior tagged to the specific version.

Evidence to check:
- A reviewer can verify each citation in 30 seconds.
- An `UNVERIFIED:` flag either got verified before merge or was acknowledged in PR.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "I know this API; I don't need to check." | The training cutoff was N months ago; the API may have changed. Check anyway. |
| "The docs are hard to find; I'll just write it." | "Hard to find" usually means "I haven't looked." 90 seconds in the docs saves hours of debugging. |
| "Stack Overflow says this works." | SO is corroborating, not primary. The accepted answer may be 8 years old and refer to a different version. |
| "I'll add the citation later." | Later means never. The citation is part of the implementation, not paperwork. |
| "It compiles, so it must be right." | Compilation verifies type signatures, not semantics. A method that exists may do something completely different than you assumed. |
| "Citation comments are noise." | They become evidence in code review and breadcrumbs in incidents. Worth the line. |

## Outputs

| Output | Location |
|---|---|
| Citations inline in code | source files (comments) |
| Unverified flags | source files (`// UNVERIFIED:` comments) |
| PR "Sources" section | PR description |
| New-dependency ADR | `.project/decision/` |

## What this SKILL does NOT do

- General code quality — that's `code-review`.
- Security of dependencies — that's `supply-chain-security`.
- Choosing the right framework — that's `architecture-pattern-selection`.
- Comprehensive documentation reading (it's grounding specific assertions, not "read all the docs").

## Anti-patterns

- Confident code with no citations on framework boundaries.
- Citations to AI-generated articles or summaries.
- Version-agnostic claims about version-specific behavior.
- "UNVERIFIED" flags removed without verification.
- Citation comments deleted as "noise" by mechanical formatting.
- Stack Overflow citations promoted to primary source.
- Hallucinated APIs blamed on "the framework changed" when no change occurred.
- Library adopted without an ADR or alternatives consideration.
- Docs link added but doesn't actually contain the claim being made.
- Source-grounding skipped for "small" changes (small changes can use hallucinated APIs too).
