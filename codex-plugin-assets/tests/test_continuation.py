"""Behavior checks for the generated Codex continuation paths."""

import importlib.util
import json
import os
import select
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "praxis-codex"
sys.path.insert(0, str(PLUGIN / "hooks"))
from project_root import REQUIRED_AGENTS, find_project_root

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
        profiles = self.project / ".codex" / "agents"
        profiles.mkdir(parents=True)
        for name in REQUIRED_AGENTS:
            (profiles / f"{name}.toml").write_text(f'name = "{name}"\n')
        self.event = {"session_id": "test-session", "cwd": str(self.project),
                      "permission_mode": "default"}

    def test_nested_root_uses_parent_ledger_and_single_marker(self):
        nested = self.project / "infra" / "local-demo"
        (nested / ".project" / "telemetry").mkdir(parents=True)
        self.assertEqual(find_project_root(nested), self.project.resolve())
        event = {**self.event, "cwd": str(nested)}
        guard.decide({**event, "prompt": "$praxis-drive"}, "UserPromptSubmit")
        self.assertTrue(guard.marker_path(self.project, "test-session").is_file())
        self.assertFalse(guard.marker_path(nested, "test-session").exists())
        self.assertEqual(guard.decide(event, "Stop")["decision"], "block")

    def test_preflight_rejects_missing_agent_profile(self):
        (self.project / ".codex" / "agents" / "qa-engineer.toml").unlink()
        helper = PLUGIN / "hooks" / "project_root.py"
        result = subprocess.run([sys.executable, str(helper), "--project-dir", str(self.project),
                                 "--require-agents", "--check-write"],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 3)
        self.assertIn("qa-engineer", result.stderr)

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

    def test_runner_reviews_only_after_implementation_tasks_finish(self):
        self.ledger.write_text(ledger_text().replace("status: done", "status: open"))
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        codex = fake_bin / "codex"
        codex.write_text(f"#!{sys.executable}\n"
                         "import json, os, pathlib, sys\n"
                         "ledger = pathlib.Path(os.environ['PRAXIS_TEST_LEDGER'])\n"
                         "log = pathlib.Path(os.environ['PRAXIS_TEST_PROMPTS'])\n"
                         "with log.open('a') as out: out.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                         "if 'slice-drain' in ' '.join(sys.argv).lower():\n"
                         "    ledger.write_text(ledger.read_text().replace('state: open', 'state: closed'))\n"
                         "else:\n"
                         "    ledger.write_text(ledger.read_text().replace('status: open', 'status: done'))\n"
                         "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}')\n")
        codex.chmod(0o755)
        prompts = self.project / "prompts.jsonl"
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
               "PRAXIS_TEST_LEDGER": str(self.ledger),
               "PRAXIS_TEST_PROMPTS": str(prompts)}
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        result = subprocess.run(["bash", str(runner), "--project-dir", str(self.project),
                                 "--harness", "codex", "--max-iterations", "3"],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        calls = [" ".join(json.loads(line)) for line in prompts.read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        self.assertIn("Do not launch formal Code/UX/Security/QA review", calls[0])
        self.assertIn("launch one formal Code/UX/Security/QA review round", calls[1])

    def test_runner_does_not_call_open_slice_drained_on_no_progress(self):
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        result = subprocess.run(["bash", str(runner), "--project-dir", str(self.project),
                                 "--harness", "codex", "--dry-run", "--max-iterations", "3"],
                                text=True, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("queue drained (no drive-eligible tasks", result.stdout)

    def test_runner_reports_local_acceptance_without_claiming_slice_closed(self):
        self.ledger.write_text(ledger_text(state="local_implementation_accepted_pending_commit")
                               + "local_acceptance_met: true\nmerged_shippable: false\n")
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        result = subprocess.run(["bash", str(runner), "--project-dir", str(self.project),
                                 "--harness", "codex", "--dry-run"],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("local acceptance met", result.stdout)
        self.assertNotIn("slices closed:     1", result.stdout)
        progress = self.project / ".project" / "telemetry" / "codex-drive-progress.json"
        self.assertIn("local acceptance met", progress.read_text())

    def test_runner_from_nested_dir_writes_only_root_telemetry(self):
        nested = self.project / "infra" / "local-demo"
        (nested / ".project" / "telemetry").mkdir(parents=True)
        self.ledger.write_text(ledger_text(state="local_implementation_accepted_pending_commit")
                               + "local_acceptance_met: true\n")
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        result = subprocess.run(["bash", str(runner), "--project-dir", str(nested),
                                 "--harness", "codex", "--dry-run"],
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(self.project.resolve()), result.stdout)
        self.assertFalse((nested / ".project" / "telemetry" / "codex-drive-progress.json").exists())

    def test_runner_streams_codex_output_before_iteration_finishes(self):
        fake_bin = self.project / "bin"
        fake_bin.mkdir()
        codex = fake_bin / "codex"
        codex.write_text(f"#!{sys.executable}\n"
                         "import os, pathlib, time\n"
                         "print('{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\",\"text\":\"stream-start\"}}', flush=True)\n"
                         "time.sleep(1)\n"
                         "ledger = pathlib.Path(os.environ['PRAXIS_TEST_LEDGER'])\n"
                         "ledger.write_text(ledger.read_text().replace('state: open', 'state: closed'))\n"
                         "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}', flush=True)\n")
        codex.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}",
               "PRAXIS_TEST_LEDGER": str(self.ledger)}
        runner = PLUGIN / "scripts" / "praxis-drive.sh"
        proc = subprocess.Popen(["bash", str(runner), "--project-dir", str(self.project),
                                 "--harness", "codex", "--max-iterations", "2"],
                                env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, bufsize=1)
        try:
            while True:
                ready, _, _ = select.select([proc.stdout], [], [], 5)
                self.assertTrue(ready, "runner produced no live output")
                line = proc.stdout.readline()
                self.assertTrue(line)
                if "stream-start" in line:
                    self.assertIsNone(proc.poll(), "runner buffered output until completion")
                    break
            proc.communicate(timeout=15)
            self.assertEqual(proc.returncode, 0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()


if __name__ == "__main__":
    unittest.main()
