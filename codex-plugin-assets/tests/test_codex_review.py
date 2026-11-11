"""Contract checks for the sandboxed Codex reviewer runner (no model calls)."""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "codex-plugin-assets" / "scripts" / "codex_review.py"

FAKE = """#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
out = a[a.index("--output-last-message") + 1]
json.dump({"argv": a, "nested": os.environ.get("PRAXIS_NESTED"), "stdin": sys.stdin.read()},
          open(out + ".call", "w"))
verdict = os.environ.get("FAKE_VERDICT", "pass")
if verdict == "crash":
    sys.exit(3)
findings = [] if verdict == "pass" else [{"severity": "blocker", "file": "a.py", "line": 1,
                                          "issue": "x", "recommendation": "y"}]
open(out, "w").write(json.dumps({"verdict": verdict, "summary": "s", "findings": findings}))
"""


class CodexReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        (self.proj / ".project" / "working").mkdir(parents=True)
        self.fake = Path(self.tmp.name) / "codex"
        self.fake.write_text(FAKE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)
        self.out = self.proj / "verdict.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_review(self, verdict="pass", role="code-reviewer", extra=()):
        env = dict(os.environ, FAKE_VERDICT=verdict)
        return subprocess.run(
            [sys.executable, str(RUNNER), "--role", role, "--project-dir", str(self.proj),
             "--prompt", "review the slice", "--codex-bin", str(self.fake),
             "--out", str(self.out), *extra],
            env=env, capture_output=True, text=True)

    def test_runs_read_only_and_nested(self):
        proc = self.run_review()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        call = json.loads(Path(str(self.out) + ".call").read_text())
        argv = call["argv"]
        self.assertEqual(argv[0], "exec")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")
        self.assertIn("--output-schema", argv)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
        self.assertEqual(call["nested"], "1")
        self.assertIn("READ-ONLY sandbox", call["stdin"])
        self.assertIn("review the slice", call["stdin"])
        verdict = json.loads(self.out.read_text())
        self.assertEqual(verdict["sandbox"], "read-only")
        self.assertEqual(verdict["role"], "code-reviewer")

    def test_changes_requested_exits_one(self):
        self.assertEqual(self.run_review("changes_requested").returncode, 1)

    def test_failed_run_is_never_a_pass(self):
        self.assertEqual(self.run_review("crash").returncode, 2)

    def test_missing_binary_exits_two(self):
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "--role", "security-reviewer", "--project-dir",
             str(self.proj), "--prompt", "x", "--codex-bin", "/nonexistent/codex"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)

    def test_only_review_roles_allowed(self):
        self.assertNotEqual(self.run_review(role="backend-developer").returncode, 0)

    def test_dry_run_runs_nothing(self):
        proc = self.run_review(extra=("--dry-run",))
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(self.out.exists())
        self.assertIn("read-only", proc.stdout)


if __name__ == "__main__":
    unittest.main()
