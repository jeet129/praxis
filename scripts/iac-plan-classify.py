#!/usr/bin/env python3
"""IaC plan classifier — the deterministic half of the iac_plan_review gate.

Reads a machine-readable infrastructure plan, auto-detects the tool, and tags
every resource change into the destructive-change classes the `iac_plan_review`
gate defines (see governance/governance.yaml). It FAILS CLOSED: if the plan
contains any blocking-class change that has NOT been explicitly dispositioned,
it exits non-zero so the workflow gate cannot clear.

Supported plan formats (auto-detected):
  - Terraform      `terraform show -json <planfile>`   (top-level `resource_changes`)
  - Pulumi         `pulumi preview --json`             (top-level `steps`)
  - CloudFormation `aws cloudformation describe-change-set --output json`  (top-level `Changes`)

This is a review aid, not a runtime interceptor — praxis does not run your
cloud or stop `apply`/`destroy`. It consumes a plan already produced (in CI or
by platform-sre) and produces the gate's evidence:
`plan_resource_change_summary` + the blocking list.

Classes (most to least severe):
  A data_bearing_destroy_or_replace  — delete/replace of a stateful resource
  B access_control_change            — IAM/role/binding/grant/service-account change
  C exposure_change                  — network/firewall/route/peering change
  D guardrail_removed                — deletion_protection off, force_destroy, etc.
  E cascade_replacement              — many replacements/deletes at once
  F stateless additive               — create/update, no replacement (auto-pass)

Usage:
  iac-plan-classify.py --plan plan.json [--format auto|terraform|pulumi|cloudformation]
                       [--disposition disp.yaml] [--out summary.json]
    --plan         plan file (or '-' for stdin)
    --format       override auto-detection (default: auto)
    --disposition  optional file of acknowledged resource addresses (one per line,
                   or YAML `acknowledged: [addr, ...]`); a listed blocking change
                   is treated as dispositioned
    --out          write the JSON resource-change summary here (the gate evidence)
    --cascade-threshold N   replacements+deletes above this flag a cascade (default 3)

Exit: 0 = no un-dispositioned blocking changes; 10 = blocking changes remain;
      2 = bad input / unrecognized format.
Zero third-party dependencies.
"""
import json
import re
import sys

# resource-type keyword sets — tolerant of snake_case (terraform: aws_security_group),
# camelCase (pulumi: aws:ec2/securityGroup:SecurityGroup) and PascalCase with '::'
# (cloudformation: AWS::EC2::SecurityGroup). `[_ ]?` bridges the word joins.
STATEFUL = re.compile(r"(db|database|rds|aurora|sql|s3|bucket|storage|blob|disk|volume|ebs|"
                      r"pvc|persistent[_ ]?volume|dynamodb|bigtable|spanner|firestore|elasticache|"
                      r"redis|memcached|warehouse|redshift|bigquery|snowflake|efs|filestore)", re.I)
ACCESS = re.compile(r"(iam|policy|role|binding|grant|service[_ ]?account|rbac|"
                    r"access[_ ]?control|acl[_ ]?policy|key[_ ]?ring|kms|secret)", re.I)
NETWORK = re.compile(r"(security[_ ]?group|firewall|ingress|egress|\bnat\b|route|peering|subnet|"
                     r"network[_ ]?acl|load[_ ]?balancer|listener|\bdns\b|\bcert|\bvpc\b)", re.I)
# guardrail flags — both snake_case (terraform/cfn) and camelCase (pulumi); value that is DANGEROUS
GUARDRAIL_KEYS = {
    "deletion_protection": False, "deletionProtection": False,
    "force_destroy": True, "forceDestroy": True,
    "skip_final_snapshot": True, "skipFinalSnapshot": True,
    "prevent_destroy": False, "preventDestroy": False,
    "enable_deletion_protection": False, "enableDeletionProtection": False,
}
# CFN guardrail property names (change set gives names, not always values)
CFN_GUARDRAIL_PROPS = {"DeletionProtection", "DeletionPolicy", "EnableDeletionProtection"}


