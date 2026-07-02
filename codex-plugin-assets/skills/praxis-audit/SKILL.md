---
name: praxis-audit
description: Use when starting a brownfield Praxis engagement in Codex; performs comprehension, architecture reconciliation, debt audit, and impact analysis.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [codebase-comprehension, architecture-documentation, tech-debt-management, impact-analysis]
triggers: [praxis audit, brownfield audit, codebase audit, existing system]
outputs: [repo_intel, architecture_reconciliation, debt_register, impact_analysis]
consumers: [praxis-discover, praxis-architect, praxis-slice]
references: [../../workflows/brownfield-enhancement.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Audit

Run the brownfield first-pass audit.

1. Read `.project/semantic/project-charter.md` and confirm `mode == brownfield`.
2. Run `codebase-comprehension` and produce `.repo-intel/` artifacts.
3. Reconcile architecture docs and ADRs against actual deployed/code reality.
4. Run `tech-debt-management` and produce `.project/operational/debt-register.md`.
5. Run `impact-analysis` for the proposed enhancement and save under `.project/operational/impact-analyses/`.
6. Recommend whether to proceed to `$praxis-discover`, revise scope, or stop.

Do not let implementation start before `.repo-intel/` exists.
