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

Phase-exit predicates (references/phase-gates.md section 2):
  * every `type: decision_node` step must resolve its predicate to EITHER a
    registered `check:` kind (`command | artifact_exists | artifact_contains |
    verdict_file`) OR a declared `fallback_gate:`. A decision_node with only
    a bare prose predicate and neither is a hard error — a silent LLM
    assertion of a boundary is a protocol violation, the same failure class
    as the `pending` status escape.
  * every `name:` on a `type: gate` / `kind: gate` step is cross-checked
    against governance/governance.yaml (warning, not a hard error — same
    tolerance as the from(...) check below). `fallback_gate:` values are NOT
    cross-checked: per references/phase-gates.md §2 a fallback_gate is a human
    review BOUNDARY (predicate not machine-checkable), distinct from a
    governance-matrix gate, and is not required to appear in governance.yaml.

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
GOVERNANCE_PATH = ROOT / "governance" / "governance.yaml"

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
DECISION_NODE_RE = re.compile(r"^\s*type:\s*decision_node\s*$", re.M)
GATE_STEP_RE = re.compile(r"^\s*(?:type|kind):\s*gate\s*$", re.M)
# Trailing `# comment` is tolerated: the drive runner strips comments before
# parsing (line.split("#", 1)[0]), so the validator must not be fooled into
# "no check here" by an inline comment on a check line.
CHECK_KIND_RE = re.compile(
    r"^\s*check:\s*(command|artifact_exists|artifact_contains|verdict_file|status_field)\s*(?:#.*)?$", re.M
)
# A `check: command` predicate MUST carry a runnable cmd/command arg; without
# one the runner builds an empty command that exits 0 → a SILENT FALSE-PASS.
COMMAND_CHECK_RE = re.compile(r"^\s*check:\s*command\s*(?:#.*)?$", re.M)
COMMAND_ARG_RE = re.compile(r"^\s*(cmd|command):\s*\S", re.M)
FALLBACK_GATE_RE = re.compile(r"^\s*fallback_gate:\s*(\S+)", re.M)
GATE_NAME_RE = re.compile(r"^\s*name:\s*(\S+)", re.M)
GOVERNANCE_GATE_KEY_RE = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*):\s*$")


def known_agents():
    return {p.stem for p in AGENTS_DIR.glob("*.md")}


def known_skills():
    return {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}


def known_workflows():
    return {p.name for p in WORKFLOWS_DIR.glob("*.yaml")}


def known_governance_gates():
    """Top-level keys under governance.yaml's `gates:` block (2-space indent,
    ending at the next 0-indent key). Tolerant line-based scan, same spirit
    as the rest of this validator."""
    if not GOVERNANCE_PATH.exists():
        return None  # signals "governance file missing" — skip the cross-check
    gates = set()
    in_gates = False
    for line in GOVERNANCE_PATH.read_text().splitlines():
        if re.match(r"^gates:\s*$", line):
            in_gates = True
            continue
        if not in_gates:
            continue
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and not line.startswith("    "):
            m = GOVERNANCE_GATE_KEY_RE.match(line)
            if m:
                gates.add(m.group(1))
            continue
        if not line.startswith(" "):
            in_gates = False  # dedent to col 0 -> end of gates: section
    return gates


def validate_workflow_file(path, agents, skills, errors, warnings, infos, governance_gates):
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
    validate_decision_node_predicates(path, lines, errors, warnings, governance_gates)


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


def validate_decision_node_predicates(path, lines, errors, warnings, governance_gates):
    """Per references/phase-gates.md section 2: every `type: decision_node`
    must resolve its predicate to a registered `check:` kind OR declare a
    `fallback_gate:`. Neither present is a hard error — a silent LLM
    assertion of a phase boundary is a protocol violation, the same failure
    class as the `pending` status escape.

    Also cross-checks every `fallback_gate:` reference, and every `name:` on
    a `type: gate` / `kind: gate` step, against the gates declared in
    governance/governance.yaml (when that file is present) — a warning, not
    a hard error, in the same spirit as the existing `from(...)` step-id
    cross-check below.

    Tolerant, line-based, same id-block technique as
    `validate_loop_contracts`: a step's block runs from its `- id:` line up
    to (but not including) the next `- id:` line at the same or shallower
    indent (or EOF). Within that block, the step's OWN header — used to
    decide whether *this* step is a decision_node/gate and whether *its own*
    predicate carries a check/fallback_gate — stops at the first nested
    child `- id:` line (if any), so a `bounded_loop` step whose loop body
    contains a nested `decision_node` isn't misread as an ungated
    decision_node itself.
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
        own_end = end
        if idx + 1 < len(id_lines):
            nxt_i = id_lines[idx + 1][0]
            if nxt_i < end:
                own_end = nxt_i  # first nested child id — this step's own header stops here
        block = "\n".join(lines[start:own_end])

        is_decision_node = bool(DECISION_NODE_RE.search(block))
        is_gate_step = bool(GATE_STEP_RE.search(block))

        fallback_m = FALLBACK_GATE_RE.search(block)

        if is_decision_node:
            has_check = bool(CHECK_KIND_RE.search(block))
            if not has_check and not fallback_m:
                errors.append(
                    f"{path.name}:{start + 1}: decision_node '{step_id}' "
                    "predicate is neither machine-checkable nor gated — a "
                    "silent LLM assertion of a boundary is a protocol "
                    "violation, see references/phase-gates.md §2"
                )

        # False-pass trap: any `check: command` (decision_node OR phase exit)
        # without a runnable cmd/command arg makes the runner build an empty
        # command that exits 0 = silent false-pass. This is the class the
        # external reviewer found; fail hard on it.
        if COMMAND_CHECK_RE.search(block) and not COMMAND_ARG_RE.search(block):
            errors.append(
                f"{path.name}:{start + 1}: step '{step_id}' uses `check: command` "
                "with no `cmd:`/`command:` arg — the runner would build an empty "
                "command that exits 0 (silent false-pass). Supply a real command, "
                "use a check kind that reads state (status_field/artifact_*), or "
                "declare a fallback_gate. See references/phase-gates.md §2."
            )

        # NOTE: a `fallback_gate:` is NOT cross-checked against governance.yaml.
        # By definition (references/phase-gates.md §2) it is the case where the
        # predicate is not machine-checkable, so the workflow-drive stops for a
        # human review BOUNDARY — that is distinct from a governance-matrix gate
        # (which has approvers + evidence). A fallback_gate MAY coincide with a
        # governance gate (e.g. architecture_sign_off), but it is not required
        # to, and warning on its absence contradicts the design. Only actual
        # `kind: gate` / `type: gate` steps must be registered in governance.yaml
        # (checked below).

        if is_gate_step and governance_gates is not None:
            name_m = GATE_NAME_RE.search(block)
            if name_m:
                gate_name = name_m.group(1).strip()
                if gate_name not in governance_gates:
                    warnings.append(
                        f"{path.name}:{start + 1}: gate step '{step_id}' "
                        f"name '{gate_name}' has no matching gate in "
                        "governance/governance.yaml"
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
    governance_gates = known_governance_gates()

    errors = []
    warnings = []
    infos = []

    wf_files = sorted(WORKFLOWS_DIR.glob("*.yaml"))
    if not wf_files:
        print(f"ERROR: no workflow files found under {WORKFLOWS_DIR}", file=sys.stderr)
        return 2

    for path in wf_files:
        validate_workflow_file(path, agents, skills, errors, warnings, infos, governance_gates)

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
