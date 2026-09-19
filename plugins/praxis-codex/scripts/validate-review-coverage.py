#!/usr/bin/env python3
"""Review-coverage guard — declare what matters, don't auto-derive.

A gate reviewer must actually LOAD the security/quality checklists it is
accountable for. This is NOT derived from skills' fuzzy `consumers:` field
(that mixes "must apply" with "might touch" and yields false positives);
it is a small hand-curated allowlist edited by intent. Add a skill here only
when a reviewer is genuinely responsible for applying it on the relevant PRs.

CI: run this in the validation suite; exits non-zero on any missing coverage.
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# reviewer agent -> skills its discipline-selection MUST name
REQUIRED = {
    "security-reviewer": [
        "secure-coding", "threat-modeling", "authn-authz",
        "supply-chain-security", "compliance-privacy", "responsible-ai",
        "iac", "llm-safety",
    ],
    # add code-reviewer / qa-engineer sets here deliberately if desired
}

def main() -> int:
    gaps = []
    for agent, skills in REQUIRED.items():
        f = ROOT / "agents" / f"{agent}.md"
        text = f.read_text(encoding="utf-8", errors="ignore") if f.exists() else ""
        for sk in skills:
            if sk not in text:
                gaps.append((agent, sk))
    if gaps:
        print("Review-coverage FAIL — a reviewer does not name a required skill:")
        for a, sk in gaps:
            print(f"  {a} is missing `{sk}` (must appear in its disciplines / discipline-selection)")
        return 1
    total = sum(len(v) for v in REQUIRED.values())
    print(f"Review-coverage OK: {total} required reviewer<->skill links present.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
