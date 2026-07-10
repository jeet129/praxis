# Technical Documentation — Worked Examples

Supporting templates for `technical-documentation/SKILL.md`. Pulled out here to keep the main skill file scannable; referenced by pointer from the relevant sections.

## Release notes — worked example

```markdown
# Release v4.7.0 — 2026-11-15

## Highlights
- [User-visible] New feature X.
- [Operations] Migration Y deployed (see runbook ABC).
- [Security] Auth library upgraded to patch CVE-2026-NNNN.

## Breaking changes
- API `GET /v1/foo` removes deprecated `legacy_id` field (deprecated 2026-09; sunset window expired).

## New
- {list}

## Changed
- {list}

## Deprecated
- {list}

## Fixed
- {list}

## Security
- {list}

## Operational notes
- Migration time estimated 15m; runs in pre-deploy window.
- Rollback procedure: revert to v4.6.x; no data migration to reverse.

## ADRs landed this release
- ADR-091 (state-machine for order lifecycle).
- ADR-092 (event bus partitioning by customer-tier).
```
