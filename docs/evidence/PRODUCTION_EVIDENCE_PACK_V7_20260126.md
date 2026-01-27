# Production Evidence Pack v7

**Release:** Investigations Create-from-Record with Duplicate Prevention
**Date:** 2026-01-26
**Release Captain:** Cursor.ai + Operator
**Status:** IN PROGRESS

---

## A) Merge Evidence

| Field | Value |
|-------|-------|
| PR | [#88](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/88) |
| State | ✓ MERGED |
| Merge SHA | `a9652cc4d8d20a268d366cc8fab88f2382f55834` |
| Merged At | 2026-01-26T23:27:52Z |
| CI Run | [21377757358](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/21377757358) |

### CI Job Summary (All Green)
| Job | Status | Duration |
|-----|--------|----------|
| ADR-0002 Fail-Fast Proof | ✓ SUCCESS | 42s |
| Build Check | ✓ SUCCESS | 39s |
| Build and Deploy Job | ✓ SUCCESS | 1m13s |
| CI Security Covenant | ✓ SUCCESS | 6s |
| Code Quality | ✓ SUCCESS | 55s |
| Code Security Analysis | ✓ SUCCESS | 16s |
| CodeQL (JS) | ✓ SUCCESS | 1m20s |
| CodeQL (Python) | ✓ SUCCESS | 1m21s |
| Dependency Vulnerability Check | ✓ SUCCESS | 48s |
| Integration Tests | ✓ SUCCESS | 1m26s |
| OpenAPI Contract Stability | ✓ SUCCESS | 43s |
| Secret Detection | ✓ SUCCESS | 6s |
| Security Scan | ✓ SUCCESS | 43s |
| Security Tests | ✓ SUCCESS | 48s |
| Smoke Tests (CRITICAL) | ✓ SUCCESS | 1m19s |
| End-to-End Tests | ✓ SUCCESS | 1m10s |
| UAT Tests | ✓ SUCCESS | 1m43s |
| Unit Tests | ✓ SUCCESS | 1m1s |
| Workflow Lint | ✓ SUCCESS | 36s |
| All Checks Passed | ✓ SUCCESS | 7s |

---

## B) Production Preflight — Duplicate Detection (BLOCKER)

**Query Executed:**
```sql
SELECT 
    assigned_entity_type, 
    assigned_entity_id, 
    COUNT(*) AS cnt
FROM investigation_runs
GROUP BY assigned_entity_type, assigned_entity_id
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 50;
```

**Result:**
```
[ OPERATOR: Execute query and paste result here ]

Expected: 0 rows returned
```

**Preflight Status:** [ ] PASS (0 rows) / [ ] FAIL (duplicates exist)

**Executed By:** _______________
**Executed At:** _______________

### If Duplicates Exist (STOP CONDITION)
If any rows returned, DO NOT proceed with migration. Execute remediation:
1. Identify canonical record per (assigned_entity_type, assigned_entity_id)
2. Archive duplicates to `investigation_runs_archive`
3. Delete duplicates
4. Re-run preflight query
5. Confirm 0 rows before proceeding

---

## C) Migration Evidence (ADR-0001)

### Migration File
- **Filename:** `alembic/versions/20260126_investigation_unique_source_constraint.py`
- **Revision ID:** `20260126_inv_unique_src`
- **Depends On:** `20260126_stage2_inv`

### Alembic Upgrade Output
```
[ OPERATOR: Run `alembic upgrade head` and paste output here ]

Command: alembic upgrade head
Executed At: _______________
```

### Alembic Current
```
[ OPERATOR: Run `alembic current` and paste output here ]

Expected: 20260126_inv_unique_src (head)
```

### Index Verification
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'investigation_runs'
  AND indexname = 'uq_investigation_runs_source';
```

**Result:**
```
[ OPERATOR: Execute query and paste result here ]

Expected:
indexname                  | indexdef
---------------------------+-----------------------------------------------------------
uq_investigation_runs_source | CREATE UNIQUE INDEX uq_investigation_runs_source ON investigation_runs (assigned_entity_type, assigned_entity_id)
```

**Migration Status:** [ ] PASS / [ ] FAIL

---

## D) Deploy Identifiers

### Backend Deployment
| Field | Value |
|-------|-------|
| Image Tag/SHA | [ OPERATOR: Record container image SHA ] |
| Deployment Time | _______________  |
| Azure Container Instance | _______________  |
| Health Check URL | `/api/v1/health` |
| Health Check Status | [ ] 200 OK / [ ] FAIL |

### Frontend Deployment
| Field | Value |
|-------|-------|
| SWA Deployment ID | [ OPERATOR: Record SWA deployment ID ] |
| Deployment Time | _______________  |
| SWA URL | _______________  |
| Health Check Status | [ ] 200 OK / [ ] FAIL |

---

## E) Production Smoke Pack

**Smoke Test Timestamp:** _______________
**Environment:** Production

### Test 1: Create Investigation from Dropdown
| Source Type | Test Result | Investigation ID | Timestamp |
|-------------|-------------|------------------|-----------|
| near_miss | [ ] PASS / [ ] FAIL | _______________ | _______________ |
| road_traffic_collision | [ ] PASS / [ ] FAIL | _______________ | _______________ |
| complaint | [ ] PASS / [ ] FAIL | _______________ | _______________ |
| reporting_incident | [ ] PASS / [ ] FAIL | _______________ | _______________ |

### Test 2: Duplicate Prevention (409)
| Source Type | Attempt | Expected | Actual | PASS/FAIL |
|-------------|---------|----------|--------|-----------|
| near_miss | Duplicate create | 409 INV_ALREADY_EXISTS | _______________ | [ ] |
| road_traffic_collision | Duplicate create | 409 INV_ALREADY_EXISTS | _______________ | [ ] |

**UI shows "Open existing investigation" link:** [ ] YES / [ ] NO

### Test 3: RTA Page Resilience
| Test | Expected | Actual | PASS/FAIL |
|------|----------|--------|-----------|
| RTA list loads | Page renders, no spinner | _______________ | [ ] |
| Force error (disconnect network) | Retry button appears | _______________ | [ ] |
| Click retry | Page reloads | _______________ | [ ] |

### Test 4: Telemetry Quarantine
| Check | Expected | Actual | PASS/FAIL |
|-------|----------|--------|-----------|
| Network tab: telemetry requests | 0 requests | _______________ | [ ] |
| Console: telemetry logs | 0 logs (no spam) | _______________ | [ ] |

**TELEMETRY_ENABLED:** `false` (quarantined per ADR-0004)

---

## F) Monitoring Window (60 minutes)

**Window Start:** _______________
**Window End:** _______________

### Metrics Thresholds
| Metric | Threshold | Actual | Status |
|--------|-----------|--------|--------|
| 5xx Error Rate | < 1% | _______________% | [ ] PASS / [ ] BREACH |
| p95 Latency (investigations) | < 500ms | _______________ms | [ ] PASS / [ ] BREACH |
| Storage Errors | 0 elevated | _______________ | [ ] PASS / [ ] BREACH |
| Auth Errors | 0 elevated | _______________ | [ ] PASS / [ ] BREACH |

### Key Endpoint Latencies
| Endpoint | p50 | p95 | p99 | Status |
|----------|-----|-----|-----|--------|
| POST /investigations/from-record | ___ms | ___ms | ___ms | [ ] |
| GET /investigations/source-records | ___ms | ___ms | ___ms | [ ] |
| GET /investigations | ___ms | ___ms | ___ms | [ ] |

### Monitoring Evidence
```
[ OPERATOR: Paste Azure Monitor / Application Insights snapshot here ]
```

### Rollback Triggered?
[ ] NO — All thresholds met
[ ] YES — Rollback executed (see Rollback Evidence below)

---

## G) Final GO/NO-GO

### Checklist
| Gate | Status |
|------|--------|
| PR merged | ✓ |
| Preflight: 0 duplicates | [ ] |
| Migration applied | [ ] |
| Index exists | [ ] |
| Backend deployed + healthy | [ ] |
| Frontend deployed + healthy | [ ] |
| Smoke: Create investigation | [ ] |
| Smoke: 409 duplicate prevention | [ ] |
| Smoke: RTA resilience | [ ] |
| Smoke: Telemetry quarantine | [ ] |
| Monitoring: 5xx < 1% | [ ] |
| Monitoring: p95 < 500ms | [ ] |

### Decision

**[ ] GO FOR PRODUCTION** — All gates passed

**[ ] NO-GO** — Gate(s) failed: _______________

---

## Signatures

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Release Captain | _______________ | _______________ | _______________ |
| SRE On-Call | _______________ | _______________ | _______________ |
| QA Lead | _______________ | _______________ | _______________ |

---

## Appendix: Rollback Procedure

If any gate fails, execute rollback:

1. **Backend Rollback:**
   ```bash
   az container restart --name qgp-api --resource-group qgp-prod
   # OR deploy previous image tag
   ```

2. **Migration Rollback:**
   ```bash
   alembic downgrade -1
   # Verify: alembic current should show 20260126_stage2_inv
   ```

3. **Frontend Rollback:**
   - SWA automatically has previous deployments
   - Or redeploy from previous main SHA

4. **Notify:**
   - Post in #releases channel
   - Page on-call if needed

---

## Appendix: Files Changed in This Release

### Backend
- `src/api/routes/investigations.py`
- `src/api/schemas/investigation.py`

### Migration
- `alembic/versions/20260126_investigation_unique_source_constraint.py`

### Frontend
- `frontend/src/api/client.ts`
- `frontend/src/pages/Investigations.tsx`
- `frontend/src/pages/RTAs.tsx`
- `frontend/src/pages/RTADetail.tsx`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/ComplaintDetail.tsx`
- `frontend/src/services/telemetry.ts`

### Documentation
- `docs/adr/ADR-0004-TELEMETRY-CORS-QUARANTINE.md`

### Tests
- `tests/integration/test_investigation_from_record.py`
- `tests/integration/test_source_records_endpoint.py`
- `tests/unit/test_telemetry_resilience.py`
