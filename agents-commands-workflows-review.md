# Agents, Commands, and Workflows Review

Scope: focused review of `agents/`, `commands/`, `.claude/commands/`, `.gemini/commands/`, `workflows/`, and the governance/install touchpoints that determine whether these orchestration assets work as a coherent public GitHub launch.

## Executive Summary

The role model is strong. The repo has a credible lifecycle shape: PM -> Architect + Challenger -> Lead Developer + specialists -> review gates -> QA -> release -> Steward. The agent descriptions generally have good boundaries, the command set maps to recognizable user intents, and the workflows read like a full delivery operating model rather than isolated prompt snippets.

The launch risk is consistency, not ambition. Commands are split across three surfaces and already drift. Workflows refer to governance fields that do not exist. Some workflows duplicate older implementation-slice definitions while a richer standalone slice workflow exists. Several reviewer agents are told to write records while their declared tool grants omit write/edit capabilities. Brownfield ownership is inconsistent between Tech Writer, Solution Architect, and the audit command.

For a GitHub launch, tighten the contract layer first: command inventory, workflow schema, gate reference syntax, agent tool grants, and ownership matrix. That will make the platform feel intentional instead of aspirational.

## What Works

1. **Lifecycle coverage is coherent.** The 16-agent set covers discovery, architecture, challenge, delivery coordination, implementation, QA, security, platform, documentation, data, ML, and library stewardship.

2. **Most agent responsibilities are explicit.** Agents usually state what they own and do not own. This is especially useful for Product Manager, Solution Architect, Lead Developer, Code Reviewer, Security Reviewer, UX Designer, and System Steward.

3. **Adversarial review is a real differentiator.** `architecture-challenger` is distinct from the Solution Architect and has selectable sub-personas for scale, security, cost, operations, and reliability.

4. **Workflow intent is end-to-end.** `implementation-slice.yaml` includes implementation, review, CI, staging, rollback, QA, documentation, and closeout, which is the right operational bar for an "agentic development platform."

5. **Commands are user-facing in the right places.** `/start`, `/discover`, `/architect`, `/audit`, `/slice`, `/release`, and `/steward` map to clear lifecycle entry points.

## Findings

### 1. Command Surfaces Have Drifted

There are three command surfaces:

- `commands/` has `review` and `factory-record` in addition to the core lifecycle commands.
- `.claude/commands/` omits `review` and `factory-record`.
- `.gemini/commands/` contains only TOML command files and also omits `review` and `factory-record`.

Concrete evidence:

- Root `commands/` includes `factory-record.md`, `review.md`, and `review.toml`.
- `.claude/commands/` lacks those three files.
- `.gemini/commands/` lacks all markdown command companions and lacks `review.toml`.
- `install.sh` copies `.claude/commands` for Claude Code and Antigravity, not root `commands/`.
- `.claude-plugin/plugin.json` points at root `commands`.

Impact: users get different commands depending on installation path. The plugin path may expose `/review`; project install likely does not. `factory-record` is documented as a command but has no TOML equivalent and is not copied by the installer.

Recommendation: define one command source of truth, then generate or sync tool-specific command directories from it. If `/review` and `/factory-record` are public commands, promote them consistently. If they are internal, remove or clearly mark them.

### 2. Published Counts Are Inconsistent

The repository currently has 81 skill directories, 16 agents, and 5 workflows. But the repo advertises different numbers:

- `commands/start.toml` says "16 agents, 78 SKILLs, 5 workflows."
- `.claude-plugin/plugin.json` says 79 SKILLs.
- `install.sh` header says 80 SKILLs and 7 slash commands.
- `PLAYBOOK.md` says 77 skills in at least one place.
- README/INSTALLATION still advertise 7 commands, while root `commands/` now has additional command assets.

Impact: this undermines trust at installation time. A public repo claiming to be a platform should pass a basic inventory check.

Recommendation: add a repository inventory script that computes counts from disk and fails CI when README, plugin manifest, install output, and `/start` command text drift.

