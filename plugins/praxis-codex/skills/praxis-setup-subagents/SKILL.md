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

1. Locate the installed plugin root by walking up from this skill until `codex-agents/` is present (call it `PLUGIN_ROOT`). The target repo is the current working directory (`TARGET`).
2. Create `.codex/agents/` in the target repository if missing.
3. Copy `codex-agents/*.toml` into `TARGET/.codex/agents/`. On a fresh install, don't overwrite existing files unless the user approves. On a **refresh/update, DO overwrite** — old copies carry stale `model` / `model_reasoning_effort` values.
4. **Apply this project's model routing to the installed profiles** so a project-level override takes effect (the whole point of an override — you never hardcode models in the plugin defaults):

   ```bash
   python3 "$PLUGIN_ROOT/scripts/apply-model-routing.py" --project-dir "$TARGET" --codex-out "$TARGET/.codex/agents"
   ```

   This resolves each agent's tier → `model` + `model_reasoning_effort` from `TARGET/.project/governance/model-routing.yaml` when it exists (project override wins), else the plugin default. With the default (`model_map: auto`), no `model` line is written and each subagent inherits the Codex session's model; set concrete model IDs in the project override's `model_map` to pin them. It rewrites only the routing lines in `TARGET/.codex/agents/*.toml` and never touches the plugin's own files.
5. Tell the user to restart Codex or start a new session so the profiles are loaded.

These files are Codex-specific. They do not affect Claude Code.

> Re-run this skill (steps 3-4, overwriting) whenever the plugin updates OR you change `.project/governance/model-routing.yaml` — that is how routing changes reach the subagent profiles.
