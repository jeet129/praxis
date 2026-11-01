"""Replay the PortiQ and Aapka Aangan Codex failure modes without live models."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "praxis-codex"
sys.path.insert(0, str(PLUGIN / "scripts"))
from codex_state import (closeout_errors, migrate_safe, read_ledger,
                         verdict, write_index)
from codex_drive import choose_lane


def ledger(slice_id: str, *, state: str = "open", flags: str = "[]",
           status: str = "done", independent: bool = False) -> str:
    dependency = "depends_on_slices: []\n" if independent else ""
    return (f"schema_version: 2\nslice: {slice_id}\n"
            f"packet: .project/working/slice-{slice_id}-packet.md\n"
            f"{dependency}state: {state}\nstop_flags: {flags}\n"
            "tasks:\n"
            f"  - id: {slice_id}-T1\n"
            "    verify: true\n    depends_on: []\n"
            f"    status: {status}\n"
            "gates:\n  code_review: pending\n  security_review: n/a\n"
            "  visual_review: n/a\n  qa: pending\n")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.working = self.root / ".project" / "working"
        self.working.mkdir(parents=True)
        gov = self.root / ".project" / "governance"
        gov.mkdir()
        (gov / "autonomy.yaml").write_text(
            "stop_after: slice\nrun_budget:\n  max_iterations_per_run: 5\n"
            "  max_slices_per_run: 3\n  cost_ceiling_proxy: 20\n"
            "stall:\n  max_iterations_without_ledger_change: 2\n"
            "harnesses:\n  codex:\n    command: codex exec \"{prompt}\"\n"
            "    json_output_flag: --json\n    usage_parse: codex-json\n")
        profiles = self.root / ".codex" / "agents"
        profiles.mkdir(parents=True)
        for name in ("delivery-lead", "lead-developer", "code-reviewer",
                     "security-reviewer", "qa-engineer"):
            (profiles / f"{name}.toml").write_text(f'name = "{name}"\n')

    def path(self, slice_id: str) -> Path:
        return self.working / f"slice-{slice_id}-tasks.yaml"

    def fake_runner(self, *, produce_evidence: bool = True,
                    gate_reached: bool = False) -> Path:
        runner = self.root / "fake-runner.py"
        runner.write_text(f"#!{sys.executable}\n"
                          "import os, pathlib, sys\n"
                          "root = pathlib.Path(sys.argv[sys.argv.index('--project-dir')+1])\n"
                          "name = sys.argv[sys.argv.index('--slice')+1]\n"
                          "path = root/'.project'/'working'/f'slice-{name}-tasks.yaml'\n"
                          "with (root/'calls').open('a') as out: out.write(name+'\\n')\n"
                          "s = path.read_text().replace('state: open', 'state: closed')\n"
                          "s = s.replace('code_review: pending', 'code_review: pass')\n"
                          "s = s.replace('qa: pending', 'qa: pass')\n"
                          f"if {gate_reached!r}: s=s.replace('stop_flags: []','stop_flags: [gate_reached]')\n"
                          f"if {produce_evidence!r}:\n"
                          "    files = {k: f'.project/working/{name}-{k}.md' for k in "
                          "('code_review','qa','tests','acceptance','summary')}\n"
                          "    for value in files.values():\n"
                          "        file = root/value; file.parent.mkdir(parents=True,exist_ok=True); file.write_text('PASS\\n')\n"
                          "    s += 'closeout_evidence:\\n' + ''.join(f'  {k}: {v}\\n' for k,v in files.items())\n"
                          "path.write_text(s)\n"
                          "print('[fake] completed '+name, flush=True)\n")
        runner.chmod(0o755)
        return runner

    def test_gate_blocks_its_lane_but_independent_lane_closes(self):
        self.path("A").write_text(ledger("A", flags="[gate_reached]"))
        self.path("B").write_text(ledger("B", independent=True))
        self.assertEqual(choose_lane([read_ledger(self.path("A")), read_ledger(self.path("B"))],
                                     "A", set(), gated_boundary={"A"}).slice_id, "B")
        (self.working / "slice-B-packet.md").write_text("B packet\n")
        runner = self.fake_runner()
        command = [sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                   "--project-dir", str(self.root), "--runner", str(runner)]
        result = subprocess.run(command, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["B"])
        self.assertIn("B closed with verified evidence", result.stdout)
        self.assertEqual(read_ledger(self.path("A")).lane(), "gated")
        index = json.loads((self.working / "codex-active-index.json").read_text())
        self.assertEqual(len(index["lanes"]), 2)
        self.assertEqual(next(item for item in index["lanes"] if item["slice"] == "B")["lane"], "closed")

    def test_crossing_new_gate_requires_declared_dependencies(self):
        self.path("A").write_text(ledger("A", flags="[gate_reached]"))
        self.path("B").write_text(ledger("B"))
        self.assertIsNone(choose_lane([read_ledger(self.path("A")), read_ledger(self.path("B"))],
                                      "A", set(), gated_boundary={"A"}))

    def test_declared_slice_dependency_waits_for_closure(self):
        self.path("A").write_text(ledger("A", status="open"))
        self.path("B").write_text(ledger("B", status="open")
                                  + "depends_on_slices: [A]\n")
        items = [read_ledger(self.path("A")), read_ledger(self.path("B"))]
        self.assertEqual(choose_lane(items, "B", set()).slice_id, "A")

    def test_workflow_subledger_runs_only_named_slice(self):
        self.path("A").write_text(ledger("A"))
        self.path("B").write_text(ledger("B"))
        (self.working / "slice-B-packet.md").write_text("B packet\n")
        runner = self.fake_runner()
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner),
                                 "--slice", "B"],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["B"])

    def test_missing_evidence_cannot_count_as_closed(self):
        self.path("B").write_text(ledger("B"))
        (self.working / "slice-B-packet.md").write_text("B packet\n")
        runner = self.fake_runner(produce_evidence=False)
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner)],
                                text=True, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("closeout blocked", result.stdout)
        self.assertNotIn("closed with verified evidence", result.stdout)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["B", "B"])

    def test_closed_label_with_reached_gate_is_not_counted(self):
        self.path("B").write_text(ledger("B"))
        (self.working / "slice-B-packet.md").write_text("B packet\n")
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner",
                                 str(self.fake_runner(gate_reached=True))],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("stopped at stop_flags: gate_reached", result.stdout)
        self.assertNotIn("closed with verified evidence", result.stdout)
        index = json.loads((self.working / "codex-active-index.json").read_text())
        self.assertEqual(index["lanes"][0]["lane"], "gated")

    def test_budget_stops_before_extra_closeout_repair(self):
        self.path("B").write_text(ledger("B"))
        (self.working / "slice-B-packet.md").write_text("B packet\n")
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner",
                                 str(self.fake_runner(produce_evidence=False)),
                                 "--max-iterations", "1"],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("budget reached before closeout repair", result.stdout)
        self.assertEqual((self.root / "calls").read_text().splitlines(), ["B"])

    def test_pending_future_gate_and_safe_legacy_status_migrate(self):
        path = self.path("T28")
        path.write_text(ledger("T28", state="fix_loop_14",
                               flags="[governance_gate_pending]", status="pending"))
        before = read_ledger(path)
        self.assertEqual(before.lane(), "ready")
        self.assertEqual(migrate_safe(path), ["pending->open"])
        self.assertTrue(path.with_suffix(".yaml.codex-pre-migration.bak").is_file())
        self.assertEqual(read_ledger(path).next_task()["id"], "T28-T1")

    def test_ambiguous_status_blocks_lane_without_guessing(self):
        path = self.path("P")
        path.write_text(ledger("P", status="waiting_for_review"))
        item = read_ledger(path)
        self.assertEqual(item.lane(), "schema_blocked")
        self.assertEqual(migrate_safe(path), [])

    def test_unverified_legacy_closed_history_is_not_rewritten(self):
        path = self.path("old")
        path.write_text(ledger("old", state="closed").replace("schema_version: 2", "schema_version: 1"))
        write_index(self.root, [read_ledger(path)])
        entry = json.loads((self.working / "codex-active-index.json").read_text())["lanes"][0]
        self.assertEqual(entry["closeout_audit"], "legacy_unverified")
        self.assertEqual(entry["closeout_errors"], [])

    def test_review_verdict_requires_final_pass(self):
        self.assertEqual(verdict("fixloop13_S1_closed_provisional_pass_final_diff_pending"), "pending")
        self.assertEqual(verdict("APPROVE_WITH_CAVEATS"), "pass")
        self.assertEqual(verdict("request_changes"), "fail")

    def test_gate_label_cannot_override_failed_evidence_file(self):
        path = self.path("E")
        path.write_text(ledger("E", state="closed")
                        .replace("code_review: pending", "code_review: pass")
                        .replace("qa: pending", "qa: pass")
                        + "closeout_evidence:\n"
                        + "  code_review: .project/working/E-code.md\n"
                        + "  qa: .project/working/E-qa.md\n"
                        + "  tests: .project/working/E-tests.md\n"
                        + "  acceptance: .project/working/E-acceptance.md\n"
                        + "  summary: .project/working/E-summary.md\n")
        (self.working / "slice-E-packet.md").write_text("packet\n")
        for name in ("code", "tests", "acceptance", "summary"):
            (self.working / f"E-{name}.md").write_text("verdict: PASS\n")
        (self.working / "E-qa.md").write_text("verdict: FAIL\nPASS mentioned later\n")
        self.assertIn("qa evidence has no explicit pass verdict",
                      closeout_errors(self.root, read_ledger(path)))

    def test_audit_limits_context_for_large_project(self):
        for number in range(24):
            name = f"MVP-{number:02d}"
            self.path(name).write_text(ledger(name, status="open"))
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--audit"],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("ready=24", result.stdout)
        self.assertIn("9 more active lanes", result.stdout)
        self.assertLessEqual(len(result.stdout.splitlines()), 18)

    def test_controller_and_packaged_runner_complete_two_stage_slice(self):
        self.path("T28").write_text(ledger("T28", flags="[governance_gate_pending]", status="open"))
        (self.working / "slice-T28-packet.md").write_text("T28 packet\n")
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        codex = fake_bin / "codex"
        codex.write_text(f"#!{sys.executable}\n"
                         "import os, pathlib, sys\n"
                         "root = pathlib.Path.cwd()\n"
                         "path = root/'.project'/'working'/'slice-T28-tasks.yaml'\n"
                         "s = path.read_text()\n"
                         "if 'slice-drain' in ' '.join(sys.argv).lower():\n"
                         "    s = s.replace('state: open', 'state: closed')\n"
                         "    s = s.replace('code_review: pending', 'code_review: pass')\n"
                         "    s = s.replace('qa: pending', 'qa: pass')\n"
                         "    files = {k: f'.project/working/T28-{k}.md' for k in "
                         "('code_review','qa','tests','acceptance','summary')}\n"
                         "    for value in files.values(): (root/value).write_text('PASS\\n')\n"
                         "    s += 'closeout_evidence:\\n' + ''.join(f'  {k}: {v}\\n' for k,v in files.items())\n"
                         "else:\n"
                         "    s = s.replace('status: open', 'status: done')\n"
                         "path.write_text(s)\n"
                         "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}')\n")
        codex.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root)],
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("T28 closed with verified evidence", result.stdout)
        checkpoint = json.loads((self.root / ".project" / "telemetry" / "codex-controller.json").read_text())
        self.assertEqual(checkpoint["iteration"], 2)

    def test_portiq_pattern_stalls_without_false_parent_closure(self):
        self.path("MVP-01").write_text(ledger("MVP-01", status="open"))
        self.path("MVP-02").write_text(ledger("MVP-02", status="open"))
        telemetry = self.root / ".project" / "telemetry"
        telemetry.mkdir()
        (telemetry / "codex-controller.json").write_text(json.dumps(
            {"run_id": "prior", "status": "stopped", "current_lane": "MVP-01"}))
        runner = self.root / "no-progress.py"
        runner.write_text(f"#!{sys.executable}\n"
                          "import pathlib, sys\n"
                          "root=pathlib.Path(sys.argv[sys.argv.index('--project-dir')+1])\n"
                          "name=sys.argv[sys.argv.index('--slice')+1]\n"
                          "with (root/'calls').open('a') as out: out.write(name+'\\n')\n")
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner)],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("ledger stalled", result.stdout)
        self.assertNotIn("closed with verified evidence", result.stdout)
        self.assertEqual((self.root / "calls").read_text().splitlines(),
                         ["MVP-01", "MVP-01", "MVP-02", "MVP-02"])

    def test_recovery_resumes_only_previous_in_progress_lane(self):
        self.path("R").write_text(ledger("R", status="in_progress"))
        (self.working / "slice-R-packet.md").write_text("R packet\n")
        telemetry = self.root / ".project" / "telemetry"
        telemetry.mkdir()
        (telemetry / "codex-controller.json").write_text(json.dumps(
            {"run_id": "prior", "status": "running", "current_lane": "R",
             "child_pid": None}))
        runner = self.root / "resume-runner.py"
        runner.write_text(f"#!{sys.executable}\n"
                          "import os, pathlib, sys\n"
                          "root=pathlib.Path(sys.argv[sys.argv.index('--project-dir')+1])\n"
                          "(root/'resume-seen').write_text(os.environ.get('PRAXIS_CODEX_RESUME',''))\n"
                          "path=root/'.project'/'working'/'slice-R-tasks.yaml'\n"
                          "s=path.read_text().replace('status: in_progress','status: done')\n"
                          "s=s.replace('state: open','state: closed')\n"
                          "s=s.replace('code_review: pending','code_review: pass')\n"
                          "s=s.replace('qa: pending','qa: pass')\n"
                          "files={k:f'.project/working/R-{k}.md' for k in "
                          "('code_review','qa','tests','acceptance','summary')}\n"
                          "for value in files.values(): (root/value).write_text('PASS\\n')\n"
                          "s+='closeout_evidence:\\n'+''.join(f'  {k}: {v}\\n' for k,v in files.items())\n"
                          "path.write_text(s)\n")
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner)],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "resume-seen").read_text(), "1")
        self.assertIn("recovering interrupted run prior", result.stdout)

    def test_heartbeat_is_visible_while_child_is_silent(self):
        self.path("H").write_text(ledger("H", status="open"))
        runner = self.root / "silent-runner.py"
        runner.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(0.45)\n")
        env = {**os.environ, "PRAXIS_CODEX_HEARTBEAT_SECONDS": "0.1"}
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner),
                                 "--max-iterations", "1"],
                                env=env, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 4)
        self.assertIn("H still running; checkpoint", result.stdout)

    def test_recovery_refuses_to_duplicate_live_child(self):
        self.path("R").write_text(ledger("R", status="in_progress"))
        telemetry = self.root / ".project" / "telemetry"
        telemetry.mkdir()
        (telemetry / "codex-controller.json").write_text(json.dumps(
            {"run_id": "prior", "status": "running", "current_lane": "R",
             "child_pid": os.getpid()}))
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--dry-run"],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 5)
        self.assertIn("still active", result.stdout)

    def test_interrupted_closeout_repair_can_resume(self):
        self.path("R").write_text(ledger("R", state="closed")
                                  .replace("code_review: pending", "code_review: pass")
                                  .replace("qa: pending", "qa: pass"))
        (self.working / "slice-R-packet.md").write_text("R packet\n")
        telemetry = self.root / ".project" / "telemetry"
        telemetry.mkdir()
        (telemetry / "codex-controller.json").write_text(json.dumps(
            {"run_id": "prior", "status": "repairing", "current_lane": "R",
             "child_pid": None}))
        runner = self.fake_runner()
        result = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "codex_drive.py"),
                                 "--project-dir", str(self.root), "--runner", str(runner)],
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("closeout repair recovered and verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
