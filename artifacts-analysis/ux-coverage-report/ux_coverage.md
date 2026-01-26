# UX Functional Coverage Report

**Generated:** 2026-01-26T10:08:41.006Z
**Score:** 70/100
**Status:** HOLD

## Summary

| Metric | Value |
|--------|-------|
| Total Passed | 0 |
| Total Failed | 6 |
| Total Skipped | 0 |
| P0 Failures | 4 |
| P1 Failures | 3 |
| P2 Failures | 0 |
| Dead Ends | 3 |

## Readiness

| Environment | Ready |
|-------------|-------|
| Staging | ❌ |
| Canary | ❌ |
| Production | ❌ |

## Audit Results

### Page Load Audit

- Passed: 0
- Failed: 2
- Skipped: 0

### Link Audit

- Total Links: 0
- Valid: 0
- Dead: 1
- External: 0

### Button Wiring Audit

- Passed: 0
- Failed: 2
- Skipped: 0
- Noop Buttons: 0

### Workflow Audit

- Passed: 0
- Failed: 2
- Skipped: 0
- Dead Ends: 2

## Failures

| Type | ID | Criticality | Error |
|------|----|--------------| ----- |
| page | policies | P1 | Test is skipped: Auth type jwt_admin not configure |
| page | policies | P1 | Test is skipped: Auth type jwt_admin not configure |
| button | portal-home::navigate-to-report | P0 | Test is skipped: Auth not configured |
| button | portal-home::navigate-to-report | P0 | Test is skipped: Auth not configured |
| workflow | portal-incident-report | P0 | Test is skipped: Auth type portal_sso not configur |
| workflow | portal-incident-report | P0 | Test is skipped: Auth type portal_sso not configur |

## Thresholds

| Level | Min Score | Max P0 | Max P1 |
|-------|-----------|--------|--------|
| Staging Ready | 85 | 0 | - |
| Canary Expand | 90 | 0 | 3 |
| Prod Promote | 95 | 0 | 1 |

---

*PII-Safe: No personally identifiable information captured in this report.*