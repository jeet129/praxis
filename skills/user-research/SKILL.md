---
name: user-research
description: Plan and synthesize lightweight user research — interview prep, hypothesis-driven discovery sessions, structured synthesis into themes and insights — to ground requirements in real user needs rather than internal assumptions. Distinct from `product-discovery` (which frames opportunities) and `wireframing-prototyping` (which validates designs).
---

# User Research


<!-- praxis:description:full -->
## Full description

Plan and synthesize lightweight user research — interview prep, hypothesis-driven discovery sessions, structured synthesis into themes and insights — to ground requirements in real user needs rather than internal assumptions. Distinct from `product-discovery` (which frames opportunities) and `wireframing-prototyping` (which validates designs). This skill runs the research methodology cleanly; its outputs feed back into discovery (validating or invalidating problem and solution hypotheses) and into wireframing (validating interaction designs).

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: ux-and-design
domain: cross-cutting
state: active
dependencies:
 - product-discovery
triggers:
 - "validating problem hypotheses from product-discovery"
 - "testing solution hypotheses with real users"
 - "validating wireframe interactions with users"
 - "structured user-feedback synthesis"
 - "running discovery interviews"
outputs:
 - research plan (objectives, methodology, participants, timeline)
 - interview script(s)
 - raw notes (per session)
 - synthesized themes + insights
 - validated / invalidated assumptions (back into product-discovery)
 - design recommendations (back into wireframing-prototyping)
consumers:
 - ux-designer (primary; or PM in solo)
 - product-manager (consumes themes for prioritization)
 - solution-architect (consumes insights for design constraints)
references: []
```
<!-- praxis:metadata:end -->

The discipline of asking users questions that produce *learning* rather than confirmation. Most teams have plenty of opinions; few have validated insights. This skill is what turns assumptions into evidence — or, more importantly, into invalidated assumptions you stop building against.

For solo development, the principal often plays both UX Designer and researcher. The discipline still applies: the structured interview script, the synthesis methodology, the explicit hypothesis-test framing. Without them, "I talked to some users" produces folklore, not evidence.

## When this skill fires

- A problem hypothesis from `product-discovery` needs validation before significant build investment.
- A solution hypothesis is being tested via wireframes or a prototype.
- An interaction design has multiple candidate approaches and the team wants signal on which works better.
- Behavioral data shows a friction point and the team wants to understand *why*.
- A new persona is being characterized for the first time.

## The procedure

### 1. Define the research question

The single most important step. A research question is specific, testable, and tied to a decision:

- **Good:** "When SMB owners receive their monthly bank statement, what's the first step they take? Is bank-to-software linking the highest-friction step, or is it identifying which transactions to ignore?"
- **Bad:** "Learn about how SMB owners do reconciliation."

The good question implies a decision (where to invest design effort); the bad question is a fishing expedition that produces volume without insight.

### 2. Pick the methodology

Match the question to the method:

| Question type | Method |
|---|---|
| "How do users currently do X?" | **Generative interviews** — open-ended, journey-focused. |
| "Does our prototype work for this persona?" | **Usability sessions** — task-based; observe + think-aloud. |
| "Which of these approaches do users prefer?" | **Comparative testing** — A/B prototype or unmoderated test. |
| "How big is this problem?" | **Survey** — quantitative; large sample; only after qualitative scoping. |
| "What's the cause of this observed friction?" | **Contextual inquiry** — observe users in their natural environment. |

For solo development, **generative interviews** and **usability sessions** are the most common. They're the cheapest and most generative.

### 3. Recruit participants

For qualitative research, **5–8 participants per persona** is the rule of thumb. Beyond 8, marginal new insight drops sharply (Nielsen's classic findings). Below 5, individual outliers can mislead.

Participant criteria:
- Match the persona definition (not generic "users").
- Mix of expertise levels if the product spans them.
- No prior involvement in the design (avoid demand characteristics).
- Compensated fairly for their time.

For solo development without a recruiting budget: friends-of-target-personas work, with the caveat that pre-existing rapport can bias results. Document the recruiting method honestly in the research plan.

### 4. Write the interview script

The script has structure but isn't rigid:

```
Opening (5 min):
 - Thank participant; remind of confidentiality.
 - Brief context: "We're building a tool for [persona]; we want to learn
 how you currently [domain task]."
 - Ground rules: no wrong answers; we're not testing them.

Warm-up (5 min):
 - Open-ended question about the domain to start the conversation.
 - "Tell me about the last time you did [domain task]."

Core (30–40 min):
 - Hypothesis-test questions (the ones tied to the research question).
 - Follow-ups: "Tell me more about that." "What were you thinking when..."
 - Avoid leading: not "Was that frustrating?" but "How did that feel?"

Probe (10 min):
 - If running usability: tasks against the prototype, think-aloud.
 - If generative: deeper exploration of unexpected paths.

Closing (5 min):
 - "Is there anything we didn't ask that you wish we had?"
 - Thank; explain next steps.
