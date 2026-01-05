# Stage 3.3 Phase 0: Scope Lock + Baseline

**Date**: 2026-01-05  
**Stage**: 3.3 - Test Infrastructure Hardening: Request Context + Audit request_id  
**Branch**: `stage-3.3-test-infrastructure-hardening`

## Objective

Close the known gap from Stage 3.2 by ensuring `request_id` is non-empty in integration tests for audit events and error envelopes.

## Scope Definition

### In Scope ✅
1. Activate `ContextMiddleware` in integration test fixtures
2. Ensure `request_id` propagates to audit events in test environment
3. Strengthen audit event tests to assert `request_id` is non-empty
4. Extend `request_id` assertions to error envelope tests (403/404/409)
5. Document changes in Stage 3.3 acceptance pack

### Out of Scope ❌
- No new features or business logic
- No CI gate changes
- No database migrations
- No changes to production middleware (already correct)
- No changes to business modules outside request_id/audit plumbing

## Known Gap from Stage 3.2

**Gap**: Audit event tests currently only assert that `request_id` field exists, not that it contains a non-empty value.

**Root Cause**: In the test environment, `request_id` may be `None` because the test client (`AsyncClient`) doesn't fully exercise the request context middleware that sets `request_id` in production.

**Impact**: Low - Production behavior is correct. Test coverage gap only.

**Evidence**: Stage 3.2 Acceptance Pack, Known Gaps section

## Target Assertion (Phase 3)

```python
# Current (Stage 3.2):
assert hasattr(audit_event, "request_id")

# Target (Stage 3.3):
assert audit_event.request_id is not None
assert len(audit_event.request_id) > 0
```

## Current Middleware Source

**Production Setup** (src/main.py):
```python
app.add_middleware(
    middleware.ContextMiddleware,
    plugins=(RequestIdPlugin(),),
)
```

**Middleware Components**:
- `starlette-context` package
- `ContextMiddleware` - Manages request-scoped context
- `RequestIdPlugin` - Generates and injects request_id

## Current Integration Test Setup

**Test Client** (tests/conftest.py):
```python
@pytest.fixture
async def client(test_session, test_user):
    """Create test client with database override."""
    app.dependency_overrides[get_db] = lambda: override_get_db(test_session)
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

**Observation**: The test client uses the production `app` instance, which should have the middleware registered. However, the middleware may not be fully active or context may not propagate correctly in the test environment.

## Baseline Proof: Current State

### Test 1: Audit Event request_id

**File**: `tests/integration/test_audit_event_runtime_contracts.py`

**Current Assertion**:
```python
# request_id should be present as a field (may be None in test environment)
assert hasattr(audit_event, "request_id")
```

**Expected Behavior**: Test passes, but `request_id` may be `None`

### Test 2: Error Envelope request_id

**File**: `tests/integration/test_error_envelope_runtime_contracts.py`

**Current Assertion**:
```python
assert "request_id" in body
assert isinstance(body["request_id"], str)
assert len(body["request_id"]) > 0
```

**Expected Behavior**: Test passes if request_id is set, fails if None

## Hypothesis

The `ContextMiddleware` is registered in production `app`, but when `AsyncClient` makes requests in tests, the middleware may not be fully invoked or the context may not propagate to the audit service and exception handlers.

**Possible Causes**:
1. Middleware is active but context doesn't persist across async boundaries
2. Test client bypasses some middleware layers
3. Context is set but not accessible in the audit service

## Verification Plan (Phase 0)

1. Run existing audit event tests to confirm request_id is None
2. Check if error envelope tests pass (they assert non-empty request_id)
3. Add debug logging to confirm middleware activation
4. Document baseline state

## Files to Touch (Approved)

### Phase 1-2 (Plumbing):
- `tests/conftest.py` - Update fixtures to ensure middleware is active
- `src/domain/services/audit_service.py` - Verify request_id sourcing

### Phase 3-4 (Test Strengthening):
- `tests/integration/test_audit_event_runtime_contracts.py` - Strengthen assertions
- `tests/integration/test_error_envelope_runtime_contracts.py` - Verify assertions

### Phase 5 (Documentation):
- `docs/evidence/STAGE3.3_ACCEPTANCE_PACK.md` - Final evidence

## Gate 0 Criteria

- ✅ Scope is locked to request_id propagation only
- ✅ No feature work
- ✅ No CI gate changes
- ✅ Baseline is documented

## Next Steps

1. Run integration tests to capture baseline behavior
2. Add debug test to verify middleware activation
3. Document findings
4. Proceed to Phase 1 if scope is confirmed

---

**Prepared by**: Lead Engineer  
**Status**: Phase 0 - Scope Lock Complete


## Baseline Test Results

### Test 1: Audit Event request_id

**Command**: `pytest tests/integration/debug_request_id_test.py::test_debug_audit_event_request_id -v -s`

**Result**:
```
=== AUDIT EVENT DEBUG ===
request_id value: None
request_id is None: True
request_id type: <class 'NoneType'>
=========================
```

**Conclusion**: ✅ Confirmed - `request_id` is `None` in audit events during integration tests.

### Test 2: Error Envelope request_id

**Command**: `pytest tests/integration/debug_request_id_test.py::test_debug_error_envelope_request_id -v -s`

**Result**:
```
=== ERROR ENVELOPE DEBUG ===
Status code: 404
request_id value: 'unknown'
request_id is None: False
request_id length: 7
============================
```

**Conclusion**: ✅ Confirmed - `request_id` is `'unknown'` (the default fallback) in error envelopes during integration tests.

## Root Cause Analysis

**Observation**: Both audit service and exception handlers use `context.get("request_id", default)` and both receive their default values.

**Root Cause**: The `ContextMiddleware` is registered in the production app, but the starlette-context is not being set or propagated correctly when `AsyncClient` makes requests in tests.

**Code Evidence**:

1. **Audit Service** (`src/domain/services/audit_service.py:47-48`):
   ```python
   if request_id is None:
       request_id = context.get("request_id", None)
   ```

2. **Exception Handlers** (`src/api/exceptions.py:20` and `:44`):
   ```python
   request_id = context.get("request_id", "unknown")
   ```

3. **Middleware Registration** (`src/main.py:80-83`):
   ```python
   app.add_middleware(
       middleware.ContextMiddleware,
       plugins=(RequestIdPlugin(),),
   )
   ```

**Hypothesis**: The `AsyncClient` test client may not fully invoke the middleware stack, or the context may not persist across async boundaries in the test environment.

## Gate 0: PASS ✅

- ✅ Scope is locked to request_id propagation only
- ✅ No feature work
- ✅ No CI gate changes
- ✅ Baseline is documented with evidence
- ✅ Root cause identified

## Next Phase

Proceed to **Phase 1**: Activate context middleware in tests (fixture-level)

**Goal**: Ensure `ContextMiddleware` is active and context propagates correctly in integration tests.

**Approach**: Investigate test client setup and ensure middleware is invoked for test requests.
