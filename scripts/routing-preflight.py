#!/usr/bin/env python3
"""
routing-preflight.py — routing decision logger (deterministic, no human).

Routing policy (one rule): **correctness sets the tier floor; cost picks within
it; the prompt cache is never a reason to sit above the floor.**

  * UP-route  -> always applied, for correctness. Cost/cache never gate an
    up-route (a wrong answer re-reads the whole context to redo the work — the
    priciest event in a cache-dominated system).
  * DOWN-route -> applied. The cache is NOT a reason to block it: a tier change
    re-renders the prompt prefix (the reasoning/effort config is rendered into
    the prompt on Claude, Codex, and Gemini), so BOTH a model switch and an
    effort change forfeit the warm cache — there is no cache-preserving lever to
    substitute. Given a re-write happens either way, a model-down is cost-optimal
    for any reused prefix: the one-time re-write amortizes within ~1-2 reuses
    because the cheaper model's recurring cache reads are cheaper in absolute
    terms. Holding the more expensive model "for the cache" only pays off for a
    genuine one-shot (non-reused) call — surfaced here as an advisory note, never
    an enforced substitution.
  * effort-only move (same model) -> applied as requested.

The check is ADVISORY: it appends a `routing_preflight` record (route,
cache-read share, prefix amortization, rationale) to
.project/telemetry/model-routing.jsonl for review. It never denies a spawn or
rewrites the requested route — correctness enforcement lives in the rubric
(capability_tier + up-route), not here. Reads the recent cache profile from
.project/telemetry/agent-spawns.jsonl (invocation_usage records); makes no model
call. Always exits 0.
"""
import argparse, json, os, sys, datetime

TIER_ORDER = {"light": 0, "standard": 1, "deep": 2}
DEFAULTS = {
    "window": 20,
    # A prefix reused at least this many times (cache_read / cache_creation) is
    # "reused" — a model-down amortizes; below it, a one-shot HOLD is marginally
    # cheaper. Advisory only.
    "reuse_amortization_min": 1.5,
}


def load_cfg(project_dir):
    cfg = dict(DEFAULTS)
    import re
    for rel in (".project/governance/model-routing.yaml",
                "governance/model-routing.yaml",
                ".agents/plugins/praxis/governance/model-routing.yaml",
                ".team/governance/model-routing.yaml"):
        path = os.path.join(project_dir, rel)
        if not os.path.isfile(path):
            continue
        try:
            block = None
            for line in open(path):
                if re.match(r'^preflight:\s*$', line):
                    block = True; continue
                if block:
                    if re.match(r'^\S', line):
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
        "prefix_tokens_est": int((cc if cc else cr) / max(1, len(rows))),
        "window": len(rows),
    }


def decide(from_tier, to_tier, profile, cfg):
    fm, fe = resolve(from_tier)
    tm, te = resolve(to_tier)
    up = TIER_ORDER.get(to_tier, 1) > TIER_ORDER.get(from_tier, 1)
    axis = "effort" if fm == tm else "model"
    cache_note = "not_a_down_route"  # advisory tag: what the cache economics say for THIS route

    # Advisory only: the route is ALWAYS applied as requested. Correctness (the
    # rubric) sets the tier; the cache never blocks a down-route or substitutes a
    # lever.
    if axis == "effort":
        reason = "effort-only move (same model family) — applied as requested"
    elif up:
        reason = (f"up-route to {tm} for correctness — applied unconditionally "
                  f"(cost/cache never gate an up-route). {tm} starts cold; batch "
                  f"same-tier work to warm it once")
    else:
        if not profile:
            cache_note = "cold_start_no_warm_cache"
            reason = (f"model-down to {tm} — cold start / no recent telemetry; applied "
                      f"as requested (no warm cache in play)")
        else:
            amort = profile.get("amortization")
            reused = (amort == float("inf")) or (amort is not None and amort >= cfg["reuse_amortization_min"])
            amort_txt = "fully warm (no rewrites in window)" if amort == float("inf") else f"prefix reused {amort}x"
            if reused:
                cache_note = "route_down_amortizes"
                reason = (f"model-down to {tm} — {amort_txt}; cost-optimal for a reused prefix. "
                          f"A tier change re-renders the prefix either way (model OR effort), so the "
                          f"one-time cache re-write is unavoidable; on a cheaper model it amortizes "
                          f"within ~1-2 reuses. Applied as requested — cache does not gate the route.")
            else:
                cache_note = "one_shot_hold_marginally_cheaper"
                reason = (f"model-down to {tm} — {amort_txt} (barely reused). For a genuine one-shot "
                          f"call, holding {fm} is marginally cheaper (no re-write to amortize); "
                          f"otherwise model-down wins. Applied as requested — advisory only, cache "
                          f"does not gate the route.")

    return {
        "axis": axis,
        "direction": "up" if up else ("same" if from_tier == to_tier else "down"),
        "requested": {"tier": to_tier, "model": tm, "effort": te},
        "applied": {"tier": to_tier, "model": tm, "effort": te},   # always as requested
        "cache_read_share": profile["cache_read_share"] if profile else None,
        "amortization": (None if (profile and profile.get("amortization") == float("inf"))
                         else (profile.get("amortization") if profile else None)),
        "action": "apply",          # advisory: never blocks
        "cache_note": cache_note,   # queryable tag of the cache-economics judgment
        "reason": reason,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-tier", required=True, choices=["deep", "standard", "light"])
    ap.add_argument("--to-tier", required=True, choices=["deep", "standard", "light"])
    ap.add_argument("--project-dir", default=".")
    ap.add_argument("--session", default=""); ap.add_argument("--agent", default="")
    ap.add_argument("--slice", default=""); ap.add_argument("--task", default="")
    # Retained for backward-compat; the check is advisory in every mode now.
    ap.add_argument("--mode", default="advise", choices=["enforce", "advise"])
    ap.add_argument("--harness", default=(os.environ.get("PRAXIS_HARNESS") or "claude-code"),
                    help="which harness is routing (claude-code|codex|antigravity|...)")
    ap.add_argument("--no-log", action="store_true")
    a = ap.parse_args()

    cfg = load_cfg(a.project_dir)
    profile = recent_profile(a.project_dir, cfg["window"])
    d = decide(a.from_tier, a.to_tier, profile, cfg)
    d.update({"ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
              "event": "routing_preflight", "harness": a.harness, "mode": "advise",
              "session": a.session or None, "agent": a.agent or None,
              "slice": a.slice or None, "task": a.task or None,
              "from_tier": a.from_tier})

    if not a.no_log:
        try:
            tdir = os.path.join(a.project_dir, ".project", "telemetry")
            os.makedirs(tdir, exist_ok=True)
            with open(os.path.join(tdir, "model-routing.jsonl"), "a") as f:
                f.write(json.dumps(d) + "\n")
        except Exception:
            pass

    print(json.dumps(d))
    sys.exit(0)


if __name__ == "__main__":
    main()
