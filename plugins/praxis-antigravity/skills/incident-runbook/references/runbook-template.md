# Reference — Runbook, severity-classification & postmortem templates

Loaded by `incident-runbook` for the full worked examples behind each discipline item in the SKILL.md. These use `order-service` as the illustrative example — copy the structure, not the specific commands, when authoring a new service's runbook set.

## Severity classification rules — worked example

Pre-decided, not negotiated mid-incident. Each service's runbook section specifies how to classify:

```markdown
## Severity classification — order-service

| Signal | SEV |
|---|---|
| API success rate < 50% | SEV1 |
| API success rate < 95% sustained 5 min | SEV2 |
| p99 latency > 2s for 10 min | SEV2 |
| p99 latency > 500ms for 30 min (NFR breach) | SEV3 |
| One AZ down (still serving from others) | SEV3 |
| Background queue depth > 10x normal | SEV3 |
| Internal admin tool down | SEV4 |
| New anomaly in error budget | SEV5 → investigate |
```

When the on-call doesn't know which severity applies, default upward. Demoting an over-classified incident is easier than promoting an under-classified one.

## Runbook structure — worked example

A runbook is *what to do* during a specific operational scenario. Written for the on-call who's stressed, sleep-deprived, and never seen this exact situation. **Concrete commands; explicit verification steps; named decision points.** A good runbook has *no* prose paragraphs; it's checklists, commands, decision points. Stress-tolerant.

```markdown
# Runbook — Database Connection Pool Exhaustion (order-service)

## Symptoms
- API returning 5xx on POST /orders.
- Logs: "could not acquire connection from pool" or "pool timeout."
- Database connection metric: in_use ≈ pool_max.
- Aurora monitoring: client connections at limit.

## Severity
- If error rate > 50%: SEV1.
- If error rate 5-50%: SEV2.
- If error rate < 5% and recovering on its own: SEV3.

## Initial actions (5 minutes)

1. Verify symptom matches:
   ```
   kubectl -n order-service-production logs -l app=order-service --tail=200 | grep -i "pool"
   ```

2. Check pool saturation:
   - Grafana dashboard: order-service / DB-pool
   - Look for: connections-in-use approaching max for > 2 min

3. Acknowledge page; update status page (if SEV1/SEV2).

## Mitigation options

### Option A: Scale up pods (most common)
If pod count < HPA max, scale manually to relieve pressure:
```
kubectl -n order-service-production scale deployment order-service --replicas=20
```
Watch the pool metric for 5 min; if it stabilizes, you've bought time.

### Option B: Kill long-running connections
If specific long-running queries are hogging connections:
```sql
SELECT pid, query_start, query FROM pg_stat_activity
  WHERE state = 'active' AND query_start < NOW() - INTERVAL '60 seconds'
  ORDER BY query_start;
```
Terminate via `SELECT pg_terminate_backend(<pid>);` — careful, this kills the connection's client request too.

### Option C: Roll back recent deploy
If symptoms started within 30 min of a deploy:
```
argocd app rollback order-service-production
```
Verify deployment-state-history before rollback to confirm previous stable revision.

## Recovery verification

- Error rate < 1% sustained 10 min.
- p99 latency back to NFR target.
- Pool utilization < 70%.

## Postmortem triggers

ALWAYS run postmortem for SEV1/SEV2. Capture:
- Why was the pool exhausted? (Query plan changed? Traffic spike? Connection leak?)
- Why did the safeguards fail? (HPA didn't scale? Pool size mis-sized?)
- What permanent fix prevents recurrence?

## Owners
- Primary owner: Platform/SRE
- Service owner: <team that owns order-service>

## Related runbooks
- Database failover: `restore-aurora.md`
- HPA stuck: `hpa-troubleshoot.md`
```

## Blameless postmortem — template

For every SEV1, SEV2, and any SEV3 that recurs or teaches something. Run within 5 business days of resolution.

```markdown
# Postmortem — <Incident Name>

**Date of incident:** YYYY-MM-DD
**Duration:** Detect → Mitigate → Resolve (minutes/hours)
**Severity:** SEV1/2/3
**Customer impact:** <users affected, requests failed, revenue impact if known>

## Summary

<One paragraph: what happened, in plain language. No jargon.>

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:23 | First error rate alarm fires (5% errors). |
| 14:25 | On-call acknowledges. |
| 14:28 | Severity classified SEV2; incident channel opened. |
| 14:35 | Root cause hypothesized: pool exhaustion. |
| 14:42 | Manual scale-up to 20 pods. |
| 14:48 | Error rate returns to baseline. |
| 14:50 | Incident closed (acceptable signal sustained). |

## Root cause

<What caused the incident. Often multi-factor — list contributing factors.>

## Why our safeguards didn't catch it

<For each safeguard that exists for this class of failure, why didn't it prevent or contain?>

## Customer impact

<Users impacted; what they experienced; whether automatic recovery applied.>

## What went well

<Detection time; communication; team coordination; runbook accuracy.>

## What went poorly

<Detection time gaps; runbook gaps; communication misses; failed mitigations.>

## Action items

| Item | Owner | Due | Severity |
|---|---|---|---|
| Increase HPA scale-up rate to 2x → 3x | platform-sre | 2 weeks | High |
| Add connection-pool saturation as page-level alert | platform-sre | 1 week | High |
| Investigate query plan regression introduced in deploy v1.4.2 | backend-developer | 2 weeks | High |
| Update runbook: add Option D (cache traffic-shedding) | platform-sre | 1 week | Medium |

## Lessons learned

<Generalizable insights. What does this teach us about the system or process?>
```
