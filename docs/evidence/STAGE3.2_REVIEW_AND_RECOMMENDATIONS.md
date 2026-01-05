# Stage 3.2 Review and Recommendations

**Date:** 2026-01-05  
**Reviewer:** Manus AI  
**Status:** Phase 1 Complete, Phases 2-5 Pending

---

## Current State Assessment

### Phase 1: RBAC Deny-Path Contract Tests ✅ COMPLETE

**What Was Delivered:**
- Created `tests/integration/test_rbac_deny_path_runtime_contracts.py` with 4 deny-path tests covering all required endpoints
- Implemented RBAC enforcement infrastructure (`src/api/dependencies/security.py`)
- Applied RBAC enforcement to all 4 create endpoints (policies, incidents, complaints, rtas)
- Updated test fixtures to grant permissions to test users
- All tests pass locally and in CI

**Gate 1 Status:** ✅ **MET**
- All 4 deny-path tests pass with canonical envelopes + request_id
- Allow-path proof: existing integration tests continue to pass (users with permissions can create resources)

**Evidence:**
- PR #19: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/19
- CI Run: All checks passing (Code Quality, Unit Tests, Integration Tests, Security Scan, etc.)
- Test file: `tests/integration/test_rbac_deny_path_runtime_contracts.py`

---

## Remaining Work Assessment

### Phase 2: 409 Conflict (Duplicate reference_number) + Unskip ❌ NOT STARTED

**Current Situation:**
- Skipped test exists at `tests/integration/test_error_envelope_runtime_contracts.py:114`
- Skip reason: "Duplicate reference number detection not yet implemented"
- No duplicate detection logic exists in Policy create endpoint

**Required Work:**
1. Add duplicate reference_number check in `src/api/routes/policies.py::create_policy()`
2. Query database for existing policy with same reference_number
3. Return 409 with canonical error envelope if duplicate found
4. Unskip the test and verify it passes

**Complexity:** **LOW-MEDIUM**
- Simple database query + conditional check
- No schema changes required (reference_number field already exists)
- No migrations needed

**Estimated Effort:** 30-45 minutes

**Risks:**
- None significant - straightforward implementation

---

### Phase 3: Error Envelope Expansion (403/404/409) ✅ PARTIALLY COMPLETE

**Current Situation:**
- 404 error envelope tests exist and pass (`test_error_envelope_runtime_contracts.py`)
- 403 error envelope tests exist and pass (via Phase 1 RBAC deny-path tests)
- 409 error envelope test exists but is skipped (will be completed in Phase 2)

**Required Work:**
1. Verify all three error types (403/404/409) use canonical envelopes
2. Add explicit runtime assertions for error_code stability ("403", "404", "409")
3. Ensure request_id is always present in all error responses

**Complexity:** **LOW**
- Most work already done in Phase 1 and existing tests
- May need minor test additions to explicitly assert error_code values

**Estimated Effort:** 15-30 minutes

**Gate 3 Status:** ⏳ **PENDING** (blocked by Phase 2)

---

### Phase 4: Audit Actor Semantics (Minimal) ❌ NOT STARTED

**Current Situation:**
- Audit event tests exist (`tests/integration/test_audit_event_runtime_contracts.py`)
- Tests verify entity_type, entity_id, actor_user_id, and timestamp fields
- Tests do NOT explicitly assert actor_user_id == current_user.id
- Tests do NOT explicitly assert request_id is recorded on audit events

**Required Work:**
1. Extend existing audit event tests to explicitly assert:
   - `audit_event.actor_user_id == current_user.id`
   - `audit_event.request_id is not None and audit_event.request_id != ""`
2. Cover minimum Policies + Incidents modules
3. Ensure tests are deterministic

**Complexity:** **LOW**
- Tests already exist, just need additional assertions
- Audit service already populates these fields

**Estimated Effort:** 15-20 minutes

**Risks:**
- request_id may be None in test environment (already handled with lenient assertions)

---

### Phase 5: CI Evidence + Acceptance Pack ❌ NOT STARTED

**Required Work:**
1. Provide CI run URL showing all checks green
2. Create comprehensive Stage 3.2 acceptance pack including:
   - CI run URL
   - Touched files table
   - Summary of RBAC deny coverage + 409 handling + audit actor assertions
   - Confirmation: 0 skipped contract tests
3. Ensure all statements are evidence-led

**Complexity:** **LOW**
- Documentation task only
- All evidence will be available after Phases 2-4 complete

