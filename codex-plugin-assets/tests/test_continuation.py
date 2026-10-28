"""Behavior checks for the generated Codex continuation paths."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "praxis-codex"
spec = importlib.util.spec_from_file_location("codex_continuation", PLUGIN / "hooks" / "codex-continuation.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def ledger_text(state="open", flags="[]"):
    return ("slice: S1\n"
            "tasks:\n"
            "  - id: S1-T1\n"
            "    agent: backend-developer\n"
            "    tier: standard\n"
            "    verify: true\n"
            "    depends_on: []\n"
            "    status: done\n"
            "    attempts: 1\n"
            "gates:\n"
            "  code_review: pending\n"
            "  qa: pending\n"
            f"state: {state}\n"
            f"stop_flags: {flags}\n")


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.working = self.project / ".project" / "working"
        self.working.mkdir(parents=True)
        self.ledger = self.working / "slice-S1-tasks.yaml"
        self.ledger.write_text(ledger_text())
        self.event = {"session_id": "test-session", "cwd": str(self.project),
                      "permission_mode": "default"}

    def test_stop_guard_continues_open_slice_but_not_gate_or_closed_slice(self):
        self.assertEqual(guard.decide({**self.event, "prompt": "$praxis-drive"}, "UserPromptSubmit"), {})
        self.assertEqual(guard.decide(self.event, "Stop")["decision"], "block")
        self.ledger.write_text(ledger_text(flags="[gate_reached]"))
        self.assertEqual(guard.decide(self.event, "Stop"), {})
        self.assertFalse(guard.marker_path(self.project, "test-session").exists())

        guard.decide({**self.event, "prompt": "$praxis-drive"}, "UserPromptSubmit")
        self.ledger.write_text(ledger_text(state="closed"))
        self.assertEqual(guard.decide(self.event, "Stop"), {})

    def test_stop_guard_honors_task_boundary_and_stall(self):
        gov = self.project / ".project" / "governance"
        gov.mkdir()
        (gov / "autonomy.yaml").write_text("stop_after: task\nrun_budget:\n  max_iterations_per_run: 4\n")
        guard.decide({**self.event, "prompt": "$praxis-drive"}, "UserPromptSubmit")
        self.assertEqual(guard.decide(self.event, "Stop"), {})
        (gov / "autonomy.yaml").write_text("stop_after: gate\nrun_budget:\n  max_iterations_per_run: 4\n")
        guard.decide({**self.event, "prompt": "$praxis-drive"}, "UserPromptSubmit")
        self.assertEqual(guard.decide(self.event, "Stop")["decision"], "block")
        self.assertEqual(guard.decide(self.event, "Stop")["decision"], "block")
        self.assertEqual(guard.decide(self.event, "Stop"), {})

    def test_runner_drains_before_reporting_success(self):
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        codex = fake_bin / "codex"
        codex.write_text(f"#!{sys.executable}\n"
                         "import os, pathlib, sys\n"
                         "ledger = pathlib.Path(os.environ['PRAXIS_TEST_LEDGER'])\n"
                         "if 'slice-drain' in ' '.join(sys.argv).lower():\n"
                         "    ledger.write_text(ledger.read_text().replace('state: open', 'state: closed'))\n"
                         "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}')\n")
        codex.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
               "PRAXIS_TEST_LEDGER": str(self.ledger)}
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        args = ["bash", str(runner), "--project-dir", str(self.project),
                "--harness", "codex", "--max-iterations", "3"]
        result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("state: closed", self.ledger.read_text())
        self.assertIn("slices closed:     1", result.stdout)

    def test_runner_does_not_call_open_slice_drained_on_no_progress(self):
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        result = subprocess.run(["bash", str(runner), "--project-dir", str(self.project),
                                 "--harness", "codex", "--dry-run", "--max-iterations", "3"],
                                text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("queue drained (no drive-eligible tasks", result.stdout)


if __name__ == "__main__":
    unittest.main()
