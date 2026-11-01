---
name: praxis-release
description: Use when running Praxis production release in Codex; assembles production_go_live evidence, gates approval, deploys, verifies, and records the release.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [deploy-release, cicd-pipeline, observability, reliability-dr, capacity-resource-estimation, supply-chain-security]
triggers: [praxis release, production release, go live, deploy production]
outputs: [production_go_live_pack, deployment_record, verification_report, release_record]
consumers: [praxis-steward]
references: [../../workflows/production-release.yaml, ../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Release

Run the production release workflow.

1. Read `workflows/production-release.yaml` and `governance/governance.yaml`.
2. Ask for the release SHA or use the stated candidate commit.
3. Assemble the `production_go_live` evidence pack from governance.
4. Evaluate conditional evidence rules and mark each item `required`, `not_applicable`, or `blocked`.
5. Stop for user approval before production deployment.
6. On approval, execute deployment, post-deploy verification, rollback if needed, and release record creation.

Do not use a reduced evidence checklist when governance requires more.
