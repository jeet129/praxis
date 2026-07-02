# Installation Playbook

Step-by-step from "I have the `praxis/` directory" to "I'm running my first real session with the platform active." Plus honest accounting of what's NOT automated.

This document is the install-focused companion to `PLAYBOOK.md` (the operating guide). Read this before your first install; read `PLAYBOOK.md` before your first session.

Maintainers publishing plugin packages should also read `docs/plugin-builds.md`.

---

## 0. What's NOT automated (read this first)

Before installing, calibrate expectations. The library ships with:

✅ **83 SKILLs** that an AI agent reads and follows, each with anti-rationalization + verification.
✅ **16 role agents** the AI can adopt, each with a `model:` default (7 Opus / 9 Sonnet).
✅ **5 workflows** orchestrating multi-step delivery.
✅ **8 slash commands** that map intent to skill sequences (including `/factory-record` for rich telemetry observations).
✅ **6 hook subscriptions** (SessionStart, SessionEnd, PostToolUse, UserPromptSubmit, SubagentStart, SubagentStop) driving a universal artifact tap.
✅ **Adaptive model routing** (`adaptive-model-routing` SKILL + per-agent frontmatter) — routes each specialist to Opus or Sonnet (or in Codex, high/medium reasoning-effort) based on task complexity.
✅ **Telemetry capture pipeline** — every SKILL / agent / workflow / command invocation logs to `.project/operational/factory-metrics/` via `scripts/factory-record.sh`. ~97% capture rate on Claude Code.
✅ **Coverage gate** — `scripts/factory-aging.sh` flags experimental SKILLs with stale/missing telemetry.
✅ **Frequency reporter** — `scripts/factory-frequency.sh` aggregates usage per SKILL / period.
✅ **Governance gates** with evidence packs.
✅ **Project memory taxonomy** (six types).
✅ **Skill validator script.**
✅ **Pre-commit hook** that auto-rebuilds the Codex plugin package (`plugins/praxis-codex/`) whenever canonical source changes.

The library does NOT ship with:

