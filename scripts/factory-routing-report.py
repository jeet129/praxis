#!/usr/bin/env python3
"""Aggregate routing/cost signal across the factory's telemetry layers.

Reads (all optional, all fail-soft):
  <project>/.project/telemetry/model-routing.jsonl    — structured routing decisions
  <project>/.project/telemetry/agent-spawns.jsonl     — structured spawn/complete events
  <project>/.project/working/routing-*.md             — prose routing logs (delivery-lead)
  <project>/.project/operational/factory-metrics/**    — per-invocation usage records

...and produces a routing + cost-proxy report: data coverage, per-slice dispatches,
per-agent activity, tier/cost breakdown, routing discipline, and heuristic
recommendations. Agent tier defaults come from this library's own agents/*.md
(`capability_tier:`) and governance/model-routing.yaml (harness model maps +
cost_weights) — resolved relative to this script's own location, NOT the
target project, so the report works against any project directory.

Usage:
  scripts/factory-routing-report.py [--project-dir PATH] [--format md|json] [--out PATH]

  --project-dir  Project root OR a .project directory directly. Default: cwd.
                 Both forms are accepted: if PATH/.project exists, that's used;
                 else if PATH itself looks like a .project directory (named
                 `.project` or contains working/operational/telemetry), PATH is
                 used as-is.
  --format       md (default) or json. json emits the raw aggregate dict.
  --out          Output file path. Default (md): <project>/.project/telemetry/
                 reports/routing-report-<YYYY-MM-DD>.md. Default (json): stdout only
                 unless --out is given.

Zero dependencies. Every ingestion step is wrapped to fail soft — a missing or
malformed source degrades the report, it never crashes the script.
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
AGENTS_DIR = LIB_ROOT / "agents"
GOVERNANCE_FILE = LIB_ROOT / "governance" / "model-routing.yaml"
VALID_TIERS = ("deep", "standard", "light")

# --------------------------------------------------------------------------
# Agent name normalization
# --------------------------------------------------------------------------

# Canonical slugs are discovered from agents/*.md at runtime (see load_agent_defaults).
# This alias table maps common abbreviations / free-text forms seen in prose routing
# logs and gate-verdict headings to canonical slugs.
AGENT_ALIASES = {
    "be": "backend-developer",
    "backend": "backend-developer",
    "backend dev": "backend-developer",
    "backend developer": "backend-developer",
    "fe": "frontend-developer",
    "frontend": "frontend-developer",
    "frontend dev": "frontend-developer",
    "frontend developer": "frontend-developer",
    "ld": "lead-developer",
    "lead dev": "lead-developer",
    "lead developer": "lead-developer",
    "dl": "delivery-lead",
    "delivery lead": "delivery-lead",
    "sa": "solution-architect",
    "solution architect": "solution-architect",
    "pm": "product-manager",
    "product manager": "product-manager",
    "qa": "qa-engineer",
    "quality": "qa-engineer",
    "security": "security-reviewer",
    "sec": "security-reviewer",
    "code": "code-reviewer",
    "code review": "code-reviewer",
    "code reviewer": "code-reviewer",
    "mobile": "mobile-developer",
    "mobile dev": "mobile-developer",
    "data": "data-engineer",
    "data eng": "data-engineer",
    "ml": "ml-ai-engineer",
    "ml/ai": "ml-ai-engineer",
    "ml ai": "ml-ai-engineer",
    "ai": "ml-ai-engineer",
    "platform": "platform-sre",
    "sre": "platform-sre",
    "platform/sre": "platform-sre",
    "ux": "ux-designer",
    "tw": "tech-writer",
    "tech writer": "tech-writer",
    "steward": "system-steward",
    "system steward": "system-steward",
    "challenger": "architecture-challenger",
    "architecture challenger": "architecture-challenger",
}


def canonicalize_agent(raw: str, known_slugs: set) -> str | None:
    """Normalize a free-text agent reference to a canonical agent slug.

    Returns None if nothing plausible matches (caller should keep the raw
    text around for the coverage note rather than silently dropping it).
    """
    if not raw:
        return None
    text = raw.strip()
    # Strip a trailing parenthetical abbreviation, e.g. "backend-developer (BE)".
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    # Strip a leading/trailing decorative markdown, punctuation.
    text = text.strip(" .:—-")
    if not text:
        return None
    lowered = text.lower()
    slug_form = re.sub(r"[\s_]+", "-", lowered)
    if slug_form in known_slugs:
        return slug_form
    if lowered in AGENT_ALIASES:
        return AGENT_ALIASES[lowered]
    if slug_form in AGENT_ALIASES:
        return AGENT_ALIASES[slug_form]
    # Try matching the first token only (e.g. "LD full-build (hash)" -> "LD").
    first_token = re.split(r"[\s(]", lowered, 1)[0].strip()
    if first_token in AGENT_ALIASES:
        return AGENT_ALIASES[first_token]
    return None


# --------------------------------------------------------------------------
# Governance + agent defaults (from THIS library, not the target project)
# --------------------------------------------------------------------------

def load_governance(path: Path) -> dict:
    """Minimal parser for the known structure of governance/model-routing.yaml.

    Returns {"claude_model_to_tier": {...}, "cost_weights": {tier: float}}.
    Fails soft: returns empty structures if the file is missing or malformed.
    """
    result = {"claude_model_to_tier": {}, "cost_weights": {}}
    if not path.exists():
        return result
    try:
        section = None
        current_harness = None
        in_map = False
        for raw in path.read_text().splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            key_val = line.strip().split(":", 1)
            key = key_val[0].strip()
            val = key_val[1].strip() if len(key_val) > 1 else ""
            if indent == 0:
                section = key
                current_harness = None
                in_map = False
                continue
            if section == "harnesses":
                if indent == 2:
                    current_harness = key
                    in_map = False
                elif indent == 4 and current_harness == "claude-code":
                    if key == "map":
                        in_map = True
                elif indent == 6 and current_harness == "claude-code" and in_map:
                    # key=tier, val=model
                    result["claude_model_to_tier"][val] = key
            elif section == "cost_weights" and indent == 2:
                try:
                    result["cost_weights"][key] = float(val)
                except ValueError:
                    pass
    except OSError:
        pass
    # Fallback cost weights if the file didn't parse (documented repo defaults).
    if not result["cost_weights"]:
        result["cost_weights"] = {"deep": 5.0, "standard": 1.0, "light": 0.25}
    return result


def load_agent_defaults(agents_dir: Path) -> dict:
    """Returns {agent_slug: capability_tier} read from agents/*.md frontmatter."""
    defaults = {}
    if not agents_dir.is_dir():
        return defaults
    for path in sorted(agents_dir.glob("*.md")):
        try:
            text = path.read_text()
        except OSError:
            continue
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            continue
        tier_m = re.search(r"^capability_tier:\s*(\S+)\s*$", m.group(1), re.M)
        if tier_m and tier_m.group(1) in VALID_TIERS:
            defaults[path.stem] = tier_m.group(1)
    return defaults


# --------------------------------------------------------------------------
# Project-dir resolution
# --------------------------------------------------------------------------

def resolve_project_dot_dir(path: Path) -> Path:
    """Accept either a project root or a .project dir directly."""
    if (path / ".project").is_dir():
        return path / ".project"
    markers = ("working", "operational", "telemetry")
    if path.name == ".project" or any((path / m).exists() for m in markers):
        return path
    # Default assumption; downstream reads are fail-soft regardless.
    return path / ".project"


# --------------------------------------------------------------------------
# Structured telemetry ingestion
# --------------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    records = []
    if not path.exists():
        return records
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        records.append(obj)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return records


# --------------------------------------------------------------------------
# Prose routing log ingestion (.project/working/routing-*.md)
# --------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
DISPATCH_HEADING_RE = re.compile(r"^##\s*Dispatch(?:ed)?\s*\d*\s*[:—-]\s*(.+)$", re.M)
GATE_KIND_RE = re.compile(r"gate-(security|code|qa)", re.I)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, m.group(2)


def classify_gate_status(text: str) -> str:
    """Heuristic pass/fail/unknown classification for a gate-verdict body."""
    upper = text.upper()
    fail_signals = ("REJECT", "FAIL", "BLOCKER")
    pass_signals = ("APPROVE", "PASS", "GREEN")
    has_fail = any(s in upper for s in fail_signals)
    has_pass = any(s in upper for s in pass_signals)
    if has_fail and has_pass:
        return "mixed"
    if has_fail:
        return "fail"
    if has_pass:
        return "pass"
    return "unknown"


def ingest_prose_routing(working_dir: Path, known_slugs: set) -> dict:
    """Parses .project/working/routing-*.md.

    Returns:
      files: number of routing-*.md files found
      dispatches: list of dispatch records:
        {slice, agent, raw_agent, source: 'explicit'|'inferred', kind, file, event, status}
      unresolved_raw_agents: raw strings that couldn't be canonicalized
    """
    out = {"files": 0, "dispatches": [], "decisions": [], "unresolved_raw_agents": []}
    if not working_dir.is_dir():
        return out
    paths = sorted(working_dir.glob("routing-*.md"))
    out["files"] = len(paths)
    for path in paths:
        try:
            text = path.read_text()
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        slice_id = fm.get("slice", "unknown")
        event = fm.get("event", "")
        fname = path.name

        # --- Structured routing decision in frontmatter (routing: block) ---
        # delivery-lead's routing-transparency discipline embeds the tier
        # decision in the routing-*.md frontmatter; treat it as a decided
        # record equivalent to a model-routing.jsonl line (source: prose).
        # parse_frontmatter is flat: the nested `routing:` block's keys land
        # as flat keys (agent, default_tier, chosen_tier, score, reason).
        # The presence of the `routing` parent key signals the block exists.
        if "routing" in fm and fm.get("agent"):
            r_agent = fm["agent"]
            agent = canonicalize_agent(r_agent, known_slugs) or r_agent
            out["decisions"].append({
                "agent": agent,
                "default_tier": fm.get("default_tier"),
                "chosen_tier": fm.get("chosen_tier"),
                "score": fm.get("score"),
                "reason": fm.get("reason", ""),
                "source": "prose-frontmatter",
                "file": fname,
                "slice": slice_id,
            })

        # --- Explicit "## Dispatch N — <agent>" / "## Dispatched: <agent>" headings ---
        explicit_agents_this_file = set()
        for m in DISPATCH_HEADING_RE.finditer(body):
            raw = m.group(1).strip()
            agent = canonicalize_agent(raw, known_slugs)
            if agent is None:
                out["unresolved_raw_agents"].append(raw)
                continue
            explicit_agents_this_file.add(agent)
            out["dispatches"].append({
                "slice": slice_id, "agent": agent, "raw_agent": raw,
                "source": "explicit", "file": fname, "event": event, "status": "n/a",
            })

        # --- Inferred dispatches from gate-verdict / LD-build filenames+events ---
        # These files don't carry a "## Dispatch" heading but ARE a real
        # specialist dispatch (the gate reviewer or the lead developer ran).
        # Heuristic, clearly labeled with source="inferred". Skipped when an
        # explicit heading in THIS file already accounted for the same agent
        # (e.g. "## Dispatched: LD full-build" already recorded lead-developer
        # explicitly — don't also count the event-text LD-mention).
        gate_m = GATE_KIND_RE.search(fname) or GATE_KIND_RE.search(event)
        if gate_m:
            gate_kind = gate_m.group(1).lower()
            agent = {"security": "security-reviewer", "code": "code-reviewer", "qa": "qa-engineer"}[gate_kind]
            if agent not in explicit_agents_this_file:
                status = classify_gate_status(body or event)
                out["dispatches"].append({
                    "slice": slice_id, "agent": agent, "raw_agent": f"gate-{gate_kind}",
                    "source": "inferred", "file": fname, "event": event, "status": status,
                })
        elif re.search(r"\bLD\b", event) or "LD full-build" in event or "LD decomposition" in event or "decomposition" in event.lower():
            if "lead-developer" not in explicit_agents_this_file:
                status = classify_gate_status(body or event)
                out["dispatches"].append({
                    "slice": slice_id, "agent": "lead-developer", "raw_agent": "LD",
                    "source": "inferred", "file": fname, "event": event, "status": status,
                })
    return out


# --------------------------------------------------------------------------
# Factory-metrics usage-record ingestion (.project/operational/factory-metrics/**)
# --------------------------------------------------------------------------

def ingest_factory_metrics(fm_dir: Path) -> dict:
    """Parses per-invocation usage records under operational/factory-metrics/.

    Returns: {records: [frontmatter dicts + _path], count: int}
    """
    out = {"records": [], "count": 0}
    if not fm_dir.is_dir():
        return out
    for path in sorted(fm_dir.rglob("*.md")):
        try:
            text = path.read_text()
        except OSError:
            continue
        fm, _ = parse_frontmatter(text)
        if not fm:
            continue
        fm["_path"] = str(path)
        out["records"].append(fm)
    out["count"] = len(out["records"])
    return out


# --------------------------------------------------------------------------
# Drive-run ingestion (.project/telemetry/drive.jsonl)
# --------------------------------------------------------------------------

HUMAN_STOP_FLAGS = {"decision_required", "gate_reached"}


def build_drive_runs(drive_events: list[dict]) -> dict:
    """Aggregates scripts/praxis-drive.sh telemetry per run_id.

    Per references/factory-metrics-schema.md's drive.jsonl schema (copied
    from references/loop-contracts.md section 4). Fails soft: malformed or
    missing records are skipped rather than raising.

    Returns:
      runs: [{run_id, iterations, slices, tasks_done, tasks_failed,
              cost_proxy_total, stop_reason, stopped_for_human}]
      totals: {iterations, tasks_done, tasks_failed, cost_proxy_total,
               runs_stopped_for_human, distinct_slices_touched}
      human_touchpoint_density: runs_stopped_for_human / distinct_slices_touched
        (heuristic — drive.jsonl has no explicit "slice closed" event, so
        distinct slices touched across all runs is used as the closest
        available proxy for "slices closed"; noted as an approximation)
    """
    by_run: dict[str, list[dict]] = defaultdict(list)
    for rec in drive_events:
        run_id = rec.get("run_id")
        if run_id:
            by_run[run_id].append(rec)

    runs = []
    all_slices = set()
    total_iterations = 0
    total_done = 0
    total_failed = 0
    total_cost = 0.0
    runs_stopped_for_human = 0

    for run_id in sorted(by_run.keys()):
        records = by_run[run_id]
        records_sorted = sorted(records, key=lambda r: r.get("iteration", 0))
        iterations = len(records_sorted)
        slices = sorted({r.get("slice") for r in records_sorted if r.get("slice")})
        done = sum(1 for r in records_sorted if r.get("outcome") == "done")
        failed = sum(1 for r in records_sorted if r.get("outcome") == "failed")
        cost_total = sum(
            r.get("cost_proxy", 0) for r in records_sorted
            if isinstance(r.get("cost_proxy"), (int, float))
        )
        last = records_sorted[-1] if records_sorted else {}
        last_flags = last.get("stop_flags") or []
        if last_flags:
            stop_reason = ",".join(last_flags)
        else:
            stop_reason = (
                "inferred: run ended without a stop_flag on the last recorded "
                "iteration (likely a budget/stall/queue-drained exit — the "
                "runner's exit code carries that detail, not the telemetry line)"
            )
        stopped_for_human = bool(set(last_flags) & HUMAN_STOP_FLAGS)
        if stopped_for_human:
            runs_stopped_for_human += 1

        all_slices |= set(slices)
        total_iterations += iterations
        total_done += done
        total_failed += failed
        total_cost += cost_total

        runs.append({
            "run_id": run_id,
            "iterations": iterations,
            "slices": slices,
            "tasks_done": done,
            "tasks_failed": failed,
            "cost_proxy_total": round(cost_total, 3),
            "stop_reason": stop_reason,
            "stopped_for_human": stopped_for_human,
        })

    distinct_slices_touched = len(all_slices)
    density = (
        round(runs_stopped_for_human / distinct_slices_touched, 3)
        if distinct_slices_touched else None
    )

    return {
        "runs": runs,
        "totals": {
            "iterations": total_iterations,
            "tasks_done": total_done,
            "tasks_failed": total_failed,
            "cost_proxy_total": round(total_cost, 3),
            "runs_stopped_for_human": runs_stopped_for_human,
            "distinct_slices_touched": distinct_slices_touched,
        },
        "human_touchpoint_density": density,
    }


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def build_report(project_dir: Path) -> dict:
    known_slugs = set(load_agent_defaults(AGENTS_DIR).keys())
    agent_defaults = load_agent_defaults(AGENTS_DIR)
    # Project-level override wins over the plugin-shipped routing table, so
    # an engagement can tune cost_weights / force_tier without editing the
    # installed plugin. project_dir here is the .project dir.
    project_gov = project_dir / "governance" / "model-routing.yaml"
    gov = load_governance(project_gov if project_gov.exists() else GOVERNANCE_FILE)

    telemetry_dir = project_dir / "telemetry"
    working_dir = project_dir / "working"
    fm_dir = project_dir / "operational" / "factory-metrics"

    spawn_events = read_jsonl(telemetry_dir / "agent-spawns.jsonl")
    routing_events = read_jsonl(telemetry_dir / "model-routing.jsonl")
    drive_events = read_jsonl(telemetry_dir / "drive.jsonl")
    prose = ingest_prose_routing(working_dir, known_slugs)
    fmetrics = ingest_factory_metrics(fm_dir)

    # Prose-frontmatter routing decisions (routing: block in routing-*.md)
    # count as decided records, same as model-routing.jsonl lines — the
    # frontmatter is the authoritative fallback when the JSONL append was
    # skipped. Normalize to the JSONL record shape and merge.
    for d in prose.get("decisions", []):
        routing_events.append({
            "agent": d.get("agent"),
            "default_tier": d.get("default_tier"),
            "chosen_tier": d.get("chosen_tier"),
            "tier": d.get("chosen_tier"),
            "score": d.get("score"),
            "reason": d.get("reason"),
            "source": "prose-frontmatter",
        })

    # ---- Data coverage --------------------------------------------------
    coverage = {
        "model_routing_jsonl": {
            "present": (telemetry_dir / "model-routing.jsonl").exists(),
            "records": len(routing_events),
        },
        "agent_spawns_jsonl": {
            "present": (telemetry_dir / "agent-spawns.jsonl").exists(),
            "records": len(spawn_events),
        },
        "drive_jsonl": {
            "present": (telemetry_dir / "drive.jsonl").exists(),
            "records": len(drive_events),
        },
        "prose_routing_logs": {
            "present": prose["files"] > 0,
            "files": prose["files"],
            "dispatch_records": len(prose["dispatches"]),
            "frontmatter_decisions": len(prose.get("decisions", [])),
        },
        "factory_metrics_usage": {
            "present": fmetrics["count"] > 0,
            "records": fmetrics["count"],
        },
    }
    coverage_notes = []
    if not coverage["model_routing_jsonl"]["present"]:
        if prose.get("decisions"):
            coverage_notes.append(
                "telemetry/model-routing.jsonl is absent, but routing decisions "
                f"were recovered from routing-*.md frontmatter ({len(prose['decisions'])} decided records)."
            )
        else:
            coverage_notes.append(
                "telemetry/model-routing.jsonl is absent — no structured routing "
                "decisions have been logged yet; tier resolution below falls back "
                "to observed spawn models or agent defaults."
            )
    if not coverage["agent_spawns_jsonl"]["present"]:
        coverage_notes.append(
            "telemetry/agent-spawns.jsonl is absent — no structured spawn/complete "
            "events; per-agent activity below is prose-log-only."
        )
    if coverage["prose_routing_logs"]["files"] == 0:
        coverage_notes.append("No .project/working/routing-*.md prose logs found.")
    if coverage["factory_metrics_usage"]["records"] == 0:
        coverage_notes.append("No factory-metrics usage records found.")
    if not coverage["drive_jsonl"]["present"]:
        coverage_notes.append(
            "telemetry/drive.jsonl is absent — no scripts/praxis-drive.sh runs "
            "recorded yet; the Drive runs section below is empty."
        )

    # ---- Per-slice dispatches (prose) -----------------------------------
    by_slice = defaultdict(lambda: {"count": 0, "agents": Counter()})
    for d in prose["dispatches"]:
        by_slice[d["slice"]]["count"] += 1
        by_slice[d["slice"]]["agents"][d["agent"]] += 1
    per_slice = {
        s: {"dispatch_count": v["count"], "agents": dict(v["agents"])}
        for s, v in sorted(by_slice.items())
    }

    # ---- Per-agent activity ---------------------------------------------
    spawn_counter = Counter(e.get("agent") for e in spawn_events if e.get("event") == "spawn" and e.get("agent"))
    complete_events_by_agent = defaultdict(list)
    for e in spawn_events:
        if e.get("event") == "complete" and e.get("agent"):
            complete_events_by_agent[e["agent"]].append(e)
    prose_dispatch_counter = Counter(d["agent"] for d in prose["dispatches"])

    all_agents = set(spawn_counter) | set(complete_events_by_agent) | set(prose_dispatch_counter) | set(agent_defaults)
    per_agent_activity = {}
    for agent in sorted(all_agents):
        completes = complete_events_by_agent.get(agent, [])
        fail_statuses = [c for c in completes if str(c.get("status", "")).lower() not in ("success", "completed", "ok", "")]
        per_agent_activity[agent] = {
            "structured_spawns": spawn_counter.get(agent, 0),
            "prose_dispatches": prose_dispatch_counter.get(agent, 0),
            "structured_completions": len(completes),
            "failure_or_retry_statuses": len(fail_statuses),
            "status_breakdown": dict(Counter(str(c.get("status", "unknown")) for c in completes)),
        }

    # ---- Tier & cost proxy ------------------------------------------------
    # Most recent structured routing decision per agent (by simple appearance order;
    # jsonl is append-only so last occurrence = most recent).
    decided_tier = {}
    decided_record = {}
    for rec in routing_events:
        agent = rec.get("agent")
        chosen = rec.get("chosen_tier") or rec.get("tier") or rec.get("resolved_tier")
        if agent and chosen in VALID_TIERS:
            decided_tier[agent] = chosen
            decided_record[agent] = rec

    # Most recent observed spawn model per agent, mapped back to tier via governance.
    observed_tier = {}
    for e in spawn_events:
        if e.get("event") == "spawn" and e.get("agent") and e.get("model"):
            tier = gov["claude_model_to_tier"].get(e["model"])
            if tier:
                observed_tier[e["agent"]] = tier

    cost_weights = gov["cost_weights"]
    tier_totals = Counter()
    tier_cost_totals = Counter()
    total_input_tokens = 0
    total_output_tokens = 0
    agent_tier_rows = {}
    for agent in sorted(all_agents):
        if agent in decided_tier:
            tier, source = decided_tier[agent], "decided"
        elif agent in observed_tier:
            tier, source = observed_tier[agent], "observed"
        elif agent in agent_defaults:
            tier, source = agent_defaults[agent], "default"
        else:
            tier, source = "standard", "default(unknown-agent-fallback)"
        spawns = per_agent_activity[agent]["structured_spawns"] + per_agent_activity[agent]["prose_dispatches"]
        weight = cost_weights.get(tier, 1.0)
        cost_proxy = spawns * weight
        tier_totals[tier] += spawns
        tier_cost_totals[tier] += cost_proxy
        agent_tier_rows[agent] = {
            "tier": tier, "tier_source": source, "spawns": spawns,
            "cost_weight": weight, "cost_proxy": round(cost_proxy, 3),
        }
        for c in complete_events_by_agent.get(agent, []):
            if isinstance(c.get("input_tokens"), (int, float)):
                total_input_tokens += c["input_tokens"]
            if isinstance(c.get("output_tokens"), (int, float)):
                total_output_tokens += c["output_tokens"]

    total_spawns_all = sum(tier_totals.values())
    tier_pct = {
        t: (round(100 * tier_totals[t] / total_spawns_all, 1) if total_spawns_all else 0.0)
        for t in VALID_TIERS
    }

    # ---- Routing discipline ------------------------------------------------
    structured_spawn_events = [e for e in spawn_events if e.get("event") == "spawn"]
    matched = 0
    for e in structured_spawn_events:
        agent, session = e.get("agent"), e.get("session")
        for rec in routing_events:
            if rec.get("agent") == agent and (session is None or rec.get("session") == session):
                matched += 1
                break
    routing_discipline_pct = (
        round(100 * matched / len(structured_spawn_events), 1) if structured_spawn_events else None
    )
    escalations = demotions = 0
    for rec in routing_events:
        default_t = rec.get("default_tier") or rec.get("default")
        chosen_t = rec.get("chosen_tier") or rec.get("tier") or rec.get("resolved_tier")
        if default_t in VALID_TIERS and chosen_t in VALID_TIERS and default_t != chosen_t:
            if VALID_TIERS.index(chosen_t) < VALID_TIERS.index(default_t):
                escalations += 1
            else:
                demotions += 1

    # ---- Recommendations (heuristics, clearly labeled) ---------------------
    recommendations = []
    TRIVIAL_SPAWN_THRESHOLD = 3
    for agent, row in agent_tier_rows.items():
        if row["tier"] != "deep":
            continue
        breakdown = per_agent_activity[agent]["status_breakdown"]
        total_completions = sum(breakdown.values())
        trivial_success = sum(v for k, v in breakdown.items() if str(k).lower() in ("success", "completed", "ok"))
        if row["spawns"] > TRIVIAL_SPAWN_THRESHOLD and total_completions and trivial_success == total_completions:
            recommendations.append(
                f"[heuristic] {agent} resolved to 'deep' tier and spawned "
                f"{row['spawns']} times with {total_completions}/{total_completions} "
                f"trivially-successful completions logged — worth a spot-check on "
                f"whether 'standard' would suffice for this agent's typical task mix."
            )
    if not decided_tier:
        recommendations.append(
            "[heuristic] No structured routing decisions logged yet "
            "(telemetry/model-routing.jsonl empty) — every tier below is "
            "resolved from observed spawn models or static agent defaults, "
            "not an actual per-task rubric decision. Wire up delivery-lead's "
            "logging per skills/adaptive-model-routing/SKILL.md to get real "
            "routing-discipline numbers."
        )
    if prose["unresolved_raw_agents"]:
        recommendations.append(
            "[data-quality] Some prose dispatch headings didn't canonicalize to "
            "a known agent slug: " + ", ".join(sorted(set(prose["unresolved_raw_agents"])))
            + ". Consider tightening naming in routing logs or extending the alias table."
        )

    drive_runs = build_drive_runs(drive_events)

    return {
        "project_dir": str(project_dir),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage": coverage,
        "coverage_notes": coverage_notes,
        "per_slice": per_slice,
        "per_agent_activity": per_agent_activity,
        "drive_runs": drive_runs,
        "tier_and_cost": {
            "agents": agent_tier_rows,
            "tier_totals_spawns": dict(tier_totals),
            "tier_totals_cost_proxy": {k: round(v, 3) for k, v in tier_cost_totals.items()},
            "tier_pct_of_spawns": tier_pct,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
        "routing_discipline": {
            "structured_spawns": len(structured_spawn_events),
            "matched_to_decision_pct": routing_discipline_pct,
            "escalations": escalations,
            "demotions": demotions,
        },
        "recommendations": recommendations,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_markdown(agg: dict) -> str:
    lines = []
    lines.append(f"# Factory routing report — {agg['generated_at']}")
    lines.append("")
    lines.append(f"Project dir: `{agg['project_dir']}`")
    lines.append("")

    lines.append("## 1. Data coverage")
    lines.append("")
    lines.append("| Source | Present | Records |")
    lines.append("|---|---|---|")
    cov = agg["coverage"]
    lines.append(f"| telemetry/model-routing.jsonl | {cov['model_routing_jsonl']['present']} | {cov['model_routing_jsonl']['records']} |")
    lines.append(f"| telemetry/agent-spawns.jsonl | {cov['agent_spawns_jsonl']['present']} | {cov['agent_spawns_jsonl']['records']} |")
    lines.append(f"| telemetry/drive.jsonl | {cov['drive_jsonl']['present']} | {cov['drive_jsonl']['records']} |")
    lines.append(f"| working/routing-*.md | {cov['prose_routing_logs']['present']} | {cov['prose_routing_logs']['files']} files / {cov['prose_routing_logs']['dispatch_records']} dispatch records |")
    lines.append(f"| operational/factory-metrics usage records | {cov['factory_metrics_usage']['present']} | {cov['factory_metrics_usage']['records']} |")
    if agg["coverage_notes"]:
        lines.append("")
        lines.append("Honest coverage notes:")
        for n in agg["coverage_notes"]:
            lines.append(f"- {n}")
    lines.append("")

    lines.append("## 2. Per-slice dispatches (from prose routing logs)")
    lines.append("")
    if agg["per_slice"]:
        lines.append("| Slice | Dispatch count | Agents |")
        lines.append("|---|---|---|")
        for slice_id, v in agg["per_slice"].items():
            agents_str = ", ".join(f"{a} ({n})" for a, n in sorted(v["agents"].items()))
            lines.append(f"| {slice_id} | {v['dispatch_count']} | {agents_str} |")
    else:
        lines.append("No slice dispatch data found in prose routing logs.")
    lines.append("")

    lines.append("## 3. Per-agent activity")
    lines.append("")
    lines.append("| Agent | Structured spawns | Prose dispatches | Structured completions | Non-success statuses |")
    lines.append("|---|---|---|---|---|")
    for agent, v in sorted(agg["per_agent_activity"].items()):
        lines.append(
            f"| {agent} | {v['structured_spawns']} | {v['prose_dispatches']} | "
            f"{v['structured_completions']} | {v['failure_or_retry_statuses']} |"
        )
    lines.append("")

    lines.append("## 4. Tier & cost proxy")
    lines.append("")
    lines.append("| Agent | Tier | Tier source | Spawns (structured+prose) | Cost weight | Cost proxy |")
    lines.append("|---|---|---|---|---|---|")
    tc = agg["tier_and_cost"]
    for agent, row in sorted(tc["agents"].items()):
        lines.append(
            f"| {agent} | {row['tier']} | {row['tier_source']} | {row['spawns']} | "
            f"{row['cost_weight']} | {row['cost_proxy']} |"
        )
    lines.append("")
    lines.append("Totals:")
    for tier in VALID_TIERS:
        spawns = tc["tier_totals_spawns"].get(tier, 0)
        cost = tc["tier_totals_cost_proxy"].get(tier, 0.0)
        pct = tc["tier_pct_of_spawns"].get(tier, 0.0)
        lines.append(f"- **{tier}**: {spawns} spawns ({pct}%), cost proxy {cost}")
    lines.append("")
    lines.append(f"Real token totals (from structured completions, when present): "
                  f"input={tc['total_input_tokens']}, output={tc['total_output_tokens']}")
    lines.append("")

    lines.append("## 5. Routing discipline")
    lines.append("")
    rd = agg["routing_discipline"]
    match_str = f"{rd['matched_to_decision_pct']}%" if rd["matched_to_decision_pct"] is not None else "n/a (no structured spawns)"
    lines.append(f"- Structured spawns with a matching structured routing decision (agent+session): {match_str}")
    lines.append(f"- Escalations (chosen tier stronger than default, per decided records): {rd['escalations']}")
    lines.append(f"- Demotions (chosen tier weaker than default, per decided records): {rd['demotions']}")
    lines.append("")

    lines.append("## 6. Drive runs (scripts/praxis-drive.sh)")
    lines.append("")
    dr = agg["drive_runs"]
    if dr["runs"]:
        lines.append("| Run | Iterations | Slices touched | Tasks done/failed | Cost proxy | Stop reason |")
        lines.append("|---|---|---|---|---|---|")
        for run in dr["runs"]:
            slices_str = ", ".join(run["slices"]) if run["slices"] else "-"
            lines.append(
                f"| {run['run_id']} | {run['iterations']} | {slices_str} | "
                f"{run['tasks_done']}/{run['tasks_failed']} | {run['cost_proxy_total']} | {run['stop_reason']} |"
            )
        lines.append("")
        t = dr["totals"]
        lines.append(
            f"Totals: {t['iterations']} iterations across {len(dr['runs'])} run(s), "
            f"{t['tasks_done']} done / {t['tasks_failed']} failed, cost proxy {t['cost_proxy_total']}."
        )
        density_str = f"{dr['human_touchpoint_density']}" if dr["human_touchpoint_density"] is not None else "n/a (no slices touched)"
        lines.append(
            f"Human-touchpoint density (runs stopped for human ÷ slices touched, heuristic): "
            f"{t['runs_stopped_for_human']} / {t['distinct_slices_touched']} = {density_str}"
        )
    else:
        lines.append("No drive runs recorded (telemetry/drive.jsonl absent or empty).")
    lines.append("")

    lines.append("## 7. Recommendations")
    lines.append("")
    if agg["recommendations"]:
        for r in agg["recommendations"]:
            lines.append(f"- {r}")
    else:
        lines.append("No flags raised by the current heuristics.")
    lines.append("")

    return "\n".join(lines)


def render_stdout_summary(agg: dict) -> str:
    cov = agg["coverage"]
    tc = agg["tier_and_cost"]
    lines = [
        "factory-routing-report summary",
        f"  project: {agg['project_dir']}",
        f"  structured routing decisions: {cov['model_routing_jsonl']['records']}",
        f"  structured spawn/complete events: {cov['agent_spawns_jsonl']['records']}",
        f"  prose routing-log files: {cov['prose_routing_logs']['files']} "
        f"({cov['prose_routing_logs']['dispatch_records']} dispatch records)",
        f"  factory-metrics usage records: {cov['factory_metrics_usage']['records']}",
        f"  drive.jsonl records: {cov['drive_jsonl']['records']} "
        f"({len(agg['drive_runs']['runs'])} drive run(s))",
        f"  tier totals (spawns): "
        + ", ".join(f"{t}={tc['tier_totals_spawns'].get(t, 0)}" for t in VALID_TIERS),
        f"  tier totals (cost proxy): "
        + ", ".join(f"{t}={tc['tier_totals_cost_proxy'].get(t, 0.0)}" for t in VALID_TIERS),
        f"  recommendations: {len(agg['recommendations'])}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate factory routing/cost telemetry into a report.")
    parser.add_argument("--project-dir", default=".", help="Project root, or a .project dir directly. Default: cwd.")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--out", default=None, help="Output file path.")
    args = parser.parse_args()

    project_root = Path(args.project_dir).expanduser().resolve()
    dot_project = resolve_project_dot_dir(project_root)

    agg = build_report(dot_project)

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
        out_path = dot_project / "telemetry" / "reports" / f"routing-report-{date_str}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)

    print(render_stdout_summary(agg))
    print(f"\nMarkdown report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
