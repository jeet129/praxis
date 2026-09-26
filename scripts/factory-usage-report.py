#!/usr/bin/env python3
"""Mine mandatory workflow artifacts into a factory usage-analytics report.

Why this script exists: the original usage-analytics approach relied on
per-event stub files under `.project/operational/factory-metrics/` written by
hooks (`read` / `preload` / session stubs). Real-world capture ratio for that
approach proved to be roughly 5% — plugin-injected skills never fire a `Read`
event, and main-session orchestration (no sub-agent Task spawn) produces no
Task events either. The tap has since been slimmed: read/preload/session
stubs are retired; command invocations are still recorded as stubs; sessions
now write one JSONL line each. This script replaces the retired capture with
a MINING approach: it reads the artifacts every workflow is already required
to produce, rather than depending on a tool-event side channel.

Reads (all optional, all fail-soft):
  <project>/.project/episodic/checkpoint-*.md              — PRIMARY. The
      universal aggregation record written at every closure boundary
      (gate/phase/slice/loop/disposition/workflow-end). See
      references/factory-metrics-schema.md, "Checkpoint records" section.
  <project>/.project/working/slice-*-packet.md
  <project>/.project/working/slice-*-tasks.yaml             — skills named
      (grepped against this library's own skills/ directory listing) and
      agents assigned per task.
  <project>/.project/working/routing-*.md                   — dispatch
      records + routing frontmatter (parsing approach mirrors, but does not
      import, scripts/factory-routing-report.py — this script stays
      standalone).
  <project>/.project/operational/factory-metrics/commands/** — command
      invocation stubs (still produced by the tap).
  <project>/.project/telemetry/sessions.jsonl                — session
      counts/span (one line per session_start/session_end).
  <project>/.project/operational/factory-metrics/** (excluding commands/)
      — legacy stub layer (skill/agent/hook/workflow/gate/reference stubs);
      counted and labeled, not treated as primary evidence.

Usage:
  scripts/factory-usage-report.py [--project-dir PATH] [--format md|json] [--out PATH]

  --project-dir  Project root OR a .project directory directly. Default: cwd.
  --format       md (default) or json.
  --out          Output path. Default (md):
                  <project>/.project/telemetry/reports/usage-report-<YYYY-MM-DD>.md
                  Default (json): stdout only, unless --out is given.

Zero dependencies beyond the Python 3 standard library. Every ingestion step
is wrapped to fail soft — a missing or malformed source degrades the
relevant section of the report, it never crashes the script.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

LIB_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = LIB_ROOT / "skills"
AGENTS_DIR = LIB_ROOT / "agents"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
DISPATCH_HEADING_RE = re.compile(r"^##\s*Dispatch(?:ed)?\s*\d*\s*[:—-]\s*(.+)$", re.M)
GATE_KIND_RE = re.compile(r"gate-(security|code|qa)", re.I)
CHECKPOINT_FILE_RE = re.compile(r"^checkpoint-(\d{8})-(\d{4})-(.+)\.md$")


# --------------------------------------------------------------------------
# Project-dir resolution (same convention as factory-routing-report.py)
# --------------------------------------------------------------------------

def resolve_project_dot_dir(path: Path) -> Path:
    """Accept either a project root or a .project dir directly."""
    if (path / ".project").is_dir():
        return path / ".project"
    markers = ("working", "operational", "telemetry", "episodic")
    if path.name == ".project" or any((path / m).exists() for m in markers):
        return path
    return path / ".project"


# --------------------------------------------------------------------------
# Known-artifact discovery (from THIS library, resolved relative to the
# script's own location — not the target project — so the report works
# against any project directory regardless of where its .project/ lives).
# --------------------------------------------------------------------------

def load_known_skills(skills_dir: Path) -> list[str]:
    if not skills_dir.is_dir():
        return []
    return sorted(p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def load_known_agents(agents_dir: Path) -> list[str]:
    if not agents_dir.is_dir():
        return []
    return sorted(p.stem for p in agents_dir.glob("*.md"))


# --------------------------------------------------------------------------
# Generic tolerant YAML-ish frontmatter parsing
#
# Handles: flat scalars ("key: value"), inline flow lists/dicts
# ("key: [a, b]", "key: {a: 1, b: 2}"), and two-space-indented block lists
# ("key:\n  - value" or "key:\n  - {a: 1, b: 2}") — the two forms the
# checkpoint schema (references/factory-metrics-schema.md) actually uses for
# agents_dispatched / skills_consumed / artifacts_produced.
# --------------------------------------------------------------------------

def parse_flow_list(raw: str) -> list:
    s = raw.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    items, depth, cur = [], 0, ""
    for ch in s:
        if ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    out = []
    for it in items:
        it = it.strip()
        if it.startswith("{") and it.endswith("}"):
            out.append(parse_flow_map(it))
        else:
            out.append(it.strip("\"'"))
    return out


def parse_flow_map(raw: str) -> dict:
    s = raw.strip()
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    d = {}
    for part in s.split(","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        d[k.strip()] = v.strip().strip("\"'")
    return d


def parse_frontmatter_tolerant(text: str) -> tuple[dict, str]:
    """Flat + list-tolerant frontmatter parser.

    Returns (fields, body). `fields` values are either strings, or lists
    (of strings and/or dicts) for keys that used a block/flow list form.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict = {}
    current_list_key = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if top and not line.startswith((" ", "\t")):
            key, val = top.group(1), top.group(2).strip()
            if val == "":
                fm[key] = []
                current_list_key = key
            elif val.startswith("[") and val.endswith("]"):
                fm[key] = parse_flow_list(val)
                current_list_key = None
            else:
                fm[key] = val.strip("\"'")
                current_list_key = None
            continue
        if current_list_key is not None and line.strip().startswith("- "):
            item = line.strip()[2:].strip()
            if item.startswith("{") and item.endswith("}"):
                fm[current_list_key].append(parse_flow_map(item))
            else:
                fm[current_list_key].append(item.strip("\"'"))
    return fm, m.group(2)


