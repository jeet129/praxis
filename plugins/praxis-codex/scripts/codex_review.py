#!/usr/bin/env python3
"""codex_review.py — run a Praxis reviewer as a separately sandboxed Codex process.

Why this exists: Codex ignores `sandbox_mode` inside a custom agent role file
(a role "must not control" sandbox_mode / approval_policy / mcp_servers), so a
reviewer spawned as a subagent inherits the parent's write access. A separate
`codex exec --sandbox read-only` process is sandboxed by the OS, so the
reviewer genuinely cannot change files, whatever it is told.

Usage:
  codex_review.py --role code-reviewer --project-dir . --prompt "Review the diff on branch X"
  codex_review.py --role security-reviewer --prompt-file .project/working/review-brief.md

Output: a JSON verdict (schema below) written to --out, default
  .project/working/reviews/<role>-<UTC timestamp>.json
Exit code: 0 pass, 1 changes_requested or blocked, 2 could not run.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REVIEW_ROLES = ("code-reviewer", "security-reviewer", "architecture-challenger")
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "summary", "findings"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "changes_requested", "blocked"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "file", "line", "issue", "recommendation"],
                "properties": {
                    "severity": {"type": "string", "enum": ["blocker", "major", "minor", "note"]},
                    "file": {"type": "string"},
                    "line": {"type": ["integer", "null"]},
                    "issue": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
            },
        },
    },
}


def load_role(role, project, plugin_root):
    """Return (developer_instructions, model, effort) for the role."""
    for base in (project / ".codex" / "agents", plugin_root / "codex-agents"):
        f = base / f"{role}.toml"
        if not f.is_file():
            continue
        text = f.read_text()
        try:
            import tomllib
            data = tomllib.loads(text)
            return (data.get("developer_instructions", ""), data.get("model", ""),
                    data.get("model_reasoning_effort", ""))
        except Exception:
            m = re.search(r'developer_instructions\s*=\s*"""(.*?)"""', text, re.S)
            model = re.search(r'^model\s*=\s*"([^"]+)"', text, re.M)
            effort = re.search(r'^model_reasoning_effort\s*=\s*"([^"]+)"', text, re.M)
            return (m.group(1) if m else "", model.group(1) if model else "",
                    effort.group(1) if effort else "")
    return "", "", ""


def build_command(args, project, schema_path, out_path, model, effort):
    cmd = [args.codex_bin, "exec", "--sandbox", "read-only", "--cd", str(project),
           "--ephemeral", "--output-schema", str(schema_path),
           "--output-last-message", str(out_path)]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["-c", f"model_reasoning_effort={json.dumps(effort)}"]
    cmd.append("-")  # prompt on stdin
    return cmd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--role", required=True, choices=REVIEW_ROLES)
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--out")
    ap.add_argument("--codex-bin", default=os.environ.get("PRAXIS_CODEX_BIN", "codex"))
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("PRAXIS_REVIEW_TIMEOUT", "1800")))
    ap.add_argument("--dry-run", action="store_true", help="print the command and prompt, run nothing")
    args = ap.parse_args()

    project = Path(args.project_dir).resolve()
    plugin_root = Path(__file__).resolve().parent.parent
    brief = args.prompt or ""
    if args.prompt_file:
        brief = (brief + "\n\n" + Path(args.prompt_file).read_text()).strip()
    if not brief:
        print("codex_review: give --prompt or --prompt-file", file=sys.stderr)
        return 2

    instructions, model, effort = load_role(args.role, project, plugin_root)
    prompt = (
        f"You are the Praxis {args.role}. You are running in a READ-ONLY sandbox: you cannot "
        "edit files, and you must not try. Inspect the repository, then answer ONLY with the "
        "JSON verdict the output schema requires. Every finding needs a file and a concrete "
        "recommendation. Use verdict `pass` only when you found no blocker or major finding.\n\n"
        + (f"## Role instructions\n{instructions.strip()}\n\n" if instructions.strip() else "")
        + f"## Review brief\n{brief}\n"
    )

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = Path(args.out) if args.out else project / ".project" / "working" / "reviews" / f"{args.role}-{stamp}.json"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(SCHEMA, fh)
        schema_path = fh.name
    cmd = build_command(args, project, schema_path, out_path, model, effort)

    if args.dry_run:
        print(json.dumps({"command": cmd, "out": str(out_path), "prompt": prompt}, indent=2))
        os.unlink(schema_path)
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PRAXIS_NESTED="1")
    try:
        proc = subprocess.run(cmd, input=prompt, text=True, env=env, timeout=args.timeout,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError:
        print(f"codex_review: `{args.codex_bin}` not found on PATH", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"codex_review: timed out after {args.timeout}s", file=sys.stderr)
        return 2
    finally:
        try:
            os.unlink(schema_path)
        except OSError:
            pass
    if proc.returncode != 0 or not out_path.is_file():
        print(f"codex_review: codex exec failed (exit {proc.returncode})\n{proc.stderr[-2000:]}", file=sys.stderr)
        return 2
    try:
        verdict = json.loads(out_path.read_text())
    except Exception as exc:
        print(f"codex_review: reviewer output is not valid JSON ({exc}); see {out_path}", file=sys.stderr)
        return 2
    verdict.update(role=args.role, reviewed_at=stamp, sandbox="read-only")
    out_path.write_text(json.dumps(verdict, indent=2) + "\n")
    blockers = sum(1 for f in verdict.get("findings", []) if f.get("severity") in ("blocker", "major"))
    print(f"{args.role}: {verdict.get('verdict')} — {len(verdict.get('findings', []))} findings "
          f"({blockers} blocker/major). Report: {out_path}")
    return 0 if verdict.get("verdict") == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
