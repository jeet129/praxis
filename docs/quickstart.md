# Quickstart — 5 Minutes to First `/discover`

The fastest path from nothing to a running Praxis session with a real
artifact on disk. Claude Code is the primary path below; short
Codex and Gemini CLI sections follow. For the full install playbook
(troubleshooting, first-30-minutes walkthrough, multi-tool details), see
[`INSTALLATION.md`](../INSTALLATION.md).

## Claude Code (primary path)

### 1. Install the plugin

**Plugin marketplace (recommended — no clone needed):**

```text
/plugin marketplace add jeet129/praxis
/plugin install praxis@praxis
```

`praxis@praxis` is `<plugin-name>@<marketplace-name>` (both are `praxis`). That
is the whole install — all 12 slash commands, 17 agents, 91 SKILLs, 9 workflows,
and the SessionStart hook are now installed. **Restart Claude Code — start a new
session — so they load.** `/reload-plugins` can pick up changes mid-session, but a
fresh session is the reliable way to activate a newly installed plugin. Nothing is
copied into your project. Updates arrive by re-running `/plugin`. Append `@<branch>` to the marketplace-add
line to pin a branch.

Prefer to work from a local checkout? Two clone-based options:

**Plugin-dir (fastest for an in-progress tree, no copying):**

```bash
git clone https://github.com/jeet129/praxis.git ~/dev/praxis
cd ~/dev/your-test-project
~/dev/praxis/try-as-plugin.sh --init .
```

`--init` creates the `.project/` memory tree (17 subdirectories) in your
project; the script then launches `claude --plugin-dir ~/dev/praxis`. Library
edits propagate immediately — no re-install.

**File install (copies the library into your project):**

```bash
git clone https://github.com/jeet129/praxis.git ~/dev/praxis
cd ~/dev/praxis
./install.sh --tool=claude-code /path/to/your-project
cd /path/to/your-project
claude
```

### 2. Verify

Paste into the session:

```
Confirm you can see Praxis. List the Praxis slash commands available,
tell me how many SKILLs and agents you can see, and read the governance
config (governance.yaml) to list the 6 core gates + 12 conditional.
```

Expected: 12 slash commands (`/start /discover /architect /slice /release
/audit /steward /review /refine-idea /factory-record /drive`), 91 SKILLs, 17 agents,
18 gates (6 core + 12 conditional). If any count is off: for a plugin install
run `/plugin` and confirm `praxis` shows installed and enabled; for the copy
install re-run it with `--dry-run` and compare against what it would create.

Alternatively, run `/start` directly — if the delivery-planner interview
begins (mode, data plane, ML, compliance, scale, stack questions), the
library is wired correctly.

### 3. Run `/discover` on a toy idea

```
/start
```

Answer the bootstrap questions. For a fast test: "Node-TS API / AWS /
greenfield / no ML / no agentic AI / no compliance regimes / not
multi-tenant / 1000 qps / 99.9% availability." This writes
`.project/semantic/project-charter.md`.

Then:

```
/discover
```

This activates the Product Manager persona and runs `product-discovery` →
`requirements-elicitation` → `requirements-interrogation` → `nfr-definition`.
When it hits `requirements-interrogation`, expect the agent to STOP and
produce a KUACQ block (Knowns / Unknowns / Assumptions / Conflicts /
Questions) — answer it, don't let the agent guess past it.

### 4. What lands in `.project/`

After the run:

```bash
cat .project/semantic/project-charter.md        # your bootstrap answers
ls .project/working/                             # in-flight discovery artifacts
```

Expect a requirements brief, user stories with acceptance criteria, a scope
boundary, an NFR register, and an assumptions/open-questions log — assembled
toward the `requirements_freeze` gate evidence pack. When that (or any) gate
closes, delivery-lead writes a checkpoint record to
`.project/episodic/checkpoint-*.md` — the primary telemetry source, mined by
`scripts/factory-usage-report.py`. Telemetry hooks are also wired by default
(`hooks/tap.sh`), writing deterministic JSONL streams under
`.project/telemetry/`. See [`telemetry.md`](telemetry.md) for what those mean.

### 5. Next steps

- Approve or push back on the `requirements_freeze` gate evidence, then
  `/architect` → `/slice` (repeat per slice) → `/release`.
- For an existing codebase, run `/audit` before `/discover`.
- Read [`PLAYBOOK.md`](../PLAYBOOK.md) for the full operating guide —
  greenfield + brownfield walkthroughs, prompt library, cadences.
- Read [`docs/model-routing.md`](model-routing.md) and
  [`docs/telemetry.md`](telemetry.md) once you're running real sessions and
  want to understand cost/tier behavior and what's being measured.

## Codex

```bash
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
```

Open Codex, run `/plugins`, install `praxis-codex`, then **restart Codex (start a
new session)** so its command skills and subagents load. Then in a session:

```text
$praxis-setup-subagents
$praxis-start
```

`$praxis-start` runs the same delivery-planner bootstrap interview as
Claude Code's `/start`. Follow with `$praxis-discover`. Full detail:
[`docs/codex-setup.md`](codex-setup.md).

## Gemini CLI

```bash
./install.sh --tool=gemini /path/to/your-project
cd /path/to/your-project
gemini
```

Gemini CLI reads the routing file at `GEMINI.md` (repo root) and the library
at `.gemini/`. Slash commands mirror Claude Code's set:
`/start /discover /architect /audit /slice /release /review /steward
/refine-idea /factory-record /drive`. Verify with:

```
Read GEMINI.md and confirm you can navigate to .gemini/skills/ and
.gemini/agents/. List the 17 agents and 91 SKILLs.
```

Full detail: [`docs/gemini-cli-setup.md`](gemini-cli-setup.md).

## Let it run

Once your first slice has run cleanly interactively — you've watched `/slice`
go through implementation, code review, security review, and QA by hand at
least once — set `stop_after` in `governance/autonomy.yaml` (`task` is the
safest starting point) and use `/drive` to let the loop run several tasks
between check-ins instead of re-prompting for each one. Start supervised, in
a sandboxed environment, with everything committed before the run. Full
guide: [`docs/autonomous-drive.md`](autonomous-drive.md).
