---
name: praxis-review
description: Use when running an on-demand Praxis review in Codex for contracts, ADRs, roadmaps, or architecture-significant paths outside a normal gate.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [code-review, secure-coding, threat-modeling, api-design, adr-decision-records]
triggers: [praxis review, review artifact, review contracts, review adrs, review roadmap]
outputs: [review_record, findings, remediation_status]
consumers: [praxis-slice, praxis-architect]
references: [../../governance/governance.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Review

Run a closed-loop review of an architecture-significant artifact.

1. Resolve the artifact scope from the user prompt.
2. Read governing context: charter, ADRs, NFR register, contracts, and relevant conventions.
3. Run or simulate the distinct reviewer roles: Architecture Challenger, Code Reviewer, and Security Reviewer.
4. Consolidate findings into BLOCK, FIX, or ACCEPT.
5. Route findings to owning agents for remediation.
6. Re-review changed surfaces until no BLOCK remains.
7. Record status under `.project/operational/reviews/`.

Do not stop at a findings list; close the loop.