**Estimated Effort:** 30-45 minutes

---

## Recommendations

### Recommendation 1: Complete Phases 2-5 in Current PR ✅ RECOMMENDED

**Rationale:**
- Phase 1 is complete and proven in CI
- Remaining phases are low-complexity and low-risk
- Total estimated effort: 90-140 minutes (1.5-2.5 hours)
- Aligns with original Stage 3.2 scope: "ONE PR with multiple phases"

**Approach:**
1. Implement Phase 2 (409 conflict detection)
2. Extend Phase 3 (error envelope assertions)
3. Extend Phase 4 (audit actor assertions)
4. Run full test suite locally
5. Commit and push to PR #19
6. Wait for CI to pass
7. Create Phase 5 acceptance pack with CI evidence
8. Merge PR #19

---

### Recommendation 2: Migration Strategy ✅ AVOID MIGRATIONS

**Rationale:**
- No schema changes required for Phase 2 (reference_number field already exists)
- Duplicate detection can be implemented with a simple query
- Aligns with constraint: "No migrations unless proven necessary (avoid if possible)"

**Decision:** Do NOT create migrations for Stage 3.2

---

### Recommendation 3: Error Code Format ⚠️ CLARIFICATION NEEDED

**Current State:**
- Error codes are currently returned as strings (e.g., "404", "403", "409")
- This matches the canonical error envelope schema

**Question for Review:**
- Is the current format (string error codes) acceptable?
- Or should error codes be semantic strings (e.g., "NOT_FOUND", "FORBIDDEN", "CONFLICT")?

**Recommendation:** Keep current format (string HTTP status codes) unless explicitly required to change

---

### Recommendation 4: Test Coverage Strategy ✅ EXTEND EXISTING TESTS

**Rationale:**
- Existing test files already cover the required scenarios
- Extending existing tests is less disruptive than creating new files
- Maintains test organization and readability

**Approach:**
- Phase 2: Unskip existing test in `test_error_envelope_runtime_contracts.py`
- Phase 3: Add assertions to existing tests in `test_error_envelope_runtime_contracts.py` and `test_rbac_deny_path_runtime_contracts.py`
- Phase 4: Add assertions to existing tests in `test_audit_event_runtime_contracts.py`

---

## Risk Assessment

### Low Risks ✅
- Phase 2 implementation (duplicate detection)
- Phase 3 test extensions (error envelope assertions)
- Phase 4 test extensions (audit actor assertions)
- Phase 5 documentation (acceptance pack)

### Medium Risks ⚠️
- None identified

### High Risks ❌
- None identified

---

## Estimated Timeline

| Phase | Estimated Effort | Complexity | Status |
|-------|------------------|------------|--------|
| Phase 1 | 2-3 hours | Medium | ✅ Complete |
| Phase 2 | 30-45 minutes | Low-Medium | ❌ Not Started |
| Phase 3 | 15-30 minutes | Low | ⏳ Partially Complete |
| Phase 4 | 15-20 minutes | Low | ❌ Not Started |
| Phase 5 | 30-45 minutes | Low | ❌ Not Started |
| **Total Remaining** | **90-140 minutes** | **Low** | **25% Complete** |

---

## Final Recommendation

**Proceed with completing Phases 2-5 in PR #19** with the following approach:

1. **Phase 2 (30-45 min):**
   - Implement duplicate reference_number detection in Policy create
   - Unskip and verify test passes

2. **Phase 3 (15-30 min):**
   - Add explicit error_code assertions to existing tests
   - Verify request_id is always present in error responses

3. **Phase 4 (15-20 min):**
   - Add actor_user_id and request_id assertions to audit event tests
   - Verify tests pass

4. **Phase 5 (30-45 min):**
   - Run full CI
   - Capture CI evidence
   - Create comprehensive acceptance pack
   - Merge PR #19

**Total Estimated Time to Completion:** 90-140 minutes (1.5-2.5 hours)

**Confidence Level:** **HIGH** - All remaining work is low-complexity and low-risk

---

## Approval Decision Point

**Question for Stakeholder:**

Should I proceed with completing Phases 2-5 in the current PR #19, or would you prefer to:
- A) Complete Phases 2-5 now (recommended)
- B) Merge Phase 1 separately and create a new PR for Phases 2-5
- C) Pause and review Phase 1 before proceeding

**My Recommendation:** **Option A** - Complete all phases in one PR as originally scoped
