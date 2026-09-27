#!/usr/bin/env python3
"""factory-antigravity-report — surface the Antigravity (agy) telemetry.

The other factory-*-report.py scripts deliberately EXCLUDE agy rows: they do
token/cost/tier-decision accounting, and agy exposes none of that (no token
counts, no cache data, no per-agent model — see docs/antigravity-setup.md,
"Cache-aware routing on Antigravity"). So the agy telemetry we capture would be
write-only without this report.

Reads the agy-tagged telemetry under <project>/.project/telemetry/:
  * antigravity-activity.jsonl  — tool audit (Pre/PostToolUse: tool, stepIdx, error)
  * model-routing.jsonl         — agy `event:model_invocation` rows (harness=antigravity)
  * sessions.jsonl              — agy `event:session_stop` rows (harness=antigravity)

Reports session count + date range, tool-usage mix, model mix, tool-error rate,
and a tier-vs-model hygiene note. It NEVER reports tokens or cost — agy does not
expose them; anything here that looked like cost would be a guess.

Usage:
  scripts/factory-antigravity-report.py [--project-dir DIR] [--format md|json] [--out FILE]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

OWN_HARNESS = "antigravity"


def resolve_telemetry(project_dir: str) -> Path:
    """Accept a project root, a .project dir directly, or any dir that already
    contains a telemetry/ folder (matches the sibling reports, and also works
    when the .project dir has a non-standard basename)."""
    p = Path(project_dir).expanduser()
    if (p / "telemetry").is_dir():
        return p / "telemetry"
    if (p / ".project" / "telemetry").is_dir():
        return p / ".project" / "telemetry"
    base = p if p.name == ".project" else p / ".project"
    return base / "telemetry"


def read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def collect(telemetry: Path) -> dict:
    act = read_jsonl(telemetry / "antigravity-activity.jsonl")
    mr = [r for r in read_jsonl(telemetry / "model-routing.jsonl")
          if r.get("harness") == OWN_HARNESS]
    se = [r for r in read_jsonl(telemetry / "sessions.jsonl")
          if r.get("harness") == OWN_HARNESS]

    pre = [r for r in act if r.get("event") == "PreToolUse"]
    post = [r for r in act if r.get("event") == "PostToolUse"]
    sessions = {r.get("session") for r in act if r.get("session")}
    tools = collections.Counter(r.get("tool") for r in pre if r.get("tool"))
    errors = [r for r in post if r.get("error")]
    models = collections.Counter(r.get("model") for r in mr if r.get("model"))
    total_inv = sum(models.values())

    ts = sorted(r["ts"] for r in act if r.get("ts"))
    flash = sum(c for m, c in models.items() if "flash" in (m or ""))
    pro = sum(c for m, c in models.items() if "pro" in (m or ""))
    high = sum(c for m, c in models.items() if (m or "").endswith("-high"))

    return {
        "present": bool(act or mr or se),
        "sessions": len(sessions),
        "activity_events": len(act),
        "tool_calls": len(pre),
        "invocations": total_inv,
        "session_stops": len(se),
        "date_range": [ts[0] if ts else None, ts[-1] if ts else None],
        "tools": tools.most_common(),
        "tool_error_count": len(errors),
        "tool_error_rate": (len(errors) / len(post)) if post else 0.0,
        "models": models.most_common(),
        "pro_share": (pro / total_inv) if total_inv else 0.0,
        "flash_share": (flash / total_inv) if total_inv else 0.0,
        "high_effort_share": (high / total_inv) if total_inv else 0.0,
    }


def hygiene_notes(d: dict) -> list[str]:
    notes = []
    if not d["present"]:
        return ["No Antigravity telemetry found. Install the plugin and run agy in this workspace."]
    if d["invocations"]:
        if d["pro_share"] < 0.02:
            notes.append(
                f"Deep-tier work almost never ran on a `pro` model (pro share "
                f"{d['pro_share']*100:.1f}%). agy has no per-agent auto-routing, so tier "
                f"discipline depends on applying `/model` by hand — the advisory tier map "
                f"(governance/model-routing.yaml) maps deep -> pro/high."
            )
        if d["high_effort_share"] < 0.05:
            notes.append(
                f"High-effort slugs were rare ({d['high_effort_share']*100:.1f}% of invocations); "
                f"most work ran at the session default effort. Consider `--effort high` / a "
                f"`-high` slug for deep-tier tasks."
            )
    notes.append(
        "No token/cost figures: agy exposes none (not in hook payloads, transcripts, "
        "logs, or its DBs). This report is activity + routing only, by platform limit."
    )
    return notes


def render_md(d: dict) -> str:
    L = ["# factory-antigravity-report", ""]
    if not d["present"]:
        L.append("No Antigravity telemetry found under this project's `.project/telemetry/`.")
        return "\n".join(L)
    lo, hi = d["date_range"]
    L += [
        f"- Sessions: **{d['sessions']}**  (session-stop records: {d['session_stops']})",
        f"- Activity events: **{d['activity_events']}**  (tool calls: {d['tool_calls']})",
        f"- Model invocations: **{d['invocations']}**",
        f"- Tool errors: **{d['tool_error_count']}**  ({d['tool_error_rate']*100:.1f}% of PostToolUse)",
        f"- Date range: {lo or 'n/a'} → {hi or 'n/a'}",
        "",
        "## Model mix (which model actually served each invocation)",
        "",
    ]
    for m, c in d["models"]:
        share = (c / d["invocations"] * 100) if d["invocations"] else 0
        L.append(f"- {share:5.1f}%  `{m}`  ({c})")
    L += ["", "## Tool usage", ""]
    for t, c in d["tools"][:20]:
        L.append(f"- `{t}`: {c}")
    L += ["", "## Notes", ""]
    for n in hygiene_notes(d):
        L.append(f"- {n}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Report Antigravity (agy) telemetry (activity + routing; no tokens/cost).")
    ap.add_argument("--project-dir", default=".", help="Project root, or a .project dir directly. Default: cwd.")
    ap.add_argument("--format", choices=["md", "json"], default="md")
    ap.add_argument("--out", default=None, help="Write to this file instead of stdout.")
    a = ap.parse_args()

    telemetry = resolve_telemetry(a.project_dir)
    data = collect(telemetry)
    data["notes"] = hygiene_notes(data)
    out = json.dumps(data, indent=2) if a.format == "json" else render_md(data)

    if a.out:
        Path(a.out).expanduser().write_text(out)
        print(f"Antigravity report written to {a.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
