# Reliability & DR — Worked Examples

Supporting templates for `reliability-dr/SKILL.md`. Pulled out here to keep the main skill file scannable; referenced by pointer from the relevant sections.

## Drill attestation example

Each drill produces an attestation in `.project/operational/drills/`:

```markdown
# DR Drill — Database Restore
Date: 2026-09-15
Drill type: production-snapshot → sandbox restore
Operators: <platform-sre on-call>
Outcome: PASS
Time-to-restore: 22 minutes (RTO target: 30 minutes)
Data integrity: verified via row-count + sample query parity
Findings: <none / list>
Next drill due: 2026-12-15
```

## DR plan document — worked example

Per service or per logical system:

```markdown
# DR Plan — order-service

## Targets
- RTO: 30 minutes (NFR-defined)
- RPO: 5 minutes
- Availability SLO: 99.9% / 30-day rolling

## Topology
- Production: multi-AZ within us-east-1; 3 replicas across 3 AZs.
- Database: Aurora Postgres with cross-AZ replication; PITR enabled (7-day window).
- DR site: warm standby in us-west-2 (snapshots replicated nightly).

## Failure modes
- Single pod fail: HPA + Cluster Autoscaler replace within minutes; no user impact.
- Single AZ fail: remaining 2 AZs absorb load; HPA scales remaining pods up.
- Single region fail: switch DNS to us-west-2; restore database from latest replicated snapshot; expected RTO 25 min.
- Database corruption: PITR to last-known-good; expected RTO 10 min.

## Backup
- Database: PITR (continuous); daily snapshots retained 35 days; cross-region snapshot retention 7 days.
- Object storage: versioned, cross-region replicated, 90-day retention.

## Runbooks
- Failover to us-west-2: .project/operational/runbooks/failover-us-west-2.md
- Database restore from snapshot: .project/operational/runbooks/restore-aurora.md
- Database PITR: .project/operational/runbooks/pitr-aurora.md

## Drill schedule
- Quarterly: database restore drill (next: 2026-12-15).
- Semi-annually: full region failover (next: 2026-11-30).

## Attestation (latest)
- Database restore drill: PASS 2026-09-15 (RTO 22 min vs target 30 min).
- Region failover: PASS 2026-08-22 (cutover 18 min; running in us-west-2 for 60 min; cutback successful).
```
