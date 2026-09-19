#!/usr/bin/env python3
"""
routing-preflight.py — cache-aware routing guardrail (deterministic, no human).

Given a PROPOSED tier route (from -> to), decide whether it would forfeit a warm,
well-amortized prompt cache, and if so SUBSTITUTE the cache-preserving lever
(keep the model, lower the effort) instead of switching model family.

Design: docs/... (preflight design). Rules:
  * effort-only move (same resolved model)        -> APPLY (cache-preserving)
  * model-family UP-switch                        -> APPLY + advise batching
  * model-family DOWN-switch, cold start          -> APPLY (no warm cache yet)
  * model-family DOWN-switch, cache_share < thr   -> APPLY (output-heavy; cheaper wins)
  * model-family DOWN-switch, cache_share >= thr  -> ENFORCE_EFFORT_DOWN (substitute)

Reads recent cache profile from .project/telemetry/agent-spawns.jsonl
(invocation_usage records), never makes a model call, appends a
`routing_preflight` audit record to .project/telemetry/model-routing.jsonl.

Exit codes: 0 applied-as-requested, 10 substituted effort-down, 20 apply+batch.
"""
import argparse, json, os, sys, datetime

TIER_ORDER = {"light": 0, "standard": 1, "deep": 2}
DEFAULTS = {
    "cache_read_mult": 0.1,
    "cache_write_mult": 1.25,
    "cache_share_threshold": 0.40,
    "window": 20,
    # relative input price per tier's model (opus=1.0, sonnet≈0.6, haiku≈0.2)
    "tier_price": {"deep": 1.0, "standard": 0.6, "light": 0.2},
}


def load_cfg(project_dir):
    cfg = dict(DEFAULTS)
    # optional preflight block in governance/model-routing.yaml (project override first)
    for rel in (".project/governance/model-routing.yaml",
                "governance/model-routing.yaml",
                ".agents/plugins/praxis/governance/model-routing.yaml",
                ".team/governance/model-routing.yaml"):
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            continue
        try:
            import re
            block = None
            for line in open(path):
                if re.match(r'^preflight:\s*$', line):
                    block = True; continue
                if block:
                    if re.match(r'^\S', line):  # dedented -> block ended
                        break
                    m = re.match(r'\s+([a-z_]+):\s*([0-9.]+)', line)
                    if m and m.group(1) in cfg:
                        cfg[m.group(1)] = float(m.group(2))
        except Exception:
            pass
        break
    return cfg


def resolve(tier):
    """Resolve a claude-code tier to (model_family, effort)."""
    m = {"deep": ("opus", "high"), "standard": ("sonnet", "medium"), "light": ("haiku", "low")}
    return m.get(tier, (tier, "medium"))


def recent_profile(project_dir, window):
    """cache_read_share + amortization from the last `window` invocation_usage rows."""
    path = os.path.join(project_dir, ".project", "telemetry", "agent-spawns.jsonl")
    if not os.path.isfile(path):
        return None
    rows = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or "invocation_usage" not in line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("event") == "invocation_usage":
                    rows.append(d)
    except Exception:
        return None
    rows = rows[-int(window):]
    if not rows:
        return None
    cr = sum(r.get("cache_read_input_tokens", 0) or 0 for r in rows)
    cc = sum(r.get("cache_creation_input_tokens", 0) or 0 for r in rows)
    inp = sum(r.get("input_tokens", 0) or 0 for r in rows)
    denom = cr + cc + inp
    if denom == 0:
        return None
    return {
        "cache_read_share": round(cr / denom, 4),
        "amortization": (round(cr / cc, 1) if cc else float("inf")),
        "prefix_tokens_est": int((cc if cc else cr) / max(1, len(rows))),  # avg prefix size per call
        "window": len(rows),
    }


