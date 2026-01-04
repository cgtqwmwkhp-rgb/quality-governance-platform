# Stage 1.1 Acceptance Pack

**Stage**: 1.1 - Release Rehearsal + Governance Drift Prevention  
**Date**: 2026-01-04  
**Status**: ✅ COMPLETE  
**PR**: #4 - https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/4

---

## Executive Summary

Stage 1.1 adds two critical production-readiness capabilities:

1. **Governance Drift Prevention**: Machine-checkable validation that branch protection settings remain fresh and coupled to CI workflow changes
2. **Release Rehearsal**: End-to-end smoke testing in CI that verifies the application starts, connects to database, and responds to health checks

Both capabilities are integrated as blocking CI gates, ensuring continuous verification.

---

## Phase Completion Status

| Phase | Title | Status | Evidence |
|-------|-------|--------|----------|
| 0 | Governance Drift Prevention | ✅ Complete | STAGE1.1_PHASE0_REPORT.md |
| Gate 0 | Drift Prevention in CI | ✅ Passed | CI run 20696326646 |
| 1 | Release Rehearsal CI Job | ✅ Complete | STAGE1.1_PHASE1_REPORT.md |
| Gate 1 | Release Rehearsal Passing | ✅ Passed | CI run 20696513849 |
| 2 | Runbooks + Acceptance Pack | ✅ Complete | This document |
| Gate 2 | Final Verification | ✅ Passed | All evidence present, CI green |

---

## Deliverables

### Phase 0: Governance Drift Prevention

**Purpose**: Prevent branch protection settings from becoming stale or mismatched with CI requirements.

**Files Created**:
- `scripts/validate_branch_protection_drift.py` - Drift validator (checks snapshot freshness)
- `docs/GOVERNANCE_DRIFT_PREVENTION.md` - Operational documentation

**Files Modified**:
- `.github/workflows/ci.yml` - Added drift check to `branch-protection-proof` job

**Validation Rules**:
1. Snapshot file must exist
2. Snapshot must be <30 days old
3. Snapshot must include CI workflow hash
4. Snapshot hash must match current CI workflow

**Integration**: Runs as part of `branch-protection-proof` job, blocking gate in `all-checks`.

---

### Phase 1: Release Rehearsal

**Purpose**: Deterministic end-to-end smoke test verifying application operational readiness.

**Files Created**:
- None (CI job only)

**Files Modified**:
- `.github/workflows/ci.yml` - Added `release-rehearsal` job
- `src/main.py` - Fixed health endpoint registration (root level)
- `src/api/__init__.py` - Removed duplicate health router

**Release Rehearsal Steps**:
1. Start Postgres service container
2. Install dependencies
3. Create safe `.env` configuration
4. Run Alembic migrations
5. Start application in background
6. Verify `/healthz` returns 200 (liveness)
7. Verify `/readyz` returns 200 (readiness + DB check)
8. Confirm `X-Request-ID` header present
9. Perform API call to generate logs
10. Stop application cleanly

**Integration**: Blocking gate in `all-checks` dependency chain.

---

## CI Status

**Latest Run**: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/20696513849

**All Jobs Passing**:
- ✅ Code Quality
- ✅ Branch Protection Proof (Stage 1.0) - **includes drift prevention**
- ✅ ADR-0002 Fail-Fast Proof
- ✅ Unit Tests
- ✅ Integration Tests
- ✅ Security Scan
- ✅ Build Check
- ✅ Governance Evidence (Stage 0.7 Gate 1)
- ✅ **Release Rehearsal (Stage 1.1)** - NEW
- ✅ All Checks Passed

---

## Evidence Files

All evidence documented in `docs/evidence/`:
- `STAGE1.1_PHASE0_REPORT.md` - Phase 0 completion (drift prevention)
- `STAGE1.1_PHASE1_REPORT.md` - Phase 1 completion (release rehearsal)
- `STAGE1.1_ACCEPTANCE_PACK.md` - This document
- `STAGE1.1_CLOSEOUT_SUMMARY.md` - Final sign-off

---

## Runbook Updates

**File**: `docs/GOVERNANCE_DRIFT_PREVENTION.md`

Documents the drift prevention workflow:
- When to re-export branch protection settings
- How to update the snapshot
- What triggers drift detection
- How to resolve drift failures

**Integration with Existing Runbooks**:
- `docs/runbooks/DEPLOYMENT_CHECKLIST.md` - References drift prevention
- `docs/runbooks/DATABASE_MIGRATIONS.md` - No changes needed
- `docs/runbooks/APPLICATION_LIFECYCLE.md` - No changes needed
- `docs/runbooks/ROLLBACK_PROCEDURES.md` - No changes needed

---

## Files Changed Summary

### Created (5 files)
- `scripts/validate_branch_protection_drift.py`
- `docs/GOVERNANCE_DRIFT_PREVENTION.md`
- `docs/evidence/STAGE1.1_PHASE0_REPORT.md`
- `docs/evidence/STAGE1.1_PHASE1_REPORT.md`
- `docs/evidence/STAGE1.1_ACCEPTANCE_PACK.md`

### Modified (3 files)
- `.github/workflows/ci.yml` - Added drift check + release-rehearsal job
- `src/main.py` - Fixed health endpoint registration
- `src/api/__init__.py` - Removed duplicate health router

**Total**: 8 files

---

## Compliance Verification

✅ **No Assumptions**: All unknowns labeled, evidence-based decisions  
✅ **Release Governance First**: No new features, only governance/operational improvements  
✅ **Migrations**: N/A (no schema changes)  
✅ **CI Reproducible**: All checks green, deterministic  
✅ **No Secrets in Repo**: Only safe placeholders  
✅ **Clear Boundaries**: Layered architecture preserved  
✅ **Evidence-Led**: All changes documented with evidence

---

## Gate Status

| Gate | Requirement | Status | Evidence |
|------|-------------|--------|----------|
| Gate 0 | Drift prevention in CI | ✅ Passed | CI run 20696326646 |
| Gate 1 | Release rehearsal passing | ✅ Passed | CI run 20696513849 |
| Gate 2 | Acceptance pack complete | ✅ Passed | This document + CI green |

---

## Operational Impact

### Drift Prevention
- **Benefit**: Prevents governance evidence from becoming stale
- **Trigger**: Automatic on every CI run
- **Action Required**: Re-export snapshot if >30 days old or CI workflow changes
- **Documentation**: `docs/GOVERNANCE_DRIFT_PREVENTION.md`

### Release Rehearsal
- **Benefit**: Catches deployment issues before production
- **Trigger**: Automatic on every PR
- **Action Required**: None (automated)
- **Duration**: ~30 seconds per run

---

## Next Steps

1. **Merge PR #4** to `main` branch
2. **Verify** drift prevention and release rehearsal in subsequent PRs
3. **Monitor** CI run times (should remain <5 minutes total)
4. **Update** branch protection snapshot within 30 days or when CI changes

---

## Sign-Off

**Stage 1.1**: ✅ COMPLETE  
**All Gates**: ✅ PASSED  
**CI Status**: ✅ GREEN  
**Evidence**: ✅ DOCUMENTED  
**Ready for Merge**: ✅ YES

---

*This acceptance pack consolidates all evidence for Stage 1.1 completion. All gates passed, all evidence documented, CI green.*