### 3. Workflow Gate References Do Not Match Governance Schema

Workflows use paths such as:

- `governance.requirements_freeze.approver`
- `governance.architecture_sign_off.approver`
- `governance.production_go_live.approver`

But `governance/governance.yaml` defines gates under `gates.*` and uses `primary_approver`, not `approver`.

Examples:

- `workflows/greenfield-api-service.yaml` uses `approver: governance.requirements_freeze.approver`.
- `workflows/brownfield-enhancement.yaml` uses `approver: governance.architecture_sign_off.approver`.
- `workflows/production-release.yaml` uses `approver: governance.production_go_live.approver`.
- `governance/governance.yaml` defines `gates.requirements_freeze.primary_approver`.

Impact: a runner or even a disciplined human interpreter cannot resolve the approval path as written.

Recommendation: standardize gate references as `governance.gates.<gate_name>.primary_approver` or simply `gate: <gate_name>` and let the runner resolve the approver and evidence list from governance.

### 4. Workflow Definitions Are Duplicated And Stale

`greenfield-api-service.yaml` references `sub_workflow: implementation-slice`, but then embeds an older inline `implementation_slice_definition`. That inline version says Wave 2 will add code review, security review, QA, CI/CD, deploy release, and production go-live.

The standalone `workflows/implementation-slice.yaml` already contains code review, security review, CI pipeline, staging deploy, staging verification, rollback, QA, documentation handoff, and slice closeout.

`greenfield-saas.yaml` also embeds its own `implementation_slice_saas_definition` rather than extending the canonical standalone implementation-slice workflow.

Impact: there are multiple definitions of "one slice." Agents and users will not know which one is authoritative.

Recommendation: make `workflows/implementation-slice.yaml` canonical. Convert greenfield API and SaaS workflows to pass profile-specific inputs/overrides into it. If SaaS needs a specialized variant, name it as a first-class workflow file rather than embedding it.

### 5. Brownfield Ownership Is Ambiguous

Brownfield comprehension and impact analysis are assigned differently across the repo:

- `agents/tech-writer.md` says Tech Writer owns `codebase-comprehension` and `impact-analysis` on every brownfield engagement/change.
- `workflows/brownfield-enhancement.yaml` assigns `codebase_comprehension` and `impact_analysis` to `solution-architect`.
- `commands/audit.toml` says Day 1 activates Tech Writer to narrate and Lead Developer to structure.

Impact: three different interpretations exist: Tech Writer owner, Solution Architect owner, and Tech Writer + Lead Developer co-run. This creates handoff ambiguity exactly where brownfield work needs the most discipline.

Recommendation: make Tech Writer the owner of `.repo-intel/` and comprehension artifacts. Make Solution Architect the consumer and architectural interpreter. For impact analysis, either:

- Tech Writer runs the artifact and Solution Architect signs architectural implications, or
- Solution Architect owns impact analysis but Tech Writer owns repo-intel freshness.

Encode the same decision in the agent files, `/audit`, and `brownfield-enhancement.yaml`.

### 6. Reviewer Agents Cannot Write The Artifacts They Are Told To Produce

Several agents have read-only tool grants but are instructed to write files:

- `architecture-challenger` has `tools: Read, Glob, Grep`, but says it writes `.project/working/challenger-report-{date}.md`.
- `code-reviewer` has `tools: Read, Glob, Grep, Bash`, but says it writes `.project/working/review-{pr-id}-{date}.md`.
- `security-reviewer` has `tools: Read, Glob, Grep, Bash`, but says it writes `.project/working/security-review-{pr-id}-{date}.md` and risk acceptance entries.

Impact: if tool grants are enforced, these agents cannot complete their own documented working pattern.

Recommendation: choose one pattern:

- Give reviewer agents `Write` for project artifact paths while still prohibiting code edits, or
- Keep reviewer agents read-only and explicitly say the orchestrator/Delivery Lead persists their returned report.

