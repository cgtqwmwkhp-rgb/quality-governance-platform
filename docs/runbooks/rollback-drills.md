# Rollback Drill Log (D05 / D23)

**Owner**: Platform Engineering
**Last Updated**: 2026-04-03
**Review Cycle**: Quarterly

---

## Purpose

This document records the results of production rollback drills, verifying that the rollback procedure documented in [`docs/runbooks/rollback.md`](rollback.md) functions correctly.

---

## Drill History

| # | Date | Type | Duration | Result | Operator | Notes |
|---|------|------|----------|--------|----------|-------|
| 1 | 2026-03-15 | Production slot swap rollback | 8 seconds | Successful | Platform Eng | Full slot swap via `az webapp deployment slot swap`; verified health endpoints post-swap. See [`docs/evidence/ROLLBACK_DRILL_20260320.md`](../evidence/ROLLBACK_DRILL_20260320.md). |
| 2 | 2026-03-20 | Audit module rollback drill | ~2 minutes | Successful | Platform Eng | Targeted rollback of audit module changes; verified via health checks and API smoke tests. See [`docs/runbooks/AUDIT_ROLLBACK_DRILL.md`](AUDIT_ROLLBACK_DRILL.md). |

## Database Point-in-Time Restore

| # | Date | Type | Duration | Result | Notes |
|---|------|------|----------|--------|-------|
| — | Planned: 2026-06-06 | PostgreSQL PITR | — | Not yet conducted | Staging environment, Azure PostgreSQL Flexible Server |

### PITR Drill Plan (2026-06-06)

**Objective**: Verify that Azure PostgreSQL Flexible Server point-in-time restore completes within the 30-minute RTO defined in SLOs.

**Pre-conditions**:
1. Staging database has at least 48 hours of continuous WAL history
2. Test data seeded with known row counts per table

**Steps**:
1. Record current row counts for `incidents`, `audit_runs`, `actions` tables
2. Insert 5 marker rows (`drill_marker_*`) into staging
3. Note the timestamp *before* marker insertion (T<sub>restore</sub>)
4. Trigger PITR via: `az postgres flexible-server restore --resource-group qgp-rg-staging --name psql-qgp-staging --source-server psql-qgp-staging --restore-point-in-time T_restore --target-name psql-qgp-staging-pitr`
5. Wait for restore to complete; record elapsed time
6. Connect to restored instance; verify marker rows are absent
7. Verify original row counts match
8. Run `/readyz` health check against staging pointed at restored DB
9. Record results in this file; clean up restored instance

**Success criteria**: Restore completes within 30 minutes; data integrity confirmed; no marker rows present

---

## Drill Schedule

| Drill Type | Frequency | Next Scheduled | Owner |
|------------|-----------|----------------|-------|
| Slot swap rollback | Quarterly | 2026-06-15 | Platform Eng |
| Database PITR | Semi-annually | 2026-Q2 | Platform Eng + DBA |
| Frontend rollback (SWA revert) | Quarterly | 2026-06-15 | Frontend Eng |

---

## Success Criteria

A rollback drill is considered successful when:

1. The rollback completes within the documented time window (slot swap: < 30s, DB PITR: < 30min)
2. Health endpoints (`/healthz`, `/readyz`) return 200 after rollback
3. A smoke test of critical API endpoints passes
4. No data loss is observed
5. Users experience < 30 seconds of downtime

---

## Related Documents

- [`docs/runbooks/rollback.md`](rollback.md) — rollback procedure
- [`docs/evidence/ROLLBACK_DRILL_20260320.md`](../evidence/ROLLBACK_DRILL_20260320.md) — drill evidence
- [`docs/evidence/chaos-testing-plan.md`](../evidence/chaos-testing-plan.md) — chaos testing plan
- [`.github/workflows/rollback-production.yml`](../../.github/workflows/rollback-production.yml) — automated rollback workflow
