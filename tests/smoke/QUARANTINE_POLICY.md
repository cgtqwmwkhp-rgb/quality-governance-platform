# Test Quarantine Policy

## Purpose
This document tracks tests that are temporarily quarantined due to incomplete features or test harness parity issues. Quarantined tests are skipped in CI but tracked for resolution.

## Quarantine Rules
1. All quarantined tests MUST have an issue/ticket linked
2. Quarantine expiry date MUST be set (max 30 days)
3. Reason for quarantine MUST be documented
4. Tests MUST be reviewed before expiry

---

## Currently Quarantined Tests

### GOVPLAT-001: Phase 3/4 Features Incomplete

**Smoke Tests:**
- **File:** `tests/smoke/test_phase3_phase4_smoke.py`
- **Quarantine Date:** 2026-01-21
- **Expiry Date:** 2026-03-23 (extended from 2026-02-21)
- **Reason:** Phase 3 (Workflow Center) and Phase 4 (Compliance Automation) features are not fully implemented. Tests assert on endpoint contracts that don't exist yet.

**E2E Tests:**
- **File:** `tests/e2e/test_workflows.py`
  - All workflow automation E2E tests (Phase 3)
- **File:** `tests/e2e/test_compliance_automation.py`
  - All compliance automation E2E tests (Phase 4)

**Resolution Plan:**
1. Complete Phase 3/4 endpoint implementations
2. Align test contracts with actual implementations
3. Remove quarantine markers

---

### GOVPLAT-002: E2E API Contract Mismatch

**E2E Tests:**
- **File:** `tests/e2e/test_portal_e2e.py`
  - Tests expect `/api/portal/report` but actual endpoint is `/api/portal/reports/`
- **File:** `tests/e2e/test_enterprise_e2e.py`
  - Enterprise journey tests hit endpoints returning 404
- **File:** `tests/e2e/test_full_workflow.py`
  - Full workflow tests hit endpoints returning 404

**Quarantine Date:** 2026-01-21
**Expiry Date:** 2026-03-23 (extended from 2026-02-21)

**Resolution Plan:**
1. Audit actual API endpoints vs test expectations
2. Update tests to match actual API contracts
3. Add missing endpoints if required by specifications
4. Remove quarantine markers

---

## Active Tests (MUST PASS)

### Smoke Tests: `tests/smoke/test_enterprise_smoke.py`
- `TestHealthSmoke` - Infrastructure health checks (CRITICAL)
- `TestAuthSmoke` - Authentication flow verification
- `TestPortalSmoke` - Portal endpoint availability
- `TestSecuritySmoke` - Security configuration checks
- `TestRateLimitingSmoke` - Rate limiting headers
- `test_smoke_test_summary` - Summary verification

### E2E Tests: `tests/e2e/test_admin_e2e.py`
- Admin panel E2E tests (if not quarantined)

### Unit Tests: `tests/unit/*`
- All unit tests with skip_on_import_error decorators

### Integration Tests: `tests/integration/*`
- All integration tests against Postgres

---

## Review Schedule
- **Weekly:** Review quarantined tests for resolution progress
- **At Expiry:** Tests MUST be either fixed or re-quarantined with justification

## Metrics
- Total quarantined files: 6
- Active test suites: Unit, Integration, Smoke (core)
- Pass rate target: 100% of non-quarantined tests
