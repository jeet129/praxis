#!/usr/bin/env python3
"""praxis_guard.py — deterministic Praxis controls, one script for every harness.

Controls live in hooks, not in skill prose, because prose is advisory and a
hook runs every time. Subcommands (hook payload on stdin):

  pretool  PreToolUse.  In order:
           1. KILL SWITCH    .project/STOP exists -> deny every tool call.
           2. READ-ONLY      a reviewer agent may not edit files.
           3. EVIDENCE STORE nobody edits verification summaries or evidence by
                             hand (file tools, or shell commands writing there);
                             only scripts/praxis-verify.py writes them.
           4. VERIFY FREEZE  a task's `verify:` command cannot change once the
                             task has started, unless the same edit adds
                             `verify_changed_reason:` (logged).
           5. EVIDENCE GATE  an edit that moves a ledger task to `done` is denied
                             unless praxis-verify recorded a passing run of the
                             task's current verify command on the current code.
  stop     Stop.        EVIDENCE AUDIT: if a recently completed task has no
           passing run on record, keep the agent working (at most twice).
  steer    UserPromptSubmit (Claude Code, Codex) / PreInvocation (Antigravity).
           If .project/STEER.md exists, inject it once, then archive it.

  --harness claude-code | codex | antigravity   selects payload + output shapes:
    Claude Code / Codex  deny = hookSpecificOutput.permissionDecision "deny"
                         stop = {"decision": "block", "reason": ...}
    Antigravity          deny = {"decision": "deny", "reason": ...}
                         stop = {"decision": "continue", "reason": ...}

Evidence (references/loop-contracts.md): `.project/local/bin/praxis-verify <id>`
runs the task's verify command and writes
  .project/operational/verification/<id>--<run>.json   committed summary
  .project/local/evidence/<id>/<run>/output.log         gitignored full log
Tasks with `verify: null` (human-checked) are exempt.

Configuration (environment):
  PRAXIS_EVIDENCE_GATE          enforce (default) | warn | off
  PRAXIS_EVIDENCE_FRESHNESS     tree (default) | off   reject runs older than the code
  PRAXIS_ALLOW_LEGACY_EVIDENCE  1 also accepts old verify-<id>.log/.exit files
  PRAXIS_READONLY_AGENTS        comma list (default: the three reviewer agents)

Fail-open: any internal error allows the action. Zero dependencies.
"""
import datetime
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import praxis_project as pp  # noqa: E402  (shared layout + evidence helpers)

READONLY_DEFAULT = "code-reviewer,security-reviewer,architecture-challenger"
EDIT_TOOLS = {
    "claude-code": {"Write", "Edit", "MultiEdit", "NotebookEdit"},
    "codex": {"apply_patch", "Edit", "Write"},
    "antigravity": {"write_to_file", "replace_file_content", "multi_replace_file_content"},
}
LEDGER_RE = re.compile(r"(^|/)\.project/working/slice-[^/]*-tasks\.ya?ml$")


# ── harness I/O ─────────────────────────────────────────────────────────────
def out_allow(harness):
    if harness == "antigravity":
        print(json.dumps({"decision": "allow"}))
    sys.exit(0)


