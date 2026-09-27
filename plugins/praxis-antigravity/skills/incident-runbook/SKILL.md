---
name: incident-runbook
description: "Operational readiness discipline. Per-service runbooks, on-call rotation, severity taxonomy, incident response workflow, blameless postmortems with action-item tracking, status-page communication. Platform/SRE owns this; consumes reliability-dr (for severity classification), observability (for incident detection), and feeds tech-debt-management (for action items) and factory-evaluation (for MTTR metrics). Use whenever a new service is being made production-ready, when an incident occurs, when running a postmortem, or when reviewing operational readiness."
---

# Incident Runbook & Operational Readiness

<!-- praxis:metadata:begin -->
```yaml
capability: operations
domain: cross-cutting
state: active
dependencies:
 - reliability-dr
 - observability
 - deploy-release
triggers:
 - "establishing on-call rotation for a new service"
 - "writing runbooks for a new operational scenario"
 - "an incident is occurring or just occurred"
 - "running a blameless postmortem"
 - "auditing operational readiness for production_go_live"
outputs:
 - per-service runbook set (one per operational scenario worth automating away from)
 - severity taxonomy + escalation matrix
 - on-call rotation schedule + handoff protocol
 - incident-response workflow
 - postmortem (per incident)
 - action items (tracked into tech-debt-management)
consumers:
 - platform-sre (primary author + on-call)
 - delivery-lead (consulted for severe incidents)
 - tech-writer (consulted for postmortem narrative + runbook polish)
 - tech-debt-management (consumes action items)
 - factory-evaluation (MTTR + postmortem cadence as library-health metrics)
references:
 - runbook-template.md
```
<!-- praxis:metadata:end -->

The discipline that turns "things break and we figure it out" into "things break, the on-call knows what to do, and we learn from it." Without it, every incident is novel; with it, every incident strengthens the system.

The principle: **incidents are inevitable; suffering through them is optional.** Runbooks make response routine; postmortems make recurrence rare.

## When this skill fires

