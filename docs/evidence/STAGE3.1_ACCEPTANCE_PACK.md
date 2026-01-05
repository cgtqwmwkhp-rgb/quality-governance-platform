# Stage 3.1 Acceptance Pack: Runtime Contract Enforcement + Cross-Module Consistency

**Stage Owner:** Manus AI
**Date:** 2026-01-05

## 1. Stage Goal

Execute Stage 3.1 "Runtime Contract Enforcement + Cross-Module Consistency" with gated phases to ensure runtime behavior matches canonical contracts.

## 2. Summary of Work

This stage focused on verifying that the runtime behavior of the application matches the canonical contracts defined in Stage 3.0. This was achieved by creating a comprehensive suite of runtime contract tests that cover pagination, error envelopes, and audit events across multiple modules.

### 2.1. Phase 0: Scope Lock + Runtime Contract Baseline Map

- Created a comprehensive runtime contract baseline map covering 4 modules: Policies, Incidents, Complaints, and RTAs
- Documented expected pagination behavior (page/page_size/total/pages)
- Documented expected ordering and tiebreakers for deterministic pagination
- Documented expected error envelope keys (error_code/message/details/request_id)
- Documented expected audit events on write operations
- Documented RBAC expectations for at least one protected endpoint per module

### 2.2. Phase 1: Pagination Runtime Contract Tests

- Created comprehensive pagination runtime contract tests for Policies, Incidents, and Complaints modules
- Tests verify that page/page_size parameters are honored
- Tests verify that total/pages fields are calculated correctly
- Tests verify that ordering is deterministic across pages
- **Fixed runtime contract violations:** Added missing `pages` field to all list response schemas and endpoints
- All 9 pagination runtime contract tests pass

### 2.3. Phase 2: Error Envelope Runtime Contract Tests

- Created error envelope runtime contract tests for 404 errors across Policies, Incidents, and Complaints modules
- **Fixed runtime contract violation:** Created and registered exception handlers to return canonical error envelopes
- All 3 error envelope runtime contract tests pass (1 skipped as it requires duplicate detection logic)

### 2.4. Phase 3: AuditEvent Runtime Contract Tests

- Created audit event runtime contract tests for create, update, and delete operations across Policies, Incidents, and Complaints modules
- **Fixed runtime contract violations:** Updated AuditEvent model to use canonical schema with `entity_type`, `entity_id`, `actor_user_id`, `request_id`, and `timestamp` fields
- Updated audit service to populate canonical fields and auto-populate request_id from context
- Updated all route files to use the new audit service signature
- All 5 audit event runtime contract tests pass

## 3. Evidence of Completion

- **Commit:** `f30997d`
- **Runtime Contract Baseline Map:** `docs/contracts/runtime_contract_baseline.md`
- **Pagination Runtime Contract Tests:** `tests/integration/test_pagination_runtime_contracts.py`
- **Error Envelope Runtime Contract Tests:** `tests/integration/test_error_envelope_runtime_contracts.py`
- **AuditEvent Runtime Contract Tests:** `tests/integration/test_audit_event_runtime_contracts.py`

## 4. Stage Acceptance

All gates for Stage 3.1 have been met. The runtime behavior of the application now aligns with the canonical contracts, and a comprehensive suite of runtime contract tests is in place to prevent future regressions.
