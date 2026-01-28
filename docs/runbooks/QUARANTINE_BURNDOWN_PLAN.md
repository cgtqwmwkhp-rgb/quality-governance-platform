# Quarantine Burn-down Plan

## Current State (Post-Wave 1, 2026-01-28)

| Metric | Value | Change |
|--------|-------|--------|
| Quarantined files (tracked) | 9 | +1 (was untracked) |
| Quarantined files (untracked) | 0 | -2 (1 deleted, 1 tracked) |
| Total quarantined tests | 183 | No change |
| Next expiry | 2026-02-21 (24 days) | - |

## Wave 1 Outcome

Wave 1 achieved **governance improvement** but no test reduction:
- ✅ Deleted empty stub file (governance cleanup)
- ✅ Added GOVPLAT-005 (previously untracked → now tracked)
- ❌ Test re-enablement blocked by async event loop conflict

**Key Finding**: All 9 quarantined files suffer from the same root cause:
```
RuntimeError: Task got Future attached to a different loop
```
This requires Phase 3 Async Test Architecture Fix before any tests can be re-enabled.

## Revised Burn-down Targets

| Phase | Target Reduction | Cumulative Target | Method |
|-------|------------------|-------------------|--------|
| Phase 3 | -53 tests | 130 remaining | Async test architecture fix (GOVPLAT-003/004/005) |
| Wave 2 | -30 tests | 100 remaining | Contract alignment (GOVPLAT-002 partial) |
| Wave 3 | -30 tests | 70 remaining | More contract fixes |
| Wave 4 | -70 tests | 0 remaining | Feature completion (GOVPLAT-001) |

**Target**: Reduce from 183 to <60 tests by expiry date (2026-02-21).

## Enforcement Rules

### Rule 1: No Untracked Quarantines
- Every skip must be in `QUARANTINE_POLICY.yaml`
- Plain `@pytest.mark.skip` without quarantine annotation FAILS CI
- Already enforced via `scripts/report_test_quarantine.py`

### Rule 2: Budget Cap
- Current max: 8 files (in policy)
- New quarantines require:
  - `approved_override: true` in YAML entry
  - Justification with issue_id
  - Offset: must remove equal or greater number first
- If quarantine count increases without override → CI FAILS

### Rule 3: Expiry Enforcement
- Expired quarantines FAIL CI (already enforced)
- 7-day warning in quarantine report output
- Expiring quarantines with no scheduled fix → release risk flag

### Rule 4: Weekly Trend Check (NEW)
- Compare current week's count to previous week
- If count increases without `approved_override` → CI FAILS
- Track in `metrics.weekly_trend` in YAML

## Wave Selection Criteria

1. **ROI Score** = (tests_regained × confidence) / code_changes_required
2. Prioritize:
   - Highest test count
   - Simplest root cause
   - Already-fixed issues (e.g., AsyncSession.query fixed in PR #103)
   - Smallest code touch

## Review Schedule

- **Weekly**: Review quarantine report, update burn-down progress
- **Before expiry**: All quarantines must be either fixed or explicitly extended with justification
- **No silent extensions**: Extensions require documented reason and new expiry

## Owners

| Issue ID | Owner | Backup |
|----------|-------|--------|
| GOVPLAT-001 | platform-team | @lead |
| GOVPLAT-002 | platform-team | @lead |
| GOVPLAT-003 | platform-team | @lead |
| GOVPLAT-004 | platform-team | @lead |
