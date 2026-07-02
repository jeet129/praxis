# Plugin Build And Distribution

This document is for maintainers publishing Praxis through plugin systems.
For end-user setup, see `docs/claude-code-setup.md` and `docs/codex-setup.md`.

## Source Layout

Praxis keeps the shared development platform content at the repository root:

```text
skills/
agents/
workflows/
governance/
references/
patterns/
scripts/
commands/
```

Tool-specific plugin assets live beside the shared source. Do not duplicate the
root skill library unless a target plugin system requires a self-contained
generated package.

```text
.claude-plugin/          Claude Code plugin and marketplace manifests
.agents/plugins/         Codex repo marketplace manifest
codex-plugin-assets/     Codex-only command skills and subagent profiles
plugins/praxis-codex/    Generated Codex installable plugin package
```

## Claude Code Plugin

Claude Code uses the root repository directly as the plugin package.

Important files:

```text
.claude-plugin/plugin.json
.claude-plugin/marketplace.json
commands/
.claude/commands/
skills/
agents/
workflows/
governance/
references/
patterns/
```

There is no generated Claude package today. The root plugin manifest points to
the canonical root folders, so changes to root skills, agents, commands, and
workflows are immediately part of the Claude Code plugin.

Validate before publishing:

```bash
bash scripts/validate-skills.sh .
bash scripts/validate-manifests.sh
```

Note: `scripts/validate-manifests.sh` currently enforces stricter fields than
the official Claude Code plugin schema for `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`. If it reports only missing optional
`version` or marketplace top-level `description`, treat that as validator drift
until the script is updated.

Local smoke test:

```bash
./try-as-plugin.sh --init /path/to/test-project
```

Marketplace distribution, once published, should use Claude Code's marketplace
commands documented in `docs/claude-code-setup.md`.

## Codex Plugin

Codex installs a self-contained plugin package from:

```text
plugins/praxis-codex/
```

Do not point users at `codex-plugin-assets/`. That directory is only the
Codex-specific source overlay.

The build combines:

```text
root shared content
+ codex-plugin-assets/
= plugins/praxis-codex/
```

Build and validate:

```bash
bash scripts/build-codex-plugin.sh
bash scripts/validate-codex-plugin.sh
```

### Automating build with the pre-commit hook

Rather than running the build manually before every commit, activate the repo-tracked pre-commit hook:

```bash
scripts/install-git-hooks.sh   # one-time per clone
```

This points `core.hooksPath` at `.githooks/`, where `pre-commit` runs `build-codex-plugin.sh` + `validate-codex-plugin.sh` and auto-stages the regenerated `plugins/praxis-codex/` so the source change and the built package land in one atomic commit. See CONTRIBUTING.md for details + escape hatches (`git commit --no-verify`).

The generated package must contain:

```text
plugins/praxis-codex/.codex-plugin/plugin.json
plugins/praxis-codex/skills/
plugins/praxis-codex/codex-agents/
plugins/praxis-codex/agents/
plugins/praxis-codex/workflows/
plugins/praxis-codex/governance/
plugins/praxis-codex/references/
plugins/praxis-codex/patterns/
plugins/praxis-codex/scripts/
```

The Codex marketplace file must point to the generated package:

```text
.agents/plugins/marketplace.json
```

Expected entry shape:

```json
{
  "name": "praxis",
  "plugins": [
    {
      "name": "praxis-codex",
      "source": {
        "source": "local",
        "path": "./plugins/praxis-codex"
      }
    }
  ]
}
```

GitHub install command:

```bash
codex plugin marketplace add jeet129/praxis \
  --sparse .agents/plugins \
  --sparse plugins/praxis-codex
```

Then install from Codex:

```text
/plugins
```

Select `praxis-codex`, start a new thread, then run:

```text
$praxis-setup-subagents
$praxis-start
```

Release rule: commit `plugins/praxis-codex/` along with `.agents/plugins/`.
Committing only `codex-plugin-assets/` is not enough for GitHub marketplace
installation. The pre-commit hook (above) enforces this — commits touching
canonical source or `codex-plugin-assets/` auto-stage the regenerated
`plugins/praxis-codex/`, so drift becomes impossible when the hook is active.

## Future Plugin Targets

Use this pattern for additional plugin systems:

1. Keep shared platform content canonical at the repo root.
2. Add target-specific source under a clearly named asset folder, for example
   `toolname-plugin-assets/`.
3. Generate a self-contained package under `plugins/toolname/` when the target
   installer cannot reference root content directly.
4. Add a target-specific validator script under `scripts/`.
5. Document install and build steps under `docs/`.
6. Avoid changing Claude Code plugin paths unless the Claude plugin itself is
   being intentionally updated.

Before publishing any plugin target, verify:

```text
manifest parses
plugin package is self-contained if installed remotely
skills have valid SKILL.md frontmatter
commands or wrapper skills route to canonical workflows
agent/subagent files are included in the installed package
install docs point to the installable artifact, not the source overlay
```