- A new service is being made production-ready — write its runbook set and assign to on-call.
- A new operational scenario is encountered — capture the response as a runbook (so the next person doesn't reinvent).
- An incident is occurring — the on-call follows the response workflow + runbooks.
- An incident has occurred — run a blameless postmortem.
- Operational readiness is being audited for production_go_live.

## Severity taxonomy

Five severities. Used for paging policy, escalation, and post-incident communication.

| Severity | Description | Response | Examples |
|---|---|---|---|
| **SEV1** | Customer-facing outage; major function unavailable for all/most users. | Page primary + secondary; engage incident commander; status page goes red. | Total API outage; production database unreachable; auth completely down. |
| **SEV2** | Major degradation; significant subset of users impacted. | Page primary; engage incident commander; status page goes yellow. | p99 latency 5x normal; checkout failing 20% of attempts; one region down. |
| **SEV3** | Minor degradation; impact small or workaround exists. | Page primary; status page may update if customer-visible. | Background job queue backed up; non-critical endpoint failing. |
| **SEV4** | Internal issue; no customer impact. | Ticket; addressed during business hours. | Internal tool broken; monitoring noise; non-prod environment down. |
| **SEV5** | Information only; tracking. | Ticket; bundled with regular work. | Logged anomaly that needs investigation; non-urgent finding. |

SEV1/SEV2 trigger pages immediately. SEV3 escalates if not acknowledged within configured window. SEV4/SEV5 are tickets, not pages.

### Severity classification rules

Pre-decided, not negotiated mid-incident. Each service's runbook section specifies how to classify. When the on-call doesn't know which severity applies, default upward — demoting an over-classified incident is easier than promoting an under-classified one. Load `references/runbook-template.md` for a worked classification table.

## On-call rotation

### Structure

- **Primary on-call** — receives pages first; responds within paging SLA (typically 5 minutes for SEV1/SEV2).
- **Secondary on-call** — receives pages if primary doesn't acknowledge within SLA; covers primary's gaps (sick, asleep, can't reach).
- **Incident commander** — for SEV1/SEV2, takes coordination role; assigns responder roles; communicates externally. Often a rotating role separate from technical on-call.

Rotation length: 1 week is standard. Shorter (3-4 days) for very small teams; longer (2 weeks) only when load is genuinely low.

### Handoff protocol

Each rotation hand-off includes:

- **Open incidents** — anything in-progress.
- **Outstanding action items** from recent postmortems.
- **Known fragile areas** — where the previous on-call worries.
- **Anticipated events** — planned changes, marketing campaigns, expected load.
- **Personal context** — anything unusual (PTO, partial coverage).

Hand-off is a 15-minute call, not a Slack message. Live conversation surfaces what the document misses.

### On-call sustainability

Pages outside business hours have a real cost — sleep, family time, mental health. Track and address:

- **Page count per rotation** — > 5 nighttime pages per week is unsustainable; escalate to reduce noise.
- **Page actionability** — pages that fire and resolve without human action are noise; quiet them.
- **Page → fix rate** — pages should produce action; pages that recur unfixed indicate a missing root-cause investigation.

`factory-evaluation` tracks these as library-health metrics Sustainable on-call is a *production-quality property*, not a personal-resilience property.

## Runbook structure

A runbook is *what to do* during a specific operational scenario. Written for the on-call who's stressed, sleep-deprived, and never seen this exact situation. **Concrete commands; explicit verification steps; named decision points.** A good runbook has *no* prose paragraphs; it's checklists, commands, decision points. Stress-tolerant.

Every runbook covers: symptoms, severity, initial actions, mitigation options (with concrete commands per option), recovery verification, postmortem triggers, owners, and related runbooks. Load `references/runbook-template.md` for a fully worked example (database connection-pool exhaustion).

## Incident response workflow

The on-call follows the same outer loop every time:

```
1. Receive page → acknowledge within paging SLA
2. Classify severity (per the rules above)
3. If SEV1/SEV2: declare incident; appoint commander; open incident channel
4. Mitigate (per runbook, or improvise if no runbook covers it)
5. Verify recovery (per runbook's recovery section)
6. Communicate (status page; internal stakeholders)
7. Hand off if rotation ends mid-incident
8. Schedule postmortem
9. Archive incident record
```

The discipline isn't about following the workflow during the incident — it's about having the workflow *be the default* so adrenaline doesn't have to invent it.

## Blameless postmortem

For every SEV1, SEV2, and any SEV3 that recurs or teaches something. Run within 5 business days of resolution.

### Format

Covers: date/duration/severity/customer-impact header, plain-language summary, timeline, root cause, why safeguards didn't catch it, customer impact, what went well/poorly, action items (owner + due date + severity), and lessons learned. Load `references/runbook-template.md` for the full postmortem template.

### Blameless discipline

The format excludes finger-pointing by design. Instead of "X made a bad change," the postmortem asks: "Why was the process such that this change reached production?" — and the answer is usually about missing review, missing test, missing alert, not about a person.

Blameless does *not* mean accountability-free. It means accountability is system-focused: what process change makes recurrence harder?

### Action item discipline

Action items are tracked, owned, and closed. A postmortem without action items closed within deadline produces the same incident again. `tech-debt-management` is where action items flow when they're not addressable in a near-term sprint.

## Status page

Customer-facing communication during incidents. Modern tools (Statuspage, StatusGator, self-hosted): subscribe to RSS / SMS / email.

### Discipline

- **Update fast** — within 10 minutes of confirming customer impact. Better to over-communicate than under.
- **Plain language** — not "elevated 5xx in primary persistence cluster" but "some users may see errors creating orders."
- **Without false reassurance** — don't say "fully resolved" until verified for 10+ minutes of clean signal.
- **Postmortem published** — for SEV1, a customer-facing postmortem (less technical than internal) is published within 5 business days.

## Outputs

| Output | Location |
|---|---|
| Per-service runbook set | `.project/operational/runbooks/` |
| Severity taxonomy + classification | `.project/procedural/severity-taxonomy.md` |
| On-call rotation schedule | external tool (PagerDuty, Opsgenie, etc.) referenced from `.project/procedural/oncall.md` |
| Incident-response workflow | `.project/procedural/incident-response.md` |
| Postmortems | `.project/operational/postmortems/postmortem-{date}-{slug}.md` |
| Open action items | `.project/working/action-items.md` (tracked through to closure) |

## Mode handling (G/B)

**Greenfield.** Build the runbook set as services become production-ready. First production deploy requires at least: a basic runbook for the service + on-call rotation + classification rules.

**Brownfield.** Audit existing runbooks for currency (a runbook that references retired services is worse than no runbook). Common findings: no formal severity taxonomy; postmortems exist but action items don't close; on-call burnt out. Address sustainability first; documentation second.

## What this skill does not do

- Detect incidents — that's `observability` instrumentation + alert routing.
- Define reliability targets — that's `reliability-dr`.
- Test the response by injecting failures — that's `chaos-engineering`.
- Fix the underlying systems — that's the development cycle informed by postmortem action items.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Runbook is a wiki page nobody reads." | Then it's not a runbook. Test it; if you can't follow it under pressure, fix it. |
| "Severity is obvious in the moment." | Definitions matter. Document them; train on them. SEV1 means specific things, not "feels bad." |
| "On-call rotation is paid; that's enough." | Compensation is necessary; psychological safety + load balance + handoff discipline are also required. |
| "Blameless postmortems are corporate-speak." | Blameless postmortems generate honest signal. Blameful ones get sanitized reports. The honest signal is the value. |
| "Action items happen eventually." | They get sidelined under feature pressure. Tag them; commit to closure; track. |
| "Communication during incident is the IC's job." | Comms requires its own role (sometimes), especially for SEV1. Don't task the IC with both response + communication. |
| "Drills are theater." | Drills are how the runbook becomes muscle memory. Schedule them. |

## Verification

You are done when:

- [ ] Runbook per incident class exists with: symptoms / severity / diagnosis steps / mitigations / escalation / postmortem trigger.
- [ ] Severity matrix documented + visible to on-call.
- [ ] On-call rotation set; handoffs documented.
- [ ] Postmortem template covers: timeline / root cause / contributing factors / action items / lessons.
- [ ] Postmortem retro is blameless (process-focused, not person-focused).
- [ ] Action items tracked to closure; SLA on closure documented.
- [ ] Drill scheduled per quarter; runbook tested.
- [ ] Communication channels documented (status page, customer email, internal alerts).

Evidence to check:
- The last incident's runbook actually worked (or the gaps were captured).
- Action items from prior incidents have measurable closure rate.

## Anti-patterns

- Pages that fire and resolve without action (noise).
- Runbooks written in prose paragraphs (stress-unfriendly).
- Postmortems without action items.
- Action items without owners or due dates.
- Severity classification negotiated during incidents.
- Status page updates 2 hours after customer impact starts.
- "Blameless" used as cover for not investigating root cause.
- On-call rotation > 12 nighttime pages per month (unsustainable; address noise + root causes).
- First incident on a new service finding the runbook missing entirely.
- Action items recurring because the same postmortem keeps writing them.
