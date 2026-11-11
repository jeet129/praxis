#!/usr/bin/env python3
"""Small, dependency-free reader for Codex slice ledgers and closeout evidence."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

TASK_STATUSES = {"open", "in_progress", "done", "failed", "blocked"}
SAFE_STATUS_ALIASES = {"pending": "open", "not_started": "open",
                       "completed": "done", "complete": "done",
                       "in-progress": "in_progress"}
INFORMATIONAL_FLAGS = {"governance_gate_pending"}
GLOBAL_FLAGS = {"budget_exceeded"}
CLOSED_STATES = {"closed", "closed_with_caveats"}
PARKED_STATES = {"parked", "paused", "deferred"}


def unquote(value: str) -> str:
    quote = None
    for i, char in enumerate(value):
        if char in ('"', "'"):
            quote = None if quote == char else char if quote is None else quote
        elif char == "#" and quote is None:
            value = value[:i]
            break
    value = value.strip()
    return value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'") else value


def inline_list(value: str) -> list[str]:
    value = unquote(value)
    if value in ("", "null", "~", "[]"):
        return []
    if value.startswith("[") and value.endswith("]"):
        return [unquote(item) for item in value[1:-1].split(",") if unquote(item)]
    return [value]


@dataclass
class Ledger:
    path: Path
    top: dict[str, str] = field(default_factory=dict)
    tasks: list[dict[str, str]] = field(default_factory=list)
    gates: dict[str, str] = field(default_factory=dict)
    evidence: dict[str, str] = field(default_factory=dict)
    stop_flags: list[str] = field(default_factory=list)

    @property
    def slice_id(self) -> str:
        return self.top.get("slice", self.path.name.removeprefix("slice-").removesuffix("-tasks.yaml"))

    @property
    def state(self) -> str:
        return self.top.get("state", "open").lower()

    @property
    def normalized_state(self) -> str:
        if self.state in CLOSED_STATES:
            return "closed"
        if self.state in PARKED_STATES:
            return "parked"
        if self.top.get("local_acceptance_met", "").lower() == "true":
            return "local_accepted"
        if self.tasks and all(self.task_status(t) == "done" for t in self.tasks):
            return "draining"
        return "open"

    @staticmethod
    def task_status(task: dict[str, str]) -> str:
        raw = task.get("status", "open").lower()
        return SAFE_STATUS_ALIASES.get(raw, raw)

    @property
    def unknown_statuses(self) -> list[str]:
        return [f"{t.get('id', '?')}={t.get('status', '?')}" for t in self.tasks
                if self.task_status(t) not in TASK_STATUSES]

    @property
    def blocking_flags(self) -> list[str]:
        return [flag for flag in self.stop_flags if flag not in INFORMATIONAL_FLAGS]

    @property
    def done_count(self) -> int:
        return sum(self.task_status(t) == "done" for t in self.tasks)

    def next_task(self) -> dict[str, str] | None:
        done_ids = {t.get("id") for t in self.tasks if self.task_status(t) == "done"}
        for task in self.tasks:
            if self.task_status(task) != "open":
                continue
            if unquote(task.get("verify", "")) in ("", "null", "~", "None"):
                continue
            if all(dep in done_ids for dep in inline_list(task.get("depends_on", "[]"))):
                return task
        return None

    @property
    def in_progress(self) -> list[dict[str, str]]:
        return [t for t in self.tasks if self.task_status(t) == "in_progress"]

    def lane(self) -> str:
        if self.unknown_statuses:
            return "schema_blocked"
        if self.normalized_state == "parked":
            return "parked"
        if self.normalized_state == "closed":
            if self.top.get("schema_version") == "2" and self.blocking_flags:
                return "gated"
            return "closed"
        if self.blocking_flags:
            return "gated" if not any(f in GLOBAL_FLAGS for f in self.blocking_flags) else "global_stop"
        if self.normalized_state == "local_accepted":
            return "local_accepted"
        if self.next_task():
            return "ready"
        if self.in_progress:
            return "resume"
        if self.tasks and self.done_count == len(self.tasks):
            return "drain"
        return "blocked"

    def reason(self) -> str:
        lane = self.lane()
        if lane == "schema_blocked":
            return "unknown task status: " + ", ".join(self.unknown_statuses)
        if lane in ("gated", "global_stop"):
            return "stop_flags: " + ", ".join(self.blocking_flags)
        if lane == "blocked":
            return "no eligible task; check dependencies, verify commands and failed tasks"
        if lane == "local_accepted":
            return self.state
        return lane

    def digest(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def read_ledger(path: Path) -> Ledger:
    ledger = Ledger(path=path)
    section = ""
    current_task = None
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            match = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", raw)
            if not match:
                continue
            key, value = match.groups()
            section = key if not unquote(value) else ""
            if key == "stop_flags":
                ledger.stop_flags = inline_list(value)
            else:
                ledger.top[key] = unquote(value)
            current_task = None
            continue
        if section == "tasks":
            match = re.match(r"^  - id:\s*(.*)$", raw)
            if match:
                current_task = {"id": unquote(match.group(1))}
                ledger.tasks.append(current_task)
                continue
            match = re.match(r"^    ([\w-]+):\s*(.*)$", raw)
            if current_task is not None and match:
                key, value = match.groups()
                if key in {"status", "verify", "depends_on", "agent", "tier", "attempts"}:
                    current_task[key] = unquote(value)
        elif section in ("gates", "closeout_evidence"):
            match = re.match(r"^  ([\w-]+):\s*(.*)$", raw)
            if match:
                key, value = match.groups()
                (ledger.gates if section == "gates" else ledger.evidence)[key] = unquote(value)
        elif section == "stop_flags":
            match = re.match(r"^  -\s*(.*)$", raw)
            if match:
                ledger.stop_flags.append(unquote(match.group(1)))
    return ledger


def verdict(value: str) -> str:
    v = value.strip().lower().replace("-", "_")
    if v in ("n/a", "na", "not_applicable") or v.startswith("n/a"):
        return "n/a"
    if any(token in v for token in ("pending", "provisional", "re_review", "re-review")):
        return "pending"
    if any(token in v for token in ("request_changes", "block", "reject", "hold", "red")) or v.startswith("fail"):
        return "fail"
    if v.startswith(("pass", "approve", "accept", "clear", "green")):
        return "pass"
    return "unknown"


def evidence_path(root: Path, value: str) -> Path | None:
    if not value or value in ("null", "~"):
        return None
    candidate = Path(value)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
        return resolved
    except ValueError:
        return None


def evidence_passes(path: Path) -> bool:
    """Require an explicit verdict near the start, not just a file's presence."""
    try:
        lines = path.read_text(errors="replace").splitlines()[:20]
    except OSError:
        return False
    positive = re.compile(r"^(PASS|PASSED|APPROVE|APPROVED|ACCEPT|ACCEPTED|CLEAR|GREEN)(?:\b|_)", re.I)
    for line in lines:
        marker = re.match(r"^\s*(?:verdict|result|status):\s*(.*)$", line, re.I)
        if marker:
            return bool(positive.match(marker.group(1)))
    for line in lines[:3]:
        if positive.match(line.strip()):
            return True
    return False


