#!/usr/bin/env python3
"""Find and validate the Praxis project used by Codex sessions."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

REQUIRED_AGENTS = (
    "delivery-lead", "lead-developer", "code-reviewer",
    "security-reviewer", "qa-engineer",
)


def find_project_root(start: Path) -> Path | None:
    """Prefer the nearest ancestor with working state, not a nested telemetry dir."""
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / ".project" / "working").is_dir():
            return candidate
    return None


def missing_agents(root: Path) -> list[str]:
    personal = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "agents"
    return [name for name in REQUIRED_AGENTS
            if not (root / ".codex" / "agents" / f"{name}.toml").is_file()
            and not (personal / f"{name}.toml").is_file()]


def check_writable(root: Path) -> None:
    for directory in (root, root / ".project" / "working"):
        try:
            with tempfile.NamedTemporaryFile(prefix=".praxis-codex-preflight-", dir=directory):
                pass
        except OSError as exc:
            raise RuntimeError(f"cannot write to {directory}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--require-agents", action="store_true")
    parser.add_argument("--check-write", action="store_true")
    args = parser.parse_args()
    root = find_project_root(args.project_dir)
    if root is None:
        print(f"Praxis Codex: no ancestor of {args.project_dir} has .project/working; "
              "start Praxis at the project root.", file=sys.stderr)
        return 2
    if args.require_agents:
        missing = missing_agents(root)
        if missing:
            print("Praxis Codex: missing agent profiles: " + ", ".join(missing)
                  + f". Run $praxis-setup-subagents in {root} and start a new Codex session.",
                  file=sys.stderr)
            return 3
    if args.check_write:
        try:
            check_writable(root)
        except RuntimeError as exc:
            print(f"Praxis Codex: {exc}", file=sys.stderr)
            return 4
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