The first option is simpler. The second option is stricter but must be written into every workflow and command.

### 7. `/slice` Command Is Simpler Than The Canonical Slice Workflow

`commands/slice.toml` dispatches one specialist based on slice domain, then runs Code Reviewer, Security Reviewer, and QA. The canonical `implementation-slice.yaml` uses Delivery Lead, Solution Architect implementation packet, Lead Developer decomposition, parallel implementation branches, CI/CD, staging deploy, staging verification, documentation check, and closeout.

Impact: `/slice` underrepresents the actual workflow. Users invoking the command may skip important orchestration steps that the workflow itself considers mandatory.

Recommendation: rewrite `/slice` as a thin launcher for `workflows/implementation-slice.yaml`. The command should not restate a reduced version of the workflow; it should gather the missing slice selector, confirm prerequisites, then execute the canonical steps.

### 8. Production Release Evidence Pack Is Inconsistent

`commands/release.toml` asks for a 10-item evidence pack with supply-chain attestation always required. `governance/governance.yaml` also lists the 10-item production gate, with Wave 3 baseline plus Wave 4 conditional additions and supply-chain always required.

But `workflows/production-release.yaml` says the deploy-release evidence package is a 7-item checklist and marks some Wave 4 items as skipped. It also notes the full governance evidence is deferred until Wave 4.

Impact: release behavior is unclear: does production require the 10-item governance gate now, or only the Wave 3 subset?

Recommendation: make governance authoritative. Production workflow should assemble `governance.gates.production_go_live.evidence_required`, evaluate conditional rules, and mark each item `required`, `not_applicable`, or `blocked`. Avoid hard-coded competing checklists in command/workflow text.

### 9. Data And ML Activation State Is Contradictory

`implementation-slice.yaml` includes `data-engineer` and `ml-ai-engineer` branches but marks them `deferred_until_wave_5` and `deferred_until_wave_6`.

At the same time:

- `agents/data-engineer.md` and `agents/ml-ai-engineer.md` exist.
- Skills for data and ML are present.
- `commands/slice.toml` says Data and ML/Agentic slices can activate those agents when charter flags are true.
- `greenfield-saas.yaml` says conditional augmentations activate Data Engineer and ML/AI Engineer.

Impact: the platform claims active data/ML delivery while the canonical slice workflow still says those branches are deferred.

Recommendation: replace wave-deferred status with activation predicates:

- `condition: has_data_plane && task_dag.has_data_tasks`
- `condition: (has_ml || has_agentic_ai) && task_dag.has_ml_tasks`

If data/ML are not production-ready yet, move them to an explicit experimental profile instead of mixing active agents with deferred workflow branches.

### 10. Delivery Lead And Lead Developer Need A Harder Boundary

The intended split is good:

- Delivery Lead owns workflow progress, state, gates, memory, and phase movement.
- Lead Developer owns one implementation slice's technical decomposition and specialist coordination.

But both have `Task`, both delegate, and both touch slice state. The distinction is described in agent prose, but not strongly encoded in workflow responsibilities or artifact ownership.

Impact: in practice, one can easily collapse into the other, especially during brownfield or multi-specialist slices.

Recommendation: add an explicit RACI table for slice lifecycle:

- Delivery Lead: opens/closes slice, owns `.project/working/active-workflow.md`, gate status, roadmap status.
- Solution Architect: owns implementation packet and architectural constraints.
- Lead Developer: owns task DAG, specialist assignments, integration validation.
- Specialists: own code changes and tests.
- Reviewers/QA: own gate verdicts.

Then reference that table from both agent files and `implementation-slice.yaml`.

### 11. System Steward Has Broad Edit Tools Despite Governance Constraints

`system-steward.md` correctly says it does not change the library unilaterally and routes changes through `steward_promotion`. It also has `Write, Edit, Bash`.

Impact: not necessarily wrong, but risky for a governance-first platform. The tool grant permits direct edits even though the role text says proposals must be approved first.

