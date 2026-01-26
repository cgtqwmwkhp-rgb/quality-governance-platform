# UX Functional Coverage Report

**Generated:** 2026-01-26T10:29:42.763Z
**Score:** 80/100
**Status:** HOLD

## Summary

| Metric | Value |
|--------|-------|
| Total Passed | 0 |
| Total Failed | 3 |
| Total Skipped | 0 |
| P0 Failures | 2 |
| P1 Failures | 2 |
| P2 Failures | 0 |
| Dead Ends | 2 |

## Readiness

| Environment | Ready |
|-------------|-------|
| Staging | ❌ |
| Canary | ❌ |
| Production | ❌ |

## Audit Results

### Page Load Audit

- Passed: 0
- Failed: 1
- Skipped: 0

### Link Audit

- Total Links: 0
- Valid: 0
- Dead: 1
- External: 0

### Button Wiring Audit

- Passed: 0
- Failed: 1
- Skipped: 0
- Noop Buttons: 0

### Workflow Audit

- Passed: 0
- Failed: 1
- Skipped: 0
- Dead Ends: 1

## Failures

| Type | ID | Criticality | Error |
|------|----|--------------| ----- |
| page | policies | P1 | page.evaluate: SecurityError: Failed to read the ' |
| button | portal-home::navigate-to-report | P0 | page.evaluate: SecurityError: Failed to read the ' |
| workflow | portal-incident-report | P0 | page.evaluate: SecurityError: Failed to read the ' |

## Thresholds

| Level | Min Score | Max P0 | Max P1 |
|-------|-----------|--------|--------|
| Staging Ready | 85 | 0 | - |
| Canary Expand | 90 | 0 | 3 |
| Prod Promote | 95 | 0 | 1 |

---

*PII-Safe: No personally identifiable information captured in this report.*