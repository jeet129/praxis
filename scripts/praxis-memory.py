#!/usr/bin/env python3
"""praxis-memory — keep .project/ memory small, indexed and honest. Zero dependencies.

  praxis-memory where <kind>                    configured path (memory-layout.yaml)
  praxis-memory map                             the session-start memory map
  praxis-memory index                           regenerate .project/INDEX.yaml + .project/index/<kind>.yaml
  praxis-memory check [--strict]                frontmatter, broken links, budgets, raw evidence in memory
  praxis-memory migrate-local [--apply]         move raw evidence (logs, JUnit, dumps, screenshots) out of
                                                memory into gitignored .project/local/, untrack it
  praxis-memory consolidate [--apply]           archive closed-slice and stale working notes, collapse
                                                review rounds, trim the inbox, merge lane notes,
                                                prune old evidence runs
  praxis-memory consolidate --print-prompt      the model-side consolidation prompt (re-check facts)
  praxis-memory context-setup [--apply]         add compaction instructions: a managed block in
                                                CLAUDE.md, compact_prompt in .codex/config.toml
  praxis-memory review-context --base BRANCH    REVIEW.md + the diff-triggered checks that match this
                                                branch, both read from BASE (a change cannot edit its judge)

Common flags: --project-dir DIR, --json.
Everything is a dry run unless --apply is given. --apply moves files with
`git mv` when they are tracked, never deletes memory notes (only evidence runs
past retention inside gitignored .project/local/evidence/), never rewrites git
history, and writes a short record of what it did to
.project/operational/memory-maintenance/.

Why: the article "Components of agent memory" (Anthropic, 2026) found that
over-recording and stale notes hurt agents more than missing notes; the cure
is a small injected layer, an index, and an offline pass that prunes and
re-checks. This script is the deterministic half of that pass.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (os.path.join(HERE, "..", "hooks"), os.path.join(HERE, "hooks"), HERE):
    if os.path.isfile(os.path.join(cand, "praxis_project.py")):
        sys.path.insert(0, os.path.abspath(cand))
        break
import praxis_project as pp  # noqa: E402

REQUIRED_FM = ("type", "date", "source")
DEFAULT_RULES = ".project/procedural/REVIEW.md"
DEFAULT_CHECKS = ".project/procedural/checks.yaml"
NOTE_EXT = (".md", ".markdown")
EVIDENCE_EXT = {"log", "exit", "pyc", "png", "jpg", "jpeg", "gif", "webp", "webm", "mp4", "mov",
                "zip", "gz", "tgz", "tar", "har", "trace", "sqlite", "db", "coverage", "out"}
EVIDENCE_DIR_RE = re.compile(r"(^|[-_.])(runs?|rerun|artifacts?|evidence|screenshots?|failing-set|staged|"
                             r"proofs?|frozen-inputs|fixtures|logs?)([-_.]|$)|^__pycache__$|^run-", re.I)
EVIDENCE_NAME_RE = re.compile(r"(^verify-|junit|pytest|stdout|stderr|output|result|trace|coverage|"
                              r"dump|snapshot|[-_.]log([-_.]|$)|[-_.]run\d*([-_.]|$))", re.I)
CLOSED_STATUS_RE = re.compile(r"^\s*(closed|done|resolved|merged|superseded|rejected|withdrawn|delivered|"
                              r"complete|completed|shipped(?!\s+for\s+approval)|cancell?ed)\b", re.I)
ROUND_SUFFIX_RE = re.compile(r"(-(round|rr|r|v|pass|delta|attempt|iter)-?\d+[a-z]?|-(second|third|fourth|final)"
                             r"-pass|-rerun|-recheck|-final\d*|-redo|-retry|-update\d*|-followup\d*)$", re.I)
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[-_]")
BIG = 256 * 1024


# ── helpers ─────────────────────────────────────────────────────────────────
def kpath(root, kind):
    return os.path.join(root, *pp.where(root, kind).split("/"))


def tracked_set(root):
    if not pp.is_git(root):
        return set()
    r = pp.git(root, "ls-files", "-z", "--", ".project", timeout=60)
    return {p for p in r.stdout.split("\0") if p}


def git_rel(root, path):
    """Path relative to root, matching `git ls-files` run from root."""
    return pp.rel(root, path)


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def newest_mtime(path):
    if os.path.isfile(path):
        return os.path.getmtime(path)
    m = os.path.getmtime(path)
    for dp, _, fns in os.walk(path):
        for f in fns:
            try:
                m = max(m, os.path.getmtime(os.path.join(dp, f)))
            except OSError:
                pass
    return m


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def frontmatter(path):
    try:
        with open(path, errors="replace") as fh:
            first = fh.readline()
            if first.strip() != "---":
                return None, first
            lines = []
            for _ in range(80):
                line = fh.readline()
                if not line or line.strip() == "---":
                    break
                lines.append(line.rstrip("\n"))
    except Exception:
        return None, ""
    fm = {}
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        v = pp.strip_comment(m.group(2))
        if v.startswith("[") and v.endswith("]"):
            v = [pp.unquote(x.strip()) for x in v[1:-1].split(",") if x.strip()]
        else:
            v = pp.unquote(v)
        fm[m.group(1)] = v
    return fm, ""


def title_of(path, fm):
    if fm and fm.get("title"):
        return str(fm["title"])
    try:
        for line in open(path, errors="replace"):
            if line.startswith("# "):
                return line[2:].strip()[:120]
    except Exception:
        pass
    return os.path.splitext(os.path.basename(path))[0]


def date_of(path, fm):
    if fm and fm.get("date"):
        return str(fm["date"])[:10]
    m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    if m:
        return m.group(1)
    return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()


def yq(v):
    return json.dumps(v, ensure_ascii=False)


def memory_kinds(root):
    """Kinds that hold durable notes (index + check). Working and local are excluded."""
    out = []
    seen = set()
    for kind in ("adr", "semantic", "procedural", "episodic", "review", "incident", "risk_acceptance"):
        p = kpath(root, kind)
        if os.path.isdir(p) and os.path.realpath(p) not in seen:
            seen.add(os.path.realpath(p))
            out.append((kind, p))
    return out


def kind_notes(root):
    """(kind, note) pairs, each note once: a kind nested in another (reviews under
    operational/) is walked on its own and skipped by its parent."""
    kinds = memory_kinds(root)
    paths = [p for _, p in kinds]
    for kind, p in kinds:
        nested = [q for q in paths if q != p and os.path.realpath(q).startswith(os.path.realpath(p) + os.sep)]
        for f in notes_in(p, skip_paths=nested):
            yield kind, f


def notes_in(path, skip_dirs=("local", "verification", "index", "telemetry", "memory-maintenance"),
             skip_paths=()):
    skip_real = {os.path.realpath(p) for p in skip_paths}
    for dp, dns, fns in os.walk(path):
        dns[:] = [d for d in dns if d not in skip_dirs and not d.startswith(".")
                  and os.path.realpath(os.path.join(dp, d)) not in skip_real]
        for f in fns:
            if f.endswith(NOTE_EXT) and f not in ("INDEX.md",):
                yield os.path.join(dp, f)


# ── index ───────────────────────────────────────────────────────────────────
def cmd_index(root, args):
    proj = os.path.join(root, ".project")
    idx_dir = os.path.join(proj, "index")
    os.makedirs(idx_dir, exist_ok=True)
    counts, by_tag, by_domain = {}, {}, {}
    grouped = {}
    for kind, f in kind_notes(root):
        grouped.setdefault(kind, []).append(f)
    for kind, path in memory_kinds(root):
        entries = []
        for f in sorted(grouped.get(kind, [])):
            fm, _ = frontmatter(f)
            fm = fm or {}
            rid = pp.rel(root, f)
            tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
            doms = fm.get("impacted_domains") if isinstance(fm.get("impacted_domains"), list) else []
            entries.append({"path": rid, "title": title_of(f, fm), "type": fm.get("type") or kind,
                            "date": date_of(f, fm), "tags": tags, "domains": doms,
                            "archived": "/archive/" in rid, "frontmatter": bool(fm)})
            for t in tags:
                by_tag.setdefault(str(t), []).append(rid)
            for d in doms:
                by_domain.setdefault(str(d), []).append(rid)
        entries.sort(key=lambda e: e["date"], reverse=True)
        counts[kind] = len(entries)
        with open(os.path.join(idx_dir, f"{kind}.yaml"), "w") as fh:
            fh.write(f"# Generated by praxis-memory index — do not edit. {pp.now_iso()}\n")
            fh.write(f"kind: {kind}\npath: {yq(pp.rel(root, path))}\nentries:\n")
            for e in entries:
                fh.write(f"  - path: {yq(e['path'])}\n    title: {yq(e['title'])}\n    type: {yq(e['type'])}\n"
                         f"    date: {yq(e['date'])}\n")
                if e["tags"]:
                    fh.write(f"    tags: {yq(e['tags'])}\n")
                if e["domains"]:
                    fh.write(f"    domains: {yq(e['domains'])}\n")
                if e["archived"]:
                    fh.write("    archived: true\n")
    with open(os.path.join(proj, "INDEX.yaml"), "w") as fh:
        fh.write(f"# Generated by praxis-memory index — do not edit. {pp.now_iso()}\n")
        fh.write("# Per-kind entries: .project/index/<kind>.yaml. Layout: .project/governance/memory-layout.yaml\n")
        fh.write("counts:\n" + "".join(f"  {k}: {v}\n" for k, v in counts.items()))
        for name, table in (("by_tag", by_tag), ("by_domain", by_domain)):
            fh.write(f"{name}:\n" if table else f"{name}: {{}}\n")
            for k in sorted(table, key=lambda x: -len(table[x]))[:60]:
                fh.write(f"  {yq(k)}: {yq(sorted(table[k])[:25])}\n")
    result = {"counts": counts, "tags": len(by_tag), "domains": len(by_domain),
              "index": ".project/INDEX.yaml"}
    print(json.dumps(result) if args.json else
          "Indexed " + ", ".join(f"{k} {v}" for k, v in counts.items()) + " -> .project/INDEX.yaml, .project/index/")
    return 0


# ── evidence classification ─────────────────────────────────────────────────
def classify(path, is_dir):
    """'evidence', 'uncertain' or None (memory)."""
    name = os.path.basename(path)
    low = name.lower()
    if is_dir:
        return "evidence" if EVIDENCE_DIR_RE.search(name) else None
    ext = low.rsplit(".", 1)[-1] if "." in low else ""
    if low.endswith(NOTE_EXT) or ext in ("yaml", "yml"):
        return None
    if ext in EVIDENCE_EXT:
        return "evidence"
    code = ext in ("patch", "diff", "py", "sh", "ts", "js", "tmpl", "sql")
    if low.startswith("verify-") and not code:
        return "evidence"
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    if ext == "xml":
        return "evidence"
    if code:
        return "uncertain"
    if ext in ("txt", "json", "csv", "html", "jsonl", "tsv"):
        return "evidence" if (EVIDENCE_NAME_RE.search(name) or size > BIG) else "uncertain"
    return "uncertain" if size <= BIG else "evidence"


def scan_evidence(root):
    """Raw evidence sitting in memory folders. Returns (items, uncertain)."""
    items, uncertain = [], []
    bases = [kpath(root, "working"), kpath(root, "review"), kpath(root, "incident")]
    seen = set()
    for base in bases:
        if not os.path.isdir(base) or os.path.realpath(base) in seen:
            continue
        seen.add(os.path.realpath(base))
        for dp, dns, fns in os.walk(base):
            keep = []
            for d in dns:
                full = os.path.join(dp, d)
                rp = pp.rel(root, full)
                if rp.startswith((".project/local", ".project/operational/verification",
                                  ".project/operational/memory-maintenance")) or "/archive" in rp:
                    continue
                if os.path.realpath(full) in seen:
                    continue
                if classify(full, True) == "evidence":
                    items.append({"path": rp, "dir": True, "bytes": size_of(full)})
                else:
                    keep.append(d)
            dns[:] = keep
            for f in fns:
                full = os.path.join(dp, f)
                c = classify(full, False)
                rp = pp.rel(root, full)
                if c == "evidence":
                    items.append({"path": rp, "dir": False, "bytes": os.path.getsize(full)})
                elif c == "uncertain":
                    uncertain.append({"path": rp, "bytes": os.path.getsize(full)})
    return items, uncertain


def tracked_ignored(root, tracked):
    """Tracked files that the managed .project/.gitignore now ignores (raw telemetry etc.)."""
    pats = [p.strip() for p in pp.GITIGNORE_BODY.splitlines() if p.strip() and not p.startswith("#")]
    out = []
    for t in tracked:
        if not t.startswith(".project/"):
            continue
        sub = t[len(".project/"):]
        for pat in pats:
            if pat.endswith("/") and sub.startswith(pat):
                out.append(t)
                break
            if fnmatch.fnmatch(sub, pat):
                out.append(t)
                break
    return sorted(out)


def git_untrack(root, paths):
    done = 0
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        r = pp.git(root, "rm", "-r", "--cached", "-q", "--ignore-unmatch", "--", *chunk, timeout=120)
        if r.returncode == 0:
            done += len(chunk)
        else:
            print("git rm --cached failed: " + r.stderr.strip()[:300], file=sys.stderr)
    return done


def maintenance_note(root, name, lines, moves=None):
    d = os.path.join(root, ".project", "operational", "memory-maintenance")
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    path = os.path.join(d, f"{stamp}-{name}.md")
    with open(path, "w") as fh:
        fh.write(f"---\ntype: operational\ndate: {stamp[:10]}\nsource: praxis-memory {name}\n"
                 f"title: Memory maintenance — {name}\n---\n\n")
        fh.write("\n".join(lines) + "\n")
    if moves:
        with open(path[:-3] + "-moves.tsv", "w") as fh:
            fh.write("old_path\tnew_path\n")
            for a, b in moves:
                fh.write(f"{a}\t{b}\n")
    return path


def move(root, src_rel, dst_rel, tracked_paths):
    src, dst = os.path.join(root, src_rel), os.path.join(root, dst_rel)
    if os.path.exists(dst):
        base, ext = os.path.splitext(dst)
        dst = f"{base}-{int(time.time())}{ext}"
        dst_rel = pp.rel(root, dst)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    rp = git_rel(root, src)
    if os.path.isdir(src):
        is_tracked = any(t.startswith(rp + "/") for t in tracked_paths)
    else:
        is_tracked = rp in tracked_paths
    if is_tracked:
        r = pp.git(root, "mv", "-k", src, dst, timeout=60)
        if r.returncode == 0 and os.path.exists(dst):
            return dst_rel
    shutil.move(src, dst)
    return dst_rel


# ── migrate-local ───────────────────────────────────────────────────────────
def cmd_migrate(root, args):
    items, uncertain = scan_evidence(root)
    tracked = tracked_set(root)
    top_rel = {i["path"]: i["path"] for i in items}

    def tracked_count(i):
        tp = top_rel[i["path"]]
        if i["dir"]:
            return sum(1 for t in tracked if t.startswith(tp + "/"))
        return 1 if tp in tracked else 0

    ignored_tracked = tracked_ignored(root, tracked)
    total = sum(i["bytes"] for i in items)
    n_tracked = sum(tracked_count(i) for i in items)
    by_area = {}
    for i in items:
        parts = i["path"].split("/")[1:]          # drop ".project"
        if parts[0] == "working":
            area = "working/" + parts[1] + "/" if (len(parts) > 2 or i["dir"]) else "working/ (top-level files)"
        else:
            area = "/".join(parts[:2]) + "/" if len(parts) > 2 else parts[0] + "/ (top-level files)"
        a = by_area.setdefault(area, [0, 0])
        a[0] += 1
        a[1] += i["bytes"]
    report = {"evidence_items": len(items), "evidence_bytes": total, "tracked_files_to_untrack": n_tracked,
              "tracked_now_ignored": len(ignored_tracked), "uncertain_kept": len(uncertain),
              "by_area": {k: {"items": v[0], "bytes": v[1]} for k, v in by_area.items()},
              "largest": sorted(items, key=lambda i: -i["bytes"])[:15],
              "uncertain_sample": sorted(uncertain, key=lambda i: -i["bytes"])[:15]}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"migrate-local {'(APPLY)' if args.apply else '(dry run — nothing changed)'}")
        print(f"  raw evidence in memory folders: {len(items)} items, {human(total)}")
        print(f"  of which tracked by git:        {n_tracked} files (would be untracked, kept on disk)")
        print(f"  tracked files now gitignored:   {len(ignored_tracked)} (raw telemetry etc.; untracked only)")
        print(f"  left in place as uncertain:     {len(uncertain)} files (notes, scripts, small data)")
        print("  by area:")
        for k, v in sorted(by_area.items(), key=lambda kv: -kv[1][1]):
            print(f"    {k:<34} {v[0]:>6} items {human(v[1]):>10}")
        print("  largest:")
        for i in report["largest"]:
            print(f"    {human(i['bytes']):>10}  {i['path']}{'/' if i['dir'] else ''}")
        if uncertain:
            print("  uncertain (kept; move by hand if they are run output):")
            for i in report["uncertain_sample"][:8]:
                print(f"    {human(i['bytes']):>10}  {i['path']}")
        print("  destination: .project/local/evidence/legacy/<original path> (gitignored)")
    if not args.apply:
        return 0
    pp.ensure_gitignore(root)
    to_untrack = []
    moves = []
    for i in items:
        if tracked_count(i):
            to_untrack.append(top_rel[i["path"]])
    to_untrack += ignored_tracked
    untracked = git_untrack(root, to_untrack) if to_untrack else 0
    legacy = os.path.join(".project", "local", "evidence", "legacy")
    for i in items:
        sub = i["path"][len(".project/"):] if i["path"].startswith(".project/") else i["path"]
        dst = os.path.join(legacy, sub)
        src = os.path.join(root, i["path"])
        if not os.path.exists(src):
            continue
        os.makedirs(os.path.dirname(os.path.join(root, dst)), exist_ok=True)
        if os.path.exists(os.path.join(root, dst)):
            dst = dst + f".{int(time.time())}"
        shutil.move(src, os.path.join(root, dst))
        moves.append((i["path"], dst.replace(os.sep, "/")))
    note = maintenance_note(root, "migrate-local", [
        f"Moved {len(moves)} raw-evidence items ({human(total)}) out of memory folders into the "
        "gitignored evidence store `.project/local/evidence/legacy/`, and untracked "
        f"{untracked} files from git (they stay on disk; git history is unchanged).",
        "", "By area:"] + [f"- {k}: {v[0]} items, {human(v[1])}" for k, v in sorted(by_area.items())] + [
        "", "The `-moves.tsv` file next to this note maps every old path to its new one, so "
        "links in older notes can still be followed on this machine. The evidence store is "
        "machine-local: other clones never had these files after this change."], moves)
    print(f"  applied: moved {len(moves)} items, untracked {untracked} files; record: {pp.rel(root, note)}")
    print("  next: review `git status`, then commit the removals together with .project/.gitignore")
    return 0


# ── check ───────────────────────────────────────────────────────────────────
LINK_RE = re.compile(r"\]\(((?:\.\.?/|\.project/)[^)#\s]+)")
WIKI_RE = re.compile(r"\[\[([^\]|#]+)")
WIKI_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{1,80}")       # note names, not [[:space:]] or TOML
CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def cmd_check(root, args):
    lay = pp.layout(root)
    errors, warnings = [], []
    stems = {}
    notes = []
    for kind, f in kind_notes(root):
        notes.append((kind, f))
        stems.setdefault(os.path.splitext(os.path.basename(f))[0], f)
    missing_fm, partial_fm, big = [], [], []
    dangling = []
    limit = lay["budgets"].get("note_kb", 32) * 1024
    for kind, f in notes:
        fm, _ = frontmatter(f)
        r = pp.rel(root, f)
        if fm is None:
            missing_fm.append(r)
        else:
            lack = [k for k in REQUIRED_FM if not fm.get(k) and not (k == "source" and fm.get("author"))]
            if lack:
                partial_fm.append(f"{r} (no {', '.join(lack)})")
        if os.path.getsize(f) > limit:
            big.append(f"{r} ({human(os.path.getsize(f))})")
        try:
            text = open(f, errors="replace").read()
        except Exception:
            continue
        text = CODE_RE.sub("", text)
        for link in LINK_RE.findall(text):
            target = os.path.normpath(os.path.join(root if link.startswith(".project/") else os.path.dirname(f), link))
            if not os.path.exists(target) and "/local/" not in link:
                dangling.append(f"{r} -> {link}")
        for w in WIKI_RE.findall(text):
            w = w.strip()
            if WIKI_NAME_RE.fullmatch(w) and w not in stems:
                dangling.append(f"{r} -> [[{w.strip()}]]")
        if fm and isinstance(fm.get("related"), list):
            for rid in fm["related"]:
                if rid and rid not in stems and not os.path.exists(os.path.join(root, rid)):
                    dangling.append(f"{r} -> related: {rid}")
    injected_chars = 0
    for p in lay["injected"]:
        fp = os.path.join(root, p)
        if os.path.isfile(fp):
            injected_chars += len(open(fp, errors="replace").read())
    if injected_chars > lay["budgets"].get("injected_chars", 6000):
        errors.append(f"injected files total {injected_chars} chars, over the {lay['budgets']['injected_chars']} "
                      "budget; move detail into linked notes")
    if dangling:
        errors.append(f"{len(dangling)} broken links (first: {dangling[0]})")
    if missing_fm:
        warnings.append(f"{len(missing_fm)} notes have no frontmatter (needs type, date, source)")
    if partial_fm:
        warnings.append(f"{len(partial_fm)} notes miss a required field (first: {partial_fm[0]})")
    if big:
        warnings.append(f"{len(big)} notes over {lay['budgets'].get('note_kb', 32)} KB (first: {big[0]})")
    items, _ = scan_evidence(root)
    if items:
        warnings.append(f"{len(items)} raw evidence items ({human(sum(i['bytes'] for i in items))}) inside memory "
                        "folders; run `praxis-memory migrate-local`")
    work = kpath(root, "working")
    if os.path.isdir(work) and len(os.listdir(work)) > 150:
        warnings.append(f"working/ has {len(os.listdir(work))} entries; run `praxis-memory consolidate`")
    tracked = tracked_set(root)
    tracked_bytes = sum(os.path.getsize(os.path.join(root, t)) for t in tracked
                        if os.path.isfile(os.path.join(root, t))) if tracked else 0
    gi = os.path.join(root, ".project", ".gitignore")
    if not (os.path.isfile(gi) and pp.GITIGNORE_BEGIN in open(gi).read()):
        warnings.append(".project/.gitignore has no Praxis-managed block (start a session or run praxis_project ensure)")
    result = {"notes": len(notes), "errors": errors, "warnings": warnings,
              "tracked_project_files": len(tracked), "tracked_project_bytes": tracked_bytes,
              "dangling_sample": dangling[:20], "missing_frontmatter_sample": missing_fm[:10]}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"praxis-memory check: {len(notes)} notes; .project/ tracked in git: {len(tracked)} files, "
              f"{human(tracked_bytes)}")
        for e in errors:
            print("  ERROR   " + e)
        for w in warnings:
            print("  warning " + w)
        if dangling[1:]:
            print("  broken links (sample):")
            for d in dangling[:10]:
                print("    " + d)
        if not errors and not warnings:
            print("  clean")
    return 1 if (args.strict and errors) else 0


# ── consolidate ─────────────────────────────────────────────────────────────
def ledger_state(path):
    text = open(path, errors="replace").read()
    tasks = pp.parse_tasks(text)
    m = re.search(r"^state:\s*(\S+)", text, re.M)
    state = pp.unquote(m.group(1)) if m else ""
    sid = re.sub(r"^slice-|-tasks\.ya?ml$", "", os.path.basename(path))
    open_ = [t for t, v in tasks.items() if v.get("status") not in ("done", "cancelled", "canceled", "dropped")]
    closed = state in ("closed", "done", "complete", "completed") or (tasks and not open_)
    return sid, closed, list(tasks)


def references_text(root):
    """Text of everything that marks work as live: open ledgers, workflow state, active notes."""
    chunks = []
    for p in pp.ledgers(root):
        sid, closed, _ = ledger_state(p)
        if not closed:
            chunks.append(open(p, errors="replace").read())
    for name in ("workflow-state.yaml", "active-workflow.md", "current-slice.md", "implementation-packet.md"):
        fp = os.path.join(kpath(root, "working"), name)
        if os.path.isfile(fp):
            chunks.append(open(fp, errors="replace").read())
    return "\n".join(chunks)


def review_key(name):
    stem = os.path.splitext(name)[0]
    stem = DATE_PREFIX_RE.sub("", stem)
    prev = None
    while prev != stem:
        prev = stem
        stem = ROUND_SUFFIX_RE.sub("", stem)
    return stem.lower()


def plan_consolidation(root):
    lay = pp.layout(root)
    ret = lay["retention"]
    now = time.time()
    work = kpath(root, "working")
    epi = kpath(root, "episodic")
    plan = {"closed_slices": [], "stale_working": [], "review_rounds": [], "inbox_closed": [],
            "lane_notes": [], "evidence_prune": []}
    if os.path.isdir(work):
        live = references_text(root)
        closed_sids, open_sids = {}, set()
        for p in pp.ledgers(root):
            sid, closed, tids = ledger_state(p)
            (closed_sids.__setitem__(sid, tids) if closed else open_sids.add(sid))
        protected = {"inbox.md", "workflow-state.yaml", "active-workflow.md", "current-slice.md",
                     "implementation-packet.md", "lanes", ".drive-active"}
        for name in sorted(os.listdir(work)):
            full = os.path.join(work, name)
            r = pp.rel(root, full)
            if name in protected or name.startswith("."):
                continue
            hit = None
            for sid, tids in closed_sids.items():
                low, s = name.lower(), sid.lower()
                if (low.startswith(f"slice-{s}-") or low.startswith(f"slice-{s}.") or
                        any(low.startswith(f"verify-{t.lower()}.") for t in tids)):
                    hit = sid
                    break
            if classify(full, os.path.isdir(full)) == "evidence":
                continue  # raw evidence goes to .project/local via migrate-local, never into episodic
            if hit and not any(name.lower().startswith(f"slice-{o.lower()}-") for o in open_sids):
                plan["closed_slices"].append({"path": r, "slice": hit,
                                              "dest": pp.rel(root, os.path.join(epi, "archive", "slices", hit, name))})
                continue
            if re.match(r"^slice-.*-tasks\.ya?ml$", name):
                continue  # open ledgers stay
            age = (now - newest_mtime(full)) / 86400
            if age >= ret["working_stale_days"] and name not in live and os.path.splitext(name)[0] not in live:
                month = time.strftime("%Y-%m", time.localtime(newest_mtime(full)))
                plan["stale_working"].append({"path": r, "age_days": int(age),
                                              "dest": pp.rel(root, os.path.join(epi, "archive", "working", month, name))})
        lanes = os.path.join(work, "lanes")
        if os.path.isdir(lanes):
            for f in sorted(glob.glob(os.path.join(lanes, "*", "*.md"))):
                fm, _ = frontmatter(f)
                if fm and fm.get("append_to"):
                    plan["lane_notes"].append({"path": pp.rel(root, f), "target": fm["append_to"]})
    rev = kpath(root, "review")
    if os.path.isdir(rev):
        groups = {}
        for f in glob.glob(os.path.join(rev, "*.md")):
            groups.setdefault(review_key(os.path.basename(f)), []).append(f)
        for key, files in sorted(groups.items()):
            if len(files) <= ret["review_rounds_keep"]:
                continue
            files.sort(key=lambda f: (os.path.getmtime(f), f), reverse=True)
            for f in files[ret["review_rounds_keep"]:]:
                if (now - os.path.getmtime(f)) / 86400 >= ret["review_rounds_min_age_days"]:
                    plan["review_rounds"].append({"path": pp.rel(root, f), "topic": key, "kept": pp.rel(root, files[0]),
                                                  "dest": pp.rel(root, os.path.join(rev, "archive", key, os.path.basename(f)))})
    inbox = kpath(root, "inbox")
    if os.path.isfile(inbox):
        text = open(inbox, errors="replace").read()
        for m in re.finditer(r"^## (R-\d+)[^\n]*\n(.*?)(?=^## R-\d+|\Z)", text, re.S | re.M):
            st = re.search(r"\*\*Status:?\*\*:?\s*(.+)", m.group(2))
            if st and CLOSED_STATUS_RE.match(st.group(1)):
                plan["inbox_closed"].append({"id": m.group(1), "status": st.group(1).strip()[:80]})
    ev = pp.evidence_root(root)
    if os.path.isdir(ev):
        keep_n, keep_days = ret["evidence_keep_runs"], ret["evidence_keep_days"]
        referenced = set()
        for base in (kpath(root, "risk_acceptance"), kpath(root, "review")):
            if os.path.isdir(base):
                for f in glob.glob(os.path.join(base, "**", "*.md"), recursive=True):
                    referenced |= set(re.findall(r"\d{8}T\d{6}(?:\d{3})?Z-[0-9a-f]{4}", open(f, errors="replace").read()))
        for tdir in sorted(glob.glob(os.path.join(ev, "*"))):
            if os.path.basename(tdir) in ("legacy", "workflow-steps") or not os.path.isdir(tdir):
                continue
            runs = sorted((d for d in glob.glob(os.path.join(tdir, "*")) if os.path.isdir(d)), reverse=True)
            for d in runs[keep_n:]:
                rid = os.path.basename(d)
                if (now - newest_mtime(d)) / 86400 < keep_days or rid in referenced:
                    continue
                plan["evidence_prune"].append({"path": pp.rel(pp.main_root(root), d), "bytes": size_of(d)})
    return plan


def apply_inbox(root, ids):
    inbox = kpath(root, "inbox")
    text = open(inbox, errors="replace").read()
    keep, moved = [], []
    parts = re.split(r"(?=^## R-\d+)", text, flags=re.M)
    for part in parts:
        m = re.match(r"^## (R-\d+)", part)
        (moved if m and m.group(1) in ids else keep).append(part)
    if not moved:
        return 0
    arch = os.path.join(kpath(root, "episodic"), "archive", "inbox-closed.md")
    os.makedirs(os.path.dirname(arch), exist_ok=True)
    header = "" if os.path.exists(arch) else ("---\ntype: episodic\ndate: " + time.strftime("%Y-%m-%d") +
                                              "\nsource: praxis-memory consolidate\ntitle: Closed inbox entries\n---\n\n")
    with open(arch, "a") as fh:
        fh.write(header + "".join(p if p.endswith("\n") else p + "\n" for p in moved))
    with open(inbox, "w") as fh:
        fh.write("".join(keep).rstrip("\n") + "\n\n<!-- closed entries: " + pp.rel(root, arch) + " -->\n"
                 if "closed entries:" not in "".join(keep) else "".join(keep))
    return len(moved)


def cmd_consolidate(root, args):
    if args.print_prompt:
        ref = os.path.join(os.path.dirname(HERE), "skills", "memory-management", "references", "consolidation.md")
        print(open(ref).read() if os.path.isfile(ref) else "consolidation prompt not found: " + ref)
        lay = pp.layout(root)
        print("\n## Injected files for this project\n" + "\n".join(f"- {p}" for p in lay["injected"]))
        return 0
    plan = plan_consolidation(root)
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print(f"consolidate {'(APPLY)' if args.apply else '(dry run — nothing changed)'}")
        lab = {"closed_slices": "working notes of closed slices -> episodic/archive/slices/",
               "stale_working": "stale working notes (no open ledger refers to them) -> episodic/archive/working/",
               "review_rounds": "earlier review rounds (newest per topic kept) -> reviews/archive/",
               "inbox_closed": "closed inbox entries -> episodic/archive/inbox-closed.md",
               "lane_notes": "parallel-lane notes to merge into their targets",
               "evidence_prune": "evidence runs past retention (gitignored, deleted)"}
        for k, label in lab.items():
            items = plan[k]
            extra = f", {human(sum(i.get('bytes', 0) for i in items))}" if k == "evidence_prune" and items else ""
            print(f"  {len(items):>6}  {label}{extra}")
            for i in items[:4]:
                print("          " + (i.get("path") or i.get("id", "")) + (f"  ({i['status']})" if "status" in i else ""))
        print("  model-side pass (re-check injected facts against code): praxis-memory consolidate --print-prompt")
    pending, _ = scan_evidence(root)
    if pending and not args.json:
        print(f"  note: {len(pending)} raw evidence items are still in memory folders; run "
              "`praxis-memory migrate-local` first so no log is archived into committed memory")
    if not args.apply:
        return 0
    if pending and not args.force:
        print("  refused: run `praxis-memory migrate-local --apply` first (or pass --force)", file=sys.stderr)
        return 1
    tracked = tracked_set(root)
    moves = []
    for k in ("closed_slices", "stale_working", "review_rounds"):
        for i in plan[k]:
            if os.path.exists(os.path.join(root, i["path"])):
                moves.append((i["path"], move(root, i["path"], i["dest"], tracked)))
    merged = 0
    for i in plan["lane_notes"]:
        src = os.path.join(root, i["path"])
        target = os.path.join(root, i["target"])
        body = open(src, errors="replace").read()
        body = body.split("\n---\n", 1)[1] if body.startswith("---") and "\n---\n" in body else body
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "a") as fh:
            fh.write("\n" + body.strip() + "\n")
        moves.append((i["path"], move(root, i["path"], pp.rel(root, os.path.join(
            kpath(root, "episodic"), "archive", "lanes", os.path.basename(os.path.dirname(src)),
            os.path.basename(src))), tracked)))
        merged += 1
    n_inbox = apply_inbox(root, {i["id"] for i in plan["inbox_closed"]}) if plan["inbox_closed"] else 0
    pruned = 0
    for i in plan["evidence_prune"]:
        shutil.rmtree(os.path.join(pp.main_root(root), i["path"]), ignore_errors=True)
        pruned += 1
    note = maintenance_note(root, "consolidate", [
        f"- archived {len(plan['closed_slices'])} working notes of closed slices",
        f"- archived {len(plan['stale_working'])} stale working notes",
        f"- archived {len(plan['review_rounds'])} earlier review rounds (newest per topic kept)",
        f"- moved {n_inbox} closed inbox entries to the episodic archive",
        f"- merged {merged} parallel-lane notes into their targets",
        f"- pruned {pruned} evidence runs past retention (gitignored store)",
        "", "Nothing was deleted from memory; archived notes keep their content. The `-moves.tsv` file "
        "maps old paths to new ones."], moves)
    print(f"  applied; record: {pp.rel(root, note)}. Review `git status` before committing.")
    return 0


# ── context setup (what compaction keeps) ───────────────────────────────────
COMPACT_TEXT = """When compacting, keep: the active slice and task id and its `verify` command;
the current hypothesis and what was ruled out; failing test names and the error
lines that matter (not full logs); decisions made and why; files changed so far.
Drop: raw tool output, file contents that can be re-read, passing test output,
and exploration that led nowhere. End the summary with the next concrete step.
Durable facts belong in .project/ (see the memory map), not in the summary."""
MD_BEGIN = "<!-- praxis:compact:begin (managed by praxis-memory context-setup) -->"
MD_END = "<!-- praxis:compact:end -->"
TOML_BEGIN = "# >>> praxis-managed (praxis-memory context-setup) >>>"
TOML_END = "# <<< praxis-managed <<<"


def _replace_block(text, begin, end, body, at_top=False):
    block = f"{begin}\n{body}\n{end}\n"
    if begin in text and end in text:
        return re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", lambda _m: block, text, flags=re.S)
    if at_top:
        return block + ("\n" + text if text.strip() else "")
    return (text.rstrip("\n") + "\n\n" if text.strip() else "") + block


def cmd_context_setup(root, args):
    changes = []
    md = os.path.join(root, "CLAUDE.md")
    md_text = open(md, errors="replace").read() if os.path.isfile(md) else ""
    if "# Compact instructions" in md_text and MD_BEGIN not in md_text:
        changes.append(("CLAUDE.md", None, "already has its own '# Compact instructions'; left alone"))
    else:
        new = _replace_block(md_text, MD_BEGIN, MD_END, "# Compact instructions\n\n" + COMPACT_TEXT)
        if new != md_text:
            changes.append(("CLAUDE.md", new, "managed '# Compact instructions' block"))
    toml = os.path.join(root, ".codex", "config.toml")
    t_text = open(toml, errors="replace").read() if os.path.isfile(toml) else ""
    outside = re.sub(re.escape(TOML_BEGIN) + r".*?" + re.escape(TOML_END), "", t_text, flags=re.S)
    if re.search(r"^\s*compact_prompt\s*=", outside, re.M):
        changes.append((".codex/config.toml", None, "already sets compact_prompt; left alone"))
    else:
        body = ('compact_prompt = """\n' + COMPACT_TEXT + '\n"""\n'
                "# Compact before the window is nearly full (default is about 90%). Set this to\n"
                "# roughly 60% of your model's context window, for example:\n"
                "# model_auto_compact_token_limit = 150000")
        new = _replace_block(t_text, TOML_BEGIN, TOML_END, body, at_top=True)
        if new != t_text:
            changes.append((".codex/config.toml", new, "managed compact_prompt block (top-level keys first)"))
    print(f"context-setup {'(APPLY)' if args.apply else '(dry run — nothing changed)'}")
    for path, new, what in changes:
        print(f"  {'write' if new is not None else 'skip '}  {path}: {what}")
    if not changes:
        print("  nothing to do: both files are current")
    print("  Antigravity: no documented compaction setting; it relies on its own context handling.")
    if args.apply:
        for path, new, _ in changes:
            if new is None:
                continue
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w") as fh:
                fh.write(new)
    return 0


# ── review context (rules read from the base branch) ────────────────────────
def parse_checks(text):
    """Minimal parser for procedural/checks.yaml (see references/review-checks.md)."""
    checks, cur, in_trigger, list_key = [], None, False, None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^\s*-\s+id:\s*(.+)$", raw)
        if m:
            cur = {"id": pp.unquote(pp.strip_comment(m.group(1))), "paths": [], "diff": "", "check": "", "origin": ""}
            checks.append(cur)
            in_trigger, list_key = False, None
            continue
        if cur is None:
            continue
        m = re.match(r"^(\s+)([a-z_]+):\s*(.*)$", raw)
        if m:
            key, val = m.group(2), pp.strip_comment(m.group(3))
            if key == "trigger":
                in_trigger, list_key = True, None
                continue
            if key in ("paths", "diff"):
                if key == "paths":
                    if val.startswith("["):
                        cur["paths"] = [pp.unquote(x.strip()) for x in val.strip("[]").split(",") if x.strip()]
                        list_key = None
                    else:
                        list_key = "paths"
                else:
                    cur["diff"] = pp.unquote(val)
                continue
            if key in ("check", "origin", "severity"):
                cur[key] = pp.unquote(val)
                in_trigger = False
            continue
        m = re.match(r"^\s+-\s+(.+)$", raw)
        if m and list_key == "paths":
            cur["paths"].append(pp.unquote(pp.strip_comment(m.group(1))))
    return checks


def glob_match(path, pattern):
    rx = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*").replace(r"\?", ".")
    return re.fullmatch(rx, path) is not None


def cmd_review_context(root, args):
    base = args.base or "main"
    def show(path):
        r = pp.git(root, "show", f"{base}:{path}", timeout=20)
        return r.stdout if r.returncode == 0 else ""
    # The layout itself is read from base too, so a branch cannot move the rules.
    layout_text = show(".project/governance/memory-layout.yaml")
    rules_path, checks_path = DEFAULT_RULES, DEFAULT_CHECKS
    for line in layout_text.splitlines():
        m = re.match(r"^\s+(review_rules|review_checks):\s*(.+)$", line)
        if m:
            v = pp.unquote(pp.strip_comment(m.group(2)))
            rules_path, checks_path = (v, checks_path) if m.group(1) == "review_rules" else (rules_path, v)
    rules = show(rules_path)
    checks = parse_checks(show(checks_path))
    files = [f for f in pp.git(root, "diff", "--name-only", f"{base}...HEAD", timeout=30).stdout.splitlines() if f]
    diff = pp.git(root, "diff", f"{base}...HEAD", timeout=60).stdout if checks else ""
    added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    matched = []
    for c in checks:
        hit_paths = [f for f in files if any(glob_match(f, p) for p in c["paths"])] if c["paths"] else files
        if c["paths"] and not hit_paths:
            continue
        if c["diff"]:
            try:
                if not re.search(c["diff"], added, re.M):
                    continue
            except re.error:
                continue
        matched.append({"id": c["id"], "check": c["check"], "origin": c["origin"],
                        "severity": c.get("severity", ""), "files": hit_paths[:20]})
    out = {"base": base, "files": files, "rules_path": rules_path, "rules": rules[:8000],
           "checks_path": checks_path, "checks_total": len(checks), "checks_matched": matched}
    print(json.dumps(out, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["where", "map", "index", "check", "migrate-local", "consolidate",
                                        "review-context", "context-setup"])
    ap.add_argument("kind", nargs="?")
    ap.add_argument("--project-dir")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--print-prompt", action="store_true")
    ap.add_argument("--base")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    root = pp.find_root(a.project_dir)
    if not root:
        print("praxis-memory: no .project/ found above this directory", file=sys.stderr)
        return 2
    if a.command == "where":
        if not a.kind:
            print(json.dumps(pp.layout(root)["kinds"], indent=2))
        else:
            print(pp.where(root, a.kind))
        return 0
    if a.command == "map":
        print(pp.memory_map(root))
        return 0
    return {"index": cmd_index, "check": cmd_check, "migrate-local": cmd_migrate,
            "consolidate": cmd_consolidate, "review-context": cmd_review_context,
            "context-setup": cmd_context_setup}[a.command](root, a)


if __name__ == "__main__":
    sys.exit(main())
