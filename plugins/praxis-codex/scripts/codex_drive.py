#!/usr/bin/env python3
"""Codex-only, resumable controller for independent Praxis slice lanes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import select
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from codex_state import (GLOBAL_FLAGS, Ledger, closeout_errors, inline_list,
                         migrate_safe, read_ledger, write_index)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from project_root import check_writable, find_project_root, missing_agents

READY = {"ready", "resume", "drain"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".codex-controller-", delete=False) as out:
        json.dump(payload, out, indent=2)
        out.write("\n")
        temporary = out.name
    os.replace(temporary, path)


def budget(root: Path, plugin: Path) -> dict:
    path = root / ".project" / "governance" / "autonomy.yaml"
    if not path.is_file():
        path = plugin / "governance" / "autonomy.yaml"
    result = {"stop_after": "gate", "max_iterations_per_run": 40,
              "max_slices_per_run": 3, "cost_ceiling_proxy": 120.0,
              "max_iterations_without_ledger_change": 2}
    section = ""
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            key, _, value = raw.partition(":")
            section = key.strip() if not value.strip() else ""
            if key.strip() == "stop_after":
                result["stop_after"] = value.split("#", 1)[0].strip()
        elif section in ("run_budget", "stall"):
            key, _, value = raw.strip().partition(":")
            if key in result and value.strip():
                result[key] = float(value.split("#", 1)[0].strip()) if key == "cost_ceiling_proxy" else int(value.split("#", 1)[0].strip())
    return result


def read_ledgers(root: Path, migrate: bool = False) -> list[Ledger]:
    paths = sorted((root / ".project" / "working").glob("slice-*-tasks.yaml"))
    if migrate:
        for path in paths:
            changes = migrate_safe(path)
            if changes:
                print(f"[praxis] migrated safe status aliases in {path.name}: {', '.join(changes)}", flush=True)
    return [read_ledger(path) for path in paths]


def dependency_ready(ledger: Ledger, by_id: dict[str, Ledger],
                     gated_boundary: set[str]) -> bool:
    """Declared dependencies must be closed; cross a new gate explicitly."""
    raw = ledger.top.get("depends_on_slices")
    if raw is None:
        return not gated_boundary
    for dep in inline_list(raw):
        if dep in gated_boundary or dep not in by_id or by_id[dep].normalized_state != "closed":
            return False
    return True


def choose_lane(ledgers: list[Ledger], preferred: str | None,
                excluded: set[str], resumable: set[str] | None = None,
                gated_boundary: set[str] | None = None) -> Ledger | None:
    resumable = resumable or set()
    blocked = gated_boundary or set()
    by_id = {ledger.slice_id: ledger for ledger in ledgers}
    candidates = [ledger for ledger in ledgers if ledger.lane() in READY
                  and (ledger.lane() != "resume" or ledger.slice_id in resumable)
                  and ledger.slice_id not in excluded
                  and dependency_ready(ledger, by_id, blocked)]
    if preferred:
        selected = next((ledger for ledger in candidates if ledger.slice_id == preferred), None)
        if selected:
            return selected
    return max(candidates, key=lambda item: (item.path.stat().st_mtime, item.slice_id)) if candidates else None


def latest_cost(root: Path, previous_size: int) -> float:
    path = root / ".project" / "telemetry" / "drive.jsonl"
    if not path.is_file() or path.stat().st_size <= previous_size:
        return 1.0
    with path.open("rb") as fh:
        fh.seek(previous_size)
        lines = fh.read().decode(errors="replace").splitlines()
    for line in reversed(lines):
        try:
            obj = json.loads(line)
            if obj.get("harness") == "codex":
                return float(obj.get("cost_proxy", 1.0))
        except (ValueError, TypeError):
            continue
    return 1.0


class Controller:
    def __init__(self, root: Path, runner: Path, *, dry_run: bool = False,
                 max_iterations: int | None = None, slice_id: str | None = None):
        self.root = root
        self.runner = runner
        self.slice_id = slice_id
        self.dry_run = dry_run
        self.config = budget(root, runner.parent.parent)
        if max_iterations is not None:
            self.config["max_iterations_per_run"] = max_iterations
        self.checkpoint_path = root / ".project" / "telemetry" / "codex-controller.json"
        self.checkpoint = json.loads(self.checkpoint_path.read_text()) if self.checkpoint_path.is_file() else {}
        self.previous_run_id = self.checkpoint.get("run_id")
        self.repairing = self.checkpoint.get("status") == "repairing"
        self.recovering = self.checkpoint.get("status") in ("running", "repairing")
        self.run_id = "codex-" + uuid.uuid4().hex[:12]
        self.current_lane = self.checkpoint.get("current_lane")
        self.resumable = {self.current_lane} if self.recovering and self.current_lane else set()
        if slice_id:
            self.resumable.add(slice_id)
        self.child_pid: int | None = None
        self.iterations = 0
        self.closed = 0
        self.cost = 0.0
        self.excluded: set[str] = set()
        self.failures: dict[str, str] = {}
        self.gated_boundaries: set[str] = set()
        self.stalls: dict[str, int] = {}

    def persist(self, status: str, *, lane: str = "", task: str = "", reason: str = "") -> None:
        self.checkpoint = {"schema_version": 1, "run_id": self.run_id,
                           "previous_run_id": self.previous_run_id,
                           "pid": os.getpid(), "child_pid": self.child_pid,
                           "updated_at": utc_now(),
                           "status": status, "current_lane": lane or self.current_lane,
                           "task": task, "iteration": self.iterations,
                           "slices_closed": self.closed, "cost_proxy": self.cost,
                           "excluded_lanes": sorted(self.excluded),
                           "failures": self.failures,
                           "gated_boundaries": sorted(self.gated_boundaries),
                           "reason": reason}
        if not self.dry_run:
            save_json(self.checkpoint_path, self.checkpoint)

    def invoke(self, lane: Ledger, *, repair: bool = False) -> int:
        env = dict(os.environ)
        env["PRAXIS_CODEX_CONTROLLER"] = "1"
        env["PRAXIS_CODEX_ONE_ITERATION"] = "1"
        if lane.lane() == "resume":
            env["PRAXIS_CODEX_RESUME"] = "1"
        if repair:
            env["PRAXIS_CODEX_CLOSEOUT_REPAIR"] = "1"
        executable = [sys.executable, str(self.runner)] if self.runner.suffix == ".py" else ["bash", str(self.runner)]
        command = [*executable, "--project-dir", str(self.root),
                   "--harness", "codex", "--slice", lane.slice_id]
        if self.dry_run:
            print("[dry-run] " + " ".join(command), flush=True)
            return 0
        process = subprocess.Popen(command, cwd=self.root, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
        self.child_pid = process.pid
        self.persist("running", lane=lane.slice_id,
                     task=(lane.next_task() or {}).get("id", "slice-drain"))
        last_notice = time.monotonic()
        heartbeat = max(0.1, float(os.environ.get("PRAXIS_CODEX_HEARTBEAT_SECONDS", "60")))
        while process.poll() is None:
            ready, _, _ = select.select([process.stdout], [], [], min(heartbeat, 30))
            if ready:
                line = process.stdout.readline()
                if line:
                    print(line, end="", flush=True)
            self.persist("running", lane=lane.slice_id,
                         task=(lane.next_task() or {}).get("id", "slice-drain"))
            if time.monotonic() - last_notice >= heartbeat:
                print(f"[praxis] {lane.slice_id} still running; checkpoint {self.checkpoint_path}", flush=True)
                last_notice = time.monotonic()
        for line in process.stdout:
            print(line, end="", flush=True)
        self.child_pid = None
        return process.returncode

    def run(self) -> int:
        if self.recovering:
            old_child = self.checkpoint.get("child_pid")
            if isinstance(old_child, int):
                try:
                    os.kill(old_child, 0)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    print(f"[praxis] previous child process {old_child} may still be active; refusing duplicate run", flush=True)
                    return 5
                else:
                    print(f"[praxis] previous child process {old_child} is still active; refusing duplicate run", flush=True)
                    return 5
            print(f"[praxis] recovering interrupted run {self.previous_run_id}; "
                  f"rechecking lane {self.current_lane}", flush=True)
        if self.repairing and self.current_lane:
            path = self.root / ".project" / "working" / f"slice-{self.current_lane}-tasks.yaml"
            if path.is_file():
                lane = read_ledger(path)
                if lane.normalized_state == "closed":
                    telemetry = self.root / ".project" / "telemetry" / "drive.jsonl"
                    old_size = telemetry.stat().st_size if telemetry.is_file() else 0
                    code = self.invoke(lane, repair=True)
                    if self.dry_run:
                        return self.finish("dry run: interrupted closeout repair", 0)
                    self.iterations += 1
                    self.cost += latest_cost(self.root, old_size)
                    after = read_ledger(path)
                    errors = closeout_errors(self.root, after)
                    if after.normalized_state != "closed" or after.blocking_flags:
                        errors.append("slice is not in an ungated closed state")
                    if code != 0 or errors:
                        self.excluded.add(lane.slice_id)
                        self.failures[lane.slice_id] = "; ".join(errors) or f"repair exited {code}"
                    else:
                        self.excluded.add(lane.slice_id)
                        self.closed += 1
                        print(f"[praxis] {lane.slice_id} closeout repair recovered and verified", flush=True)
                        if self.config["stop_after"] == "slice":
                            return self.finish(f"stop_after=slice: {lane.slice_id} closed", 0)
        while self.iterations < self.config["max_iterations_per_run"]:
            ledgers = read_ledgers(self.root, migrate=not self.dry_run)
            if not self.dry_run:
                write_index(self.root, ledgers)
            if self.slice_id:
                ledgers = [ledger for ledger in ledgers if ledger.slice_id == self.slice_id]
            if self.recovering and self.current_lane:
                current = next((item for item in ledgers if item.slice_id == self.current_lane), None)
                if current and current.lane() == "gated":
                    self.gated_boundaries.add(current.slice_id)
            if any(ledger.lane() == "global_stop" for ledger in ledgers):
                flags = [f"{ledger.slice_id}: {ledger.reason()}" for ledger in ledgers if ledger.lane() == "global_stop"]
                return self.finish("global stop: " + "; ".join(flags), 4)
            lane = choose_lane(ledgers, self.current_lane, self.excluded,
                               self.resumable, self.gated_boundaries)
            if lane is None:
                reasons = [f"{ledger.slice_id}: {ledger.reason()}" for ledger in ledgers
                           if ledger.lane() not in ("closed", "parked")]
                reasons.extend(f"{slice_id}: {reason}" for slice_id, reason in self.failures.items())
                if self.gated_boundaries and any(ledger.lane() in READY for ledger in ledgers):
                    reasons.append("ready lanes need explicit depends_on_slices to cross this run's gate")
                if not ledgers:
                    return self.finish("no slice ledgers found", 2)
                return self.finish("no ready lane; " + ("; ".join(reasons) or "all lanes closed"),
                                   0 if not self.failures and all(ledger.lane() in ("closed", "local_accepted", "gated", "parked") for ledger in ledgers) else 5)
            self.current_lane = lane.slice_id
            before = lane.digest()
            telemetry = self.root / ".project" / "telemetry" / "drive.jsonl"
            old_size = telemetry.stat().st_size if telemetry.is_file() else 0
            print(f"[praxis] {lane.slice_id}: {lane.lane()} "
                  f"({lane.done_count}/{len(lane.tasks)} tasks)", flush=True)
            self.persist("running", lane=lane.slice_id,
                         task=(lane.next_task() or {}).get("id", "slice-drain"))
            code = self.invoke(lane)
            if self.dry_run:
                return self.finish("dry run: selected " + lane.slice_id, 0)
            self.iterations += 1
            self.resumable.add(lane.slice_id)
            self.cost += latest_cost(self.root, old_size)
            after = read_ledger(lane.path)
            if any(flag in GLOBAL_FLAGS for flag in after.blocking_flags):
                return self.finish(f"global stop from {lane.slice_id}: {after.reason()}", 4)
            if after.blocking_flags:
                self.gated_boundaries.add(lane.slice_id)
                self.excluded.add(lane.slice_id)
                print(f"[praxis] {lane.slice_id} stopped at {after.reason()}; "
                      "checking declared independent lanes", flush=True)
            elif code != 0:
                self.excluded.add(lane.slice_id)
                self.failures[lane.slice_id] = f"runner exited {code}"
                print(f"[praxis] {lane.slice_id} runner exited {code}; checking other lanes", flush=True)
            elif after.normalized_state in ("closed", "local_accepted"):
                local = after.normalized_state == "local_accepted"
                errors = closeout_errors(self.root, after, local=local)
                if errors and after.normalized_state == "closed":
                    if self.iterations >= self.config["max_iterations_per_run"]:
                        return self.finish(f"budget reached before closeout repair for {lane.slice_id}: "
                                           + "; ".join(errors), 4)
                    if self.cost >= self.config["cost_ceiling_proxy"]:
                        return self.finish(f"cost proxy budget reached before closeout repair for {lane.slice_id}", 4)
                    print(f"[praxis] {lane.slice_id} closeout evidence incomplete: " + "; ".join(errors), flush=True)
                    self.persist("repairing", lane=lane.slice_id, reason="; ".join(errors))
                    repair_size = telemetry.stat().st_size if telemetry.is_file() else 0
                    repair_code = self.invoke(after, repair=True)
                    self.iterations += 1
                    self.cost += latest_cost(self.root, repair_size)
                    after = read_ledger(lane.path)
                    errors = closeout_errors(self.root, after, local=False)
                    if after.normalized_state != "closed":
                        errors.append("slice state is not closed after repair")
                    if after.blocking_flags:
                        errors.append(after.reason())
                        self.gated_boundaries.add(lane.slice_id)
                    if repair_code != 0 or errors:
                        self.excluded.add(lane.slice_id)
                        failure = "; ".join(errors) or f"repair exited {repair_code}"
                        self.failures[lane.slice_id] = failure
                        print(f"[praxis] {lane.slice_id} closeout blocked: {failure}", flush=True)
                elif errors:
                    self.excluded.add(lane.slice_id)
                    self.failures[lane.slice_id] = "; ".join(errors)
                    print(f"[praxis] {lane.slice_id} local acceptance evidence incomplete: " + "; ".join(errors), flush=True)
                if not errors:
                    self.excluded.add(lane.slice_id)
                    if local:
                        print(f"[praxis] {lane.slice_id} locally accepted; delivery remains pending", flush=True)
                    else:
                        self.closed += 1
                        print(f"[praxis] {lane.slice_id} closed with verified evidence", flush=True)
                        if self.config["stop_after"] == "slice":
                            return self.finish(f"stop_after=slice: {lane.slice_id} closed", 0)
            elif before == after.digest():
                self.stalls[lane.slice_id] = self.stalls.get(lane.slice_id, 0) + 1
                if self.stalls[lane.slice_id] >= self.config["max_iterations_without_ledger_change"]:
                    self.excluded.add(lane.slice_id)
                    self.failures[lane.slice_id] = "ledger stalled"
                    print(f"[praxis] {lane.slice_id} stalled; checking other lanes", flush=True)
            else:
                self.stalls[lane.slice_id] = 0
            if self.cost >= self.config["cost_ceiling_proxy"]:
                return self.finish("cost proxy budget reached", 4)
            if self.closed >= self.config["max_slices_per_run"]:
                return self.finish("max_slices_per_run reached", 4)
            if self.config["stop_after"] == "task":
                return self.finish("stop_after=task boundary", 0)
        return self.finish("max_iterations_per_run reached", 4)

    def finish(self, reason: str, code: int) -> int:
        if not self.dry_run:
            write_index(self.root, read_ledgers(self.root))
        self.persist("stopped", reason=reason)
        print(f"[praxis] stopped: {reason}; iterations={self.iterations}, "
              f"closed={self.closed}, cost_proxy={self.cost:.2f}", flush=True)
        return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--runner", type=Path, default=Path(__file__).resolve().parent / "praxis-drive.sh")
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--slice", help="Drive only this slice (used by workflow mode)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--json", action="store_true", help="Full JSON output for --audit")
    args = parser.parse_args()
    root = find_project_root(args.project_dir)
    if root is None:
        print("Praxis Codex: no ancestor has .project/working", file=sys.stderr)
        return 2
    if args.audit:
        from codex_state import index_record
        ledgers = read_ledgers(root)
        if args.json:
            print(json.dumps({"lanes": [index_record(root, ledger) for ledger in ledgers]}, indent=2))
        else:
            counts = Counter(ledger.lane() for ledger in ledgers)
            print("Praxis Codex lanes: " + ", ".join(f"{name}={count}" for name, count in sorted(counts.items())))
            active = [ledger for ledger in ledgers if ledger.lane() not in ("closed", "parked")]
            for ledger in sorted(active, key=lambda item: item.path.stat().st_mtime, reverse=True)[:15]:
                print(f"  {ledger.slice_id}: {ledger.lane()} "
                      f"{ledger.done_count}/{len(ledger.tasks)} tasks; {ledger.reason()[:120]}")
            if len(active) > 15:
                print(f"  … {len(active) - 15} more active lanes; use --audit --json for all")
        return 0
    missing = missing_agents(root)
    if missing:
        print("Praxis Codex: missing profiles: " + ", ".join(missing), file=sys.stderr)
        return 3
    try:
        check_writable(root)
    except RuntimeError as exc:
        print(f"Praxis Codex: {exc}", file=sys.stderr)
        return 4
    lock_path = root / ".project" / "working" / "codex-controller.lock"
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Praxis Codex: another controller is already running", file=sys.stderr)
            return 5
        return Controller(root, args.runner.resolve(), dry_run=args.dry_run,
                          max_iterations=args.max_iterations, slice_id=args.slice).run()


if __name__ == "__main__":
    raise SystemExit(main())
