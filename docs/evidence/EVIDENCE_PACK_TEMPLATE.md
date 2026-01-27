# Evidence Pack Template

## Purpose

This template defines the mandatory evidence required for every production release. All items must be present and verified before merge.

---

## 1. PR Details

| Field | Value |
|-------|-------|
| PR Number | #___ |
| PR Title | |
| Merge Commit | |
| Merged At (UTC) | |
| Author | |

---

## 2. CI Run Evidence

### Primary CI Run

| Field | Value |
|-------|-------|
| Run ID | |
| Run URL | |
| Status | PASS / FAIL |

### Required Job Status

| Job | Status | Duration | Notes |
|-----|--------|----------|-------|
| Code Quality | ✅/❌ | | Must include Mock Gate |
| Unit Tests | ✅/❌ | | |
| Integration Tests | ✅/❌ | | Must show Postgres proof |
| E2E Tests | ✅/❌ | | |
| UAT Tests | ✅/❌ | | |
| Smoke Tests (CRITICAL) | ✅/❌ | | |
| Security Scan | ✅/❌ | | |
| ADR-0002 Fail-Fast Proof | ✅/❌ | | **MANDATORY** |
| All Checks Passed | ✅/❌ | | |

---

## 3. PostgreSQL + Migration Proof (ADR-0001)

### Integration Tests Job Excerpt

```
# Paste excerpt from Integration Tests job showing:
# 1. PostgreSQL container initialization
# 2. Alembic upgrade chain
# 3. Test execution against real database

Example:
Initialize containers: success
Run Alembic migrations: 
  - Applying 20260104_initial_schema...
  - Applying 20260120_add_uvdb_achilles...
  - Applying 20260126_investigation_enhancements...
  - All migrations applied successfully
Run integration tests: 45 passed, 0 failed
```

### Verification

- [ ] PostgreSQL container initialized (not SQLite)
- [ ] `alembic upgrade head` completed successfully
- [ ] All migrations applied without errors
- [ ] Integration tests passed against real Postgres

---

## 4. ADR-0002 Fail-Fast Proof

### Job Status

| Field | Value |
|-------|-------|
| Job Name | ADR-0002 Fail-Fast Proof |
| Status | ✅ PASS / ❌ FAIL |
| Duration | |

### Verification

- [ ] Job explicitly ran (not skipped)
- [ ] Fail-fast validation passed
- [ ] No placeholder secrets detected
- [ ] No localhost database references

---

## 5. Mock Data Eradication Gate

### Gate Output

```
# Paste mock gate output from Code Quality job

Example:
[PASS] No mock data patterns detected in scoped files.
```

### Scoped Files Verified

- [ ] frontend/src/pages/Actions.tsx (PR1)
- [ ] frontend/src/pages/PlanetMark.tsx (PR2)
- [ ] frontend/src/pages/UVDBAudits.tsx (PR2)
- [ ] frontend/src/pages/Standards.tsx (PR3)
- [ ] frontend/src/pages/ComplianceEvidence.tsx (PR3)

---

## 6. Security Evidence

### Security Scan Job

| Check | Status |
|-------|--------|
| Safety (dependency vulnerabilities) | ✅/❌ |
| Bandit (code security) | ✅/❌ |
| Secret Detection | ✅/❌ |
| CodeQL Analysis | ✅/❌ |

---

## 7. Test Summary

| Test Type | Passed | Failed | Skipped | Coverage |
|-----------|--------|--------|---------|----------|
| Unit | | | | |
| Integration | | | | |
| E2E | | | | |
| UAT | | | | |
| Smoke | | | | |

---

## 8. Rollback Plan

### Rollback Method

- [ ] Git revert (recommended)
- [ ] Feature flag disable
- [ ] Manual hotfix

### Rollback Verification

- [ ] Mock gate will pass after rollback
- [ ] No mock data reintroduced
- [ ] Runbook reviewed: `docs/runbooks/[MODULE]_ROLLBACK.md`

---

## 9. Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Engineer | | | |
| Reviewer | | | |
| QA (if applicable) | | | |

---

## Template Version

- Version: 1.0
- Last Updated: 2026-01-27
- Introduced in: PR #99

---

## Quick Checklist

Before merging, verify ALL of the following:

- [ ] CI Run ID recorded
- [ ] All required jobs GREEN
- [ ] PostgreSQL + Migration proof captured
- [ ] ADR-0002 proof job explicitly passed
- [ ] Mock gate output shows PASS
- [ ] Security scans clean
- [ ] Rollback plan documented and mock-safe
