#!/usr/bin/env python3
"""Cross-reference validator for Praxis workflows and commands.

For each workflows/*.yaml:
  * every `agent:` value must match a file in agents/<value>.md
  * every `skill:`/`skills:` mention (including list items under `consumes_skills:`)
    must match a directory skills/<value>/
  * every `from(X...)` expression's leading identifier X must resolve to a
    step id/name declared in the same file, OR be one of the well-known
    external-context keywords (parent, planner, self) or a file-path-looking
    reference (contains '.' or '/', e.g. from(.project/...)) which is not a
    step reference and is skipped
  * `predicate:` names/expressions are listed as info (not validated — they're
    free-form boolean expressions, not registry lookups)

For each commands/*.md and commands/*.toml:
  * any workflows/<name>.yaml path mentioned in the body must exist

Loop contracts (references/loop-contracts.md section 1):
  * any step with `type: bounded_loop` must carry a `loop_contract:` block
    containing `exit_criteria`, `max_iterations` (either inside the block or
    on the step itself — some steps express the cap via `max_iterations:`
    directly, e.g. `from(runtime_bindings.max_passes)`), and `on_exhaustion`.
    Missing any of these is a hard error.

Exit codes:
  1 — hard failure (missing agent, missing skill, missing workflow file referenced
      by a command)
  0 — clean, or only warnings/info

Zero third-party dependencies (no pyyaml) — uses a tolerant line-based scan,
not a full YAML parser. Good enough for this repo's consistent step-list shape.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / "agents"
SKILLS_DIR = ROOT / "skills"
WORKFLOWS_DIR = ROOT / "workflows"
COMMANDS_DIR = ROOT / "commands"

EXTERNAL_CONTEXT_KEYWORDS = {
    "parent", "planner", "self", "governance", "principal", "principal_intent",
    "command", "runtime_bindings", "loop_state",
}

FROM_RE = re.compile(r"from\(\s*([^\s.,)]+)")
ID_RE = re.compile(r"^\s*-?\s*id:\s*(\S+)")
AGENT_RE = re.compile(r"^\s*agent:\s*(\S+)")
SKILL_RE = re.compile(r"^\s*skills?:\s*(\S+)\s*$")
LIST_ITEM_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_-]+)\s*(#.*)?$")
PREDICATE_RE = re.compile(r"^\s*predicate:\s*(.*)$")


def known_agents():
    return {p.stem for p in AGENTS_DIR.glob("*.md")}


def known_skills():
    return {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}


def known_workflows():
    return {p.name for p in WORKFLOWS_DIR.glob("*.yaml")}


def validate_workflow_file(path, agents, skills, errors, warnings, infos):
    lines = path.read_text().splitlines()
    step_ids = set()

    # Pass 1: collect step ids anywhere in the file (top-level steps, parallel
    # branches, failure_paths, etc. all use the same `id:` convention).
    for line in lines:
        m = ID_RE.match(line)
        if m:
            step_ids.add(m.group(1).strip())

    # Pass 2: check agent:, skill(s):, consumes_skills list items, from(...), predicate:
    in_consumes_skills = False
    consumes_skills_indent = None
    for lineno, line in enumerate(lines, 1):
        stripped = line.rstrip()

        # consumes_skills: block — following indented `- name` lines are skill refs
        if re.match(r"^\s*consumes_skills:\s*$", stripped):
            in_consumes_skills = True
            consumes_skills_indent = len(line) - len(line.lstrip())
            continue
        if in_consumes_skills:
            indent = len(line) - len(line.lstrip()) if line.strip() else None
            item_m = LIST_ITEM_RE.match(line)
            if item_m and indent is not None and indent > consumes_skills_indent:
                skill_name = item_m.group(1)
                if skill_name not in skills:
                    errors.append(
                        f"{path.name}:{lineno}: consumes_skills entry '{skill_name}' has no skills/{skill_name}/"
                    )
                continue
            else:
                in_consumes_skills = False
                # fall through to normal processing of this line

        m = AGENT_RE.match(stripped)
        if m:
            agent_name = m.group(1).strip().rstrip(",")
            if agent_name not in agents:
                errors.append(
                    f"{path.name}:{lineno}: agent '{agent_name}' has no agents/{agent_name}.md"
                )

        m = SKILL_RE.match(stripped)
        if m:
            skill_name = m.group(1).strip()
            if skill_name not in skills:
                errors.append(
                    f"{path.name}:{lineno}: skill '{skill_name}' has no skills/{skill_name}/"
                )

        for fm in FROM_RE.finditer(stripped):
            ref = fm.group(1)
            if ref in EXTERNAL_CONTEXT_KEYWORDS:
                continue
            if ref.startswith(".") or "/" in ref:
                # file-path-looking reference, e.g. from(.project/operational/...)
                continue
            if ref not in step_ids:
                warnings.append(
                    f"{path.name}:{lineno}: from({ref}...) does not match any step id/name in this file"
                )

        pm = PREDICATE_RE.match(stripped)
        if pm and pm.group(1) and pm.group(1) != "|":
            infos.append(f"{path.name}:{lineno}: predicate: {pm.group(1)}")

    validate_loop_contracts(path, lines, errors)


def validate_loop_contracts(path, lines, errors):
    """Any step with `type: bounded_loop` must carry a `loop_contract:` block
    with `exit_criteria`, `max_iterations`, and `on_exhaustion` — per
    references/loop-contracts.md section 1. Tolerant, line-based: a step's
    block runs from its `- id:` line up to (but not including) the next
    `- id:` line at the same or shallower indent (or EOF). `max_iterations`
    is accepted either inside `loop_contract:` or directly on the step
    (workflows/ideation-refinement-loop.yaml expresses its cap that way, via
    `from(runtime_bindings.max_passes)`, and the validator tolerates both
    shapes rather than forcing a duplicate).
    """
    id_lines = []
    for i, line in enumerate(lines):
        m = ID_RE.match(line)
        if m:
            indent = len(line) - len(line.lstrip())
            id_lines.append((i, indent, m.group(1).strip()))

    for idx, (start, indent, step_id) in enumerate(id_lines):
        end = len(lines)
        for nxt_i, nxt_indent, _ in id_lines[idx + 1:]:
            if nxt_indent <= indent:
                end = nxt_i
                break
        block = "\n".join(lines[start:end])

        if not re.search(r"^\s*type:\s*bounded_loop\s*$", block, re.M):
            continue

        missing = []
        if not re.search(r"^\s*loop_contract:\s*$", block, re.M):
            missing.append("loop_contract:")
        if not re.search(r"^\s*exit_criteria:", block, re.M):
            missing.append("exit_criteria")
        if not re.search(r"^\s*max_iterations:", block, re.M):
            missing.append("max_iterations")
        if not re.search(r"^\s*on_exhaustion:", block, re.M):
            missing.append("on_exhaustion")

        if missing:
            errors.append(
                f"{path.name}:{start + 1}: step '{step_id}' has type: bounded_loop "
                f"but is missing {', '.join(missing)} (see references/loop-contracts.md section 1)"
            )


def validate_commands(workflows, errors, warnings):
    wf_ref_re = re.compile(r"workflows/([A-Za-z0-9_-]+\.yaml)")
    for path in sorted(list(COMMANDS_DIR.glob("*.md")) + list(COMMANDS_DIR.glob("*.toml"))):
        text = path.read_text()
        for m in wf_ref_re.finditer(text):
            wf_name = m.group(1)
            if wf_name not in workflows:
                errors.append(
                    f"{path.name}: references workflows/{wf_name} which does not exist"
                )


def main():
    agents = known_agents()
    skills = known_skills()
    workflows = known_workflows()

    errors = []
    warnings = []
    infos = []

    wf_files = sorted(WORKFLOWS_DIR.glob("*.yaml"))
    if not wf_files:
        print(f"ERROR: no workflow files found under {WORKFLOWS_DIR}", file=sys.stderr)
        return 2

    for path in wf_files:
        validate_workflow_file(path, agents, skills, errors, warnings, infos)

    validate_commands(workflows, errors, warnings)

    print("Praxis — workflow cross-reference validator")
    print("=============================================")
    print(f"  workflows scanned: {len(wf_files)}")
    print(f"  agents known:      {len(agents)}")
    print(f"  skills known:      {len(skills)}")
    print()

    if infos:
        print(f"Info: {len(infos)} predicate(s) found (not validated, listed for review):")
        for i in infos:
            print(f"  i {i}")
        print()

    if warnings:
        print(f"Warnings: {len(warnings)}")
        for w in warnings:
            print(f"  ! {w}")
        print()

    if errors:
        print(f"Errors: {len(errors)}")
        for e in errors:
            print(f"  x {e}")
        print()
        print("FAIL")
        return 1

    print("OK: no missing agent/skill/workflow references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
