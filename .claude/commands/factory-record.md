---
description: "Record a rich factory-metrics observation for a praxis artifact (skill, agent, workflow, command). Use when you've just finished using an experimental skill and want to capture what worked, what didn't, and what should change before steward review."
---

You are recording a factory-metrics observation. This is the rich, human-authored complement to the auto-stub entries that the PostToolUse hook writes — those tell us *something happened*; this tells us *what happened and what we learned*.

## Step 1 — Identify the artifact

Ask the user (or infer from recent conversation) which artifact they want to record an observation for:

- **Type:** skill | agent | workflow | command | hook | gate | reference
- **Name:** the artifact's identifier (e.g., `requirements-intake`, `delivery-lead`, `brownfield-enhancement`)

If the user has just been working with a specific praxis artifact in this session, propose it as the default and ask for confirmation.

## Step 2 — Capture observation

Ask these in order (skip any the user has already said in this session):

1. **What happened?** What was the artifact being used for in this session?
2. **What worked?** Where did the discipline land correctly — what did you notice working as designed?
3. **Friction?** Where was the artifact clunky, ambiguous, slow, or required workarounds?
4. **Edge cases?** Situations the artifact didn't anticipate — what did you have to improvise?
5. **Suggested refinements?** What would you change about the artifact based on this use?

Don't insist on all five if the user only has one or two to share. Quality > completeness.

## Step 3 — Optional context

If known and the user hasn't said it:
- **Slice id** (if in a slice context)
- **Outcome** (success / failure / partial)
- **Duration** (roughly, in minutes)

## Step 4 — Write the file

Compose the markdown body and invoke the recorder script:

```bash
# Build observation as a temp file
OBS=$(mktemp)
cat > "$OBS" <<'EOF'
## What worked
{ what the user said about what worked }

## Friction
{ what the user said about friction }

## Edge cases
{ what the user said about edge cases }

## Suggested refinements
{ what the user said about refinements }
EOF

# Call the recorder
"${CLAUDE_PLUGIN_ROOT}/scripts/factory-record.sh" \
    --type        {type} \
    --name        {name} \
    --tool        claude-code \
    --trigger     slash-command \
    --invocation  read \
    --outcome     {outcome or null} \
    --slice       {slice or empty} \
    --duration    {duration in seconds or empty} \
    --observation "$OBS" \
    --mode        per-use
```

## Step 5 — Confirm

Tell the user the file was written, show the path, and ask if they want to record another observation. The aging report (`scripts/factory-aging.sh`) will surface this entry to the System Steward at the next quarterly review.

## Notes

- **Don't write secrets, customer data, or sensitive PII.** Telemetry files commit to git.
- **Skip the command for routine auto-stub captures** — the PostToolUse hook handles those. Use this command when you have something substantive to say.
- **Frequency:** for experimental skills, after every meaningful use. For active skills, only when you have a real observation (don't pad).