def decide(from_tier, to_tier, profile, cfg):
    fm, fe = resolve(from_tier)
    tm, te = resolve(to_tier)
    up = TIER_ORDER.get(to_tier, 1) > TIER_ORDER.get(from_tier, 1)
    axis = "effort" if fm == tm else "model"
    r = cfg["tier_price"][to_tier] / cfg["tier_price"][from_tier] if from_tier in cfg["tier_price"] and to_tier in cfg["tier_price"] else None
    break_even = round((cfg["cache_write_mult"] / cfg["cache_read_mult"]) * (r / (1 - r)), 1) if r and r < 1 else None

    applied_model, applied_effort = tm, te
    est_saving = 0

    if axis == "effort":
        action, reason = "apply", "effort-only move (same model family) — cache-preserving; applied as requested"
    elif up:
        action = "apply"
        reason = f"up-route to {tm} for capability — applied as-is (correctness). {tm} starts cold; batch queued same-tier work to warm it once"
    else:
        # model-family DOWN-switch
        if not profile:
            action, reason = "apply", "cold start / no recent telemetry — no warm cache to forfeit; applied as requested"
        elif profile["cache_read_share"] < cfg["cache_share_threshold"]:
            action = "apply"
            reason = (f"output-heavy: cache-read share {profile['cache_read_share']:.0%} < "
                      f"{cfg['cache_share_threshold']:.0%} — a cheaper model genuinely wins; applied model-down to {tm}")
        else:
            # ENFORCE: keep the warm model, take only the lower effort
            action = "enforce_effort_down"
            applied_model, applied_effort = fm, te
            pfx = profile.get("prefix_tokens_est") or 0
            est_saving = int(pfx * (cfg["cache_write_mult"] - cfg["cache_read_mult"]))  # cold-write avoided vs warm-read
            amort = profile.get("amortization")
            amort_txt = "no rewrites in window (fully warm)" if amort == float("inf") else f"prefix reused {amort}x"
            reason = (f"context-heavy: cache-read share {profile['cache_read_share']:.0%} "
                      f"({amort_txt}) — model-down to {tm} would forfeit the warm {fm} "
                      f"prefix; kept {fm}, lowered effort {fe}->{te}")
    return {
        "axis": axis, "direction": "up" if up else ("same" if from_tier == to_tier else "down"),
        "requested": {"tier": to_tier, "model": tm, "effort": te},
        "applied": {"tier": to_tier if action != "enforce_effort_down" else from_tier + "@" + to_tier + "-effort",
                    "model": applied_model, "effort": applied_effort},
        "r": round(r, 3) if r else None, "break_even": break_even,
        "cache_read_share": profile["cache_read_share"] if profile else None,
        "amortization": (None if (profile and profile.get("amortization") == float("inf")) else (profile.get("amortization") if profile else None)),
        "action": action, "est_saving_tokens": est_saving, "reason": reason,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-tier", required=True, choices=["deep", "standard", "light"])
    ap.add_argument("--to-tier", required=True, choices=["deep", "standard", "light"])
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--session", default=""); ap.add_argument("--agent", default="")
    ap.add_argument("--slice", default=""); ap.add_argument("--task", default="")
    ap.add_argument("--mode", default="enforce", choices=["enforce", "advise"])
    ap.add_argument("--harness", default=(os.environ.get("PRAXIS_HARNESS") or "claude-code"),
                    help="which harness is routing (claude-code|codex|antigravity|...)")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args()

    cfg = load_cfg(a.project_dir)
    profile = recent_profile(a.project_dir, cfg["window"])
    d = decide(a.from_tier, a.to_tier, profile, cfg)
    d.update({"ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "event": "routing_preflight", "harness": a.harness, "mode": a.mode,
              "session": a.session or None, "agent": a.agent or None,
              "slice": a.slice or None, "task": a.task or None,
              "from_tier": a.from_tier})
    # In advise mode, record the intended action but do not present `applied` as final.
    if a.mode == "advise":
        d["applied_note"] = "advise mode: logged intent only; caller applied the requested route"

    if not a.no_log:
        try:
            tdir = os.path.join(a.project_dir, ".project", "telemetry")
            os.makedirs(tdir, exist_ok=True)
            with open(os.path.join(tdir, "model-routing.jsonl"), "a") as f:
                f.write(json.dumps(d) + "\n")
        except Exception:
            pass

    print(json.dumps(d))
    sys.exit({"apply": 0, "enforce_effort_down": 10}.get(d["action"], 0))


if __name__ == "__main__":
    main()
