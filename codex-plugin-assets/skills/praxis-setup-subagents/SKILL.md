---
name: praxis-setup-subagents
description: Use when installing Praxis Codex subagent profiles into a target repo so Codex can spawn role-specific agents.
---

<!-- praxis:metadata:begin -->
```yaml
capability: command
domain: codex-plugin
state: active
dependencies: []
triggers: [praxis setup subagents, install subagents, codex agents, setup codex agents]
outputs: [codex_agent_profiles]
consumers: [praxis-slice, praxis-review, praxis-architect]
references: [../../codex-agents]
```
<!-- praxis:metadata:end -->

# Praxis Setup Subagents

Install Praxis Codex subagent profiles into the current repository.

1. Locate the installed plugin root by walking up from this skill until `codex-agents/` is present.
2. Create `.codex/agents/` in the target repository if missing.
3. Copy `codex-agents/*.toml` into `.codex/agents/`.
4. Do not overwrite existing files unless the user explicitly approves.
5. Tell the user to restart Codex or start a new session so the profiles are loaded.

These files are Codex-specific. They do not affect Claude Code.