def out_deny(harness, reason):
    if harness == "antigravity":
        print(json.dumps({"decision": "deny", "reason": reason}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    sys.exit(0)


def tool_of(harness, payload):
    if harness == "antigravity":
        tc = payload.get("toolCall") or {}
        return tc.get("name") or "", tc.get("args") or {}
    return payload.get("tool_name") or "", payload.get("tool_input") or {}


def agent_of(payload):
    name = payload.get("agent_type") or payload.get("subagent_type") or ""
    return str(name).split(":")[-1]


def project_root(payload):
    start = ""
    wps = payload.get("workspacePaths")
    if isinstance(wps, list) and wps:
        start = wps[0]
    start = start or payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".project")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return ""
        cur = parent


def log(root, record):
    if not root:
        return
    try:
        d = os.path.join(root, ".project", "telemetry")
        os.makedirs(d, exist_ok=True)
        record = dict(record, ts=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      event="praxis_guard")
        with open(os.path.join(d, "guard.jsonl"), "a") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ── ledger parsing + evidence (shared with praxis-verify) ───────────────────
parse_tasks = pp.parse_tasks


def evidence_problem(root, task_id, task, check_fresh=False, ledger=None):
    """None if evidence is fine or not checkable, else a reason string."""
    return pp.evidence_problem(root, task_id, task, check_fresh=check_fresh, ledger=ledger)


def newly_done(before_text, after_text):
    before, after = parse_tasks(before_text), parse_tasks(after_text)
    return {tid: t for tid, t in after.items()
            if t.get("status") == "done" and before.get(tid, {}).get("status") != "done"}


# ── proposed file content per harness ───────────────────────────────────────
def apply_codex_patch(patch, path, current):
    """Apply the hunks for `path` from a Codex apply_patch body. None if unsure."""
    sections = re.split(r"^\*\*\* (?=Update File:|Add File:|Delete File:|End Patch)", patch, flags=re.M)
    for sec in sections:
        head, _, body = sec.partition("\n")
        kind, _, target = head.partition(":")
        target = target.strip()
        if not target or not (path.endswith(target) or os.path.basename(path) == os.path.basename(target)):
            continue
        if kind == "Add File":
            return "\n".join(l[1:] for l in body.splitlines() if l.startswith("+")) + "\n"
        if kind != "Update File":
            return None
        text = current
        for hunk in re.split(r"^@@.*$", body, flags=re.M):
            old, new = [], []
            for l in hunk.splitlines():
                if l.startswith("*** "):
                    continue
                if l.startswith("-"):
                    old.append(l[1:])
                elif l.startswith("+"):
                    new.append(l[1:])
                elif l.startswith(" ") or l == "":
                    old.append(l[1:]); new.append(l[1:])
            if not old and not new:
                continue
            o, n = "\n".join(old), "\n".join(new)
            if o and o in text:
                text = text.replace(o, n, 1)
            elif o.strip() and o.strip() in text:
                text = text.replace(o.strip(), n.strip(), 1)
            else:
                return None
        return text
    return None


def proposed_edit(harness, tool, args):
    """Return (path, after_text) for a file edit, or (path, None) if unknown."""
    if harness == "claude-code":
        path = args.get("file_path") or ""
        if tool == "Write":
            return path, args.get("content")
        if tool in ("Edit", "MultiEdit") and os.path.isfile(path):
            text = open(path, errors="replace").read()
            edits = args.get("edits") or [args]
            for e in edits:
                old, new = e.get("old_string"), e.get("new_string")
                if old is None or new is None or old not in text:
                    return path, None
                text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
            return path, text
        return path, None
    if harness == "codex":
        patch = args.get("command") or args.get("patch") or args.get("input") or ""
        if isinstance(patch, list):
            patch = "\n".join(str(x) for x in patch)
        targets = re.findall(r"^\*\*\* (?:Update|Add) File:\s*(.+)$", patch, flags=re.M)
        for t in targets:
            if LEDGER_RE.search(t.strip().replace("\\", "/")):
                path = t.strip()
                current = open(path, errors="replace").read() if os.path.isfile(path) else ""
                return path, apply_codex_patch(patch, path, current)
        return (targets[0].strip() if targets else ""), None
    # antigravity: argument names are not documented; try the common spellings.
    path = next((args[k] for k in ("TargetFile", "AbsolutePath", "file_path", "path")
                 if isinstance(args.get(k), str)), "")
    content = next((args[k] for k in ("CodeContent", "content", "Content")
                    if isinstance(args.get(k), str)), None)
    return path, content


# ── evidence store protection + verify freeze ───────────────────────────────
PROTECTED_RE = re.compile(r"(^|/)\.project/(operational/verification|local/evidence)(/|$)")
SHELL_TOOLS = {"Bash", "shell", "exec_command", "local_shell", "run_command", "run_shell_command"}
WRITE_HINT = re.compile(r"(>|\btee\b|\bcp\b|\bmv\b|\brm\b|\bsed\s+-i|\btruncate\b|\btouch\b|"
                        r"\bln\b|\binstall\b|\brsync\b|\bdd\b|write_text|open\()")


def shell_command(args):
    for k in ("command", "cmd", "CommandLine", "commandLine"):
        v = args.get(k)
        if isinstance(v, list):
            return " ".join(str(x) for x in v)
        if isinstance(v, str):
            return v
    return ""


def protected_shell_write(cmd):
    """A shell command that writes into the evidence store, other than the runner."""
    if "operational/verification" not in cmd and "local/evidence" not in cmd:
        return False
    if re.search(r"praxis-(verify|memory)(\.py)?\b", cmd):
        return False
    return bool(WRITE_HINT.search(cmd))


def verify_changes(before_text, after_text):
    """Tasks whose verify command changed after they started, without a reason."""
    before, after = parse_tasks(before_text), parse_tasks(after_text)
    bad = []
    for tid, b in before.items():
        a = after.get(tid)
        if not a or a.get("verify") == b.get("verify"):
            continue
        started = (b.get("status") not in (None, "", "open", "todo", "pending")
                   or str(b.get("attempts") or "0") != "0")
        reason = a.get("verify_changed_reason")
        if started and (pp.is_null(reason) or reason == b.get("verify_changed_reason")):
            bad.append(tid)
    return bad


# ── subcommands ─────────────────────────────────────────────────────────────
def cmd_pretool(harness, payload):
    root = project_root(payload)
    tool, args = tool_of(harness, payload)
    agent = agent_of(payload)

    if root and os.path.exists(os.path.join(root, ".project", "STOP")):
        log(root, {"harness": harness, "control": "kill_switch", "tool": tool, "agent": agent})
        out_deny(harness, "PRAXIS KILL SWITCH: .project/STOP exists, so every tool call is "
                          "refused. Stop working and report your current state to the user. "
                          "(The operator removes .project/STOP to resume.)")

    is_edit = tool in EDIT_TOOLS.get(harness, set())
    readonly = {a.strip() for a in os.environ.get("PRAXIS_READONLY_AGENTS", READONLY_DEFAULT).split(",") if a.strip()}
    if is_edit and agent in readonly:
        log(root, {"harness": harness, "control": "readonly_agent", "tool": tool, "agent": agent})
        out_deny(harness, f"{agent} is a read-only reviewer and may not edit files. Report "
                          "findings in your reply; the owning agent makes the change.")

    mode = os.environ.get("PRAXIS_EVIDENCE_GATE", "enforce")
    if root and mode != "off" and tool in SHELL_TOOLS and protected_shell_write(shell_command(args)):
        log(root, {"harness": harness, "control": "evidence_store", "tool": tool, "agent": agent})
        if mode == "enforce":
            out_deny(harness, "PRAXIS EVIDENCE STORE: .project/operational/verification/ and "
                              ".project/local/evidence/ are written only by praxis-verify. Run "
                              "`.project/local/bin/praxis-verify <task-id>` instead of writing results yourself.")
    if is_edit and root and mode != "off":
        path, after = proposed_edit(harness, tool, args)
        targets = [path or ""]
        if harness == "codex":
            patch = args.get("command") or args.get("patch") or args.get("input") or ""
            patch = "\n".join(str(x) for x in patch) if isinstance(patch, list) else str(patch)
            targets += re.findall(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+)$", patch, flags=re.M)
        if any(t and PROTECTED_RE.search(t.strip().replace("\\", "/")) for t in targets):
            log(root, {"harness": harness, "control": "evidence_store", "tool": tool, "agent": agent,
                       "path": path})
            if mode == "enforce":
                out_deny(harness, "PRAXIS EVIDENCE STORE: verification summaries and evidence are written "
                                  "only by praxis-verify. Run `.project/local/bin/praxis-verify <task-id>`.")
        norm = (path or "").replace("\\", "/")
        if path and not os.path.isabs(path):
            path = os.path.join(root, path)
        if LEDGER_RE.search(norm) and after is not None:
            before = open(path, errors="replace").read() if os.path.isfile(path) else ""
            frozen = verify_changes(before, after)
            if frozen:
                log(root, {"harness": harness, "control": "verify_freeze", "mode": mode,
                           "agent": agent, "tasks": frozen})
                if mode == "enforce":
                    out_deny(harness, "PRAXIS VERIFY FREEZE: the verify command of " + ", ".join(frozen)
                                      + " cannot change after the task has started, because a change must "
                                        "not edit its own check. If the command is genuinely wrong, add "
                                        "`verify_changed_reason: <why>` to the task in the same edit; it is "
                                        "logged for review.")
            problems = []
            for tid, task in newly_done(before, after).items():
                p = evidence_problem(root, tid, task, check_fresh=True, ledger=path)
                if p:
                    problems.append(f"{tid}: {p}")
            if problems:
                log(root, {"harness": harness, "control": "evidence_gate", "mode": mode,
                           "agent": agent, "problems": problems})
                if mode == "enforce":
                    out_deny(harness, "PRAXIS EVIDENCE GATE: a task cannot be marked done "
                                      "without passing verify evidence.\n- " + "\n- ".join(problems)
                                      + "\nRun `.project/local/bin/praxis-verify <task-id>`, confirm it passes, then "
                                        "update the ledger. If the task genuinely cannot be "
                                        "machine-verified, set its status to blocked and say why.")
    out_allow(harness)


def cmd_stop(harness, payload):
    root = project_root(payload)
    mode = os.environ.get("PRAXIS_EVIDENCE_GATE", "enforce")
    if not root or os.path.exists(os.path.join(root, ".project", "STOP")):
        return finish_stop(harness, None)  # no project, or the operator wants it stopped
    if mode == "off" or payload.get("stop_hook_active"):
        # No evidence audit on a continuation turn (avoids audit loops); an
        # armed drive may still continue, bounded by its own counter.
        return finish_stop(harness, goal_continuation(harness, root, payload))
    problems, now = [], time.time()
    for ledger in glob.glob(os.path.join(root, ".project", "working", "slice-*-tasks.y*ml")):
        try:
            if now - os.path.getmtime(ledger) > 2 * 3600:
                continue  # not touched in this run
            tasks = parse_tasks(open(ledger, errors="replace").read())
        except Exception:
            continue
        for tid, task in tasks.items():
            if task.get("status") != "done" or not task.get("completed_at"):
                continue
            try:
                done_at = datetime.datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00"))
                if done_at.tzinfo is None:
                    done_at = done_at.replace(tzinfo=datetime.timezone.utc)
                if (datetime.datetime.now(datetime.timezone.utc) - done_at).total_seconds() > 24 * 3600:
                    continue
            except Exception:
                continue
            p = evidence_problem(root, tid, task, ledger=ledger)
            if p:
                problems.append(f"{os.path.basename(ledger)} {tid}: {p}")
    if not problems:
        return finish_stop(harness, goal_continuation(harness, root, payload))
    # Never loop forever: at most two audit continuations per session.
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or payload.get("conversationId") or "s"))[:64]
    counter = os.path.join(root, ".project", "telemetry", f".guard-audit-{sid}")
    try:
        os.makedirs(os.path.dirname(counter), exist_ok=True)
        n = int(open(counter).read().strip() or 0) if os.path.isfile(counter) else 0
        open(counter, "w").write(str(n + 1))
    except Exception:
        n = 2
    log(root, {"harness": harness, "control": "evidence_audit", "mode": mode, "problems": problems, "round": n + 1})
    if mode != "enforce" or n >= 2:
        return finish_stop(harness, None)
    return finish_stop(harness, "PRAXIS EVIDENCE AUDIT: these tasks are marked done without a passing "
                                "praxis-verify run. Run `.project/local/bin/praxis-verify <task-id>` for each "
                                "(or reopen the task) before "
                                "finishing:\n- " + "\n- ".join(problems))