❌ **Automatic Steward synthesis.** The Steward agent still reads the metric files manually at quarterly review; the aggregation → proposals step is not automated yet (though `factory-frequency.sh` produces the raw aggregates it consumes).
❌ **Automatic change application.** Approved SKILL changes still require you to edit the file.
❌ **CI/CD hooks for the library itself.** No pipeline auto-validates new SKILLs against the registry (roadmap item).
❌ **Guaranteed 100% telemetry capture.** The residual ~3% (SKILL uses that don't involve reading the SKILL.md OR producing an observable output OR spawning a sub-agent) is invisible; `factory-aging.sh` catches it via aging thresholds instead.

The "quarterly steward cadence" is real DISCIPLINE you run — but now with real telemetry it reads, not hypothetical observations. The factory-evaluation review is still human-driven; the *data* under it is captured automatically.

**Bottom line: the library is a structured discipline with high-quality content + tooling for routing + tooling for measurement. It's not an autopilot, but the measurement loop is closed. When you read PLAYBOOK.md and it says "quarterly evaluation runs," the Steward now has real per-SKILL usage data to read.**

---

## 1. Pre-install checklist

### 1.1 System requirements

- **macOS or Linux.** Bash 4+, standard Unix tools. Tested on macOS.
- **AI coding tool** — at least one of: Claude Code (recommended), Codex, Cursor, Gemini CLI, OpenCode, GitHub Copilot, Kiro, Antigravity.
- **Python 3.8+** — only required if you want to run the YAML validator manually. Otherwise optional.
- **Git** — for managing the projects you'll be working on.

### 1.2 Decide your install location

The library lives in a directory you can copy from. Recommended:

```bash
# Put the library somewhere stable on your machine
mkdir -p ~/dev/tooling
mv /path/where/you/got/praxis ~/dev/tooling/
# Final location:
ls ~/dev/tooling/praxis
```

DO NOT install from the Cowork session outputs folder (it gets cleaned). Move it to a stable location first.

### 1.3 Decide your install target

Per-project (recommended for first test):
- `~/dev/my-test-project/.claude/` — Claude Code reads this automatically.
- Easy to inspect; easy to throw away if something goes wrong.
- Memory tree `.project/` lives next to it.

User-global (after you're confident):
- `~/.claude/` — available to every project you open in Claude Code.
- Memory tree is still per-project.

For your first install, **use per-project**.

### 1.4 Decide your tool

| Tool | Choose if |
|---|---|
| **Claude Code** | Default. Best UX for the platform (slash commands + hook + plugin manifests). |
| **Codex** | You prefer Codex's plugin marketplace, skills, and subagent profiles. |
| **Cursor / Gemini / OpenCode / Copilot / Kiro / Antigravity** | Per-tool docs in `docs/<tool>-setup.md`. |

For your first install, **use Claude Code**.

---

## 2. Install — step by step

### 2.1 Verify the library is where you expect

```bash
cd ~/dev/tooling/praxis
ls README.md PLAYBOOK.md INSTALLATION.md install.sh uninstall.sh
ls skills/ | head -5
ls agents/
```

Expected:
- README.md, PLAYBOOK.md (this file too), install.sh, uninstall.sh are present
- `skills/` has 84 subdirectories (83 active + 1 tombstone)
- `agents/` has 16 .md files

If anything is missing, re-download or restore.

### 2.2 Pick a test project

For a real test, use an existing repo. If you don't have one handy:

```bash
mkdir -p ~/dev/test-aidp
cd ~/dev/test-aidp
git init
echo "# Test Project" > README.md
git add . && git commit -m "init"
```

### 2.3 Dry-run the install (always do this first)

```bash
cd ~/dev/tooling/praxis
./install.sh --dry-run ~/dev/test-aidp
```

Expected output:
```
==> Installing Claude Code layout → /home/you/dev/test-aidp/.claude
  [dry-run] would create /home/you/dev/test-aidp/.claude
  [dry-run] would copy agents/ (16 files)
  [dry-run] would copy skills/ (83 active; skipped 1 tombstones)
  [dry-run] would copy workflows/ (5 files)
  ...
==> Creating project memory tree → /home/you/dev/test-aidp/.project
  [dry-run] would create /home/you/dev/test-aidp/.project (17 subdirs)
```

If the dry-run looks wrong (target path wrong, missing items, etc.) — fix before running for real.

### 2.4 Run the install

```bash
./install.sh ~/dev/test-aidp
```

Expected output ends with:
```
==> Done.

Next steps:

1. Open the project in your tool:
   • Claude Code:  cd /home/you/dev/test-aidp && claude

2. Sanity check (paste into the assistant):
   "Confirm you can see the Praxis..."
```

### 2.5 Verify the install

Three checks:

**Check 1 — Files landed correctly:**
```bash
cd ~/dev/test-aidp
ls -la .claude/
# Expected: agents/ skills/ workflows/ governance/ patterns/ references/
#           hooks/ scripts/ commands/ .claude-plugin/ README.md PLAYBOOK.md

find .claude/skills -name SKILL.md | wc -l
# Expected: 83

find .claude/agents -name '*.md' | wc -l
# Expected: 16

find .claude/workflows -name '*.yaml' | wc -l
# Expected: 5

ls .claude/commands/
# Expected: 8 .md files (start, discover, architect, slice, release, audit, steward, factory-record)

find .project -type d | wc -l
# Expected: 18 (the root + 17 subdirs)
```

**Check 2 — Validator passes:**
```bash
bash .claude/scripts/validate-skills.sh ~/dev/test-aidp/.claude
# Expected: "✓ Library health: 83 active skills in target 70-90 band."
# Failures = 0
```

**Check 3 — SessionStart hook runs:**
```bash
CLAUDE_PROJECT_DIR=~/dev/test-aidp bash .claude/hooks/session-start.sh 2>&1 | head -20
# Expected: a banner with "Praxis — session start"
# It will warn "No project charter found" — that's correct; we haven't bootstrapped yet.
```

If all three checks pass, the install is good.

### 2.6 Open the project in Claude Code

```bash
cd ~/dev/test-aidp
claude
```

You should see the SessionStart hook output in the session prelude.

### 2.6.5 Alternative — load as plugin instead of copying files

The library is structured as a Claude Code plugin (`.claude-plugin/plugin.json` + `commands/` + `hooks/` + `agents/` + `skills/` all at the right paths). You can load it as a plugin WITHOUT running install.sh — Claude Code reads the directory directly.

**Use this path if you want to:**
- Test the library without copying anything into your project (faster iteration).
- See library updates immediately (no re-install needed).
- Keep your project repo clean (no `.claude/` directory added).

```bash
# One-command launcher (handles memory tree + plugin loading)
~/dev/tooling/praxis/try-as-plugin.sh --init ~/dev/test-aidp

# Or manually:
cd ~/dev/test-aidp
claude --plugin-dir ~/dev/tooling/praxis
```

The bundled `try-as-plugin.sh` script:
1. Validates the library root + `claude` CLI presence.
2. With `--init`, creates the `.project/` memory tree (17 directories) in your target.
3. `cd`s into the target and runs `claude --plugin-dir <library>`.

Flags: `--dry-run` (preview), `--init` (create `.project/` memory tree first), `--help`.

**What you get with plugin-dir loading:**
- All 83 SKILLs available.
- All 16 agents available.
- All 8 slash commands available (`/start`, `/discover`, etc.).
- SessionStart hook fires.
- Governance gates accessible.

**Differences from install.sh:**
- No `.claude/` directory created in your project.
- Library changes (edits to SKILL.md files) propagate immediately — no re-install.
- To switch off, just don't pass `--plugin-dir` next time. Nothing to uninstall.
- `.project/` memory tree IS still created in your project (passed with `--init`).

**When to use install.sh instead:**
- Multi-tool install (Codex / Cursor / etc.) — those don't read `--plugin-dir`.
- Frozen-version distribution to teammates (install.sh creates a snapshot).
- CI / automation that doesn't run interactive `claude`.

### 2.7 First sanity-check prompt

Paste this into Claude Code:

```
Confirm you can see the Praxis. Specifically:

1. List the slash commands available in .claude/commands/.
2. Read .claude/skills/using-praxis/SKILL.md and summarize the
   intent → workflow routing.
3. Read .claude/governance/governance.yaml and list the 7 active gates +
   4 conditional gates.
4. Tell me how many SKILLs and agents you can see.

Expected: 8 slash commands, 83 SKILLs, 16 agents, governance gates as listed.
If anything differs, report.
```

Expected response from Claude: lists 8 slash commands, the workflow routing tree, 7+4 gates, 83 SKILLs, 16 agents.

If the response is incomplete or wrong, the install is partial — check Section 4 (Troubleshooting).

---

## 3. Bootstrap your first project

The first real use. We'll bootstrap project state, then do one small thing.

### 3.1 Run `/start`

In Claude Code, type:

```
/start
```

This invokes the bootstrap slash command. The agent will:
1. Run `delivery-planner` to interview you about the project's characteristics.
2. Write the project charter to `.project/semantic/project-charter.md`.
3. Establish the architecture-doc skeleton.
4. Tell you which governance gates apply.

You'll be asked questions like:
- Mode: greenfield (new project) or brownfield (existing codebase)?
- Has data plane (non-trivial data work)? Yes/no.
- Has ML? Yes/no.
- Has agentic AI (LLM features)? Yes/no.
- Compliance regimes? (SOC 2, GDPR, HIPAA, PCI-DSS, etc., or none.)
- Scale target (QPS)?
- Availability target (99.9%, 99.95%, etc.)?
- Multi-tenant? Yes/no.
- Preferred stack? (Node-TS / Java-Spring / Python / etc.)
- Cloud? (AWS / Azure / GCP / Kubernetes-agnostic.)

Answer based on the test project. For a quick test, you can say "Node-TS / AWS-agnostic-on-k8s / 1000 qps / 99.9% / greenfield / no ML / no agentic / no compliance / not multi-tenant."

### 3.2 Verify the charter was written

```bash
cat .project/semantic/project-charter.md
```

Expected: a YAML-ish or Markdown file with your answers reflected.

### 3.3 Re-run the SessionStart hook (manual test)

Open a new terminal session in the project:

```bash
cd ~/dev/test-aidp
CLAUDE_PROJECT_DIR=$(pwd) bash .claude/hooks/session-start.sh 2>&1 | head -25
```

Expected: the hook now reads your charter and surfaces the flags. No "no charter" warning.

### 3.4 First slice (greenfield path)

In Claude Code:

```
/discover
```

The agent will activate the Product Manager persona and run through the discovery + requirements skills. Walk through it.

When the agent hits `requirements-interrogation`, it should produce a KUACQ block (Knowns / Unknowns / Assumptions / Conflicts / Questions) and STOP for your input.

That's the discipline working. Answer the questions, the agent proceeds, eventually it'll prep the `requirements_freeze` gate evidence pack.

You're testing.

---

## 4. Troubleshooting

### Problem: SessionStart hook doesn't fire automatically

The hook is configured at `.claude/hooks/hooks.json`. Claude Code reads this on session start.

**Diagnosis:**
```bash
cat .claude/hooks/hooks.json
# Should reference SessionStart event + session-start.sh script
```

**Fixes:**
1. Verify Claude Code version supports SessionStart hooks (recent versions do).
2. Run the hook manually to verify the script itself works (see §2.5 Check 3).
3. If the hook works manually but doesn't fire automatically, Claude Code's hook discovery may need the hook at `~/.claude/hooks/` for user-level, or the project must be configured to recognize project-local hooks.

If you can't get auto-firing to work, you can still paste the hook output manually at session start — the agent operates correctly either way.

### Problem: Slash commands not recognized

Claude Code reads commands from `.claude/commands/*.toml`.

**Diagnosis:**
```bash
ls .claude/commands/
# Should show: start.toml architect.toml audit.toml discover.toml release.toml slice.toml steward.toml
```

**Fixes:**
1. Verify Claude Code version supports project-level slash commands.
2. Try invoking as `/start` (must start with `/`).
3. If still not recognized, the prompt content is in the TOML file — read it and paste manually as a workaround.

### Problem: Validator script fails

```bash
bash .claude/scripts/validate-skills.sh ~/dev/test-aidp/.claude
# If "Failed: N>0"
```

This shouldn't happen on a fresh install. If it does:
1. Check which SKILL failed (the validator names it).
2. Read that SKILL's frontmatter — it likely has malformed YAML.
3. Re-copy the library from the source location.

### Problem: Permission denied on scripts

```bash
chmod +x .claude/scripts/validate-skills.sh
chmod +x .claude/hooks/session-start.sh
```

### Problem: Files weren't copied (no `.claude/` directory after install)

The install.sh may have hit an error mid-way. Look at the output for the actual failure. Common causes:
- Target directory doesn't exist (`/path/to/test-aidp` not created)
- Target was a file, not a directory
- Permissions

Re-run with `--dry-run` first to see what would happen.

### Problem: Agent can see the library but invokes the wrong SKILLs

This is normal for the first few sessions while you and the agent are calibrating. The slash commands route deterministically; free-form prompts route via the front-door SKILL.

If the agent persistently picks wrong SKILLs:
1. Ensure the agent has READ `.claude/skills/using-praxis/SKILL.md` first.
2. If not, paste: *"Read .claude/skills/using-praxis/SKILL.md before doing anything else. That's the front-door routing logic for this library."*

### Problem: Install hit the dotfile guard

If you're installing from inside a Cowork session and get "blocked location" errors on `.claude/` paths, you're hitting a session sandbox. Move the library to a regular directory on your machine and install from there.

### Problem: I want to undo the install

```bash
cd ~/dev/tooling/praxis
./uninstall.sh ~/dev/test-aidp
```

This removes `.claude/` and `.team/` and `AGENTS.md`. By default it preserves `.project/` (your project memory). Add `--purge-memory` to wipe `.project/` too.

---

## 5. First-test recommendations

For your first real session, pick ONE of these paths:

### Path A — Greenfield slice (recommended for first test)

A small new feature. Walks through the most polished workflow.

1. `/start` — bootstrap charter.
2. `/discover` — Phase A (PM + requirements).
3. Stop at `requirements_freeze` gate; review the evidence pack.
4. Either approve and continue with `/architect`, or stop here and assess.

Time: 30-60 minutes for a small feature.

What to look for:
- Did the agent ask the right discovery questions?
- Did the KUACQ block surface real unknowns?
- Did NFRs come out measurable?
- Did the gate evidence pack feel substantive or perfunctory?

### Path B — Brownfield audit on a real repo

Pick a repo you actually own. Run the brownfield first-week sequence.

1. `/start` — bootstrap with `mode: B` (brownfield).
2. `/audit` — runs codebase-comprehension + arch reconciliation + debt audit + impact analysis.

Time: 1-2 hours for a small repo; longer for substantial.

What to look for:
- Did codebase-comprehension produce a useful system map?
- Did the debt register actually surface real debt items?
- Was the architecture reconciliation grounded in the deployed reality?

### Path C — Specific SKILL test

If you want to test a specific discipline, invoke it directly. For example:

```
Apply the threat-modeling SKILL to this design: [paste design]. Use STRIDE.
Output trust boundaries, threats per category, and mitigations.
Save to .project/operational/threat-model-<feature>.md.
```

The agent reads `.claude/skills/threat-modeling/SKILL.md` and follows its process.

Time: 30 minutes.

What to look for:
- Did the agent actually follow the SKILL's process (not freelance)?
- Did the verification checklist get applied?
- Did the common-rationalizations table get acknowledged?

---

## 6. Multi-tool / multi-machine considerations

### Installing for a different tool

Same library; different addressing:

```bash
codex plugin marketplace add jeet129/praxis --sparse .agents/plugins --sparse plugins/praxis-codex
./install.sh --tool=cursor ~/dev/test-aidp
./install.sh --tool=gemini ~/dev/test-aidp
./install.sh --tool=copilot ~/dev/test-aidp
./install.sh --tool=opencode ~/dev/test-aidp
./install.sh --tool=kiro ~/dev/test-aidp
./install.sh --tool=antigravity ~/dev/test-aidp
./install.sh --tool=all ~/dev/test-aidp     # every layout side-by-side
```

Per-tool setup notes: `docs/<tool>-setup.md`.

### Installing on a new machine

The library is just files. Either:
1. `rsync -av praxis/ user@host:~/dev/tooling/`, OR
2. Put it in a git repo + clone on the new machine.

After move/clone, run install.sh as usual.

### Sharing with a team

Two paths:

1. **Each developer installs locally.** Works; everyone has their own copy.
2. **Publish as a Claude Code marketplace plugin.** The `.claude-plugin/marketplace.json` is pre-configured; you'd substitute the github source and push. Then teammates can `/plugin marketplace add <your-org>/praxis`. See `docs/claude-code-setup.md`.

### Updating to a new library version

When the library evolves (you or System Steward propose changes):

```bash
# Pull updates to your library copy
cd ~/dev/tooling/praxis
git pull   # if you've put it in git

# Re-install to existing projects with --force
cd ~/dev/tooling/praxis
./install.sh --force ~/dev/test-aidp
```

`--force` overwrites `.claude/` with the new version. Your `.project/` memory is preserved (it's not touched).

---

## 7. What about the "self-evolving" claim

To do real telemetry-driven evolution, you'd need:

1. **Telemetry collector.** A small daemon or shell script that watches your session and logs:
   - Each SKILL the agent reads (file-read events).
   - Each agent persona invoked.
   - Each gate event.
   - Each workflow step.
   - Outcomes (slice closed, release shipped, etc.).
   - Output: append-only JSONL log somewhere on disk.

2. **Metric computation script.** Periodically (cron / launchd / GitHub Actions) reads the logs and produces the factory-evaluation report:
   - Skill invocation counts.
   - Agent activity.
   - Workflow completion rates.
   - Gate evidence-completeness-on-first-submission.
   - Output: `.project/operational/factory-metrics/<quarter>.md`.

3. **Steward-as-real-input.** Then when you invoke `/steward`, the agent has actual data to consume. Currently it relies on your recollection.

This is a ~1-2 week build that you should do once you're running 2-3 projects with the platform and care about library health. Skip it for the first few projects; treat the Steward as a quarterly review companion that helps you think through "what didn't fire much this quarter? what should I remove?"

If you decide to build the telemetry layer:
- Output format: one event per line, JSONL, with timestamp + project_id + event_type + payload.
- Storage: `.project/operational/telemetry/<date>.jsonl` (the project-memory taxonomy already has the right folder).
- Aggregator: a Python script reading the JSONL + producing the factory-report markdown.
- Schedule: cron quarterly; faster if you want.

Or honestly, just do the quarterly review by reading `factory-evaluation` SKILL and answering its questions from your own observations. It's still structured discipline; just not measured.

---

## 8. Daily / weekly / quarterly cadence reminder

After install + first project, the operating rhythm:

| Cadence | What you do | What invokes it |
|---|---|---|
| **Per slice** (2-5 days) | Run `/slice`. Apply review gates. | Manual via slash command. |
| **Per release** | Run `/release`. Assemble evidence pack. Gate fires. | Manual via slash command. |
| **Monthly** | Architecture-doc reconciliation. Runbook freshness. | Manual; the SKILL describes the procedure. |
| **Quarterly** | Run `/steward`. Review what fired / didn't. Tune trigger phrases. | Manual; SessionStart hook will warn if overdue (> 90 days). |

The SessionStart hook is your operational reminder system. It surfaces:
- Charter (so the agent doesn't re-discover it).
- Library counts.
- Recent ADRs.
- Open debt items.
- Quarterly steward overdue (>90 days) ⚠️ warning.

That's all the automation. The discipline is yours.

---

## 9. After your first successful test

If your first test session went well:

1. **Note what worked.** Which SKILLs felt sharp? Which were over-engineered?
2. **Note what didn't.** Where did the agent invoke the wrong SKILL? Where did the rationalization tables fail to land?
3. **Add findings to your own quarterly review notes** (`.project/operational/factory-metrics/<quarter>.md` — create the file).
4. **Plan project #2.** Different domain, different stack — see if the same library serves both.

If something fundamental broke:
1. **Don't blame the library first.** Check install (Section 4).
2. **Find which SKILL was at fault.** Read it; assess if it's wrong or if the agent misapplied it.
3. **If the SKILL is genuinely wrong**, edit it directly OR open a steward proposal.

Welcome to maintaining the library. That's the work.

---

## 10. Appendix — what each artifact does

For quick reference when you're looking at the installed `.claude/` tree:

| Artifact | What it does | When you'd touch it |
|---|---|---|
| `.claude/agents/*.md` | Role-agent definitions. | Customize an agent's working style. |
| `.claude/skills/*/SKILL.md` | The 83 disciplines. | Add domain-specific anti-rationalizations from your project's experience. |
| `.claude/workflows/*.yaml` | Multi-step orchestrations. | Customize phase ordering or add a new workflow for a recurring pattern. |
| `.claude/governance/governance.yaml` | Gate definitions + approver matrix. | Customize gate evidence requirements or approver routing. |
| `.claude/commands/*.toml` | Slash commands. | Add a slash command for a recurring activity. |
| `.claude/hooks/session-start.sh` | The SessionStart hook. | Add additional context surfacing. |
| `.claude/scripts/validate-skills.sh` | Skill validator. | Extend with project-specific frontmatter checks. |
| `.claude/references/*.md` | Cross-cutting references. | Add a checklist that multiple SKILLs reference. |
| `.claude/patterns/` | Reusable solution shapes. | (Currently empty; add as patterns emerge.) |
| `.claude/.claude-plugin/*.json` | Plugin manifests for marketplace install. | Update when publishing a new version. |
| `.claude/README.md` | Library overview. | Reading reference. |
| `.claude/PLAYBOOK.md` | Operating guide. | Reading reference. |
| `.project/semantic/` | What you know (charter, NFRs, glossary). | Write when discovery / arch decisions land. |
| `.project/episodic/` | What happened (retros, incidents). | Write after incidents + retros. |
| `.project/procedural/` | How you do things (policies). | Write when codifying a procedure. |
| `.project/decision/` | ADRs (immutable). | Write per architectural decision. |
| `.project/operational/` | What's live (runbooks, releases, debt). | Write when ops state changes. |
| `.project/working/` | In-flight artifacts. | Write during active work; aged out per cadence. |

---

## 11. Where to read next

After you've installed + verified:

- **`PLAYBOOK.md`** — full operating guide. Greenfield walkthrough, brownfield walkthrough, prompt library, cadences, troubleshooting (operating, not install).
- **`README.md`** — library overview. Skill catalog. Agent roster. Governance gates summary.
- **`docs/getting-started.md`** — universal getting-started across all 8 supported tools.
- **`docs/<your-tool>-setup.md`** — your specific tool's setup notes.
- **`.claude/skills/using-praxis/SKILL.md`** — the front-door SKILL. The single most important read.

For each SKILL you find yourself invoking often, read the actual `SKILL.md` once. The verification + rationalization sections compound — once you've internalized them, the agent's adherence improves because you'll notice when it's skipping them.
