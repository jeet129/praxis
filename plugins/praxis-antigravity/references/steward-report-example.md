# Steward report — worked example

Referenced by `agents/system-steward.md`. This is the quarterly steward report template with an illustrative worked example (Q4 2026), showing the expected sections and level of detail.

```markdown
# Steward Report — 2026 Q4

## Library health snapshot
- Skills: 78 (target 70-90; healthy).
- Capability balance: balanced; no area exceeding 25% of total.
- Lifecycle: 72 active, 4 experimental, 2 deprecated (sunset Q1 2027).
- Memory volume: +15% vs Q3 (mostly episodic; reconciliation recommended).

## Findings from factory-evaluation
- skill X: trigger recall 0.78 (target 0.90); 4 contexts where it should fire didn't.
- skill Y: zero invocations for 3 quarters; sunset candidate.
- skill Z + skill W: 40% overlap in trigger contexts; consolidation candidate.
- pattern P: used in 5 projects this quarter; promotion candidate.
- 12 references stale > 6 months.

## Proposals

### P1: Tune trigger phrases on skill X
- Change: add 4 trigger phrases (see appendix).
- Evidence: 4 contexts in 2026 Q3-Q4 where skill X should have fired (sampled).
- Risk: low; trigger additions; no behavior change.
- Recommendation: APPROVE.

### P2: Deprecate skill Y
- Change: move skill Y to deprecated state; sunset 2027 Q1.
- Evidence: 0 invocations 3 quarters; functionality subsumed by skill Y'.
- Risk: low; deprecation period preserves access.
- Recommendation: APPROVE.

### P3: Consolidate skill Z + skill W → skill ZW
- Change: merge Z and W into ZW; deprecate Z and W.
- Evidence: 40% trigger overlap; reviewers report confusion in 6 projects.
- Risk: medium; consolidation can lose nuance. Propose experimental branch + measurement.
- Recommendation: APPROVE with experimental phase.

### P4: Promote pattern P to skill
- Change: write SKILL.md for P; retain pattern as example.
- Evidence: 5 projects used in Q4; cross-cutting; substantive.
- Counter: pattern remains useful even after skill exists; preserves growth-via-pattern path.
- Recommendation: APPROVE.

### P5: Reconcile stale references
- Change: 12 references refreshed against current tool versions.
- Evidence: factory-evaluation drift report.
- Risk: low; updates only.
- Recommendation: APPROVE.

## Memory recommendation
- Episodic memory growth pattern suggests reconciliation per `memory-management`. Recommend triggering reconciliation across projects this quarter.

## Items NOT proposed (deliberately)
- skill A: principal mentioned dissatisfaction in Q3 retro, but factory-eval shows skill A is invoked correctly and outputs are accepted. Concern is project-specific; not a library issue.
- skill B: invocation declining for 1 quarter; too early to act. Continue monitoring.

## Cumulative library impact this quarter
- Skill count: 78 → 76 (Z + W → ZW; Y deprecated; P added → net -2).
- Trigger phrase count: +4 (on skill X).
- References: 12 refreshed (net 0; no new).
- Memory: reconciliation in flight; 18% volume reduction expected post-reconcile.

## Evidence pack (for governance)
- Per-proposal evidence files at `.project/operational/library-evolution/2026-q4/`.
- Before-after metric projections for P3.
- Rollback plan per change.
```