Recommendation: split Steward behavior into two modes:

- `proposal_mode`: write reports/diffs/proposed patches only.
- `apply_mode`: edit library files only after `steward_promotion` approval.

This can be encoded in command/workflow text even if tool grants remain broad.

### 12. Workflow Syntax Is Valid YAML But Lacks A Semantic Schema

A Ruby YAML parse check passes for all workflow and governance YAML files. That only proves syntax validity. The workflow language includes custom concepts such as `agent_invocation`, `skill_invocation`, `decision_node`, `parallel`, `gate`, `per_slice`, `from(...)`, `if_exists`, `with_findings_as_input`, and implicit variable bindings.

Impact: no validator catches the current gate-reference mismatch, duplicate subworkflow definitions, unresolved symbols, missing agents/skills, or impossible branches.

Recommendation: add a workflow linter that checks:

- Every `agent` exists in `agents/`.
- Every `skill` exists in `skills/`.
- Every `sub_workflow` exists in `workflows/`.
- Every `gate` exists in `governance.gates`.
- Gate approver/evidence paths match governance schema.
- Every `from(step.output)` references a prior reachable step/output.
- Embedded subworkflow definitions are forbidden unless marked experimental.
- Conditional branches declare skipped-output defaults.

### 13. Commands Mix Prompt Instructions With Operational State Changes

Commands like `/review` and `/factory-record` instruct the agent to write operational records and update active workflow state. This is useful, but the command layer does not define preconditions, required arguments, output paths, idempotency behavior, or whether a command may be run inside an active workflow.

Impact: repeated command runs can create duplicate or conflicting records, especially for `/review`, `/audit`, and `/factory-record`.

Recommendation: add a common command contract:

- `purpose`
- `required_args`
- `preconditions`
- `reads`
- `writes`
- `idempotency_key`
- `may_run_during_active_workflow`
- `success_artifacts`
- `failure_behavior`

Keep the prose prompt, but add this metadata in TOML so tools and humans can reason about command behavior.

## Priority Remediation Plan

1. **Unify inventories.** Generate counts and command lists from disk. Update README, INSTALLATION, PLAYBOOK, plugin manifest, `install.sh`, and `/start`.

2. **Choose command source of truth.** Decide whether root `commands/` or `.claude/commands/` owns command definitions. Generate other surfaces.

3. **Fix gate references.** Replace every `governance.<gate>.approver` reference with the actual `governance.gates.<gate>.primary_approver` model, or move to `gate: <name>` references.

4. **Canonicalize implementation slices.** Remove stale inline slice definitions from parent workflows or mark them as historical examples. Route to standalone workflow files.

5. **Resolve brownfield ownership.** Pick Tech Writer vs Solution Architect ownership for comprehension and impact analysis, then update agents, `/audit`, and brownfield workflow consistently.

6. **Fix reviewer write semantics.** Either grant reviewers `Write` for reports or declare that the orchestrator persists reports. Update all reviewer agents and workflows accordingly.

7. **Add semantic validators.** Start with inventory and workflow/governance checks. This gives the repo a credible "platform" feel and prevents future drift.

8. **Add RACI documentation.** One concise table for phases and one for implementation slice ownership will reduce agent overlap and improve user confidence.

## Suggested Launch Bar

Before positioning this as an end-to-end accelerated development platform, I would require:

- `./scripts/validate-inventory.sh` passes.
- `./scripts/validate-workflows.sh` passes.
- Install dry-runs for Claude, Gemini, Codex, and Antigravity show the same advertised core command set.
- `/start`, README, plugin manifest, and installer agree on counts.
- A sample greenfield walkthrough and brownfield walkthrough produce the expected `.project/` artifact tree.
- At least one golden-path `implementation-slice` trace exists as documentation.

The repository is close in concept. The main improvement is making the orchestration assets behave like productized interfaces instead of hand-maintained prompt files.
