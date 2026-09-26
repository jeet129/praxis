# Workflow file shape

Canonical structure of a Praxis workflow YAML, extracted from `using-praxis`.

```yaml
name: greenfield-api-service
version: 1
entry_criteria:
  - requirements_brief_exists
  - target_repo_identified
  - mode_known
steps:
  - id: discovery
    type: agent_invocation
    agent: product-manager
    skill: requirements-elicitation
    inputs:
      from: initial_brief
    outputs: [requirements_brief, scope_boundary]
    on_failure: escalate

  - id: nfr_definition
    type: agent_invocation
    agent: product-manager
    skill: nfr-definition
    inputs:
      from: requirements_brief
    outputs: [nfr_register]

  - id: requirements_gate
    type: gate
    name: requirements_freeze
    approver: governance.requirements_freeze.approver

  - id: architecture
    type: parallel
    branches:
      - agent: solution-architect
        skill: architecture-pattern-selection
        outputs: [architecture_decision, c4_diagrams]
      - agent: ml-ai-engineer
        skill: ml-problem-framing
        condition: project.has_ml == true

  - id: challenger_review
    type: agent_invocation
    agent: architecture-challenger
    skill: architecture-pattern-selection
    sub_personas: [scale, security, cost, operations, reliability]
    inputs:
      from: architecture
    outputs: [challenge_report]

  - id: nfr_check
    type: decision_node
    predicate: nfr_satisfied(architecture_decision, nfr_register)
    branches:
      true: [architecture_gate]
      false: [architecture, with_violations_as_input]

  - id: architecture_gate
    type: gate
    name: architecture_sign_off
    approver: governance.architecture_sign_off.approver

  - id: implementation_loop
    type: per_slice
    workflow: implementation-slice
    until: project_phasing.complete == true

exit_criteria:
  - all_phases_complete
  - production_go_live_approved
failure_paths:
  rollback:
    - revert_repo_changes
    - close_slice
    - notify_human
```

