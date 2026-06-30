# Skills Review

Scope: skills only. This review focuses on gaps, responsibility ambiguity, routing precision, missing supporting resources, and opportunities to make the skill layer more efficient.

## Findings

1. **Missing referenced skill resources will break agent execution.**

   At least 45 declared references are missing from `skills/*/references/`, including API design, compliance, data pipelines, RAG, LLM safety, performance testing, and evaluation tooling.

   Examples:
   - `skills/api-design/SKILL.md` declares `rest-openapi.md`, `grpc-proto.md`, `asyncapi-events.md`, and `graphql.md`, but only `contract-review.md` exists.
   - `skills/compliance-privacy/SKILL.md` declares several regime references that do not exist yet.
   - `skills/rag-design/SKILL.md`, `skills/llm-safety/SKILL.md`, `skills/evaluation-engineering/SKILL.md`, and `skills/performance-testing/SKILL.md` declare missing tool references.

   Recommendation: add a reference-existence validator and either ship the references or move planned references into a backlog section instead of active metadata.

2. **`skill-registry` describes an outdated metadata model.**

   `skills/skill-registry/SKILL.md` says extended metadata lives in frontmatter, but the current validator requires only `name` and `description` in frontmatter and reads Praxis metadata from the body metadata block.

   Impact: contributors and agents receive contradictory instructions about how skills are structured.

   Recommendation: update `skill-registry` to describe the actual two-tier model:
   - Claude-compatible frontmatter: `name`, `description`
   - Praxis metadata block: `capability`, `domain`, `state`, `dependencies`, `triggers`, `outputs`, `consumers`, `references`

3. **Some foundational skills promise generated runtime artifacts that do not exist yet.**

   Examples:
   - `skill-registry` promises generated `skill-registry.yaml`.
   - `memory-management` promises `.project/INDEX.yaml`.
   - `factory-evaluation` depends on telemetry validation/migration tooling that is not fully present.

   Recommendation: either implement the supporting scripts or mark those outputs as planned/manual so the skill text does not overstate current automation.

4. **Boundary sections are missing in high-leverage skills.**

   Skills missing `## What this skill does not do` include:
   - `architecture-documentation`
   - `doubt-driven-decisions`
   - `engineering-standards`
   - `factory-evaluation`
   - `impact-analysis`
   - `legacy-modernization`
   - `requirements-intake`
   - `source-grounded-coding`
   - `stack-flutter`
   - `stack-java-spring`
   - `stack-node-ts`
   - `stack-python`
   - `tech-debt-management`
   - `technical-documentation`
   - `using-praxis`

   Impact: these are exactly the skills where agents are likely to over-apply guidance unless the boundary is explicit.

   Recommendation: add concise non-ownership boundaries to each, especially foundational/runtime and stack-pack skills.

5. **Anti-pattern sections are missing in several skills.**

   Skills missing `## Anti-patterns` include:
   - `delivery-planner`
   - `engineering-standards`
   - `memory-management`
   - `nfr-definition`
   - `project-memory`
   - `project-phasing`
   - `requirements-elicitation`
   - `requirements-intake`
   - `secure-coding`
   - `skill-registry`

   Recommendation: add short anti-pattern lists for each. These are useful because they constrain agent rationalization, especially in recurring workflow skills.

6. **Trigger quality is uneven.**

   The validator reports 20 descriptions lacking the exact `Use when` trigger phrase. This matters because descriptions are part of routing behavior, not just documentation.

   Affected skills include:
   - `capacity-resource-estimation`
   - `code-review`
   - `codebase-comprehension`
   - `delivery-planner`
   - `distributed-systems-patterns`
   - `domain-discovery`
   - `evaluation-engineering`
   - `impact-analysis`
   - `ml-problem-framing`
   - `ml-serving-deployment`
   - `platform-aws`
   - `platform-azure`
   - `platform-gcp`
   - `project-memory`
   - `requirements-interrogation`
   - `responsible-ai`
   - `source-grounded-coding`
   - `stack-web-frontend`
   - `tech-debt-management`
   - `user-research`

   Recommendation: normalize every description to include explicit `Use when...` phrasing.

7. **`delivery-planner` has a lifecycle ambiguity.**

   `/start` uses `delivery-planner` to bootstrap the project charter, but `delivery-planner/SKILL.md` frames the skill as something that runs after discovery, NFR, and architecture inputs exist.

   Recommendation: split the responsibility conceptually:
   - `charter bootstrap`: initial flags, mode, stack/cloud, compliance, project type
   - `workflow instantiation`: post-discovery/NFR/architecture executable workflow instance
   - `re-planning`: material mid-project changes

   This does not necessarily require three skills, but the staged behavior should be explicit.

8. **Requirements skills are mostly clean, but KUACQ needs compression modes.**

   `requirements-interrogation` is valuable, but requiring a full KUACQ block at every substantive phase entry can become heavy for repeated slice work.

   Recommendation: add modes:
   - `full`: new phase, high-risk slice, ambiguous inputs
   - `delta`: repeat slice with known context; only changed knowns/unknowns/assumptions
   - `skip-with-rationale`: trivial change, typo, mechanical update