```

The script is the *backbone*; deviation in pursuit of an unexpected lead is allowed (and encouraged) when the participant says something interesting.

### 5. Run the sessions

Per session:
- Record (with consent), so synthesis can revisit verbatim.
- Take notes during the session — facts, observations, surprises. Not interpretations yet.
- Avoid leading. The interviewer's job is to ask and listen, not to teach or persuade.
- Time-box. Sessions over 60 minutes degrade in quality.

Solo development tip: even if you're solo, *record* the sessions. Synthesis from memory after the fact is unreliable; recordings let you re-listen with fresh ears.

### 6. Synthesize

After all sessions:

**Pass 1: collect raw observations.** Per participant, list the concrete things they said and did. Avoid interpretation at this pass — just facts.

**Pass 2: cluster into themes.** Look across participants for patterns. A theme is a finding that appears in multiple sessions, not just one. Use affinity grouping (sticky notes or a digital equivalent).

**Pass 3: extract insights.** An insight is a theme plus a "so what." It connects observation to design implication:

- *Observation:* "5 of 7 participants opened email to find their bank statement before opening our tool."
- *Theme:* Users start the reconciliation flow outside our product, in email.
- *Insight:* Our product is missing the *entry* into the journey. Users arrive without the statement loaded; we treat this as their starting point but it's actually their second step.

**Pass 4: map back to hypotheses.** For each problem and solution hypothesis from `product-discovery`, mark it:
- **Validated** — evidence supports it.
- **Invalidated** — evidence contradicts it.
- **Refined** — evidence reshapes it (the new form is the next hypothesis).
- **Untested** — sessions didn't touch this hypothesis (may need follow-up research).

### 7. Output the research report

Concise. The report has:

```markdown
# User Research: <topic>

**Research question:** <one sentence>
**Method:** <interview / usability / comparison / survey>
**Participants:** N=X (description)
**Date:** YYYY-MM-DD
**Researcher:** <name>

## Key insights (top 3–5)

1. <Insight headline>. <Supporting observation> (N=X participants).
2. ...

## Themes

<Theme 1 with supporting quotes/observations>
<Theme 2 ...>

## Hypothesis disposition

| Hypothesis (from product-discovery) | Disposition | Evidence |
|---|---|---|
| <hypothesis text> | validated | (N=X out of N participants) |
| <hypothesis text> | invalidated | (counter-evidence) |
| <hypothesis text> | refined | (new form: ...) |
| <hypothesis text> | untested | needs follow-up |

## Design recommendations

<Concrete, actionable; tied to insights above>

## Open questions

<What the research didn't answer; next research priorities>
```

Short, actionable, evidence-linked. A 30-page research report nobody reads is worse than a 2-page report the team acts on.

## Outputs

| Output | Location | Lifecycle |
|---|---|---|
| Research plan | `.project/working/research-plan-{topic}.md` | Working; archived to episodic on completion |
| Interview scripts | `.project/working/research-script-{topic}.md` | Working |
| Session recordings | external storage (privacy compliance applies) | Per data-retention policy |
| Raw notes per session | `.project/working/research-notes-{participant-id}.md` | Working |
| Synthesized themes + insights | `.project/episodic/research-report-{topic}-{date}.md` | Permanent |
| Hypothesis disposition update | back into `.project/episodic/discovery-{date}.md` | Append |

## Mode handling (G/B)

**Greenfield.** Standard research methodology.

**Brownfield.** Research often focuses on existing-product friction. Leverage behavioral data (analytics, support tickets, NPS) as a starting signal; interviews then explore the *why* behind what the data shows.

## What this skill does not do

- Frame the opportunity — that's `product-discovery` (which user research validates).
- Wireframe — that's `wireframing-prototyping`.
- Quantify market size — that's market research, a different discipline.
- Conduct longitudinal studies — out of scope for ; specialized.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Talking to a few users is research." | Conversations + observation + structured questions = research. Just chatting isn't. |
| "Five users is enough." | For some questions yes (Nielsen). For others (quantitative validation), no. Choose method by question. |
| "Surveys are easy." | Survey design is its own craft. Leading questions + bad scales produce noise. |
| "Research delays shipping." | Research informs what to ship. Skipping it ships the wrong thing. |
| "We know our users." | You know who-bought-yesterday. Research surfaces who-doesn't-buy and why. |
| "Insights are obvious from the transcript." | Synthesis is the skill. Patterns across N interviews surface things one interview doesn't. |

## Verification

You are done when:

- [ ] Research question framed (what decision will this inform?).
- [ ] Method chosen (interview / survey / usability / contextual / diary).
- [ ] Sample defined (size + recruitment criteria).
- [ ] Script / protocol prepared.
- [ ] Sessions conducted + recorded (with consent).
- [ ] Notes / transcripts available.
- [ ] Synthesis surfaces themes + verbatims + outliers.
- [ ] Findings linked to decisions: "because X, we should Y."
- [ ] Open questions logged.

Evidence to check:
- A decision was actually informed by the research.
- Findings + verbatims are accessible to PM, design, engineering.

## Anti-patterns

- Researching to confirm rather than to learn. The research question is honest if there's a plausible answer that would *invalidate* a current belief.
- Single-participant insights treated as themes. Themes require multiple participants.
- Leading questions ("Wasn't that frustrating?"). Bias.
- Skipping recording. Memory-based synthesis is unreliable.
- Reports without action. Every insight ties to a design or product decision.

## Ethical baseline

- **Consent** — participants know what they're doing and how their data will be used.
- **Confidentiality** — identifying info redacted in shared reports.
- **Compensation** — participants are paid fairly for their time.
- **Data retention** — recordings deleted per the retention policy (typically 90 days for raw recordings; synthesized themes are permanent).

These are non-negotiable.
