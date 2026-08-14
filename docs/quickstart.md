# Quickstart — 5 Minutes to First `/discover`

The fastest path from "I have the `praxis/` directory" to a running session
with a real artifact on disk. Claude Code is the primary path below; short
Codex and Gemini CLI sections follow. For the full install playbook
(troubleshooting, first-30-minutes walkthrough, multi-tool details), see
[`INSTALLATION.md`](../INSTALLATION.md).

## Claude Code (primary path)

### 1. Clone

```bash
git clone https://github.com/jeet129/praxis.git ~/dev/praxis
```

### 2. Load the library

Two ways — pick one:

**Plugin-dir (fastest, no copying):**

```bash
cd ~/dev/your-test-project
~/dev/praxis/try-as-plugin.sh --init .
```

`--init` creates the `.project/` memory tree (17 subdirectories) in your
project; the script then launches `claude --plugin-dir ~/dev/praxis`.
Library edits propagate immediately — no re-install.

**File install (copies the library into your project):**

```bash
cd ~/dev/praxis
./install.sh --tool=claude-code /path/to/your-project
cd /path/to/your-project
claude
```

### 3. Verify

Paste into the session:

```
Confirm you can see the Praxis. List the slash commands in .claude/commands/,
tell me how many SKILLs and agents you can see, and read
.claude/governance/governance.yaml to list the 6 core gates + 11 conditional.
```

Expected: 12 slash commands (`/start /discover /architect /slice /release
/audit /steward /review /refine-idea /factory-record /drive`), 91 SKILLs, 17 agents,
17 gates (6 core + 11 conditional). If any count is off, re-run the install
with `--dry-run` first and compare against what it says it would create.

Alternatively, run `/start` directly — if the delivery-planner interview
begins (mode, data plane, ML, compliance, scale, stack questions), the
library is wired correctly.

### 4. Run `/discover` on a toy idea

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

### 5. What lands in `.project/`

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

### 6. Next steps

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

Open Codex, run `/plugins`, install `praxis-codex`. Then in a session:

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