def _arg(name, default=None):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _guardrail_hits(after):
    hits = []
    if isinstance(after, dict):
        for k, bad in GUARDRAIL_KEYS.items():
            if k in after and after.get(k) == bad:
                hits.append(k)
    return hits


# --------------------------------------------------------------------------
# normalization: every tool -> [{address, type, actions, after, guardrail_props}]
# `actions` uses Terraform semantics: ["create"], ["update"], ["delete"],
# ["create","delete"] (replace), ["no-op"], ["read"].
# --------------------------------------------------------------------------
def normalize(plan, fmt="auto"):
    if fmt == "auto":
        if isinstance(plan, dict) and "resource_changes" in plan:
            fmt = "terraform"
        elif isinstance(plan, dict) and "steps" in plan:
            fmt = "pulumi"
        elif isinstance(plan, dict) and "Changes" in plan:
            fmt = "cloudformation"
        else:
            raise ValueError("unrecognized plan format — expected Terraform `resource_changes`, "
                             "Pulumi `steps`, or CloudFormation `Changes`")
    out = []
    if fmt == "terraform":
        for rc in plan.get("resource_changes", []) or []:
            ch = rc.get("change", {}) or {}
            out.append({"address": rc.get("address", "?"), "type": rc.get("type", ""),
                        "actions": ch.get("actions", []) or [], "after": ch.get("after") or {},
                        "guardrail_props": []})
    elif fmt == "pulumi":
        opmap = {
            "create": ["create"], "update": ["update"], "delete": ["delete"],
            "replace": ["create", "delete"], "create-replacement": ["create", "delete"],
            "delete-replaced": ["delete"], "import": ["read"],
            "import-replacement": ["create", "delete"],
            "same": ["no-op"], "read": ["read"], "read-replacement": ["read"], "refresh": ["no-op"],
        }
        for st in plan.get("steps", []) or []:
            op = st.get("op", "")
            actions = opmap.get(op, ["update"] if op else ["no-op"])
            new = st.get("newState") or {}
            old = st.get("oldState") or {}
            rtype = new.get("type") or old.get("type") or ""
            urn = st.get("urn") or new.get("urn") or ""
            addr = urn.split("::")[-1] if urn else (rtype or "?")
            after = new.get("inputs") or new.get("outputs") or {}
            out.append({"address": addr or "?", "type": rtype, "actions": actions,
                        "after": after, "guardrail_props": []})
    elif fmt == "cloudformation":
        for c in plan.get("Changes", []) or []:
            rc = c.get("ResourceChange") or {}
            action = rc.get("Action", "")             # Add | Modify | Remove | Import | Dynamic
            repl = str(rc.get("Replacement", "")).lower()   # true | false | conditional
            if action == "Add":
                actions = ["create"]
            elif action == "Remove":
                actions = ["delete"]
            elif action == "Modify":
                actions = ["create", "delete"] if repl in ("true", "conditional") else ["update"]
            elif action == "Import":
                actions = ["read"]
            else:
                actions = ["update"]
            rtype = rc.get("ResourceType", "")
            addr = rc.get("LogicalResourceId") or rc.get("PhysicalResourceId") or "?"
            # CFN change set lacks after-VALUES, but Details name the changed properties;
            # surface guardrail property names so Class D can flag (value unverifiable).
            gprops = []
            for d in rc.get("Details", []) or []:
                tgt = (d.get("Target") or {}).get("Name")
                if tgt in CFN_GUARDRAIL_PROPS:
                    gprops.append(tgt)
            out.append({"address": addr, "type": rtype, "actions": actions,
                        "after": {}, "guardrail_props": gprops})
    else:
        raise ValueError(f"unknown --format {fmt}")
    return fmt, out


