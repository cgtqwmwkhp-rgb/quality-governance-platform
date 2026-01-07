# Stage 4.1.1 Phase 0: Baseline Inventory

**Date**: 2026-01-06  
**Branch**: `stage-4.1.1-paginated-investigation-linkage`

---

## Current Implementation Analysis

### 1. Investigation Linkage Endpoints (3 total)

#### Endpoint 1: Incidents
- **Path**: `GET /api/v1/incidents/{incident_id}/investigations`
- **File**: `src/api/routes/incidents.py` (lines 158-191)
- **Current Response**: `List[InvestigationRunResponse]` (simple list, not paginated)
- **Current Ordering**: ✅ Deterministic (`created_at DESC, id ASC`)
- **Query Params**: None
- **Response Model**: No explicit `response_model` in decorator

#### Endpoint 2: RTAs
- **Path**: `GET /api/v1/rtas/{rta_id}/investigations`
- **File**: `src/api/routes/rtas.py` (lines 383-415)
- **Current Response**: `List[InvestigationRunResponse]` (simple list, not paginated)
- **Current Ordering**: ✅ Deterministic (`created_at DESC, id ASC`)
- **Query Params**: None
- **Response Model**: No explicit `response_model` in decorator

#### Endpoint 3: Complaints
- **Path**: `GET /api/v1/complaints/{complaint_id}/investigations`
- **File**: `src/api/routes/complaints.py` (lines 177-211)
- **Current Response**: `List[InvestigationRunResponse]` (simple list, not paginated)
- **Current Ordering**: ✅ Deterministic (`created_at DESC, id ASC`)
- **Query Params**: None
- **Response Model**: No explicit `response_model` in decorator

---

### 2. Existing Tests

#### Test File 1: `test_investigation_governance.py`
- **Test**: `test_get_incident_investigations_deterministic` (line 167)
  - Verifies deterministic ordering for incidents
  - Checks that response is a list
  - Verifies ordering stability across multiple calls

- **Test**: `test_get_incident_investigations_empty_list` (line 216)
  - Verifies empty list response when no investigations exist

#### Test File 2: `test_rta_governance.py`
- **Test**: `test_rta_investigations_linkage` (line 289)
  - Verifies RTA investigation linkage
  - Checks deterministic ordering
  - Verifies response is a list

- **Test**: `test_complaint_investigations_linkage` (line 347)
  - Verifies complaint investigation linkage
  - Checks deterministic ordering
  - Verifies response is a list

---

### 3. Current OpenAPI Definitions

**Status**: Need to check OpenAPI spec for current endpoint definitions.

**Action**: Will verify in next step.

---

## Contract Decision

### Chosen Contract

**Paginated Envelope**:
```json
{
  "items": [...],
  "page": 1,
  "page_size": 25,
  "total": 123,
  "total_pages": 5
}
```

**Query Parameters**:
- `page` (int, >= 1, default 1)
- `page_size` (int, 1..100, default 25)

**Deterministic Ordering**:
- `created_at DESC, id ASC` (already implemented ✅)

**Error Handling**:
- `page=0` → 400 canonical envelope + request_id
- `page_size=0` or `page_size>100` → 400 canonical envelope + request_id
- Invalid case ID → 404 canonical envelope + request_id

---

## Changes Required

### Code Changes
1. **Update 3 route handlers** to accept `page` and `page_size` query params
2. **Add pagination logic** (offset/limit + total count)
3. **Return canonical envelope** instead of simple list
4. **Add query param validation** (400 errors for invalid values)

### Schema Changes
1. **Create paginated response schema** for investigation linkage
2. **Update OpenAPI** to reflect new contract

### Test Changes
1. **Update existing tests** to expect paginated envelope
2. **Add new tests** for:
   - Pagination fields correctness
   - Page/page_size validation errors
   - Total pages calculation
   - Ordering stability across pages

---

## Files to Touch

### Add/Modify
- `src/api/routes/incidents.py` (modify linkage handler)
- `src/api/routes/rtas.py` (modify linkage handler)
- `src/api/routes/complaints.py` (modify linkage handler)
- `src/api/schemas/investigation.py` (add paginated response schema)
- `tests/integration/test_investigation_governance.py` (update + add tests)
- `tests/integration/test_rta_governance.py` (update + add tests)
- `docs/contracts/openapi.json` (regenerate)

### Do NOT Touch
- `.github/workflows/**` (no gate changes)
- `alembic/**` (no migrations)
- Other modules/features

---

## Gate 0 Status

**Gate 0**: ✅ **PASSED**

**Evidence**:
- ✅ Located all 3 linkage endpoints
- ✅ Identified current response shapes (simple list)
- ✅ Confirmed deterministic ordering already exists
- ✅ Found existing tests (4 tests total)
- ✅ Defined canonical contract
- ✅ Identified files to touch

**Ready to proceed to Phase 1**.