def goal_continuation(harness, root, payload):
    """Keep an armed in-session drive going while the ledger has open tasks.

    Claude Code and Antigravity. (Codex has codex-continuation.py and its own
    create_goal tool, so it is left alone here.) Armed by
    .project/working/.drive-active, which `praxis-goal.py --arm` writes and
    `--disarm` removes. Bounded by PRAXIS_GOAL_MAX_CONTINUES (default 25) per
    session, and it never continues a task that is blocked or failed.
    """
    if harness == "codex" or os.environ.get("PRAXIS_DRIVE_RUNNER") == "1":
        return None  # praxis-drive.sh runs one iteration per session and owns the loop
    marker = os.path.join(root, ".project", "working", ".drive-active")
    if not os.path.isfile(marker):
        return None
    try:
        want = open(marker).read().strip()
    except Exception:
        want = ""
    # Context budget: after N finished tasks or a large transcript, hand off to
    # a fresh session (the ledger is the hand-off). First stop: ask the agent to
    # leave the ledger and task notes current. Second stop: disarm and let it end.
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or payload.get("conversationId") or "s"))[:64]
    flag = os.path.join(root, ".project", "telemetry", f".handoff-{sid}")
    if os.path.isfile(flag):
        try:
            os.remove(flag)
            os.remove(marker)
        except Exception:
            pass
        log(root, {"harness": harness, "control": "context_handoff", "phase": "stopped"})
        global NOTICE
        NOTICE = ("Praxis paused the drive to save tokens: start a fresh session (Claude Code /clear, "
                  "Antigravity a new conversation) and run /drive again; the ledger carries the state.")
        return None
    try:
        since = os.path.getmtime(marker)
    except Exception:
        since = None
    budget = pp.context_budget(root)
    handoff = None
    if budget["on_session_budget"] == "ask":
        handoff = pp.session_handoff(root, since, payload.get("transcript_path"), want)
    else:
        # Default: never stop for the budget. Tell the person once per budget step
        # that this is a good moment to clear; the drive (and auto-compaction) go on.
        global HINT
        HINT = pp.budget_hint(root, sid, since, payload.get("transcript_path"), want)
        if HINT:
            log(root, {"harness": harness, "control": "context_hint"})
    if handoff:
        try:
            os.makedirs(os.path.dirname(flag), exist_ok=True)
            open(flag, "w").write(pp.now_iso())
        except Exception:
            return None
        log(root, {"harness": harness, "control": "context_handoff", "phase": "requested"})
        return handoff
    open_tasks = []
    for ledger in sorted(glob.glob(os.path.join(root, ".project", "working", "slice-*-tasks.y*ml"))):
        if want and want not in os.path.basename(ledger):
            continue
        try:
            tasks = parse_tasks(open(ledger, errors="replace").read())
        except Exception:
            continue
        open_tasks += [f"{tid} ({t.get('status')})" for tid, t in tasks.items()
                       if t.get("status") in ("open", "in_progress")]
    if not open_tasks:
        return None
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or payload.get("conversationId") or "s"))[:64]
    counter = os.path.join(root, ".project", "telemetry", f".goal-continue-{sid}")
    try:
        limit = int(os.environ.get("PRAXIS_GOAL_MAX_CONTINUES", "25"))
        os.makedirs(os.path.dirname(counter), exist_ok=True)
        n = int(open(counter).read().strip() or 0) if os.path.isfile(counter) else 0
        if n >= limit:
            return None
        open(counter, "w").write(str(n + 1))
    except Exception:
        return None
    log(root, {"harness": harness, "control": "goal_continue", "round": n + 1, "open": len(open_tasks)})
    return ("PRAXIS DRIVE: the slice ledger still has open tasks: " + ", ".join(open_tasks[:8])
            + ". Take the next one: hand it to a fresh specialist subagent (brief by path: task id, ac, "
              "verify command, packet, notes), let it implement and run `.project/local/bin/praxis-verify "
              "<task-id>`, take back only its short report, then update the ledger. If you are blocked, set the task to blocked with the "
              "reason and stop.")