def as_list(fm: dict, key: str) -> list:
    v = fm.get(key)
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# --------------------------------------------------------------------------
# (a) Checkpoint records — PRIMARY source
# --------------------------------------------------------------------------

def ingest_checkpoints(episodic_dir: Path) -> dict:
    out = {"files": 0, "records": [], "parse_errors": 0}
    if not episodic_dir.is_dir():
        return out
    paths = sorted(episodic_dir.glob("checkpoint-*.md"))
    out["files"] = len(paths)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            out["parse_errors"] += 1
            continue
        fm, body = parse_frontmatter_tolerant(text)
        if not fm or fm.get("type") != "checkpoint":
            out["parse_errors"] += 1
            continue
        m = CHECKPOINT_FILE_RE.match(path.name)
        file_date = None
        if m:
            file_date = f"{m.group(1)[0:4]}-{m.group(1)[4:6]}-{m.group(1)[6:8]}"
        agents_dispatched = []
        for item in as_list(fm, "agents_dispatched"):
            if isinstance(item, dict):
                try:
                    dispatches = int(re.sub(r"[^\d]", "", item.get("dispatches", "0")) or 0)
                except ValueError:
                    dispatches = 0
                agents_dispatched.append({
                    "agent": item.get("agent", "unknown"),
                    "tier": item.get("tier", "unknown"),
                    "dispatches": dispatches,
                })
        skills_consumed = [s for s in as_list(fm, "skills_consumed") if isinstance(s, str) and s]
        artifacts_produced = [s for s in as_list(fm, "artifacts_produced") if isinstance(s, str) and s]
        try:
            cost_proxy = float(fm.get("cost_proxy", 0) or 0)
        except ValueError:
            cost_proxy = 0.0
        try:
            human_touchpoints = int(re.sub(r"[^\d]", "", str(fm.get("human_touchpoints", "0"))) or 0)
        except ValueError:
            human_touchpoints = 0
        out["records"].append({
            "path": str(path),
            "file": path.name,
            "date": file_date,
            "boundary": fm.get("boundary", "unknown"),
            "workflow": fm.get("workflow", "n/a"),
            "phase": fm.get("phase", "n/a"),
            "gate": fm.get("gate", "n/a"),
            "verdict": fm.get("verdict", "n/a"),
            "slice": fm.get("slice", "n/a"),
            "agents_dispatched": agents_dispatched,
            "skills_consumed": skills_consumed,
            "artifacts_produced": artifacts_produced,
            "cost_proxy": cost_proxy,
            "human_touchpoints": human_touchpoints,
            "deviations": fm.get("deviations", "none"),
            "body": body.strip(),
        })
    return out


