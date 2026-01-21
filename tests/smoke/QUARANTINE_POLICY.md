# Smoke Test Quarantine Policy

## Purpose
This document tracks tests that are temporarily quarantined due to incomplete features or test harness parity issues. Quarantined tests are skipped in CI but tracked for resolution.

## Quarantine Rules
1. All quarantined tests MUST have an issue/ticket linked
2. Quarantine expiry date MUST be set (max 30 days)
3. Reason for quarantine MUST be documented
4. Tests MUST be reviewed before expiry

---

## Currently Quarantined Tests

### File: `test_phase3_phase4_smoke.py`
- **Quarantine Date:** 2026-01-21
- **Expiry Date:** 2026-02-21
- **Issue:** GOVPLAT-001 (Phase 3/4 features incomplete)
- **Reason:** Phase 3 (Workflow Center) and Phase 4 (Compliance Automation) features are not fully implemented. Tests assert on endpoint contracts that don't exist yet.
- **Affected Test Classes:**
  - `TestWorkflowCenterSmoke` - endpoints `/api/workflows/templates`, `/instances`, `/approvals/pending`, `/delegations`, `/stats`, `/start` have contract mismatches
  - `TestComplianceAutomationSmoke` - endpoints `/api/compliance-automation/*` have contract mismatches  
  - `TestFrontendPagesSmoke` - requires running frontend
  - `TestIntegrationSmoke` - requires all Phase 3/4 endpoints working
  - `TestDataIntegritySmoke` - requires seed data not present
- **Resolution Plan:** 
  1. Align test contracts with actual endpoint implementations
  2. Add required seed data to test fixtures
  3. Remove quarantine when Phase 3/4 feature development complete

---

## Active Smoke Tests (MUST PASS)

These tests are NOT quarantined and MUST pass for CI to be green:

### File: `test_enterprise_smoke.py`
- `TestHealthSmoke` - Infrastructure health checks (CRITICAL)
- `TestAuthSmoke` - Authentication flow verification
- `TestPortalSmoke` - Portal endpoint availability
- `TestSecuritySmoke` - Security configuration checks
- `TestRateLimitingSmoke` - Rate limiting headers
- `test_smoke_test_summary` - Summary verification

---

## Review Schedule
- **Weekly:** Review quarantined tests for resolution progress
- **At Expiry:** Tests MUST be either fixed or re-quarantined with justification

## Metrics
- Total quarantined: 1 file (37 tests)
- Active smoke tests: 35 tests
- Pass rate target: 100% of non-quarantined tests