NOTICE = None  # shown to the user when a stop is allowed (context hand-off)
HINT = None    # shown to the user alongside a continuation (budget hint)


def finish_stop(harness, reason):
    if not reason and NOTICE:
        print(json.dumps({"systemMessage": NOTICE} if harness != "antigravity"
                         else {"decision": "stop", "reason": NOTICE}))
        sys.exit(0)
    if reason:
        if harness == "antigravity":
            print(json.dumps({"decision": "continue", "reason": reason}))
        else:
            out = {"decision": "block", "reason": reason}
            if HINT:
                out["systemMessage"] = HINT  # shown to the person, not the model
            print(json.dumps(out))
    elif harness == "antigravity":
        print(json.dumps({"decision": "stop"}))
    sys.exit(0)


def cmd_steer(harness, payload):
    root = project_root(payload)
    path = os.path.join(root, ".project", "STEER.md") if root else ""
    if not path or not os.path.isfile(path):
        if harness == "antigravity":
            print("{}")
        sys.exit(0)
    text = open(path, errors="replace").read().strip()[:6000]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        os.replace(path, os.path.join(root, ".project", f"STEER.delivered-{stamp}.md"))
    except Exception:
        sys.exit(0)  # cannot archive -> do not inject, or it would repeat forever
    log(root, {"harness": harness, "control": "steer", "chars": len(text)})
    msg = ("OPERATOR STEERING NOTE (from .project/STEER.md; follow it, it overrides the "
           "current plan where they conflict):\n" + text)
    if harness == "antigravity":
        print(json.dumps({"injectSteps": [{"systemMessage": {"systemMessage": msg}}]}))
    else:
        event = payload.get("hook_event_name") or "UserPromptSubmit"
        print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": msg}}))
    sys.exit(0)


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else ""
    harness = "claude-code"
    if "--harness" in argv:
        harness = argv[argv.index("--harness") + 1]
    try:
        raw = os.environ.get("PRAXIS_HOOK_PAYLOAD") or sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if os.environ.get("PRAXIS_NESTED") == "1":
            raise ValueError("nested helper session")
        {"pretool": cmd_pretool, "stop": cmd_stop, "steer": cmd_steer}[cmd](harness, payload)
    except SystemExit:
        raise
    except Exception:
        if harness == "antigravity":
            print(json.dumps({"decision": "allow"}) if cmd == "pretool"
                  else (json.dumps({"decision": "stop"}) if cmd == "stop" else "{}"))
        sys.exit(0)


if __name__ == "__main__":
    main()