# --------------------------------------------------------------------------
# (b) Working packets / task ledgers — skill mentions + per-task agents
# --------------------------------------------------------------------------

def canonicalize_agent_raw(raw: str, known_agents: set) -> str:
    """Best-effort normalization: strip a 'praxis:' harness prefix, lowercase,
    collapse whitespace/underscores to hyphens. Returns the normalized form
    even if it doesn't match a known agent slug (caller decides how to
    treat unmatched agents)."""
    if not raw:
        return ""
    text = raw.strip()
    text = re.sub(r"^praxis:", "", text)
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    text = text.strip(" .:—-\"'")
    slug = re.sub(r"[\s_]+", "-", text.lower())
    return slug


def ingest_working_artifacts(working_dir: Path, known_skills: set, known_agents: set) -> dict:
    """Parses slice-*-packet.md and slice-*-tasks.yaml.

    Returns:
      packet_files, tasks_files: counts
      skill_mentions: [{skill, file, date, kind: 'packet'|'tasks'}]
      task_agents: [{agent, raw_agent, tier, file, date}]
    """
    out = {"packet_files": 0, "tasks_files": 0, "skill_mentions": [], "task_agents": []}
    if not working_dir.is_dir():
        return out

    packet_paths = sorted(working_dir.glob("slice-*-packet.md"))
    tasks_paths = sorted(working_dir.glob("slice-*-tasks.yaml"))
    out["packet_files"] = len(packet_paths)
    out["tasks_files"] = len(tasks_paths)

    skill_slug_re = {s: re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(s) + r"(?![A-Za-z0-9_-])") for s in known_skills}

    for path, kind in [(p, "packet") for p in packet_paths] + [(p, "tasks") for p in tasks_paths]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, _ = parse_frontmatter_tolerant(text)
        file_date = fm.get("created") or fm.get("date")
        for skill, pattern in skill_slug_re.items():
            if pattern.search(text):
                out["skill_mentions"].append({
                    "skill": skill, "file": path.name, "date": file_date, "kind": kind,
                })
        if kind == "tasks":
            for m in re.finditer(r"^\s*agent:\s*(.+?)\s*$", text, re.M):
                raw = m.group(1).strip()
                agent = canonicalize_agent_raw(raw, known_agents)
                # Grab the nearest preceding "tier:" on a following line, if present,
                # by a small forward window — tolerant, not a real YAML parse.
                tier = None
                tail = text[m.end():m.end() + 200]
                tier_m = re.search(r"^\s*tier:\s*(\S+)", tail, re.M)
                if tier_m:
                    tier = tier_m.group(1).strip()
                out["task_agents"].append({
                    "agent": agent, "raw_agent": raw, "tier": tier,
                    "file": path.name, "date": file_date,
                })
    return out


# --------------------------------------------------------------------------
# (c) Prose routing logs — dispatch records + routing frontmatter
#
# Parsing approach mirrors scripts/factory-routing-report.py's
# ingest_prose_routing, deliberately re-implemented (not imported) to keep
# this script standalone per house convention.
# --------------------------------------------------------------------------

