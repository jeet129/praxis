#!/usr/bin/env python3
"""Mine real Claude Code token usage from local session transcripts and
correlate it with praxis's own telemetry (sessions, drive runs, routing
decisions) to produce a token/cost report.

Why this script exists: scripts/factory-routing-report.py's "cost proxy" is a
tier-weighted RELATIVE unit (see references/factory-metrics-schema.md /
docs/telemetry.md) — useful for trend comparison, not an actual token or
dollar count. scripts/praxis-drive.sh now captures real usage for its own
headless invocations (drive.jsonl input_tokens/output_tokens/total_cost_usd),
but that only covers drive-runner iterations, not interactive sessions. This
script fills the interactive-session gap by mining Claude Code's own
transcript files.

Where transcripts live (ASSUMPTION — verify locally, code defends against it
being wrong): Claude Code writes one JSONL file per session under
  ~/.claude/projects/<munged-project-path>/<session-id>.jsonl
where <munged-project-path> is the project's absolute path with every '/'
replaced by '-' (leading '/' becomes a leading '-'). This is the convention
observed in Claude Code installs; it is NOT guaranteed by any public spec and
may change. This sandbox has no ~/.claude directory to verify against, so the
script (a) tries the computed munge, (b) falls back to a fuzzy match against
whatever directories ARE present under --claude-projects, and (c) accepts
--transcripts-dir to bypass the guess entirely. Each assistant-role JSONL line
is expected to carry `message.usage` ({input_tokens, output_tokens,
cache_read_input_tokens, cache_creation_input_tokens}) and `message.model`,
per Claude Code's transcript format as of 2026.

Reads (all optional, all fail-soft):
  <claude-projects>/<munged-project-dir>/*.jsonl   — session transcripts (the
      "--transcripts-dir" override skips the munge/lookup entirely). Lines
      may carry `isSidechain: true` for subagent (Task tool) activity; this
      script partitions main-thread vs sidechain messages, groups sidechain
      messages into per-invocation segments, and best-effort-attributes each
      segment to an agent (see "Sidechain-aware attribution" below).
  <project>/.project/telemetry/sessions.jsonl       — session ids/boundaries,
      for filename-based transcript-to-session matching
  <project>/.project/telemetry/drive.jsonl          — drive-run windows +
      per-run cost_proxy, for the proxy-calibration section; also the exact
      per-task token source when a task ran under drive
  <project>/.project/telemetry/model-routing.jsonl  — slice timestamps, for
      best-effort time-window slice attribution
  <project>/.project/working/routing-*.md           — frontmatter `routing.agent`
      + `created` timestamp, a best-effort agent-identity fallback for
      sidechain segments that carry no agent field of their own
  <project>/.project/working/slice-*-tasks.yaml      — task ledger, parsed
      tolerantly for `started_at`/`completed_at` (references/loop-contracts.md
      §2); when present, transcript messages are attributed to tasks by time
      window (approximation — see "Per task" section)

Sidechain-aware attribution (Job 1): Claude Code transcript lines carry
`isSidechain: true` on subagent (Task tool) activity in versions that support
it; older transcripts omit the field entirely, and this script degrades
honestly (notes it, skips the section) rather than guessing. Where the field
is present: (a) a line with `isSidechain` absent or falsy is main-thread; (b)
contiguous sidechain assistant messages (per transcript file) are grouped
into one invocation segment, closed and a new one opened when the gap to the
previous sidechain message exceeds 5 minutes OR a main-thread message
intervenes; (c) each segment's agent identity is resolved best-effort: an
`agentName`/`subagentType`-shaped field on the line or its first message
first, else a ±3-minute match against `routing-*.md` frontmatter timestamps,
else labeled `unattributed-subagent` — every row is tagged with which of the
three grounded the label.

Task-window attribution (Job 2): when a task ledger carries `started_at`/
`completed_at` (stamped by drive or interactive execution per
references/loop-contracts.md §2), transcript messages (main-thread AND
sidechain) falling inside a task's window are summed as an approximation of
that task's token cost — explicitly labeled as such, since (unlike
`drive.jsonl`'s exact per-iteration capture) shared context makes this a
time-window allocation, not a measurement. `drive.jsonl`'s exact numbers are
preferred over the window approximation whenever both exist for a task.

Usage:
  scripts/factory-token-report.py [--project-dir PATH]
                                   [--claude-projects DIR]
                                   [--transcripts-dir DIR]
                                   [--format md|json] [--out PATH]

  --project-dir      Project root OR a .project directory directly. Default: cwd.
  --claude-projects  Root of Claude Code's per-project transcript store.
                      Default: ~/.claude/projects. Ignored if --transcripts-dir given.
  --transcripts-dir  Exact directory containing this project's *.jsonl
                      transcripts. Overrides the --claude-projects munge/lookup.
  --format           md (default) or json.
  --out              Output path. Default (md):
                      <project>/.project/telemetry/reports/token-report-<YYYY-MM-DD>.md
                      Default (json): stdout only, unless --out is given.

Zero dependencies beyond the Python 3 standard library. Exits 0 even when no
transcripts are found (that's the expected CI case) — every ingestion step
degrades its section of the report rather than crashing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Project-dir resolution (same convention as factory-routing-report.py /
# factory-usage-report.py)
# --------------------------------------------------------------------------

def resolve_project_dot_dir(path: Path) -> Path:
    """Accept either a project root or a .project dir directly."""
    if (path / ".project").is_dir():
        return path / ".project"
    markers = ("working", "operational", "telemetry", "episodic")
    if path.name == ".project" or any((path / m).exists() for m in markers):
        return path
    return path / ".project"


def project_root_from_dot_dir(dot_dir: Path) -> Path:
    return dot_dir.parent if dot_dir.name == ".project" else dot_dir


# --------------------------------------------------------------------------
# Transcript directory resolution
# --------------------------------------------------------------------------

def munge_project_path(project_root: Path) -> str:
    """Claude Code's observed convention: absolute path with every '/'
    replaced by '-'. E.g. /Users/x/my-project -> -Users-x-my-project."""
    return str(project_root).replace("/", "-")


def resolve_transcripts_dir(project_root: Path, claude_projects: Path) -> tuple[Path | None, str]:
    """Returns (dir_or_None, note). Tries the exact munge first; falls back
    to a fuzzy suffix/substring match against whatever's actually present
    under claude_projects (defensive — the munge convention is unverified in
    this environment)."""
    if not claude_projects.is_dir():
        return None, f"{claude_projects} does not exist — no Claude Code transcript store found on this machine/sandbox."

    exact = claude_projects / munge_project_path(project_root)
    if exact.is_dir():
        return exact, f"resolved by exact munge match: {exact.name}"

    # Fuzzy fallback: look for a subdirectory whose munged form contains the
    # project's basename, or whose de-munged form (dashes -> slashes) ends
    # with the project's own path tail.
    basename = project_root.name
    candidates = []
    try:
        for child in claude_projects.iterdir():
            if not child.is_dir():
                continue
            if basename and basename in child.name:
                candidates.append(child)
    except OSError:
        pass
    if len(candidates) == 1:
        return candidates[0], f"resolved by fuzzy basename match: {candidates[0].name} (exact munge {exact.name} not found)"
    if len(candidates) > 1:
        return None, (
            f"exact munge {exact.name} not found, and {len(candidates)} fuzzy candidates matched basename "
            f"'{basename}' ambiguously ({', '.join(c.name for c in candidates[:5])}...) — pass --transcripts-dir explicitly."
        )
    return None, f"no transcript directory found under {claude_projects} for project {project_root} (tried exact munge {exact.name!r} and basename fuzzy match)."


# --------------------------------------------------------------------------
# Timestamp parsing (tolerant of the several shapes seen across sources)
# --------------------------------------------------------------------------

def parse_ts(raw) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    # Normalize a trailing 'Z' to +00:00 for fromisoformat.
    candidate = s[:-1] + "+00:00" if s.endswith("Z") else s
    for fmt_fn in (
        lambda v: datetime.fromisoformat(v),
        lambda v: datetime.strptime(v, "%Y-%m-%d"),
        lambda v: datetime.strptime(v, "%Y-%m-%dT%H:%M:%S"),
    ):
        try:
            dt = fmt_fn(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


# --------------------------------------------------------------------------
# JSONL ingestion
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


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# --------------------------------------------------------------------------
# Slice-window attribution (best-effort)
# --------------------------------------------------------------------------

SLICE_WINDOW_PAD_SECONDS = 3 * 3600  # pad each slice's observed ts range by 3h either side


def build_slice_windows(routing_events: list[dict], drive_events: list[dict]) -> dict[str, tuple[datetime, datetime]]:
    spans: dict[str, list] = defaultdict(lambda: [None, None])
    for rec in list(routing_events) + list(drive_events):
        slice_id = rec.get("slice")
        ts = parse_ts(rec.get("ts"))
        if not slice_id or ts is None:
            continue
        span = spans[slice_id]
        if span[0] is None or ts < span[0]:
            span[0] = ts
        if span[1] is None or ts > span[1]:
            span[1] = ts
    windows = {}
    for slice_id, (lo, hi) in spans.items():
        if lo is None or hi is None:
            continue
        pad = timedelta_seconds(SLICE_WINDOW_PAD_SECONDS)
        windows[slice_id] = (lo - pad, hi + pad)
    return windows


def timedelta_seconds(n):
    from datetime import timedelta
    return timedelta(seconds=n)


def attribute_slice(ts: datetime, windows: dict[str, tuple[datetime, datetime]]) -> str | None:
    if ts is None or not windows:
        return None
    matches = [(slice_id, hi - lo) for slice_id, (lo, hi) in windows.items() if lo <= ts <= hi]
    if not matches:
        return None
    # Narrowest window wins (most specific attribution); ties broken by slice id.
    matches.sort(key=lambda m: (m[1], m[0]))
    return matches[0][0]


# --------------------------------------------------------------------------
# Sidechain-aware per-agent-invocation attribution (Job 1)
# --------------------------------------------------------------------------

SIDECHAIN_SEGMENT_GAP_SECONDS = 5 * 60
ROUTING_PROSE_MATCH_WINDOW_SECONDS = 3 * 60

# Defensive: the field carrying subagent identity on a sidechain line/message
# varies across Claude Code versions and hasn't been pinned to one name in
# this sandbox (no local ~/.claude to inspect). Try the shapes seen in the
# wild, in order; first non-empty string wins.
AGENT_IDENTITY_FIELDS = ("agentName", "subagentType", "subagent_type", "agent_name", "agent")


def extract_agent_identity(rec: dict, msg: dict) -> str | None:
    for src in (rec, msg):
        if not isinstance(src, dict):
            continue
        for key in AGENT_IDENTITY_FIELDS:
            v = src.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def parse_frontmatter_flat(text: str) -> dict:
    """Minimal flat frontmatter parse: every 'key: value' line becomes a flat
    key regardless of indentation (a later line with the same key wins).
    Deliberately re-implemented here, not imported, to keep this script
    standalone (house convention — see factory-usage-report.py's own
    re-implementation note). This is enough to recover routing-*.md's nested
    `routing:` block the same way factory-routing-report.py's parse_frontmatter
    does: the nested keys (agent, default_tier, ...) land as flat top-level
    keys because indentation is ignored."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip().strip("\"'")
    return fm


