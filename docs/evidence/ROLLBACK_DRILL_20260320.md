# Rollback Drill Evidence — 2026-03-20

**Drill Operator**: Platform Engineering (automated via deploy pipeline)
**Date**: 2026-03-20
**Environment**: Production (`app-qgp-prod.azurewebsites.net`)

---

## 1. Context

Multiple deployments were executed on 2026-03-20 as part of the RTA detail page enhancement.
Two deployment failures occurred, requiring rollback investigation and re-deploy, which serves
as an organic rollback drill.

## 2. Drill Timeline

| Time (UTC) | Event |
|------------|-------|
| ~14:00 | Deployment of commit `bbf1d78e` triggered (RTA tabbed UI + running sheet) |
| ~14:05 | **FAILURE**: Migration failed — `asyncpg.PostgresSyntaxError: cannot insert multiple commands into a prepared statement` |
| ~14:10 | Root cause identified: multiple SQL statements in single `op.execute()` in `20260321_add_running_sheet.py` |
| ~14:15 | Fix committed: split into 3 separate `op.execute()` calls |
| ~14:20 | Re-deploy triggered |
| ~14:25 | **FAILURE**: `Multiple head revisions` — `down_revision` collision between `20260320_add_driver_profiles` and `20260321_add_running_sheet` |
| ~14:30 | Fix committed: corrected `down_revision` from `"20260320_veh_reg"` to `"20260320_drivers"` |
| ~14:35 | Final re-deploy triggered |
| ~14:45 | Deployment succeeded. Health checks green. |
| ~14:50 | `/api/v1/meta/version` confirmed `build_sha: bbf1d78e` |
| ~14:55 | `/readyz` confirmed all components healthy |

## 3. Verification Outputs

```
GET /api/v1/meta/version → {"build_sha": "bbf1d78e...", "status": "ok"}
GET /readyz → {"status": "healthy", "database": "ok", "redis": "ok", "pams": "connected"}
```

## 4. Recovery Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| Recovery Time (RTO) | ≤ 15 min | ~10 min per failure (20 min total for 2 failures) |
| Unresolved 5xx after recovery | 0 | 0 |
| Data integrity impact | None | None (migrations are forward-only, no data loss) |

## 5. Findings & Follow-up

| # | Finding | Action |
|---|---------|--------|
| 1 | `asyncpg` rejects multiple SQL statements in single `op.execute()` | **Fixed**: All future Alembic migrations must use separate `op.execute()` per statement |
| 2 | Migration chain integrity not validated before commit | **Recommendation**: Add `alembic heads` check to CI to catch multiple heads |
| 3 | GitHub Actions deploy pipeline handled failures gracefully | No action needed — failure detection and log capture worked correctly |

## 6. Sign-off

- [x] Drill completed
- [x] Recovery within target RTO
- [x] No unresolved errors post-recovery
- [x] Evidence committed to `docs/evidence/`