def ingest_routing_logs(working_dir: Path, known_agents: set) -> dict:
    out = {"files": 0, "dispatches": [], "decisions": []}
    if not working_dir.is_dir():
        return out
    paths = sorted(working_dir.glob("routing-*.md"))
    out["files"] = len(paths)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, body = parse_frontmatter_tolerant(text)
        slice_id = fm.get("slice", "unknown")
        date = fm.get("date") or fm.get("created")
        fname = path.name

        if "routing" in fm and fm.get("agent"):
            out["decisions"].append({
                "agent": canonicalize_agent_raw(fm["agent"], known_agents) or fm["agent"],
                "chosen_tier": fm.get("chosen_tier"),
                "file": fname, "slice": slice_id, "date": date,
            })

        explicit_this_file = set()
        for m in DISPATCH_HEADING_RE.finditer(body):
            raw = m.group(1).strip()
            agent = canonicalize_agent_raw(raw, known_agents)
            if not agent:
                continue
            explicit_this_file.add(agent)
            out["dispatches"].append({
                "slice": slice_id, "agent": agent, "raw_agent": raw,
                "source": "explicit", "file": fname, "date": date,
            })

        gate_m = GATE_KIND_RE.search(fname)
        if gate_m:
            gate_kind = gate_m.group(1).lower()
            agent = {"security": "security-reviewer", "code": "code-reviewer", "qa": "qa-engineer"}[gate_kind]
            if agent not in explicit_this_file:
                out["dispatches"].append({
                    "slice": slice_id, "agent": agent, "raw_agent": f"gate-{gate_kind}",
                    "source": "inferred", "file": fname, "date": date,
                })
    return out


# --------------------------------------------------------------------------
# (d) Command invocation stubs + (f) legacy stub layer
# --------------------------------------------------------------------------