def classify(changes, cascade_threshold=3):
    tagged = []
    n_replace = n_delete = 0
    for ch in changes:
        actions = ch["actions"]
        if actions in (["no-op"], ["read"], []):
            continue
        rtype = ch["type"]
        destructive = "delete" in actions
        replace = "delete" in actions and "create" in actions
        if replace:
            n_replace += 1
        elif "delete" in actions:
            n_delete += 1
        classes = []
        if destructive and STATEFUL.search(rtype):
            classes.append("A:data_bearing_destroy_or_replace")
        if ACCESS.search(rtype) and actions != ["create"]:
            classes.append("B:access_control_change")
        if NETWORK.search(rtype) and (destructive or "update" in actions):
            classes.append("C:exposure_change")
        for k in _guardrail_hits(ch.get("after")):
            classes.append(f"D:guardrail_removed({k})")
        for prop in ch.get("guardrail_props", []):     # CFN: name only, value unverifiable
            classes.append(f"D:guardrail_property_changed({prop}; verify value manually)")
        tagged.append({"address": ch["address"], "type": rtype, "actions": actions,
                       "replace": replace, "classes": classes})
    cascade = (n_replace + n_delete) > cascade_threshold
    return tagged, {"replacements": n_replace, "deletes": n_delete, "cascade": cascade}


def load_dispositions(path):
    if not path:
        return set()
    try:
        txt = open(path).read()
    except Exception:
        return set()
    acked = set()
    m = re.search(r"acknowledged\s*:\s*\[(.*?)\]", txt, re.S)
    if m:
        acked |= {x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()}
    for line in txt.splitlines():
        line = line.strip().lstrip("-").strip().strip('"\'')
        if line and not line.endswith(":") and "acknowledged" not in line and "[" not in line:
            acked.add(line)
    return {a for a in acked if a}


def main():
    plan_path = _arg("--plan")
    if not plan_path:
        sys.stderr.write("iac-plan-classify: --plan required\n")
        return 2
    try:
        raw = sys.stdin.read() if plan_path == "-" else open(plan_path).read()
        plan = json.loads(raw)
    except Exception as e:
        sys.stderr.write(f"iac-plan-classify: cannot read plan JSON: {e}\n")
        return 2
    try:
        fmt, changes = normalize(plan, _arg("--format", "auto"))
    except ValueError as e:
        sys.stderr.write(f"iac-plan-classify: {e}\n")
        return 2

    tagged, totals = classify(changes, int(_arg("--cascade-threshold", "3")))
    acked = load_dispositions(_arg("--disposition"))

    BLOCKING = ("A:", "B:", "C:", "D:")
    blocking = [t for t in tagged if any(c.startswith(BLOCKING) for c in t["classes"])]
    undispositioned = [t for t in blocking if t["address"] not in acked]

    summary = {
        "format": fmt,
        "totals": {
            "resource_changes": len(tagged),
            "replacements": totals["replacements"],
            "deletes": totals["deletes"],
            "cascade": totals["cascade"],
            "blocking": len(blocking),
            "undispositioned_blocking": len(undispositioned),
        },
        "changes": tagged,
        "blocking": blocking,
        "undispositioned_blocking": [t["address"] for t in undispositioned],
        "dispositioned": sorted(acked & {t["address"] for t in blocking}),
    }
    out = _arg("--out")
    if out:
        try:
            open(out, "w").write(json.dumps(summary, indent=2) + "\n")
        except Exception:
            pass

    print(f"IaC plan [{fmt}]: {len(tagged)} changes | {totals['replacements']} replace, "
          f"{totals['deletes']} delete | cascade={totals['cascade']} | "
          f"{len(blocking)} blocking-class, {len(undispositioned)} un-dispositioned")
    undel = [u["address"] for u in undispositioned]
    for t in blocking:
        mark = "UNDISPOSITIONED" if t["address"] in undel else "acked"
        print(f"  [{mark}] {t['address']} ({','.join(t['classes'])})")
    if totals["cascade"]:
        print(f"  NOTE cascade: {totals['replacements'] + totals['deletes']} destructive changes in one plan "
              f"— escalate each in-scope resource to its Class A/B/C evidence")

    if undispositioned:
        print("\nGATE=BLOCK — un-dispositioned destructive changes remain; the iac_plan_review "
              "verdict cannot clear until each is acknowledged with evidence.")
        return 10
    print("\nGATE=CLEAR — no un-dispositioned blocking changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
