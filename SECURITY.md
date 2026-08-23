# Security Policy

## Supported status

Praxis is **early-stage software** (`0.1.0`) — a prompt/skill/agent library, not a running service.
There is a single actively-maintained line (the `main` branch); there are no
released version branches receiving backports. Security-relevant fixes land on
`main` and are noted in [`CHANGELOG.md`](CHANGELOG.md).

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security concern.

- Preferred: use [GitHub Security Advisories](https://github.com/jeet129/praxis/security/advisories/new)
  for this repository (`jeet129/praxis`) to report privately.
- Alternative: email [jitesh921@gmail.com](mailto:jitesh921@gmail.com) with a
  description of the issue, the affected file(s)/skill(s)/agent(s), and, if
  possible, a reproduction.

We'll acknowledge reports as promptly as we can for a project at this stage.
There is no formal SLA yet — this is disclosed here rather than left implicit,
consistent with the project's early-stage status.

## Scope

Praxis is a library of prompts, SKILL definitions, agent personas, workflow
specs, and governance gates that AI coding agents (Claude Code, Codex, Antigravity, and others) load and act on. It is not a hosted service and does not
process end-user data on its own. Given that shape, the realistic risk surface
is:

- **Prompt injection via untrusted repository content.** Agents read files from
  the project they're operating in (code, docs, issues, PR descriptions, etc.).
  Content in an untrusted repo could attempt to manipulate agent behavior —
  e.g., instructions embedded in a README or code comment trying to get an
  agent to skip a governance gate, exfiltrate secrets, or take destructive
  action.
- **Agents executing shell commands.** Several skills and hooks (e.g.
  `hooks/tap.sh`, `scripts/*.sh`, `scripts/*.py`) run local commands. A
  compromised or malicious script, or a manipulated agent following injected
  instructions, could execute unwanted commands with the permissions of the
  session running it.
- **Supply-chain risk in the generated Codex package** (`plugins/praxis-codex/`)
  and other tool-specific install layouts — these are build outputs; treat
  provenance the same as the source they're generated from.

Praxis does not attempt to sandbox agent execution itself — that's the job of
the harness (Claude Code, Codex, etc.) and how you run it.

### Recommendations for users

- Run agents under your coding harness's sandboxing / permission model rather
  than with unrestricted shell and filesystem access.
- Treat any content coming from an untrusted or externally-contributed
  repository (including issue text, PR descriptions, and third-party code
  comments) as potentially adversarial input to the agent, not as trusted
  instructions.
- Review governance-gate outputs and evidence packs before approving —
  gates exist specifically to create a human checkpoint before irreversible
  or high-stakes actions (e.g. `production_go_live`, `architecture_sign_off`).
- Review `scripts/*.sh` and `scripts/*.py` before running them in an
  environment with sensitive credentials, as you would for any third-party
  automation.

## Disclosure

We don't currently operate a bug bounty. Reasonable-effort private disclosure
with a fix window is appreciated; we'll credit reporters in the fix's
changelog entry unless anonymity is requested.