def ingest_factory_metrics_stubs(fm_dir: Path) -> dict:
    """Splits operational/factory-metrics/** into commands/ (still produced,
    treated as a real source) vs everything else (legacy: skill/agent/hook/
    workflow/gate/reference stubs — no longer receive read/preload/session
    records, counted and clearly labeled, not treated as primary evidence)."""
    out = {"commands": [], "legacy_count": 0, "legacy_by_type": Counter()}
    if not fm_dir.is_dir():
        return out
    commands_dir = fm_dir / "commands"
    if commands_dir.is_dir():
        for path in sorted(commands_dir.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm, _ = parse_frontmatter_tolerant(text)
            if not fm:
                continue
            out["commands"].append({
                "name": fm.get("artifact_name", path.parent.name),
                "date": fm.get("date", ""),
                "session": fm.get("session", ""),
                "outcome": fm.get("outcome", "null"),
                "file": str(path),
            })
    for type_dir in ("skills", "agents", "workflows", "hooks", "gates", "references"):
        base = fm_dir / type_dir
        if not base.is_dir():
            continue
        n = sum(1 for _ in base.rglob("*.md"))
        out["legacy_count"] += n
        out["legacy_by_type"][type_dir] = n
    return out


# --------------------------------------------------------------------------
# (e) Session telemetry
# --------------------------------------------------------------------------

def ingest_sessions(telemetry_dir: Path) -> dict:
    out = {"present": False, "events": 0, "sessions": set(), "min_ts": None, "max_ts": None}
    path = telemetry_dir / "sessions.jsonl"
    if not path.exists():
        return out
    out["present"] = True
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Harness-scoped: skip other-harness session rows (e.g.
                # antigravity session_stop) folded into the shared stream so
                # they do not inflate claude-code/codex session counts.
                if obj.get("harness") not in (None, "claude-code", "codex"):
                    continue
                out["events"] += 1
                sid = obj.get("session")
                if sid:
                    out["sessions"].add(sid)
                ts = obj.get("ts")
                if ts:
                    if out["min_ts"] is None or ts < out["min_ts"]:
                        out["min_ts"] = ts
                    if out["max_ts"] is None or ts > out["max_ts"]:
                        out["max_ts"] = ts
    except OSError:
        pass
    return out


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def build_report(project_dir: Path) -> dict:
    known_skills = set(load_known_skills(SKILLS_DIR))
    known_agents = set(load_known_agents(AGENTS_DIR))

    episodic_dir = project_dir / "episodic"
    working_dir = project_dir / "working"
    fm_dir = project_dir / "operational" / "factory-metrics"
    telemetry_dir = project_dir / "telemetry"

    checkpoints = ingest_checkpoints(episodic_dir)
    working = ingest_working_artifacts(working_dir, known_skills, known_agents)
    routing = ingest_routing_logs(working_dir, known_agents)
    stubs = ingest_factory_metrics_stubs(fm_dir)
    sessions = ingest_sessions(telemetry_dir)

    # ---- Data coverage ----------------------------------------------------
    coverage = {
        "checkpoints": {"present": checkpoints["files"] > 0, "files": checkpoints["files"],
                         "parsed": len(checkpoints["records"]), "parse_errors": checkpoints["parse_errors"]},
        "working_packets": {"present": working["packet_files"] > 0, "files": working["packet_files"]},
        "working_tasks": {"present": working["tasks_files"] > 0, "files": working["tasks_files"]},
        "routing_logs": {"present": routing["files"] > 0, "files": routing["files"],
                          "dispatch_records": len(routing["dispatches"])},
        "command_stubs": {"present": len(stubs["commands"]) > 0, "records": len(stubs["commands"])},
        "sessions_jsonl": {"present": sessions["present"], "events": sessions["events"],
                            "sessions": len(sessions["sessions"])},
        "legacy_stub_layer": {"present": stubs["legacy_count"] > 0, "records": stubs["legacy_count"],
                               "by_type": dict(stubs["legacy_by_type"])},
    }
    coverage_notes = []
    if checkpoints["files"] == 0:
        coverage_notes.append(
            "No .project/episodic/checkpoint-*.md files found — this is the primary "
            "usage source and it's empty. Either the project predates the checkpoint "
            "convention, or delivery-lead hasn't written one yet. Everything below "
            "falls back to secondary sources (packets, routing logs, command stubs), "
            "which is a materially weaker evidence base."
        )
    elif checkpoints["parse_errors"]:
        coverage_notes.append(
            f"{checkpoints['parse_errors']} file(s) under episodic/checkpoint-*.md "
            "didn't parse as valid checkpoint frontmatter (missing/garbled "
            "frontmatter, or type != checkpoint) — excluded from the counts below."
        )
    if working["packet_files"] == 0 and working["tasks_files"] == 0:
        coverage_notes.append("No .project/working/slice-*-packet.md or slice-*-tasks.yaml found.")
    if routing["files"] == 0:
        coverage_notes.append("No .project/working/routing-*.md prose dispatch logs found.")
    if not sessions["present"]:
        coverage_notes.append(
            "telemetry/sessions.jsonl is absent — engagement summary below has no "
            "session count/span."
        )
    if stubs["legacy_count"] > 0:
        coverage_notes.append(
            f"{stubs['legacy_count']} legacy factory-metrics stub(s) found under "
            f"skills/agents/hooks/workflows/gates/references — these predate the "
            "capture slimdown (read/preload/session stubs retired) and are counted "
            "for continuity only, not treated as current usage evidence."
        )
    if len(stubs["commands"]) == 0:
        coverage_notes.append("No command-invocation stubs found under operational/factory-metrics/commands/.")

    # ---- Per-skill usage ----------------------------------------------------
    skill_usage = defaultdict(lambda: {"checkpoints": set(), "packets": set(), "last_seen": None, "sources": set()})

    def bump_skill(skill, source_file, date, source_label):
        row = skill_usage[skill]
        if source_label == "checkpoint":
            row["checkpoints"].add(source_file)
        else:
            row["packets"].add(source_file)
        row["sources"].add(source_label)
        if date and (row["last_seen"] is None or date > row["last_seen"]):
            row["last_seen"] = date

    for rec in checkpoints["records"]:
        for skill in rec["skills_consumed"]:
            bump_skill(skill, rec["file"], rec["date"], "checkpoint")
    for m in working["skill_mentions"]:
        bump_skill(m["skill"], m["file"], m["date"], "packet" if m["kind"] == "packet" else "tasks-yaml")

    per_skill = {}
    for skill in sorted(skill_usage.keys()):
        row = skill_usage[skill]
        per_skill[skill] = {
            "checkpoints_appearing_in": sorted(row["checkpoints"]),
            "packets_naming_it": sorted(row["packets"]),
            "last_seen": row["last_seen"],
            "sources": sorted(row["sources"]),
        }
    never_observed = sorted(known_skills - set(skill_usage.keys()))

    # ---- Per-agent usage ----------------------------------------------------
    agent_usage = defaultdict(lambda: {"dispatches": 0, "tiers": set(), "last_active": None, "sources": set()})

    def bump_agent(agent, n, tier, date, source_label):
        if not agent:
            return
        row = agent_usage[agent]
        row["dispatches"] += n
        if tier:
            row["tiers"].add(tier)
        if date and (row["last_active"] is None or date > row["last_active"]):
            row["last_active"] = date
        row["sources"].add(source_label)

    for rec in checkpoints["records"]:
        for a in rec["agents_dispatched"]:
            bump_agent(a["agent"], max(a["dispatches"], 1), a["tier"], rec["date"], "checkpoint")
    for ta in working["task_agents"]:
        bump_agent(ta["agent"], 1, ta["tier"], ta["date"], "tasks-yaml")
    for d in routing["dispatches"]:
        bump_agent(d["agent"], 1, None, d["date"], "routing-log")
    for d in routing["decisions"]:
        bump_agent(d["agent"], 0, d.get("chosen_tier"), d["date"], "routing-log")  # tier/date signal, no double-count dispatch

    per_agent = {}
    for agent in sorted(agent_usage.keys()):
        row = agent_usage[agent]
        per_agent[agent] = {
            "dispatches": row["dispatches"],
            "tiers_seen": sorted(row["tiers"]),
            "last_active": row["last_active"],
            "sources": sorted(row["sources"]),
        }

    # ---- Per-workflow (checkpoints only — the only source that names a workflow) ----
    workflow_boundaries = defaultdict(Counter)
    workflow_gate_verdicts = defaultdict(Counter)
    for rec in checkpoints["records"]:
        wf = rec["workflow"] or "n/a"
        workflow_boundaries[wf][rec["boundary"]] += 1
        if rec["gate"] not in (None, "n/a", ""):
            v = (rec["verdict"] or "n/a").lower()
            bucket = "pass" if v in ("approved", "pass", "approve") else (
                "reject" if v in ("rejected", "reject", "fail") else "other")
            workflow_gate_verdicts[wf][bucket] += 1

    per_workflow = {}
    for wf in sorted(set(workflow_boundaries) | set(workflow_gate_verdicts)):
        per_workflow[wf] = {
            "boundaries": dict(workflow_boundaries.get(wf, {})),
            "gate_verdicts": dict(workflow_gate_verdicts.get(wf, {})),
        }

    # ---- Per-command invocations --------------------------------------------
    command_counts = Counter(c["name"] for c in stubs["commands"])
    command_last_date = {}
    for c in stubs["commands"]:
        name = c["name"]
        if c["date"] and (name not in command_last_date or c["date"] > command_last_date[name]):
            command_last_date[name] = c["date"]
    per_command = {
        name: {"invocations": n, "last_seen": command_last_date.get(name)}
        for name, n in sorted(command_counts.items())
    }

    # ---- Engagement summary --------------------------------------------------
    total_cost_proxy = round(sum(rec["cost_proxy"] for rec in checkpoints["records"]), 3)
    engagement = {
        "sessions": len(sessions["sessions"]),
        "session_events": sessions["events"],
        "span_start": sessions["min_ts"],
        "span_end": sessions["max_ts"],
        "checkpoints": len(checkpoints["records"]),
        "total_cost_proxy_from_checkpoints": total_cost_proxy,
        "total_human_touchpoints_from_checkpoints": sum(rec["human_touchpoints"] for rec in checkpoints["records"]),
    }

    return {
        "project_dir": str(project_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": coverage,
        "coverage_notes": coverage_notes,
        "per_skill": per_skill,
        "never_observed_skills": never_observed,
        "known_skill_count": len(known_skills),
        "per_agent": per_agent,
        "known_agent_count": len(known_agents),
        "per_workflow": per_workflow,
        "per_command": per_command,
        "engagement": engagement,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_markdown(agg: dict) -> str:
    lines = []
    lines.append(f"# Factory usage report — {agg['generated_at']}")
    lines.append("")
    lines.append(f"Project dir: `{agg['project_dir']}`")
    lines.append("")

    lines.append("## 1. Data coverage")
    lines.append("")
    cov = agg["coverage"]
    lines.append("| Source | Present | Detail |")
    lines.append("|---|---|---|")
    lines.append(f"| episodic/checkpoint-*.md (primary) | {cov['checkpoints']['present']} | "
                  f"{cov['checkpoints']['files']} file(s), {cov['checkpoints']['parsed']} parsed, "
                  f"{cov['checkpoints']['parse_errors']} parse error(s) |")
    lines.append(f"| working/slice-*-packet.md | {cov['working_packets']['present']} | {cov['working_packets']['files']} file(s) |")
    lines.append(f"| working/slice-*-tasks.yaml | {cov['working_tasks']['present']} | {cov['working_tasks']['files']} file(s) |")
    lines.append(f"| working/routing-*.md | {cov['routing_logs']['present']} | "
                  f"{cov['routing_logs']['files']} file(s), {cov['routing_logs']['dispatch_records']} dispatch record(s) |")
    lines.append(f"| operational/factory-metrics/commands/** | {cov['command_stubs']['present']} | {cov['command_stubs']['records']} record(s) |")
    lines.append(f"| telemetry/sessions.jsonl | {cov['sessions_jsonl']['present']} | "
                  f"{cov['sessions_jsonl']['events']} event(s), {cov['sessions_jsonl']['sessions']} session(s) |")
    legacy_detail = ", ".join(f"{k}:{v}" for k, v in cov["legacy_stub_layer"]["by_type"].items()) or "none"
    lines.append(f"| operational/factory-metrics/{{skills,agents,...}} (legacy stub layer) | "
                  f"{cov['legacy_stub_layer']['present']} | {cov['legacy_stub_layer']['records']} record(s) ({legacy_detail}) |")
    if agg["coverage_notes"]:
        lines.append("")
        lines.append("Honest coverage notes:")
        for n in agg["coverage_notes"]:
            lines.append(f"- {n}")
    lines.append("")

    lines.append("## 2. Per-skill usage")
    lines.append("")
    if agg["per_skill"]:
        lines.append("| Skill | Checkpoints appearing in | Packets/tasks naming it | Last seen | Sources |")
        lines.append("|---|---|---|---|---|")
        for skill, v in sorted(agg["per_skill"].items()):
            lines.append(
                f"| {skill} | {len(v['checkpoints_appearing_in'])} | {len(v['packets_naming_it'])} | "
                f"{v['last_seen'] or 'unknown'} | {', '.join(v['sources'])} |"
            )
    else:
        lines.append("No skill usage evidence found in checkpoints or working packets/task ledgers.")
    lines.append("")
    lines.append(f"**Never observed** ({len(agg['never_observed_skills'])} of {agg['known_skill_count']} known skills — "
                  "candidates for steward review; absence of evidence in a young project is weak evidence, "
                  "not proof the skill is unused):")
    if agg["never_observed_skills"]:
        lines.append("")
        for s in agg["never_observed_skills"]:
            lines.append(f"- {s}")
    else:
        lines.append("(none — every known skill has at least one observed use)")
    lines.append("")

    lines.append("## 3. Per-agent activity")
    lines.append("")
    if agg["per_agent"]:
        lines.append("| Agent | Dispatches | Tiers seen | Last active | Sources |")
        lines.append("|---|---|---|---|---|")
        for agent, v in sorted(agg["per_agent"].items()):
            lines.append(
                f"| {agent} | {v['dispatches']} | {', '.join(v['tiers_seen']) or 'unknown'} | "
                f"{v['last_active'] or 'unknown'} | {', '.join(v['sources'])} |"
            )
    else:
        lines.append("No agent-dispatch evidence found.")
    lines.append(f"\n({agg['known_agent_count']} known agent slugs in this library's agents/ directory.)")
    lines.append("")

    lines.append("## 4. Per-workflow")
    lines.append("")
    if agg["per_workflow"]:
        for wf, v in sorted(agg["per_workflow"].items()):
            lines.append(f"### {wf}")
            lines.append("")
            if v["boundaries"]:
                lines.append("Checkpoints by boundary type: " + ", ".join(
                    f"{k}={n}" for k, n in sorted(v["boundaries"].items())))
            else:
                lines.append("No boundary data.")
            if v["gate_verdicts"]:
                lines.append("Gate verdicts: " + ", ".join(
                    f"{k}={n}" for k, n in sorted(v["gate_verdicts"].items())))
            lines.append("")
    else:
        lines.append("No workflow data (only checkpoint records name a workflow).")
    lines.append("")

    lines.append("## 5. Per-command invocations")
    lines.append("")
    if agg["per_command"]:
        lines.append("| Command | Invocations | Last seen |")
        lines.append("|---|---|---|")
        for name, v in sorted(agg["per_command"].items()):
            lines.append(f"| {name} | {v['invocations']} | {v['last_seen'] or 'unknown'} |")
    else:
        lines.append("No command-invocation stubs found.")
    lines.append("")

    lines.append("## 6. Engagement summary")
    lines.append("")
    eng = agg["engagement"]
    lines.append(f"- Sessions: {eng['sessions']} ({eng['session_events']} session_start/session_end events)")
    span = f"{eng['span_start']} → {eng['span_end']}" if eng["span_start"] else "unknown"
    lines.append(f"- Span: {span}")
    lines.append(f"- Checkpoints: {eng['checkpoints']}")
    lines.append(f"- Total cost_proxy (summed from checkpoint frontmatter): {eng['total_cost_proxy_from_checkpoints']}")
    lines.append(f"- Total human_touchpoints (summed from checkpoint frontmatter): {eng['total_human_touchpoints_from_checkpoints']}")
    lines.append("")

    return "\n".join(lines)


def render_stdout_summary(agg: dict) -> str:
    cov = agg["coverage"]
    eng = agg["engagement"]
    lines = [
        "factory-usage-report summary",
        f"  project: {agg['project_dir']}",
        f"  checkpoints: {cov['checkpoints']['files']} file(s), {cov['checkpoints']['parsed']} parsed",
        f"  working packets/tasks: {cov['working_packets']['files']}/{cov['working_tasks']['files']}",
        f"  routing logs: {cov['routing_logs']['files']} file(s), {cov['routing_logs']['dispatch_records']} dispatch record(s)",
        f"  command stubs: {cov['command_stubs']['records']}",
        f"  sessions: {cov['sessions_jsonl']['sessions']} ({cov['sessions_jsonl']['events']} events)",
        f"  legacy stub layer: {cov['legacy_stub_layer']['records']} record(s)",
        f"  skills observed: {len(agg['per_skill'])}/{agg['known_skill_count']} "
        f"(never observed: {len(agg['never_observed_skills'])})",
        f"  agents observed: {len(agg['per_agent'])}/{agg['known_agent_count']}",
        f"  total cost_proxy: {eng['total_cost_proxy_from_checkpoints']}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Mine mandatory workflow artifacts into a factory usage-analytics report.")
    parser.add_argument("--project-dir", default=".", help="Project root, or a .project dir directly. Default: cwd.")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--out", default=None, help="Output file path.")
    args = parser.parse_args()

    try:
        project_root = Path(args.project_dir).expanduser().resolve()
        dot_project = resolve_project_dot_dir(project_root)
        agg = build_report(dot_project)
    except Exception as exc:  # last-resort fail-soft: never crash the caller
        print(f"factory-usage-report: internal error, degrading to empty report: {exc}", file=sys.stderr)
        agg = {
            "project_dir": str(args.project_dir), "generated_at": datetime.now(timezone.utc).isoformat(),
            "coverage": {}, "coverage_notes": [f"internal error: {exc}"], "per_skill": {},
            "never_observed_skills": [], "known_skill_count": 0, "per_agent": {}, "known_agent_count": 0,
            "per_workflow": {}, "per_command": {},
            "engagement": {"sessions": 0, "session_events": 0, "span_start": None, "span_end": None,
                           "checkpoints": 0, "total_cost_proxy_from_checkpoints": 0.0,
                           "total_human_touchpoints_from_checkpoints": 0},
        }

    if args.format == "json":
        payload = json.dumps(agg, indent=2, sort_keys=True)
        if args.out:
            out_path = Path(args.out).expanduser()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n")
        print(render_stdout_summary(agg))
        if args.out:
            print(f"\nJSON report written to {args.out}")
        else:
            print()
            print(payload)
        return 0

    md = render_markdown(agg)
    if args.out:
        out_path = Path(args.out).expanduser()
    else:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_path = dot_project / "telemetry" / "reports" / f"usage-report-{date_str}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)

    print(render_stdout_summary(agg))
    print(f"\nMarkdown report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