def load_routing_prose_events(working_dir: Path) -> list[dict]:
    """Best-effort agent-identity source for sidechain segments that carry no
    agent field of their own: .project/working/routing-{timestamp}.md
    frontmatter's `routing.agent` + `created` timestamp (the
    routing-transparency discipline in agents/delivery-lead.md). Returns
    [{agent, ts, file}]; entries missing an agent or an unparseable
    timestamp are silently dropped (fail-soft, not an error)."""
    events = []
    if not working_dir.is_dir():
        return events
    for path in sorted(working_dir.glob("routing-*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = parse_frontmatter_flat(text)
        agent = fm.get("agent")
        ts = parse_ts(fm.get("created"))
        if agent and ts is not None:
            events.append({"agent": agent, "ts": ts, "file": path.name})
    return events


def match_routing_prose_agent(ts: datetime | None, routing_prose_events: list[dict]) -> str | None:
    if ts is None or not routing_prose_events:
        return None
    window_seconds = ROUTING_PROSE_MATCH_WINDOW_SECONDS
    best = None
    for e in routing_prose_events:
        delta = abs((e["ts"] - ts).total_seconds())
        if delta <= window_seconds and (best is None or delta < best[0]):
            best = (delta, e["agent"])
    return best[1] if best else None


def resolve_sidechain_segment_identity(segment: dict, routing_prose_events: list[dict]) -> tuple[str, str]:
    """Returns (agent_label, source) where source is 'field' | 'routing-match'
    | 'unattributed'."""
    if segment.get("identity_field"):
        return segment["identity_field"], "field"
    matched = match_routing_prose_agent(segment.get("start_ts"), routing_prose_events)
    if matched:
        return matched, "routing-match"
    return "unattributed-subagent", "unattributed"


# --------------------------------------------------------------------------
# Task-ledger parsing + window attribution (Job 2)
# --------------------------------------------------------------------------

TASK_BLOCK_RE = re.compile(r"(?m)^\s*-\s*id:\s*(.+?)\s*$")
TOP_LEVEL_KEY_RE = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_]*:\s*")


def _task_field(block: str, key: str) -> str | None:
    m = re.search(r"(?m)^\s*" + re.escape(key) + r":\s*(.+?)\s*$", block)
    if not m:
        return None
    return m.group(1).strip().strip("\"'") or None


def parse_task_ledger_file(path: Path) -> dict:
    """Tolerant parse of a slice-<id>-tasks.yaml ledger (loop-contracts.md
    §2). Not a real YAML parser (house convention — see
    factory-usage-report.py's ingest_working_artifacts for the same
    tolerant-regex approach applied to `agent`/`tier`); pulls just the
    fields this script needs: per-task id/agent/status/started_at/completed_at."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"slice": None, "tasks": []}
    slice_m = re.search(r"(?m)^slice:\s*(.+?)\s*$", text)
    slice_id = slice_m.group(1).strip().strip("\"'") if slice_m else None

    tasks = []
    matches = list(TASK_BLOCK_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]
        # For the last task in the list, cut the block at the next
        # column-0 key (gates:, state:, stop_flags: — ledger-level fields
        # that follow the tasks: list) so field lookups don't bleed past
        # the task's own indented block.
        cut = TOP_LEVEL_KEY_RE.search(block)
        if cut:
            block = block[:cut.start()]
        tasks.append({
            "id": m.group(1).strip().strip("\"'"),
            "agent": _task_field(block, "agent"),
            "status": _task_field(block, "status"),
            "started_at": parse_ts(_task_field(block, "started_at")),
            "completed_at": parse_ts(_task_field(block, "completed_at")),
        })
    return {"slice": slice_id, "tasks": tasks, "file": path.name}


def load_task_ledgers(working_dir: Path) -> list[dict]:
    ledgers = []
    if not working_dir.is_dir():
        return ledgers
    for path in sorted(working_dir.glob("slice-*-tasks.yaml")):
        ledgers.append(parse_task_ledger_file(path))
    return ledgers


def build_task_windows(ledgers: list[dict]) -> tuple[dict, int, int]:
    """Returns (windows, tasks_total, tasks_without_window). windows is
    {task_id: {slice, agent, start, end}} — only tasks with BOTH
    started_at and completed_at (end >= start) get a window; a task with
    only one timestamp, or none, can't be windowed and is counted in
    tasks_without_window instead."""
    windows = {}
    tasks_total = 0
    tasks_without_window = 0
    for ledger in ledgers:
        for t in ledger["tasks"]:
            tasks_total += 1
            start, end = t["started_at"], t["completed_at"]
            if start is not None and end is not None and end >= start:
                windows[t["id"]] = {
                    "slice": ledger["slice"], "agent": t["agent"],
                    "start": start, "end": end,
                }
            else:
                tasks_without_window += 1
    return windows, tasks_total, tasks_without_window


def attribute_task(ts: datetime | None, task_windows: dict) -> str | None:
    if ts is None or not task_windows:
        return None
    matches = [(tid, w["end"] - w["start"]) for tid, w in task_windows.items() if w["start"] <= ts <= w["end"]]
    if not matches:
        return None
    matches.sort(key=lambda mtc: (mtc[1], mtc[0]))
    return matches[0][0]


def build_drive_task_usage(drive_events: list[dict]) -> tuple[dict, dict]:
    """Exact per-task usage from drive.jsonl's real-usage fields, for tasks
    that ran under drive (references/loop-contracts.md §4). Returns
    (per_task_usage, per_task_meta) — meta carries {slice, agent} from the
    first record seen for that task."""
    per_task = defaultdict(blank_usage)
    per_task_meta = {}
    for rec in drive_events:
        task_id = rec.get("task")
        if not task_id:
            continue
        inp, out = num(rec.get("input_tokens")), num(rec.get("output_tokens"))
        cr, cc = num(rec.get("cache_read_input_tokens")), num(rec.get("cache_creation_input_tokens"))
        if any(v is not None for v in (inp, out, cr, cc)):
            add_usage(per_task[task_id], inp, out, cr, cc)
            per_task_meta.setdefault(task_id, {"slice": rec.get("slice"), "agent": rec.get("agent")})
    return dict(per_task), per_task_meta


def build_task_attribution_rows(task_windows: dict, mined_per_task: dict,
                                 drive_task_usage: dict, drive_task_meta: dict) -> list[dict]:
    rows = []
    all_task_ids = set(task_windows) | set(drive_task_usage)
    for task_id in sorted(all_task_ids):
        window = task_windows.get(task_id)
        exact = drive_task_usage.get(task_id)
        has_exact = exact is not None and exact["messages"] > 0
        if has_exact:
            usage = exact
            source = "exact"
            meta = drive_task_meta.get(task_id, {})
            slice_id = meta.get("slice") or (window["slice"] if window else None)
            agent = meta.get("agent") or (window["agent"] if window else None)
            window_str = (
                f"{window['start'].strftime('%Y-%m-%dT%H:%MZ')} → {window['end'].strftime('%Y-%m-%dT%H:%MZ')}"
                if window else "n/a (drive-only)"
            )
        elif window is not None and task_id in mined_per_task:
            usage = mined_per_task[task_id]
            source = "window"
            slice_id = window["slice"]
            agent = window["agent"]
            window_str = f"{window['start'].strftime('%Y-%m-%dT%H:%MZ')} → {window['end'].strftime('%Y-%m-%dT%H:%MZ')}"
        else:
            continue
        rows.append({
            "task": task_id, "slice": slice_id or "n/a", "agent": agent or "unknown",
            "window": window_str, "source": source, "usage": usage,
        })
    return rows


# --------------------------------------------------------------------------
# Usage accumulator
# --------------------------------------------------------------------------

def blank_usage() -> dict:
    return {"messages": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def add_usage(bucket: dict, inp, out, cache_read, cache_creation):
    bucket["messages"] += 1
    bucket["input_tokens"] += inp or 0
    bucket["output_tokens"] += out or 0
    bucket["cache_read_input_tokens"] += cache_read or 0
    bucket["cache_creation_input_tokens"] += cache_creation or 0


# --------------------------------------------------------------------------
# Transcript mining
# --------------------------------------------------------------------------

def mine_transcripts(transcripts_dir: Path, session_ids: set, slice_windows: dict,
                      routing_prose_events: list[dict] | None = None,
                      task_windows: dict | None = None) -> dict:
    per_session = defaultdict(blank_usage)
    per_model = defaultdict(blank_usage)
    per_day = defaultdict(blank_usage)
    per_slice = defaultdict(blank_usage)
    unattributed_slice = blank_usage()
    per_task = defaultdict(blank_usage)
    unattributed_task = blank_usage()
    main_thread_totals = blank_usage()
    sidechain_totals = blank_usage()
    raw_sidechain_segments = []  # per-file, in mining order
    routing_prose_events = routing_prose_events or []
    task_windows = task_windows or {}
    files = sorted(transcripts_dir.glob("*.jsonl"))
    matched_by_filename = 0
    parse_errors = 0
    total_lines = 0
    saw_isSidechain_field = False

    for path in files:
        session_id = path.stem
        if session_id in session_ids:
            matched_by_filename += 1
        current_segment = None
        last_sidechain_ts = None
        main_intervened = False
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    total_lines += 1
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        parse_errors += 1
                        continue
                    if not isinstance(rec, dict):
                        continue

                    if "isSidechain" in rec:
                        saw_isSidechain_field = True
                    is_side = bool(rec.get("isSidechain"))
                    rec_type = rec.get("type")

                    # A main-thread conversational turn seen while a sidechain
                    # segment is open closes that segment (job 1b: "a
                    # main-thread message intervenes"). Non-assistant/user
                    # record types (tool results, summaries, etc.) don't
                    # count as a conversational turn either way.
                    if rec_type in ("assistant", "user") and not is_side and current_segment is not None:
                        main_intervened = True

                    if rec_type != "assistant":
                        continue
                    msg = rec.get("message")
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    if not isinstance(usage, dict) or not usage:
                        continue
                    inp = num(usage.get("input_tokens"))
                    out = num(usage.get("output_tokens"))
                    cr = num(usage.get("cache_read_input_tokens"))
                    cc = num(usage.get("cache_creation_input_tokens"))
                    model = msg.get("model") or rec.get("model") or "unknown"
                    ts = parse_ts(rec.get("timestamp") or rec.get("ts"))
                    day = ts.strftime("%Y-%m-%d") if ts else "unknown"

                    add_usage(per_session[session_id], inp, out, cr, cc)
                    add_usage(per_model[model], inp, out, cr, cc)
                    add_usage(per_day[day], inp, out, cr, cc)

                    slice_id = attribute_slice(ts, slice_windows) if ts else None
                    if slice_id:
                        add_usage(per_slice[slice_id], inp, out, cr, cc)
                    else:
                        add_usage(unattributed_slice, inp, out, cr, cc)

                    task_id = attribute_task(ts, task_windows) if ts else None
                    if task_id:
                        add_usage(per_task[task_id], inp, out, cr, cc)
                    else:
                        add_usage(unattributed_task, inp, out, cr, cc)

                    if is_side:
                        add_usage(sidechain_totals, inp, out, cr, cc)
                        gap_broken = (
                            current_segment is None
                            or main_intervened
                            or (
                                last_sidechain_ts is not None and ts is not None
                                and (ts - last_sidechain_ts).total_seconds() > SIDECHAIN_SEGMENT_GAP_SECONDS
                            )
                        )
                        if gap_broken:
                            if current_segment is not None:
                                raw_sidechain_segments.append(current_segment)
                            current_segment = {
                                "file": path.name, "start_ts": ts, "end_ts": ts,
                                "usage": blank_usage(), "identity_field": None,
                            }
                        if current_segment["identity_field"] is None:
                            ident = extract_agent_identity(rec, msg)
                            if ident:
                                current_segment["identity_field"] = ident
                        add_usage(current_segment["usage"], inp, out, cr, cc)
                        if ts is not None:
                            if current_segment["start_ts"] is None:
                                current_segment["start_ts"] = ts
                            current_segment["end_ts"] = ts
                            last_sidechain_ts = ts
                        main_intervened = False
                    else:
                        add_usage(main_thread_totals, inp, out, cr, cc)
        except OSError:
            continue
        if current_segment is not None:
            raw_sidechain_segments.append(current_segment)

    sidechain_segments = []
    for idx, seg in enumerate(raw_sidechain_segments, start=1):
        agent, source = resolve_sidechain_segment_identity(seg, routing_prose_events)
        sidechain_segments.append({
            "segment_id": f"{seg['file']}#{idx}",
            "file": seg["file"],
            "start_ts": seg["start_ts"],
            "end_ts": seg["end_ts"],
            "agent": agent,
            "attribution_source": source,
            "usage": seg["usage"],
            "matched_slice": attribute_slice(seg["start_ts"], slice_windows) if seg["start_ts"] else None,
        })

    return {
        "files_found": len(files),
        "matched_by_filename": matched_by_filename,
        "total_lines_read": total_lines,
        "parse_errors": parse_errors,
        "per_session": dict(per_session),
        "per_model": dict(per_model),
        "per_day": dict(per_day),
        "per_slice": dict(per_slice),
        "unattributed_slice": unattributed_slice,
        "per_task": dict(per_task),
        "unattributed_task": unattributed_task,
        "main_thread_totals": main_thread_totals,
        "sidechain_totals": sidechain_totals,
        "sidechain_segments": sidechain_segments,
        "saw_isSidechain_field": saw_isSidechain_field,
    }


# --------------------------------------------------------------------------
# Proxy calibration: tier cost_proxy (relative unit, from drive.jsonl) vs
# actual mined tokens, per slice, for slices where both exist.
# --------------------------------------------------------------------------

def build_proxy_calibration(drive_events: list[dict], per_slice_tokens: dict) -> list[dict]:
    cost_proxy_by_slice = defaultdict(float)
    for rec in drive_events:
        slice_id = rec.get("slice")
        cp = num(rec.get("cost_proxy"))
        if slice_id and cp is not None:
            cost_proxy_by_slice[slice_id] += cp

    rows = []
    all_slices = set(cost_proxy_by_slice) | set(per_slice_tokens)
    for slice_id in sorted(all_slices):
        cost_proxy = cost_proxy_by_slice.get(slice_id)
        usage = per_slice_tokens.get(slice_id)
        total_tokens = (usage["input_tokens"] + usage["output_tokens"]) if usage else None
        ratio = (
            round(total_tokens / cost_proxy, 1)
            if (cost_proxy and total_tokens is not None and cost_proxy > 0)
            else None
        )
        rows.append({
            "slice": slice_id,
            "cost_proxy_total": round(cost_proxy, 3) if cost_proxy is not None else None,
            "actual_total_tokens": total_tokens,
            "tokens_per_cost_proxy_unit": ratio,
        })
    return rows


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------

def build_report(project_dir: Path, claude_projects: Path, transcripts_dir_override: Path | None) -> dict:
    telemetry_dir = project_dir / "telemetry"
    working_dir = project_dir / "working"
    project_root = project_root_from_dot_dir(project_dir)

    sessions_events = read_jsonl(telemetry_dir / "sessions.jsonl")
    drive_events = read_jsonl(telemetry_dir / "drive.jsonl")
    routing_events = read_jsonl(telemetry_dir / "model-routing.jsonl")
    session_ids = {e.get("session") for e in sessions_events if e.get("session")}

    routing_prose_events = load_routing_prose_events(working_dir)
    task_ledgers = load_task_ledgers(working_dir)
    task_windows, tasks_total, tasks_without_window = build_task_windows(task_ledgers)
    drive_task_usage, drive_task_meta = build_drive_task_usage(drive_events)

    # First-class source: tokens.jsonl — per-session usage captured
    # deterministically by the SessionEnd hook for EVERY session (interactive
    # or drive). Sessions present here are authoritative; transcript mining
    # below only fills sessions the hook missed (dedupe by session id).
    hook_token_events = read_jsonl(telemetry_dir / "tokens.jsonl")
    hook_sessions = {e.get("session") for e in hook_token_events if e.get("session")}

    if transcripts_dir_override is not None:
        transcripts_dir = transcripts_dir_override
        resolution_note = f"explicit --transcripts-dir: {transcripts_dir}"
        dir_exists = transcripts_dir.is_dir()
        if not dir_exists:
            resolution_note += " (does not exist)"
    else:
        transcripts_dir, resolution_note = resolve_transcripts_dir(project_root, claude_projects)
        dir_exists = transcripts_dir is not None and transcripts_dir.is_dir()

    coverage_notes = [resolution_note]

    if not dir_exists:
        mined = {
            "files_found": 0, "matched_by_filename": 0, "total_lines_read": 0,
            "parse_errors": 0, "per_session": {}, "per_model": {}, "per_day": {},
            "per_slice": {}, "unattributed_slice": blank_usage(),
            "per_task": {}, "unattributed_task": blank_usage(),
            "main_thread_totals": blank_usage(), "sidechain_totals": blank_usage(),
            "sidechain_segments": [], "saw_isSidechain_field": False,
        }
        coverage_notes.append(
            "No transcripts found — this is the expected result in CI/sandboxes "
            "without a local ~/.claude/projects store, or on a machine that has "
            "never run Claude Code interactively against this project. All token "
            "totals below are zero; that is not the same as zero real usage."
        )
    else:
        slice_windows = build_slice_windows(routing_events, drive_events)
        mined = mine_transcripts(transcripts_dir, session_ids, slice_windows,
                                  routing_prose_events, task_windows)
        if mined["files_found"] == 0:
            coverage_notes.append(f"Transcript directory {transcripts_dir} exists but contains no *.jsonl files.")
        elif mined["matched_by_filename"] == 0:
            coverage_notes.append(
                f"{mined['files_found']} transcript file(s) found, but none matched a known session id from "
                "sessions.jsonl by filename — session-level totals below use the transcript's own filename as "
                "the session key regardless (best-effort labeling, not a verified session match)."
            )
        if not mined["saw_isSidechain_field"]:
            coverage_notes.append(
                "No mined transcript line carried an `isSidechain` field — this Claude Code "
                "version's transcripts predate sidechain tracking, or no transcripts were "
                "mined at all. Section 8 (per agent invocation) is skipped rather than "
                "guessed."
            )

    if tasks_total == 0:
        coverage_notes.append(
            "No task ledger (.project/working/slice-*-tasks.yaml) found — section 9 "
            "(per task, window-attributed) has nothing to attribute against."
        )
    elif not task_windows:
        coverage_notes.append(
            f"{tasks_total} task(s) found across {len(task_ledgers)} ledger(s), but none "
            "carry both started_at and completed_at yet (references/loop-contracts.md §2) "
            "— section 9 (per task, window-attributed) has no windows to attribute against."
        )
    elif tasks_without_window:
        coverage_notes.append(
            f"{tasks_without_window} of {tasks_total} ledger task(s) lack a complete "
            "started_at/completed_at pair and are excluded from window attribution."
        )

    # ---- Drive-run real usage (already captured deterministically by
    # scripts/praxis-drive.sh — surfaced here for a single combined view) ----
    drive_real_usage = blank_usage()
    drive_total_cost_usd = 0.0
    have_drive_cost = False
    for rec in drive_events:
        inp, out = num(rec.get("input_tokens")), num(rec.get("output_tokens"))
        cr, cc = num(rec.get("cache_read_input_tokens")), num(rec.get("cache_creation_input_tokens"))
        if any(v is not None for v in (inp, out, cr, cc)):
            add_usage(drive_real_usage, inp, out, cr, cc)
        cost = num(rec.get("total_cost_usd"))
        if cost is not None:
            drive_total_cost_usd += cost
            have_drive_cost = True

    proxy_calibration = build_proxy_calibration(drive_events, mined["per_slice"])
    task_attribution_rows = build_task_attribution_rows(
        task_windows, mined["per_task"], drive_task_usage, drive_task_meta
    )

    # Merge hook-captured per-session usage (tokens.jsonl, authoritative) over
    # mined transcripts: hook record replaces the mined bucket for the same
    # session; hook-only sessions are added. Mining remains for sessions the
    # hook missed (pre-upgrade sessions, crashed sessions without SessionEnd).
    hook_merged = 0
    for e in hook_token_events:
        sid = e.get("session")
        if not sid:
            continue
        bucket = blank_usage()
        for k in bucket:
            v = e.get(k)
            if isinstance(v, (int, float)):
                bucket[k] = int(v)
        bucket["messages"] = mined["per_session"].get(sid, {}).get("messages", 0)
        mined["per_session"][sid] = bucket
        hook_merged += 1
    if hook_merged:
        coverage_notes.append(
            f"{hook_merged} session(s) use authoritative SessionEnd-hook token capture "
            "(telemetry/tokens.jsonl); transcript mining filled the rest."
        )

    totals = blank_usage()
    for bucket in mined["per_session"].values():
        for k in totals:
            totals[k] += bucket[k]

    input_output_ratio = (
        round(totals["input_tokens"] / totals["output_tokens"], 2)
        if totals["output_tokens"] else None
    )
    cache_total = totals["cache_read_input_tokens"] + totals["cache_creation_input_tokens"]
    cache_hit_ratio = (
        round(totals["cache_read_input_tokens"] / cache_total, 3)
        if cache_total else None
    )

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_dir": str(project_dir),
        "transcripts_dir": str(transcripts_dir) if transcripts_dir else None,
        "coverage_notes": coverage_notes,
        "mined": mined,
        "totals": totals,
        "input_output_ratio": input_output_ratio,
        "cache_hit_ratio": cache_hit_ratio,
        "drive_real_usage": {
            "usage": drive_real_usage,
            "total_cost_usd": round(drive_total_cost_usd, 4) if have_drive_cost else None,
            "runs_with_cost_data": have_drive_cost,
        },
        "proxy_calibration": proxy_calibration,
        "sidechain_segments": mined["sidechain_segments"],
        "saw_isSidechain_field": mined["saw_isSidechain_field"],
        "main_thread_totals": mined["main_thread_totals"],
        "sidechain_totals": mined["sidechain_totals"],
        "task_attribution_rows": task_attribution_rows,
        "tasks_total": tasks_total,
        "tasks_without_window": tasks_without_window,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def _usage_row(label: str, u: dict) -> str:
    return f"| {label} | {u['messages']} | {u['input_tokens']} | {u['output_tokens']} | {u['cache_read_input_tokens']} | {u['cache_creation_input_tokens']} |"


def render_markdown(agg: dict) -> str:
    lines = []
    lines.append(f"# Factory token report — {agg['generated_at']}")
    lines.append("")
    lines.append(f"Project dir: `{agg['project_dir']}`")
    lines.append(f"Transcripts dir: `{agg['transcripts_dir'] or 'n/a'}`")
    lines.append("")

    lines.append("## 1. Coverage")
    lines.append("")
    for n in agg["coverage_notes"]:
        lines.append(f"- {n}")
    m = agg["mined"]
    lines.append(f"- Transcript files found: {m['files_found']} (matched to a known session id by filename: {m['matched_by_filename']})")
    lines.append(f"- Assistant-message lines with usage mined: {sum(v['messages'] for v in m['per_session'].values())}")
    if m["parse_errors"]:
        lines.append(f"- Lines that failed to parse as JSON (skipped, fail-soft): {m['parse_errors']}")
    lines.append("")

    lines.append("## 2. Totals")
    lines.append("")
    t = agg["totals"]
    lines.append(f"- Input tokens: {t['input_tokens']}")
    lines.append(f"- Output tokens: {t['output_tokens']}")
    lines.append(f"- Cache-read input tokens: {t['cache_read_input_tokens']}")
    lines.append(f"- Cache-creation input tokens: {t['cache_creation_input_tokens']}")
    ratio = agg["input_output_ratio"]
    lines.append(f"- Input:output ratio: {ratio if ratio is not None else 'n/a (no output tokens)'}")
    chr_ = agg["cache_hit_ratio"]
    lines.append(f"- Cache hit ratio (cache-read ÷ (cache-read + cache-creation)): {chr_ if chr_ is not None else 'n/a (no cache activity)'}")
    lines.append("")

    lines.append("## 3. Per-model")
    lines.append("")
    if m["per_model"]:
        lines.append("| Model | Messages | Input | Output | Cache-read | Cache-creation |")
        lines.append("|---|---|---|---|---|---|")
        for model, u in sorted(m["per_model"].items()):
            lines.append(_usage_row(model, u))
    else:
        lines.append("No per-model data (no transcripts mined).")
    lines.append("")

    lines.append("## 4. Per-day")
    lines.append("")
    if m["per_day"]:
        lines.append("| Day | Messages | Input | Output | Cache-read | Cache-creation |")
        lines.append("|---|---|---|---|---|---|")
        for day, u in sorted(m["per_day"].items()):
            lines.append(_usage_row(day, u))
    else:
        lines.append("No per-day data (no transcripts mined).")
    lines.append("")

    lines.append("## 5. Per-slice (best-effort time-window attribution)")
    lines.append("")
    if m["per_slice"]:
        lines.append("| Slice | Messages | Input | Output | Cache-read | Cache-creation |")
        lines.append("|---|---|---|---|---|---|")
        for slice_id, u in sorted(m["per_slice"].items()):
            lines.append(_usage_row(slice_id, u))
        lines.append(_usage_row("(unattributed)", m["unattributed_slice"]))
    else:
        lines.append("No per-slice data (no transcripts mined, or no slice windows could be built from routing/drive telemetry).")
    lines.append("")
    lines.append(
        "Slice attribution is best-effort: a transcript message is attributed to the "
        "narrowest slice window (padded ±3h) whose observed telemetry timestamps "
        "(model-routing.jsonl + drive.jsonl) cover the message's own timestamp. "
        "Overlapping slices or gaps in telemetry will misattribute or drop messages "
        "into the unattributed bucket — treat this table as directional, not exact."
    )
    lines.append("")

    lines.append("## 6. Drive-runner real usage (scripts/praxis-drive.sh, deterministic)")
    lines.append("")
    dr = agg["drive_real_usage"]
    lines.append(
        "This is the OTHER real-token capture path — headless `praxis-drive.sh` "
        "iterations that captured `--output-format json` usage directly, no "
        "transcript mining needed. Surfaced here for one combined picture."
    )
    lines.append("")
    lines.append(_usage_row("drive.jsonl", dr["usage"]).replace("| drive.jsonl |", "| Source | Messages | Input | Output | Cache-read | Cache-creation |\n|---|---|---|---|---|---|\n| drive.jsonl |"))
    if dr["total_cost_usd"] is not None:
        lines.append(f"\nTotal real cost reported by the harness across drive iterations: ${dr['total_cost_usd']}")
    else:
        lines.append("\nNo `total_cost_usd` recorded in drive.jsonl yet (dry-runs, a non-JSON harness, or no drive runs at all).")
    lines.append("")

    lines.append("## 7. Proxy calibration (tier cost_proxy vs actual tokens, per slice)")
    lines.append("")
    pc = agg["proxy_calibration"]
    if pc:
        lines.append("| Slice | cost_proxy total (drive.jsonl) | Actual tokens (mined) | Tokens per cost_proxy unit |")
        lines.append("|---|---|---|---|")
        for row in pc:
            cp = row["cost_proxy_total"] if row["cost_proxy_total"] is not None else "n/a"
            tok = row["actual_total_tokens"] if row["actual_total_tokens"] is not None else "n/a"
            ratio = row["tokens_per_cost_proxy_unit"] if row["tokens_per_cost_proxy_unit"] is not None else "n/a"
            lines.append(f"| {row['slice']} | {cp} | {tok} | {ratio} |")
        lines.append("")
        lines.append(
            "Reads governance/model-routing.yaml's `cost_weights` (deep/standard/light) "
            "produce `cost_proxy` — a RELATIVE unit, not a token or dollar count "
            "(see docs/telemetry.md). This table is the calibration check: rows with both "
            "columns populated let you sanity-check whether the tier weights roughly "
            "track real token consumption for slices that were also driven headlessly."
        )
    else:
        lines.append("No slice had both a cost_proxy total (drive.jsonl) and mined token data — nothing to calibrate yet.")
    lines.append("")

    lines.append("## 8. Per agent invocation (sidechain segments)")
    lines.append("")
    if not m["saw_isSidechain_field"]:
        lines.append(
            "Skipped: no mined transcript line carried an `isSidechain` field. Either no "
            "transcripts were mined, or this Claude Code version's transcripts predate "
            "sidechain (subagent) tracking — this script degrades honestly rather than "
            "guessing which lines were subagent activity."
        )
    else:
        segs = agg["sidechain_segments"]
        if segs:
            lines.append("| Segment | Agent (best-effort) | Attribution source | Messages | Input | Output | Cache-read | Cache-creation | Matched slice |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for seg in segs:
                u = seg["usage"]
                lines.append(
                    f"| {seg['segment_id']} | {seg['agent']} | {seg['attribution_source']} | "
                    f"{u['messages']} | {u['input_tokens']} | {u['output_tokens']} | "
                    f"{u['cache_read_input_tokens']} | {u['cache_creation_input_tokens']} | "
                    f"{seg['matched_slice'] or 'unattributed'} |"
                )
            lines.append("")
            lines.append(
                "A segment groups contiguous sidechain (subagent/Task-tool) assistant "
                "messages within one transcript file — a new segment starts when the gap "
                "since the previous sidechain message exceeds 5 minutes, or a main-thread "
                "message intervenes. `Attribution source` is honest about how the agent "
                "label was grounded: `field` (an agent-identity field was present on the "
                "line/message), `routing-match` (best-effort ±3-minute match against "
                "`routing-*.md` frontmatter timestamps), or `unattributed` (neither — shown "
                "as `unattributed-subagent`)."
            )
        else:
            lines.append("`isSidechain` is present in this transcript set, but no sidechain (subagent) messages were found.")
        lines.append("")
        lines.append("**Main-thread vs sidechain split (all mined messages):**")
        lines.append("")
        lines.append("| Thread | Messages | Input | Output | Cache-read | Cache-creation |")
        lines.append("|---|---|---|---|---|---|")
        lines.append(_usage_row("main-thread", agg["main_thread_totals"]))
        lines.append(_usage_row("sidechain", agg["sidechain_totals"]))
    lines.append("")

    lines.append("## 9. Per task (window-attributed, approximation)")
    lines.append("")
    lines.append(
        "Shared-context input tokens are allocated to a task by time window — an "
        "approximation, unlike `drive.jsonl`'s exact per-iteration measurement. A task "
        "gets a window only when its ledger entry carries both `started_at` and "
        "`completed_at` (references/loop-contracts.md §2). When a task has BOTH an exact "
        "`drive.jsonl` figure and a window approximation, the exact figure is shown "
        "(`source: exact`); otherwise the window approximation is shown (`source: window`)."
    )
    lines.append("")
    rows = agg["task_attribution_rows"]
    if rows:
        lines.append("| Task | Slice | Agent | Window | Source | Messages | Input | Output | Cache-read | Cache-creation |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for row in rows:
            u = row["usage"]
            lines.append(
                f"| {row['task']} | {row['slice']} | {row['agent']} | {row['window']} | "
                f"{row['source']} | {u['messages']} | {u['input_tokens']} | {u['output_tokens']} | "
                f"{u['cache_read_input_tokens']} | {u['cache_creation_input_tokens']} |"
            )
    elif agg["tasks_total"] == 0:
        lines.append("No task ledger found (`.project/working/slice-*-tasks.yaml`) — nothing to attribute.")
    else:
        lines.append(
            f"{agg['tasks_total']} ledger task(s) found, but none carry a complete "
            "`started_at`/`completed_at` pair yet, and none have `drive.jsonl` exact "
            "usage either — nothing to attribute."
        )
    lines.append("")

    return "\n".join(lines)


def render_stdout_summary(agg: dict) -> str:
    t = agg["totals"]
    m = agg["mined"]
    lines = [
        "factory-token-report summary",
        f"  project: {agg['project_dir']}",
        f"  transcripts dir: {agg['transcripts_dir'] or 'n/a'}",
        f"  transcript files found: {m['files_found']} (matched by filename: {m['matched_by_filename']})",
        f"  totals: input={t['input_tokens']} output={t['output_tokens']} "
        f"cache_read={t['cache_read_input_tokens']} cache_creation={t['cache_creation_input_tokens']}",
    ]
    if m["files_found"] == 0:
        lines.append("  note: no transcripts found (expected in CI/sandboxes without a local Claude Code history)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Mine real Claude Code token usage from local session transcripts.")
    parser.add_argument("--project-dir", default=".", help="Project root, or a .project dir directly. Default: cwd.")
    parser.add_argument("--claude-projects", default="~/.claude/projects", help="Root of Claude Code's per-project transcript store.")
    parser.add_argument("--transcripts-dir", default=None, help="Exact directory of this project's *.jsonl transcripts (bypasses the munge/lookup).")
    parser.add_argument("--format", choices=["md", "json"], default="md")
    parser.add_argument("--out", default=None, help="Output file path.")
    args = parser.parse_args()

    project_root = Path(args.project_dir).expanduser().resolve()
    dot_project = resolve_project_dot_dir(project_root)
    claude_projects = Path(args.claude_projects).expanduser()
    transcripts_dir_override = Path(args.transcripts_dir).expanduser().resolve() if args.transcripts_dir else None

    agg = build_report(dot_project, claude_projects, transcripts_dir_override)

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
        out_path = dot_project / "telemetry" / "reports" / f"token-report-{date_str}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)

    print(render_stdout_summary(agg))
    print(f"\nMarkdown report written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
