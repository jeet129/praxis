# Contributing

Thank you for your interest in contributing. This document covers what kinds of contributions are welcome, the conventions to follow, and the workflow.

## Status

This library is **early and actively maturing**. External contributions are welcome now — with larger changes discussed first — as it validates against more real projects. The contribution paths are:

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

New SKILLs must pass the **four-condition Skill Creation Policy** (per `agents/system-steward.md`):

1. Distinct trigger context (won't fold into an existing skill).
2. Cross-project applicability (not a one-off).
3. Substantive content (not a paragraph dressed as a skill).
4. Clear downstream consumers.

If a new idea fails any condition, consider contributing as a **reference** or **pattern** instead (see below).

**House template.** New SKILL.md files should follow the shape of an existing
one rather than inventing a new structure — `skills/threat-modeling/SKILL.md`
and `skills/definition-of-done/SKILL.md` are good references. That means: the
eight-field frontmatter block, a pushy trigger-laden `description`, the body
sections in the order Common rationalizations → Verification → What this
skill does NOT do → Anti-patterns, and — where the skill needs deep
tool-specific detail — that detail pushed into `references/<topic>.md`
rather than inlined.

**Length ceiling: ≤300 lines per SKILL.md.** This is enforced by convention,
not a validator check, but it's load-bearing — the library did a
progressive-disclosure pass (see `CHANGELOG.md`) moving embedded templates,
worked examples, and long code blocks out of SKILL.md bodies and into
`references/`. If your SKILL is pushing past 300 lines, that's the signal to
split the depth into a reference and cite it from frontmatter, not to keep
writing in the main file.

**New SKILLs start `state: experimental`**, not `active`. A SKILL only
graduates to `active` once it has real usage telemetry behind it (see
`docs/telemetry.md`) — `scripts/factory-aging.sh` flags experimental SKILLs
whose telemetry has gone stale, which is one of the signals the System
Steward uses to decide promote vs. prune at the quarterly review.

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

Agent definitions live at `agents/<name>.md`. New agents are rare — the 17-agent roster covers the standard delivery team. Propose via issue first.

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

## Generated surfaces — never hand-edit these

Some files in the repo are **derived** from canonical source by a script.
Editing them directly will get silently overwritten (or will drift out of
sync and fail CI). Know which is which:

| Generated surface | Source of truth | Regenerate with |
|---|---|---|
| `plugins/praxis-codex/` (the whole tree) | `skills/`, `agents/`, `workflows/`, `governance/`, `references/`, `patterns/`, `scripts/` + Codex overlays in `codex-plugin-assets/` | `scripts/build-codex-plugin.sh`, checked by `scripts/validate-codex-plugin.sh` |
| Skill / agent / workflow / gate **counts** quoted in `README.md`, `.claude-plugin/*.json`, `.cursor/rules/`, and a few SKILL bodies | the actual directory contents | `scripts/build-registry.py` (`--check` for CI drift-detection, no-write) |
| `model:` / `model_reasoning_effort:` fields in `agents/*.md` frontmatter and `codex-plugin-assets/codex-agents/*.toml` | `governance/model-routing.yaml` (tier → model map) | `scripts/apply-model-routing.py` (`--check` for CI) |

Rules that follow from this:

- **Never edit `plugins/praxis-codex/` by hand.** If you need a Codex-side
  change, edit the canonical source or the relevant file in
  `codex-plugin-assets/`, then rebuild. The pre-commit hook does this for you
  automatically on relevant commits (see below); manual rebuilds use
  `scripts/build-codex-plugin.sh`.
- **Never hand-edit a count.** If you add or remove a SKILL/agent/workflow/gate,
  run `scripts/build-registry.py` (no flag) to rewrite the count-bearing
  surfaces, and run it with `--check` before committing to confirm nothing is
  left stale. CI runs the `--check` form and fails the build on drift.
- **Never hand-edit a `model:` field.** Change the tier→model mapping in
  `governance/model-routing.yaml` instead and run
  `scripts/apply-model-routing.py`. Hand-editing an agent's `model:` field
  works locally but `apply-model-routing.py --check` in CI will flag it as
  out of sync with the routing table and fail.

## One-time setup: install git hooks

After cloning, activate the repo-tracked pre-commit hook:

```bash
scripts/install-git-hooks.sh
```

This points git at `.githooks/` so every commit automatically:
- Rebuilds `plugins/praxis-codex/` when canonical source (`skills/`, `agents/`, `workflows/`, etc.) or Codex overlays (`codex-plugin-assets/`) change.
- Runs `scripts/validate-codex-plugin.sh` on the result.
- Auto-stages regenerated files so source + built package land in one atomic commit.
- **Reminds you (non-blocking) to check docs.** If the commit touches
  `agents/`, `skills/`, `workflows/`, `commands/`, `governance/`, `scripts/`,
  or `hooks/` but touches none of `README.md`, `INSTALLATION.md`,
  `PLAYBOOK.md`, `CHANGELOG.md`, `ROADMAP.md`, or `docs/`, the hook prints a
  warning asking you to double-check the docs still match the behavior you
  just changed. It does not fail the commit — it's a nudge, not a gate.

Skip the rebuild/validate in emergencies with `git commit --no-verify` — but that also skips the docs reminder, so re-check documentation manually if you do. Restore normal behavior with the same install command.

## Pull request workflow

1. **Fork** the repo + create a branch from `main`.
2. **Install git hooks** if you haven't: `scripts/install-git-hooks.sh` (see section above).
3. **Write your changes** following the conventions above.
4. **Run the relevant validators** from the suite below — must pass with zero failures. At minimum `bash scripts/validate-skills.sh`; add the others per what you touched.
5. **Run YAML parse check**: every SKILL.md frontmatter must parse cleanly.
6. **Cross-reference check**: if you added a SKILL, update `consumers:` lists of any SKILL it consumes; if you added a reference, cite it from the SKILL's frontmatter.
7. **Commit** with descriptive messages (per `references/git-workflow-checklist.md` if you want). The pre-commit hook rebuilds the Codex plugin package automatically — do not bypass with `--no-verify` unless the build itself is broken (in which case fix the build first).
8. **Open a PR** with: what changed, why, how to test, any breaking changes.
9. **Address review** within reasonable time.

## Validator suite

There are seven validators. Run the ones relevant to what you touched before
opening a PR; CI runs all of them plus a routing-report smoke test on every
push.

| Script | Checks | Run when you touch |
|---|---|---|
| `bash scripts/validate-skills.sh` | Required frontmatter fields present; declared `name` matches directory; `state` is a valid enum; cited reference files exist (warning); library health band (70-90 SKILLs). | `skills/` |
| `bash scripts/validate-manifests.sh` | Claude Code plugin + marketplace manifests (`.claude-plugin/*.json`) are valid JSON and reference real paths. | `.claude-plugin/`, `commands/`, top-level manifest files |
| `python3 scripts/validate-workflows.py` | Workflow YAML parses; referenced agents/gates/skills in each `workflows/*.yaml` actually exist. | `workflows/` |
| `python3 scripts/validate-references.py` | Every `references:` path cited from a SKILL's frontmatter resolves to a real file. | `skills/*/references/`, SKILL frontmatter `references:` lists |
| `bash scripts/validate-codex-plugin.sh` | The generated `plugins/praxis-codex/` package is structurally valid and in sync with canonical source. | `codex-plugin-assets/`, or anything that changes canonical source (run after rebuilding) |
| `python3 scripts/apply-model-routing.py --check` | Every agent's `model:` (or Codex `model_reasoning_effort:`) field matches what `governance/model-routing.yaml` resolves for its `capability_tier`. Exits 1 on drift, writes nothing. | `agents/*.md` frontmatter, `governance/model-routing.yaml` |
| `python3 scripts/build-registry.py --check` | Skill/agent/workflow/gate counts quoted across `README.md`, plugin manifests, `.cursor/rules/`, and a few SKILL bodies match the actual directory contents. Exits 1 on drift, writes nothing. | Anything that adds/removes a SKILL, agent, workflow, or gate |

One additional test guards routing behavior: `bash scripts/test-routing-parity.sh`
asserts the no-drive resolver (`scripts/resolve-model.py`) and the drive runner
(`scripts/praxis-drive.sh`) resolve every tier to the same model/effort on both
harnesses, and that a project override (incl. `force_tier`) moves both together.
Run it when you touch `resolve-model.py`, `praxis-drive.sh`'s routing, or
`governance/model-routing.yaml`'s structure.

Operator-facing scripts you may also touch (not PR-gating validators):
`scripts/resolve-model.py` (tier→model/effort from the EFFECTIVE table — the
single source of truth for spawn routing), `scripts/setup-claude-agents.sh` and
`apply-model-routing.py --claude-out/--codex-out` (materialize project-local
agent profiles from a project routing override), and
`scripts/governance-overrides.py` + `scripts/refresh-governance-overrides.sh`
(diff/merge a project's `.project/governance/` overrides against plugin
defaults; the SessionStart hook warns on drift).

Two additional scripts aggregate telemetry rather than validate structure —
not required for a PR to pass, but useful when working on telemetry-adjacent
changes: `scripts/factory-frequency.sh` (usage aggregation) and
`scripts/factory-aging.sh` (experimental-SKILL coverage gate). See
`docs/telemetry.md` for the full telemetry picture and
`scripts/factory-routing-report.py` for the cost/routing reporter that CI
smoke-tests.

Fix-forward, don't drop the flag: if `apply-model-routing.py --check` or
`build-registry.py --check` reports drift, run the same script **without**
`--check` to have it rewrite the derived surfaces, then commit the result —
don't hand-edit the counts or model fields yourself (see "Generated
surfaces" above).

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
