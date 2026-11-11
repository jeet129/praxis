# Claude Code workflow scripts

Dynamic workflow scripts shipped with the Praxis plugin. Claude Code runs them
as `/praxis:<name>`; the plugin manifest points here with its `workflows`
field (the repository's `workflows/` folder holds Praxis lifecycle YAML, which
is a different thing).

| Command | What it does | Input |
|---|---|---|
| `/praxis:pre-merge-review` | Three independent reviews of the branch (correctness, security, tests and standards), then every finding is challenged by another agent before it is reported | optional base branch, default `main` |
| `/praxis:evidence-audit` | Re-runs the verify command of every task marked done in the slice ledgers and reports which still pass | optional slice id |

Both are read-only by instruction: agents are told not to edit files. Use
permission rules if you need that enforced.

Check the scripts offline with `node scripts/validate-claude-workflows.js`. It
confirms the documented contract (meta block first, no timestamps or imports,
phases match) and runs each script against mock agents. It does not run real
agents, so run each workflow once on a small branch before relying on it.
Requires Claude Code v2.1.154 or later with dynamic workflows turned on.
