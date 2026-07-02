---
name: praxis-slice
description: Use when running one Praxis implementation slice in Codex; follows implementation-slice.yaml with subagents, review gates, QA, staging, documentation, and closeout.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: [source-grounded-coding, code-review, secure-coding, testing-strategy, cicd-pipeline, deploy-release]
triggers: [praxis slice, implementation slice, build next slice, run slice]
outputs: [slice_status, prs, review_reports, qa_report, documentation_check, episodic_entry]
consumers: [praxis-release, praxis-review]
references: [../../workflows/implementation-slice.yaml]
```
<!-- praxis:metadata:end -->

# Praxis Slice

Run one implementation slice end-to-end.

1. Read `workflows/implementation-slice.yaml`.
2. Read `.project/working/active-workflow.md` and the phased roadmap.
3. Identify the next slice or ask the user for the slice id.
4. Use installed Codex subagents where available: Delivery Lead, Solution Architect, Lead Developer, implementation specialists, Code Reviewer, Security Reviewer, QA Engineer, and Tech Writer.
5. If subagents are not installed, use the matching role markdown under `agents/`.
6. Follow workflow gates exactly and persist artifacts under `.project/`.
7. Do not close the slice until review, security, QA, documentation, and integration checks are complete.

Do not collapse owner and reviewer roles.
