# ETL Contract Probe: Advisory Mode Policy

**Date**: 2026-02-04
**Author**: Release Engineering
**Status**: Active
**Issue Reference**: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/issues/143

## Summary

The ETL Contract Probe CI job (`ETL Contract Probe (Staging ACA)`) operates in **ADVISORY mode** and is **non-blocking for PR merges**.

## Scope

The probe validates staging Azure Container Apps (ACA) backend infrastructure:
- `/api/v1/meta/version`
- `/healthz`
- `/readyz`
- `/api/v1/incidents`
- `/api/v1/complaints/`
- `/api/v1/investigations`

## Why Non-Blocking

| Reason | Explanation |
|--------|-------------|
| **Infrastructure vs Code** | Validates staging infrastructure availability, not PR code correctness |
| **External Dependencies** | Staging ACA may be temporarily unavailable during deployments/maintenance |
| **Transient Failures** | Network timeouts or cold starts cause spurious failures |
| **CI Scope** | PR CI should validate code quality, not infrastructure state |

## Enforcement Modes

```
VERIFIED    = Staging reachable + all 6+ contract checks pass
DEGRADED    = Staging reachable + critical pass, non-critical fail
UNAVAILABLE = Staging unreachable (NOT validated)
FAILED      = Staging reachable but critical checks failed
```

**In ADVISORY mode**: Only `FAILED` outcome with 4+ critical failures is flagged — but still non-blocking.

## When to Investigate

1. Multiple consecutive PRs show `FAILED` status
2. Production deployment is planned
3. Infrastructure changes affect the endpoints

## CI Run Evidence (PR #142)

- Run ID: 21670787179
- Job: ETL Contract Probe (Staging ACA)
- Outcome: `FAILED` (4 critical failures)
- Root Cause: Staging ACA infrastructure endpoints not responding
- Impact: **None** — advisory mode, PR merge not blocked
- Action: Documented in issue #143

## Related PRs

- PR #142: Stage 1 API exposure endpoints + governance hygiene for this policy
