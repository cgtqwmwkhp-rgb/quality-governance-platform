# Quarantine Burn-down Plan

## Current State (2026-01-28)

| Metric | Value |
|--------|-------|
| Quarantined files (tracked) | 8 |
| Quarantined files (untracked) | 2 |
| Total quarantined tests | 183 |
| Next expiry | 2026-02-21 (24 days) |

## Burn-down Targets

| Week | Target Reduction | Cumulative Target | Method |
|------|------------------|-------------------|--------|
| Week 1 | -35 tests | 148 remaining | Wave 1: async fixes, delete stubs |
| Week 2 | -30 tests | 118 remaining | Wave 2: contract alignment |
| Week 3 | -30 tests | 88 remaining | Wave 3: missing feature tests |
| Week 4 | -30 tests | 58 remaining | Wave 4: final push |

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
