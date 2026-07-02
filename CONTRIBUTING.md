# Contributing

Thank you for your interest in contributing. This document covers what kinds of contributions are welcome, the conventions to follow, and the workflow.

## Status

This library is **maturing in private**. The goal is to open it up for external contributions once it has been validated against multiple real projects. For now, the contribution paths are:

1. **Issues**: bug reports, design discussions, feature proposals → file as GitHub issues.
2. **Internal PRs**: from the project owner.
3. **External PRs**: welcome for fixes and small additions, evaluated on quality + fit. Larger changes — please open an issue first to discuss.

## What can be contributed

### Skills

A SKILL is the unit of agent guidance. Each lives at `skills/<name>/SKILL.md` and must have:

- **Eight-field frontmatter**: `name`, `description`, `capability`, `domain`, `state`, `dependencies`, `triggers`, `outputs`, `consumers`, `references`.
- **Pushy `description`** ending in "Use when…" trigger phrases — this is what drives invocation.
- **Common rationalizations** table — pre-empts the failure modes the agent would otherwise rationalize into.
- **Verification** section — concrete "you are done when…" checklist + evidence-to-check.
- **What this skill does NOT do** — boundary statement.
- **Anti-patterns** — observational failure shapes.

New SKILLs must pass the **four-condition Skill Creation Policy** (per `skills/system-steward.md`):

1. Distinct trigger context (won't fold into an existing skill).
2. Cross-project applicability (not a one-off).
3. Substantive content (not a paragraph dressed as a skill).
4. Clear downstream consumers.

If a new idea fails any condition, consider contributing as a **reference** or **pattern** instead (see below).

### References

References are tool-specific or framework-specific drill-downs cited from SKILL frontmatter. They live at `skills/<skill>/references/<topic>.md`.

Use references for:

- Tool variants (e.g., `airflow.md` vs `dagster.md` cited from `data-pipeline`).
- Stack-specific implementation (e.g., `spring-boot-3.md` cited from `stack-java-spring`).
- Compliance regime details (e.g., `soc2.md` cited from `compliance-privacy`).

The reference inventory lives at `references/MISSING-INVENTORY.md`. To contribute:

1. Pick a missing reference from the inventory.
2. Write content following the style of an existing one (e.g., `skills/data-modeling/references/postgres.md`).
3. Update the inventory: move the row from "Missing" to "Shipping"; update the count.

References are 150-400 lines, substantive, and include: when to use, concepts, code patterns, gotchas, common rationalizations, verification, official sources.

### Patterns

Patterns live at `patterns/` (currently empty — see `patterns/README.md`). Use for reusable solution shapes referenced from multiple SKILLs (strangler fig, anti-corruption layer, outbox, saga, etc.).

### Agents

Agent definitions live at `agents/<name>.md`. New agents are rare — the 16-agent roster covers the standard delivery team. Propose via issue first.

### Workflows

Workflows live at `workflows/<name>.yaml`. They orchestrate phases + agents + gates. Changes to existing workflows must preserve gate semantics; new workflows propose a new project type.

### Examples

Sanitized real-project artifacts go in `examples/`. See `examples/README.md`.

### Documentation

Improvements to `README.md`, `PLAYBOOK.md`, `INSTALLATION.md`, or per-tool setup docs in `docs/` are always welcome.

## Style conventions

### YAML frontmatter

- Strict YAML; descriptions must parse cleanly (no unquoted colons in flow scalars).
- Lowercase kebab-case for SKILL / agent names; match directory name.
- `state: active` for shipping SKILLs; `experimental` for in-progress; `deprecated` or `removed` for tombstones.

### Markdown

- Section headings use `##` for major sections, `###` for sub-sections.
- Tables for comparisons and decision matrices.
- Code fences with language tags.
- 80-100 character lines preferred but not enforced.

### Anti-rationalization tables

Format:
```markdown
## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Specific rationalization the agent might form" | Concrete counter-argument |
```

5-7 rows. Each rationalization should be one the agent would actually think — not a straw man.

### Verification sections

Format:
```markdown
## Verification

You are done when:

- [ ] Checkable item 1
- [ ] Checkable item 2

Evidence to check:
- Specific artifact or signal
- Another specific check
```

7-10 items. Each item should be objectively verifiable (someone can confirm yes/no).

## One-time setup: install git hooks

After cloning, activate the repo-tracked pre-commit hook:

```bash
scripts/install-git-hooks.sh
```

This points git at `.githooks/` so every commit automatically:
- Rebuilds `plugins/praxis-codex/` when canonical source (`skills/`, `agents/`, `workflows/`, etc.) or Codex overlays (`codex-plugin-assets/`) change.
- Runs `scripts/validate-codex-plugin.sh` on the result.
- Auto-stages regenerated files so source + built package land in one atomic commit.

Skip in emergencies with `git commit --no-verify`. Restore with the same install command.

## Pull request workflow

1. **Fork** the repo + create a branch from `main`.
2. **Install git hooks** if you haven't: `scripts/install-git-hooks.sh` (see section above).
3. **Write your changes** following the conventions above.
4. **Run the validator**: `bash scripts/validate-skills.sh` — must pass with zero failures.
5. **Run YAML parse check**: every SKILL.md frontmatter must parse cleanly.
6. **Cross-reference check**: if you added a SKILL, update `consumers:` lists of any SKILL it consumes; if you added a reference, cite it from the SKILL's frontmatter.
7. **Commit** with descriptive messages (per `references/git-workflow-checklist.md` if you want). The pre-commit hook rebuilds the Codex plugin package automatically — do not bypass with `--no-verify` unless the build itself is broken (in which case fix the build first).
8. **Open a PR** with: what changed, why, how to test, any breaking changes.
9. **Address review** within reasonable time.

## Validator

`bash scripts/validate-skills.sh` checks:
- Required frontmatter fields present.
- Declared `name` matches directory.
- `state` is a valid enum.
- Cited references files exist (warning).
- Library health band (70-90 SKILLs).

## What we won't accept

- Skills that are vague advice without process steps.
- Skills that duplicate existing functionality without merging.
- References without verifiable accuracy (cite official docs).
- Changes that break the YAML parse or validator.
- Changes that introduce dependency cycles.
- Skills that bring the count above 100 without a corresponding consolidation (per `system-steward.md` Library Health Targets).

## Code of conduct

By participating in this project you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Licensing

By contributing, you agree your contributions will be licensed under the [MIT License](LICENSE).

## Questions

For substantive questions about the platform design — phase ordering, gate evidence, the orchestration model — please reference the relevant SKILL or the `ai-dev-team-skill-blueprint.md` design document, then open an issue with what you found and where you're confused.

For practical contribution questions — "where does this file go?", "how do I run the validator?" — please open a GitHub Discussion or issue with the `question` label.
