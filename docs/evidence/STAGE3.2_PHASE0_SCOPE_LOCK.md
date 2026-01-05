# Stage 3.2 Phase 0: Scope Lock + Skip Identification + Disposition Decision

## Date
2026-01-05

## Skipped Test Identification

**Test Name:** `test_409_conflict_canonical_envelope`  
**Location:** `tests/integration/test_error_envelope_runtime_contracts.py:114`  
**Skip Reason:** "Duplicate reference number detection not yet implemented"

**Test Intent:**
- Create a policy with a specific reference_number
- Attempt to create another policy with the same reference_number
- Assert HTTP 409 Conflict
- Assert canonical error envelope with error_code/message/details/request_id

## Disposition Decision

**CHOSEN: Fix Now (Preferred)**

**Rationale:**
1. **Minimal Scope:** Reference number uniqueness is already a natural constraint in the domain model
2. **Low Risk:** Adding a simple uniqueness check before insert is a targeted, low-risk change
3. **High Value:** Completing the 409 error envelope contract coverage is a core goal of Stage 3.2
4. **No Broad Refactor Required:** Can be implemented with a simple query check in the create endpoint

**Implementation Plan:**
- Add reference_number uniqueness check in the policy create endpoint
- Return 409 with canonical error envelope if duplicate detected
- Unskip and complete the test

## Scope Lock

**Allowed Changes:**
1. Add RBAC deny-path integration tests for 4 modules (Policies, Incidents, Complaints, RTAs)
2. Add reference_number duplicate detection in policy create endpoint
3. Implement 409 error response with canonical envelope
4. Unskip the conflict error envelope test
5. Add error envelope expansion tests for 403/404/409
6. Add audit actor semantics checks for 2+ modules

**Forbidden Changes:**
- No new business features or modules
- No weakening of CI gates
- No changes to governance covenants
- No schema migrations unless proven necessary (avoid if possible)

## Gate 0 Status

**GATE 0 MET:** ✅ YES

**Verification:**
- Scope is strictly limited to RBAC deny tests + 409 handling + contract enforcement
- No new business functionality beyond error handling and access control
- All changes are test-driven and evidence-led
- Disposition chosen: Fix now (duplicate detection)

## Next Phase

Proceed to Phase 1: RBAC Deny-Path Integration Tests for 4 Modules
