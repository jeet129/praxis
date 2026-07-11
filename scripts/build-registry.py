#!/usr/bin/env python3
"""Scan the Praxis tree and keep derived count/list surfaces in sync.

Source of truth (scanned fresh every run):
  * skills/*/SKILL.md      (archive/ lives outside skills/, so it's naturally excluded)
  * agents/*.md
  * workflows/*.yaml
  * commands/*.md

Derived surfaces this script rewrites:
  * .claude-plugin/plugin.json   — `skills` and `agents` arrays, description counts
  * .claude-plugin/marketplace.json — plugins[0].description count phrase
  * plugin.json (root)           — description count phrase
  * GEMINI.md                    — "(N SKILLs)" phrase
  * .cursor/rules/000-ai-delivery-platform.md — "N SKILLs"/"N role agents"/"N workflows" lines
  * skills/skill-registry/SKILL.md    — "~N skills", "current_count: N", "All N active SKILLs"
  * skills/factory-evaluation/SKILL.md — "SKILLs: N (target 70-90)"

Usage:
  scripts/build-registry.py           # apply — rewrites files in place
  scripts/build-registry.py --check   # CI mode: report drift, exit 1 if any found, write nothing

Zero third-party dependencies.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"
WORKFLOWS_DIR = ROOT / "workflows"
COMMANDS_DIR = ROOT / "commands"


def scan_counts():
    skills = sorted(
        p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")
    )
    agents = sorted(p.name for p in AGENTS_DIR.glob("*.md"))
    workflows = sorted(p.name for p in WORKFLOWS_DIR.glob("*.yaml"))
    commands = sorted(p.name for p in COMMANDS_DIR.glob("*.md"))
    gates = count_gates()
    return {
        "skills": skills,
        "agents": agents,
        "workflows": workflows,
        "commands": commands,
        "gates": gates,
    }


def count_gates():
    """Count gate definitions: 2-space-indented keys inside the `gates:` block
    of governance/governance.yaml."""
    path = ROOT / "governance" / "governance.yaml"
    if not path.exists():
        return 0
    n = 0
    in_gates = False
    for line in path.read_text().splitlines():
        if re.match(r"^gates:\s*$", line):
            in_gates = True
            continue
        if in_gates:
            if re.match(r"^[a-zA-Z_]", line):  # next top-level key
                break
            if re.match(r"^  [a-zA-Z_][a-zA-Z0-9_]*:\s*$", line):
                n += 1
    return n


def diff_note(label, before, after):
    if before == after:
        return None
    return f"  {label}: {before!r} -> {after!r}"


class Drift:
    def __init__(self):
        self.notes = []

    def add(self, path, label, before, after):
        note = diff_note(label, before, after)
        if note:
            self.notes.append(f"{path}\n{note}")

    def any(self):
        return bool(self.notes)


def load_json(path):
    return json.loads(path.read_text())


def dump_json_like(path, data):
    """Write JSON preserving the 2-space indent style used across manifests."""
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text)


def process_claude_plugin_json(counts, drift, check):
    path = ROOT / ".claude-plugin" / "plugin.json"
    if not path.exists():
        return
    raw = path.read_text()
    data = json.loads(raw)

    new_skills = [f"./skills/{name}" for name in counts["skills"]]
    new_agents = [f"./agents/{name}" for name in counts["agents"]]

    drift.add(path, "skills[]", data.get("skills"), new_skills)
    drift.add(path, "agents[]", data.get("agents"), new_agents)

    n_skills, n_agents, n_workflows = (
        len(counts["skills"]),
        len(counts["agents"]),
        len(counts["workflows"]),
    )
    old_desc = data.get("description", "")
    new_desc = re.sub(
        r"\d+ SKILLs, \d+ role agents, \d+ workflows",
        f"{n_skills} SKILLs, {n_agents} role agents, {n_workflows} workflows",
        old_desc,
    )
    drift.add(path, "description", old_desc, new_desc)

    if not check:
        data["skills"] = new_skills
        data["agents"] = new_agents
        data["description"] = new_desc
        dump_json_like(path, data)


def process_marketplace_json(counts, drift, check):
    path = ROOT / ".claude-plugin" / "marketplace.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    n_skills, n_agents, n_workflows = (
        len(counts["skills"]),
        len(counts["agents"]),
        len(counts["workflows"]),
    )
    plugins = data.get("plugins", [])
    for plugin in plugins:
        old_desc = plugin.get("description", "")
        new_desc = re.sub(
            r"\d+ SKILLs · \d+ role agents · \d+ workflows",
            f"{n_skills} SKILLs · {n_agents} role agents · {n_workflows} workflows",
            old_desc,
        )
        new_desc = re.sub(
            r"\d+ slash commands",
            f"{len(counts['commands'])} slash commands",
            new_desc,
        )
        new_desc = re.sub(
            r"\d+ (?:active )?governance gates",
            f"{counts['gates']} governance gates",
            new_desc,
        )
        drift.add(path, "plugins[].description", old_desc, new_desc)
        if not check:
            plugin["description"] = new_desc
    if not check:
        dump_json_like(path, data)


def process_root_plugin_json(counts, drift, check):
    path = ROOT / "plugin.json"
    if not path.exists():
        return
    data = json.loads(path.read_text())
    n_skills, n_agents, n_workflows = (
        len(counts["skills"]),
        len(counts["agents"]),
        len(counts["workflows"]),
    )
    old_desc = data.get("description", "")
    new_desc = re.sub(
        r"\d+ SKILLs, \d+ agents, \d+ workflows",
        f"{n_skills} SKILLs, {n_agents} agents, {n_workflows} workflows",
        old_desc,
    )
    new_desc = re.sub(
        r"\d+ (?:active )?governance gates",
        f"{counts['gates']} governance gates",
        new_desc,
    )
    drift.add(path, "description", old_desc, new_desc)
    if not check:
        data["description"] = new_desc
        # Root plugin.json uses ensure_ascii-style escaped unicode historically;
        # json.dumps with ensure_ascii=True keeps the — escapes intact.
        text = json.dumps(data, indent=2, ensure_ascii=True) + "\n"
        path.write_text(text)


def process_gemini_md(counts, drift, check):
    path = ROOT / "GEMINI.md"
    if not path.exists():
        return
    text = path.read_text()
    n_skills = len(counts["skills"])
    new_text = re.sub(r"\(\d+ SKILLs\)", f"({n_skills} SKILLs)", text)
    if new_text != text:
        drift.notes.append(f"{path}\n  (N SKILLs) phrase updated to ({n_skills} SKILLs)")
    if not check and new_text != text:
        path.write_text(new_text)


def process_cursor_rules(counts, drift, check):
    path = ROOT / ".cursor" / "rules" / "000-ai-delivery-platform.md"
    if not path.exists():
        return
    text = path.read_text()
    n_skills, n_agents, n_workflows = (
        len(counts["skills"]),
        len(counts["agents"]),
        len(counts["workflows"]),
    )
    new_text = text
    new_text = re.sub(r"\d+ SKILLs in", f"{n_skills} SKILLs in", new_text)
    new_text = re.sub(r"\d+ role agents in", f"{n_agents} role agents in", new_text)
    new_text = re.sub(r"\d+ workflows in", f"{n_workflows} workflows in", new_text)
    if new_text != text:
        drift.notes.append(f"{path}\n  count phrases updated (skills={n_skills}, agents={n_agents}, workflows={n_workflows})")
    if not check and new_text != text:
        path.write_text(new_text)


def process_skill_registry_skill(counts, drift, check):
    path = SKILLS_DIR / "skill-registry" / "SKILL.md"
    if not path.exists():
        return
    text = path.read_text()
    n_skills = len(counts["skills"])
    new_text = text
    new_text = re.sub(r"~\d+ skills", f"~{n_skills} skills", new_text)
    new_text = re.sub(r"current_count:\s*\d+", f"current_count: {n_skills}", new_text)
    new_text = re.sub(r"All \d+ active SKILLs", f"All {n_skills} active SKILLs", new_text)
    if new_text != text:
        drift.notes.append(f"{path}\n  stale skill counts updated to {n_skills}")
    if not check and new_text != text:
        path.write_text(new_text)


def process_factory_evaluation_skill(counts, drift, check):
    path = SKILLS_DIR / "factory-evaluation" / "SKILL.md"
    if not path.exists():
        return
    text = path.read_text()
    n_skills = len(counts["skills"])
    new_text = re.sub(
        r"SKILLs: \d+ \(target 70-90\)",
        f"SKILLs: {n_skills} (target 70-90)",
        text,
    )
    if new_text != text:
        drift.notes.append(f"{path}\n  'SKILLs: N (target 70-90)' updated to {n_skills}")
    if not check and new_text != text:
        path.write_text(new_text)




def process_text_count_surfaces(counts, drift, check):
    """README.md and install.sh carry prose count phrases; keep them exact."""
    n_skills, n_agents, n_workflows, n_commands = (
        len(counts["skills"]),
        len(counts["agents"]),
        len(counts["workflows"]),
        len(counts["commands"]),
    )
    subs = [
        (re.compile(r"\d+\+? skills\b"), f"{n_skills} skills"),
        (re.compile(r"\d+\+? active SKILLs\b"), f"{n_skills} active SKILLs"),
        (re.compile(r"\d+\+? SKILL\.md bundles"), f"{n_skills} SKILL.md bundles"),
        (re.compile(r"\d+ SKILLs\b"), f"{n_skills} SKILLs"),
        (re.compile(r"\d+(?:-\d+)? role agents\b"), f"{n_agents} role agents"),
        (re.compile(r"\d+(?:-\d+)? role personas\b"), f"{n_agents} role personas"),
        (re.compile(r"agents/\s+\d+(?:-\d+)? role agents"), f"agents/                   {n_agents} role agents"),
        (re.compile(r"\d+(?:-\d+)? named (compositions|workflows)"), f"{n_workflows} named \\1"),
        (re.compile(r"\d+ agents\b"), f"{n_agents} agents"),
        (re.compile(r"\d+ workflows\b"), f"{n_workflows} workflows"),
        (re.compile(r"\d+ slash commands\b"), f"{n_commands} slash commands"),
        (re.compile(r"\d+ (?:active )?governance gates\b"), f"{len(counts['gates']) if isinstance(counts['gates'], list) else counts['gates']} governance gates"),
    ]
    for rel in ("README.md", "install.sh",
                "commands/start.md", ".claude/commands/start.md",
                "commands/start.toml", ".gemini/commands/start.toml"):
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text()
        new_text = text
        for rx, repl in subs:
            new_text = rx.sub(repl, new_text)
        drift.add(path, "count phrases", None if new_text == text else "stale", None if new_text == text else "updated")
        if not check and new_text != text:
            path.write_text(new_text)

def main():
    check = "--check" in sys.argv
    counts = scan_counts()
    drift = Drift()

    process_claude_plugin_json(counts, drift, check)
    process_marketplace_json(counts, drift, check)
    process_root_plugin_json(counts, drift, check)
    process_gemini_md(counts, drift, check)
    process_cursor_rules(counts, drift, check)
    process_skill_registry_skill(counts, drift, check)
    process_factory_evaluation_skill(counts, drift, check)
    process_text_count_surfaces(counts, drift, check)

    print("Praxis — registry build")
    print("========================")
    print(f"  skills:    {len(counts['skills'])}")
    print(f"  agents:    {len(counts['agents'])}")
    print(f"  workflows: {len(counts['workflows'])}")
    print(f"  commands:  {len(counts['commands'])}")
    print()

    if check:
        if drift.any():
            print("Drift detected (run without --check to fix):")
            for note in drift.notes:
                print(note)
            return 1
        print("OK: all derived surfaces in sync.")
        return 0

    if drift.any():
        print("Updated surfaces:")
        for note in drift.notes:
            print(note)
    else:
        print("All surfaces already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
