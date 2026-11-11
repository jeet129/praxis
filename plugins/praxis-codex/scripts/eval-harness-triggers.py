#!/usr/bin/env python3
"""eval-harness-triggers.py — run the evals/ trigger and negative cases through
Codex or Antigravity and grade whether the expected skill was loaded.

Claude Code has its own runner (`claude plugin eval`); this covers the other two.
Costs real tokens and needs a logged-in CLI. Not part of CI.

  eval-harness-triggers.py --harness codex       [--project-dir DIR] [--case GLOB] [--json]
  eval-harness-triggers.py --harness antigravity [--project-dir DIR] [--case GLOB] [--json]

How a case is graded
  codex        `codex exec --json` emits one JSON event per line. Codex loads a
               skill by reading its SKILL.md with a shell command, so a
               command_execution event whose command names <skill>/SKILL.md is
               direct evidence: LOADED. The skill name appearing only in the
               reply text is weaker: MENTIONED.
  antigravity  `agy -p` has no event stream. The Praxis telemetry hook writes
               every tool call to .project/telemetry/antigravity-activity.jsonl,
               so a new row whose summary names the skill is LOADED; the name in
               the reply text is MENTIONED.
  negative-*   pass when no SKILL.md was read at all.
Exit: 0 every trigger LOADED and every negative clean, 1 otherwise, 2 cannot run.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def cases(pattern):
    out = []
    for case in sorted((ROOT / "evals").iterdir()):
        if not case.is_dir() or not (case / "prompt.md").is_file():
            continue
        kind = case.name.split("-", 1)[0]
        if kind not in ("trigger", "negative") or not fnmatch.fnmatch(case.name, pattern):
            continue
        text = (case / "prompt.md").read_text()
        prompt = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S).strip()
        skill = ""
        grader = case / "graders" / "skill-fired.md"
        if grader.is_file():
            m = re.search(r'^input_match:\s*"?([^"\n]+)"?', grader.read_text(), re.M)
            skill = m.group(1).strip() if m else ""
        out.append((case.name, kind, skill, prompt))
    return out


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def run_codex(binary, project, prompt, timeout):
    proc = subprocess.run([binary, "exec", "--sandbox", "read-only", "--ephemeral", "--json",
                           "-C", str(project), "-"], input=prompt, text=True, capture_output=True,
                          timeout=timeout, env=dict(os.environ, PRAXIS_NESTED="1"))
    commands, reply = [], []
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        for d in walk(event):
            if d.get("type") == "command_execution" and isinstance(d.get("command"), str):
                commands.append(d["command"])
            if d.get("type") == "agent_message" and isinstance(d.get("text"), str):
                reply.append(d["text"])
    return proc.returncode, commands, "\n".join(reply)


def run_agy(binary, project, prompt, timeout):
    activity = project / ".project" / "telemetry" / "antigravity-activity.jsonl"
    before = activity.stat().st_size if activity.is_file() else 0
    proc = subprocess.run([binary, "-p", prompt], cwd=project, text=True, capture_output=True, timeout=timeout)
    rows = []
    if activity.is_file():
        with activity.open(errors="replace") as fh:
            fh.seek(before)
            for line in fh:
                try:
                    r = json.loads(line)
                    rows.append(f"{r.get('tool')} {r.get('toolSummary') or ''}")
                except ValueError:
                    pass
    return proc.returncode, rows, proc.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--harness", required=True, choices=["codex", "antigravity"])
    ap.add_argument("--project-dir", type=Path, default=Path.cwd())
    ap.add_argument("--case", default="*")
    ap.add_argument("--bin")
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("PRAXIS_EVAL_TIMEOUT", "300")))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    binary = a.bin or os.environ.get("PRAXIS_EVAL_BIN") or ("codex" if a.harness == "codex" else "agy")
    project = a.project_dir.resolve()
    runner = run_codex if a.harness == "codex" else run_agy
    results = []
    for name, kind, skill, prompt in cases(a.case):
        try:
            code, evidence, reply = runner(binary, project, prompt, a.timeout)
        except FileNotFoundError:
            print(f"{binary} not found on PATH", file=sys.stderr)
            return 2
        except subprocess.TimeoutExpired:
            results.append({"case": name, "kind": kind, "skill": skill, "result": "TIMEOUT", "ok": False})
            continue
        skill_reads = [e for e in evidence if "SKILL.md" in e or re.search(r"\bskills?/", e)]
        if kind == "trigger":
            loaded = any(skill in e for e in evidence if "SKILL.md" in e or "skill" in e.lower())
            result = "LOADED" if loaded else ("MENTIONED" if skill in reply else "MISS")
            ok = result == "LOADED"
        else:
            result = "CLEAN" if not skill_reads else "LOADED_A_SKILL"
            ok = result == "CLEAN"
        if code != 0 and not evidence and not reply:
            result, ok = f"RUN_FAILED(exit {code})", False
        results.append({"case": name, "kind": kind, "skill": skill, "result": result, "ok": ok})
        if not a.json:
            print(f"{result:<16} {name}" + (f" -> {skill}" if skill else ""), flush=True)
    summary = {"harness": a.harness, "cases": len(results), "passed": sum(r["ok"] for r in results),
               "mentioned_only": sum(r["result"] == "MENTIONED" for r in results), "results": results}
    if a.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"{a.harness}: {summary['passed']}/{summary['cases']} passed "
              f"({summary['mentioned_only']} named the skill without loading it)")
    return 0 if results and summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
