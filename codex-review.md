# Codex Review

## Findings

1. **Launch blocker: install/test path currently fails.**
   `./install.sh --dry-run --tool=claude-code /private/tmp` and `./try-as-plugin.sh --dry-run /private/tmp` both exit with code 1 before printing the banner. The likely cause is the `grep` count pipeline under `set -euo pipefail` when there are no `state: removed` skills in `install.sh` and `try-as-plugin.sh`. This must be fixed before public launch.

2. **Launch blocker: manifest validation fails.**
   `bash scripts/validate-manifests.sh` reports `.claude-plugin/plugin.json` missing `version` and `.claude-plugin/marketplace.json` missing top-level `description`.

3. **Counts and claims are inconsistent across the repo.**
   The validator finds **81 active skills, 0 tombstones**, but docs and manifests say 77, 78, 79, 80, and 80/80 in different places. This is a credibility issue for a platform whose value proposition is disciplined delivery.

4. **Telemetry story is internally contradictory.**
   `INSTALLATION.md` says telemetry collection does not exist, but the repo has `hooks/tap.sh`, `factory-record.sh`, `factory-frequency.sh`, `factory-aging.sh`, and `factory-evaluation` describes a layered capture model. The real position seems to be: Claude Code has lightweight event capture; cross-tool telemetry is schema-compatible but not equally automated. Say that plainly.

5. **The lifecycle framing around `delivery-planner` is ambiguous.**
   `/start` uses it to bootstrap a charter, but `delivery-planner/SKILL.md` says it fires after enough discovery, NFR, and architecture data exists. The skill later verifies the charter output. Split this into "charter bootstrap" and "workflow instantiation/re-planning", or make the staged behavior explicit.

6. **Contribution docs describe the old skill metadata model.**
   `CONTRIBUTING.md` asks for extended frontmatter, but `validate-skills.sh` explicitly allows only `name` and `description` in frontmatter and moves Praxis metadata into the body. This will cause bad external PRs.

7. **Repo hygiene is not launch-ready.**
   `.DS_Store` files are present, and `references/factory-metrics-schema.md` references missing `scripts/validate-factory-metrics.sh`.

## What Makes Sense

The core architecture is strong: workflow -> agent -> skill -> governance is easy to explain and maps well to real delivery. The `using-praxis` front-door is the right abstraction because it keeps a large library usable. The Architecture Challenger is a genuine differentiator, especially with sub-personas and explicit override governance. The System Steward/factory-evaluation loop is also strategically good: it gives the platform a story for staying sharp instead of becoming prompt sprawl.

## Recommended Improvements Before GitHub Launch

1. Fix installer/plugin dry-runs and manifest validation first.
2. Normalize all public counts from generated checks, not hand-written numbers.
3. Reframe README around "disciplined agentic delivery system", with the Challenger and governance evidence packs as the hook.
4. Clarify tool support tiers: Claude Code is first-class; others are portable content/addressing unless equivalent hooks exist.
5. Add CI for `validate-skills.sh`, `validate-manifests.sh`, YAML parse, missing referenced scripts/files, and no `.DS_Store`.
6. Add one complete worked example: greenfield SaaS or brownfield enhancement from `/start` through one `/slice`.
7. Decide whether telemetry is alpha, partial, or roadmap, then make docs, factory skills, and scripts agree.

## Verification Run

- `validate-skills.sh` passes with 81 active skills.
- Workflow/governance YAML parses with Ruby.
- `validate-manifests.sh` fails.
- Installer and plugin dry-runs fail.

No files were changed during the original review.