def closeout_errors(root: Path, ledger: Ledger, *, local: bool = False) -> list[str]:
    errors: list[str] = []
    if not ledger.tasks or ledger.done_count != len(ledger.tasks):
        errors.append("implementation tasks are not all done")
    packet = evidence_path(root, ledger.top.get("packet", ""))
    if packet is None or not packet.is_file() or packet.stat().st_size == 0:
        errors.append("slice packet is missing")
    required = ["code_review", "qa"]
    for key in ("security_review", "visual_review"):
        if key in ledger.gates and verdict(ledger.gates[key]) != "n/a":
            required.append(key)
    for key in required:
        gate = verdict(ledger.gates.get(key, ""))
        if gate != "pass":
            errors.append(f"{key} verdict is {gate}")
            continue
        path = evidence_path(root, ledger.evidence.get(key, ""))
        if path is None or not path.is_file():
            errors.append(f"{key} evidence file is missing")
        elif not evidence_passes(path):
            errors.append(f"{key} evidence has no explicit pass verdict")
    for key in ("tests", "acceptance"):
        path = evidence_path(root, ledger.evidence.get(key, ""))
        if path is None or not path.is_file():
            errors.append(f"{key} evidence file is missing")
        elif not evidence_passes(path):
            errors.append(f"{key} evidence has no explicit pass verdict")
    if not local:
        summary = evidence_path(root, ledger.evidence.get("summary", ""))
        if summary is None or not summary.is_file() or summary.stat().st_size == 0:
            errors.append("slice-close summary is missing")
    return errors


def index_record(root: Path, ledger: Ledger) -> dict:
    lane = ledger.lane()
    version = ledger.top.get("schema_version", "1")
    audit = "verified_schema" if version == "2" or ledger.evidence else "legacy_unverified"
    return {"slice": ledger.slice_id, "state": ledger.state,
            "normalized_state": ledger.normalized_state, "lane": lane,
            "closeout_audit": audit,
            "local_acceptance_met": ledger.top.get("local_acceptance_met", "").lower() == "true",
            "merged_shippable": ledger.top.get("merged_shippable", "").lower() == "true",
            "tasks_done": ledger.done_count, "tasks_total": len(ledger.tasks),
            "next_task": (ledger.next_task() or {}).get("id"),
            "stop_flags": ledger.stop_flags, "reason": ledger.reason(),
            "closeout_errors": closeout_errors(root, ledger, local=lane == "local_accepted")
            if audit == "verified_schema" and lane in ("closed", "local_accepted") else []}


def migrate_safe(path: Path) -> list[str]:
    """Migrate only unambiguous task aliases; save the original once."""
    source = path.read_text()
    changes = []
    for old, new in SAFE_STATUS_ALIASES.items():
        pattern = re.compile(rf"^([ ]{{4}}status:[ \t]*){re.escape(old)}([ \t]*(?:#.*)?)$", re.M | re.I)
        if pattern.search(source):
            source = pattern.sub(lambda match: match.group(1) + new + match.group(2), source)
            changes.append(f"{old}->{new}")
    if changes:
        backup = path.with_suffix(path.suffix + ".codex-pre-migration.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(source)
    return changes


def write_index(root: Path, ledgers: list[Ledger]) -> Path:
    target = root / ".project" / "working" / "codex-active-index.json"
    payload = {"schema_version": 1, "lanes": [index_record(root, ledger) for ledger in ledgers]}
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2) + "\n")
    temp.replace(target)
    return target
