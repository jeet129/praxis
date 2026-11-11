"""Parallel lane supervisor: selection, worktrees and merge policy (no model calls)."""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANES = ROOT / "plugins" / "praxis-codex" / "scripts" / "codex_lanes.py"

# Fake single-lane controller: writes the file named in FAKE_FILE_<slice>
# (default lane-<slice>.txt) and closes the lane's ledger.
FAKE = """#!/usr/bin/env python3
import os, sys
from pathlib import Path
a = sys.argv[1:]
wt = Path(a[a.index("--project-dir") + 1]); sid = a[a.index("--slice") + 1]
if os.environ.get("FAKE_FAIL") == sid:
    sys.exit(7)
name = os.environ.get("FAKE_FILE_" + sid, "lane-" + sid + ".txt")
(wt / name).write_text("work from " + sid + "\\n")
led = wt / ".project" / "working" / ("slice-" + sid + "-tasks.yaml")
led.write_text(led.read_text().replace("status: open", "status: done").replace("state: open", "state: closed"))
(wt / ".project" / "working" / ("verify-" + sid + "-T1.log")).write_text("ok\\n")
"""

LEDGER = """slice: {sid}
{deps}tasks:
  - id: {sid}-T1
    summary: x
    agent: backend-developer
    tier: standard
    verify: "true > .project/working/verify-{sid}-T1.log 2>&1"
    depends_on: []
    status: open
    attempts: 0
state: open
stop_flags: []
"""


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout


class LanesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        (self.repo / ".project" / "working").mkdir(parents=True)
        sh(self.repo, "git", "init", "-q", "-b", "main")
        (self.repo / "shared.txt").write_text("base\n")
        (self.repo / ".gitignore").write_text(".project/\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.fake = Path(self.tmp.name) / "fake_controller.py"
        self.fake.write_text(FAKE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IEXEC)

    def tearDown(self):
        self.tmp.cleanup()

    def ledger(self, sid, deps="depends_on_slices: []\n"):
        (self.repo / ".project" / "working" / f"slice-{sid}-tasks.yaml").write_text(
            LEDGER.format(sid=sid, deps=deps))

    def run_lanes(self, *extra, env=None):
        e = dict(os.environ, PRAXIS_LANES_POLL_SECONDS="0.1", **(env or {}))
        p = subprocess.run([sys.executable, str(LANES), "--project-dir", str(self.repo),
                            "--controller", str(self.fake), "--json", *extra],
                           capture_output=True, text=True, env=e)
        try:
            return p.returncode, json.loads(p.stdout), p.stderr
        except ValueError:
            return p.returncode, {}, p.stderr + p.stdout

    def test_two_independent_lanes_merge(self):
        self.ledger("A"); self.ledger("B")
        code, rep, err = self.run_lanes("--max-parallel", "2")
        self.assertEqual(code, 0, err)
        self.assertEqual({rep["lanes"][s]["status"] for s in "AB"}, {"merged"})
        self.assertTrue((self.repo / "lane-A.txt").is_file() and (self.repo / "lane-B.txt").is_file())
        self.assertEqual(sh(self.repo, "git", "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")
        self.assertIn("state: closed", (self.repo / ".project/working/slice-A-tasks.yaml").read_text())
        self.assertTrue((self.repo / ".project/working/verify-B-T1.log").is_file())
        self.assertFalse((self.repo / ".praxis-worktrees" / "A").exists())
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain", "--untracked-files=no").strip(), "")

    def test_undeclared_lane_is_not_parallelised(self):
        self.ledger("A"); self.ledger("B", deps="")
        code, rep, _ = self.run_lanes()
        self.assertEqual(rep["selected"], ["A"])
        self.assertIn("B", rep["skipped"])
        self.assertFalse((self.repo / "lane-B.txt").exists())

    def test_open_dependency_blocks_lane(self):
        self.ledger("A"); self.ledger("B", deps="depends_on_slices: [A]\n")
        _, rep, _ = self.run_lanes("--dry-run")
        self.assertEqual(rep["selected"], ["A"])
        self.assertIn("dependency", rep["skipped"]["B"])

    def test_conflict_is_aborted_and_branch_kept(self):
        self.ledger("A"); self.ledger("B")
        code, rep, _ = self.run_lanes("--max-parallel", "2",
                                      env={"FAKE_FILE_A": "shared.txt", "FAKE_FILE_B": "shared.txt"})
        self.assertEqual(code, 1)
        self.assertEqual(rep["lanes"]["A"]["status"], "merged")
        self.assertEqual(rep["lanes"]["B"]["status"], "needs_manual_merge")
        self.assertEqual((self.repo / "shared.txt").read_text(), "work from A\n")
        self.assertIn("praxis/lane-B", sh(self.repo, "git", "branch", "--list", "praxis/lane-B"))
        self.assertTrue((self.repo / ".praxis-worktrees" / "B").is_dir())
        self.assertEqual(sh(self.repo, "git", "status", "--porcelain", "--untracked-files=no").strip(), "")
        self.assertIn("state: open", (self.repo / ".project/working/slice-B-tasks.yaml").read_text())

    def test_failed_lane_is_not_merged(self):
        self.ledger("A"); self.ledger("B")
        code, rep, _ = self.run_lanes("--max-parallel", "2", env={"FAKE_FAIL": "B"})
        self.assertEqual(code, 1)
        self.assertEqual(rep["lanes"]["A"]["status"], "merged")
        self.assertEqual(rep["lanes"]["B"]["status"], "failed")
        self.assertFalse((self.repo / "lane-B.txt").exists())

    def test_dirty_tree_refuses(self):
        self.ledger("A")
        (self.repo / "shared.txt").write_text("uncommitted\n")
        code, _, err = self.run_lanes()
        self.assertEqual(code, 2)
        self.assertIn("uncommitted", err)

    def test_kill_switch_refuses(self):
        self.ledger("A")
        (self.repo / ".project" / "STOP").touch()
        code, _, err = self.run_lanes()
        self.assertEqual(code, 2)
        self.assertIn("kill switch", err)

    def test_max_parallel_limits_selection(self):
        for s in "ABC":
            self.ledger(s)
        _, rep, _ = self.run_lanes("--dry-run", "--max-parallel", "2")
        self.assertEqual(rep["selected"], ["A", "B"])
        self.assertIn("C", rep["skipped"])


if __name__ == "__main__":
    unittest.main()
