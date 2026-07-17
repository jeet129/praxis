#!/usr/bin/env python3
"""Compare / merge per-project governance overrides against plugin defaults.

`.project/governance/model-routing.yaml` and `autonomy.yaml` are seeded ONCE
and then win over the plugin's copies (so per-engagement tuning survives plugin
updates). The cost of that contract: new default KEYS added by a plugin update
(e.g. the codex `effort_flag` / `effort_arg_prefix` that switch on per-iteration
reasoning-effort routing) never reach an existing project on their own. This
tool detects that drift and merges it non-destructively.

Zero dependencies. Parses the strict-subset YAML these two files use (2-3
levels of nested maps; inline {} / [] treated as opaque scalars). Comments and
blank lines are ignored for comparison and preserved on merge.

Subcommands:
  diff  PLUGIN PROJECT
      Report key-paths added-in-plugin (new functionality your copy lacks),
      changed-default (present in both, value differs), and project-only.
      Exit 0 if your copy already has every plugin key; exit 3 on drift
      (plugin has keys you lack) — this is what the SessionStart warning reads.

  merge PLUGIN PROJECT
      Write to stdout the PLUGIN file with the PROJECT's values overlaid: keeps
      new keys + comments + structure from the plugin, keeps tuned values from
      the project. Reports added / changed-default / project-only to stderr.
"""

import re
import sys

_KV = re.compile(r"^(?P<indent>\s*)(?P<key>[A-Za-z0-9_.-]+):(?P<rest>.*)$")


def _value_of(rest: str) -> str:
    """Scalar value on a `key: value` line, comment stripped. '' = a nested
    map header (children follow on deeper-indented lines)."""
    return rest.split("#", 1)[0].strip()


def parse_paths(text: str):
    """Return {dotted_path: value} for every scalar-valued key. Nested map
    headers (empty value) become path segments, not entries."""
    paths = {}
    stack = []  # (indent, key)
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        m = _KV.match(line)
        if not m:
            continue
        indent = len(m.group("indent"))
        key = m.group("key")
        val = _value_of(m.group("rest"))
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([k for _, k in stack] + [key])
        if val == "":
            stack.append((indent, key))
        else:
            paths[path] = val
    return paths


def _classify(plugin_text: str, project_text: str):
    P = parse_paths(plugin_text)
    J = parse_paths(project_text)
    added = {k: P[k] for k in P if k not in J}                      # new in plugin
    changed = {k: (J[k], P[k]) for k in P if k in J and J[k] != P[k]}  # default moved
    project_only = {k: J[k] for k in J if k not in P}              # your additions
    return P, J, added, changed, project_only


def _report(stream, name, added, changed, project_only):
    if added:
        stream.write(f"  + new in plugin ({name}) — missing from your copy:\n")
        for k, v in added.items():
            stream.write(f"      {k}: {v}\n")
    if changed:
        stream.write(f"  ~ default changed ({name}) — kept YOUR value, review:\n")
        for k, (jv, pv) in changed.items():
            stream.write(f"      {k}: yours={jv!r}  plugin-now={pv!r}\n")
    if project_only:
        stream.write(f"  · your own keys ({name}) — left untouched:\n")
        for k, v in project_only.items():
            stream.write(f"      {k}: {v}\n")


def cmd_diff(plugin_path, project_path):
    plugin_text = open(plugin_path).read()
    project_text = open(project_path).read()
    _, _, added, changed, project_only = _classify(plugin_text, project_text)
    _report(sys.stdout, project_path, added, changed, project_only)
    # Drift = the plugin has functionality (keys) your copy lacks. Changed
    # defaults alone do NOT trip the warning (they are usually your tuning).
    sys.exit(3 if added else 0)


def cmd_merge(plugin_path, project_path):
    plugin_text = open(plugin_path).read()
    project_text = open(project_path).read()
    P, J, added, changed, project_only = _classify(plugin_text, project_text)

    # Walk the plugin file (the template: current structure + comments + all new
    # keys) and overlay the project's value wherever the project set that path.
    out = []
    stack = []
    for raw in plugin_text.splitlines():
        line = raw.rstrip("\n")
        m = _KV.match(line)
        if m:
            indent = len(m.group("indent"))
            key = m.group("key")
            val = _value_of(m.group("rest"))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            path = ".".join([k for _, k in stack] + [key])
            if val == "":
                stack.append((indent, key))
            elif path in J and J[path] != P.get(path):
                # keep the project's tuned value; preserve any inline comment
                cm = re.search(r"(\s#.*)$", line)
                comment = cm.group(1) if cm else ""
                line = f"{m.group('indent')}{key}: {J[path]}{comment}"
        out.append(line)

    sys.stdout.write("\n".join(out) + "\n")
    if added or changed or project_only:
        sys.stderr.write("governance-overrides merge report:\n")
        _report(sys.stderr, project_path, added, changed, project_only)
    if project_only:
        sys.stderr.write(
            "  NOTE: your own keys above are NOT in the plugin template and were "
            "dropped from the merged output — re-add them if still wanted.\n"
        )


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("diff", "merge"):
        sys.stderr.write("usage: governance-overrides.py {diff|merge} PLUGIN PROJECT\n")
        sys.exit(2)
    (cmd_diff if sys.argv[1] == "diff" else cmd_merge)(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