9. **Security responsibilities are conceptually well separated, but execution depends on missing references.**

   Current separation is strong:
   - `threat-modeling`: design-time STRIDE and trust boundaries
   - `authn-authz`: identity and authorization model
   - `secure-coding`: code-level defenses and review
   - `compliance-privacy`: controls, evidence, retention, audit
   - `supply-chain-security`: dependency and build provenance

   Recommendation: keep these separate. Focus improvement on missing stack references, per-regime references, and explicit handoff artifacts between the skills.

10. **Infra/release skills risk over-processing small projects.**

   `cicd-pipeline`, `deploy-release`, `environments`, and `iac` are strong but heavy.

   Recommendation: add activation profiles:
   - `solo/simple`: minimal CI, one staging-like environment, basic deploy/rollback, essential security gates
   - `team/standard`: full CI chain, dev/test/staging/prod, signed artifacts, standard production gate
   - `regulated/high-risk`: full evidence packs, DR, chaos, perf soak, compliance artifacts, advanced rollout strategy

   This lets the same skills scale without making small projects feel over-governed.

11. **AI/agentic skills are strong, but `responsible-ai` versus `llm-safety` needs sharper trigger boundaries.**

   Current distinction:
   - `llm-safety`: LLM-specific guardrails, prompt injection, jailbreaks, output validation, tool-call validation
   - `responsible-ai`: broader fairness, robustness, transparency, model cards, human-in-the-loop, harm-signal governance

   Ambiguity: LLM-only features may trigger both, even when the feature is low-stakes.

   Recommendation: define activation rules:
   - Always use `llm-safety` for LLM/agent features.
   - Use `responsible-ai` when the feature affects people, access, safety, regulated decisions, financial/medical/legal outcomes, ranking, eligibility, or high-stakes automation.

12. **Capability taxonomy has drift.**

   Most data skills use `capability: data`, but `skills/data-pipeline/SKILL.md` uses `capability: data-engineering`.

   Recommendation: normalize to one capability value unless the distinction is intentional and documented in `skill-registry`.

13. **`source-grounded-coding` should be more central to implementation.**

   This skill directly addresses the agent-specific failure mode of hallucinated framework/library APIs.

   Recommendation: make it a default dependency or required pre-step for:
   - stack packs
   - new dependency adoption
   - framework upgrades
   - unfamiliar API usage
   - implementation slices touching external libraries

## What Works

The skill library has a strong operating shape. The strongest areas are:

- `using-praxis`: useful front door and routing model.
- `requirements-interrogation`: strong clarification discipline.
- `architecture-pattern-selection`: clear KISS/YAGNI architecture bias.
- `threat-modeling`: practical STRIDE workflow with clean handoffs.
- `agentic-architecture`: current and production-minded.
- `rag-design`: concrete, modern RAG defaults.
- `evaluation-engineering`: strong AI QA framing.
- `source-grounded-coding`: important agent-specific guardrail.

The major clusters are also reasonably well separated:

- Discovery: `product-discovery`, `requirements-elicitation`, `requirements-interrogation`, `nfr-definition`, `requirements-intake`
- Architecture: `domain-discovery`, `architecture-pattern-selection`, `api-design`, `data-modeling`, `project-phasing`
- Security: `threat-modeling`, `authn-authz`, `secure-coding`, `compliance-privacy`, `supply-chain-security`
- Quality: `testing-strategy`, `code-review`, `performance-testing`, `accessibility`
- Infra/release: `iac`, `environments`, `cicd-pipeline`, `deploy-release`, `observability`, `reliability-dr`
- AI/ML: `ml-problem-framing`, `ml-training-evaluation`, `ml-serving-deployment`, `ml-monitoring-drift`, `agentic-architecture`, `rag-design`, `evaluation-engineering`, `llm-safety`, `responsible-ai`

## Priority Remediation Plan

1. **Fix active metadata and references.**
   Add reference-existence validation and clean up all missing references.

2. **Fix skill metadata doctrine.**
   Update `skill-registry` and contribution guidance to match the actual two-tier metadata model.

3. **Add missing boundaries.**
   Add `What this skill does not do` to high-leverage runtime, stack, and maintenance skills.

4. **Normalize triggers.**
   Ensure every skill description includes `Use when...` and avoid vague trigger phrases.

5. **Introduce activation profiles.**
   Add lightweight/standard/regulated profiles to heavy governance, release, infra, and quality skills.

6. **Clarify staged lifecycle ownership.**
   Refine `delivery-planner`, `using-praxis`, `project-memory`, `memory-management`, and `skill-registry` so promised automation matches actual implementation.

7. **Make source-grounding mandatory where it matters.**
   Require `source-grounded-coding` for framework/library/tool decisions in implementation slices.

## Validation Notes

- `bash scripts/validate-skills.sh .` passes.
- Current count: 81 active skills, 0 removed tombstones.
- Validator reports 20 warnings, all trigger-description warnings.
- Every skill has a `## Verification` section.
- Several skills are missing `What this skill does not do` and/or `Anti-patterns` sections.
- Missing skill references are the most material skills-layer launch risk.
