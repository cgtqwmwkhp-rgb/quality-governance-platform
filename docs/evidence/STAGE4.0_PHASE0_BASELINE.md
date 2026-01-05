# Stage 4.0 Phase 0: Baseline Inventory + Usage Scan

**Date**: 2026-01-05  
**Phase**: 0 - Baseline + Break Confirmation  
**Status**: COMPLETE

---

## Objective

Confirm current state of `/api/v1/rtas` (Root Cause Analysis) endpoints and scan for all usage across the repository before executing breaking change removal.

---

## 1. OpenAPI Baseline Confirmation

**Current OpenAPI paths containing "rta"**:

```
/api/v1/incidents/{incident_id}/rtas
/api/v1/rta
/api/v1/rta/actions
/api/v1/rtas/
/api/v1/rtas/{rta_id}
```

**Confirmed**:
- ✅ `/api/v1/rtas` (Root Cause Analysis - standalone module) EXISTS
- ✅ `/api/v1/rta` (Road Traffic Collisions) EXISTS
- ⚠️ **BREAKING CHANGE**: `/api/v1/rtas/` and `/api/v1/rtas/{rta_id}` will be REMOVED

---

## 2. Repository-Wide Usage Scan

### 2.1 Tests Directory

**File**: `tests/integration/test_audit_events.py`
- Line 72: `response = await client.post("/api/v1/rtas/", json=data, headers=auth_headers)`
- **Impact**: Test must be updated to use new Investigation API

**File**: `tests/integration/test_rta_api.py`
- Line 42: `response = await client.post("/api/v1/rtas/", json=data, headers=auth_headers)`
- Line 57: `response = await client.post("/api/v1/rtas/", json=data, headers=auth_headers)`
- Line 79: `response = await client.get("/api/v1/rtas/", headers=auth_headers)`
- Line 125: `response = await client.patch(f"/api/v1/rtas/{rta.id}", json=data, headers=auth_headers)`
- **Impact**: Entire test file must be replaced with Investigation API tests

**Total Test Files Affected**: 2

---

### 2.2 Documentation Directory

**File**: `docs/evidence/STAGE2.3_ACCEPTANCE_PACK.md`
- Line 44: `response = await client.post("/api/v1/rtas/", json=data, headers=auth_headers)`
- **Impact**: Historical evidence document (no update needed)

**File**: `docs/modules/RTA.md`
- Lines 30-34: Full API documentation for `/api/v1/rtas` endpoints
- **Impact**: Document must be replaced with Investigation module documentation

**File**: `docs/contracts/runtime_contract_baseline.md`
- Line 13: Lists RTAs as a module
- Lines 161-190: Full contract specification for `/api/v1/rtas` endpoints
- **Impact**: Contract must be updated to reflect Investigation API

**Total Doc Files Affected**: 3 (2 require updates, 1 historical)

---

### 2.3 Source Code

**File**: `src/api/__init__.py`
- Line 17: `router.include_router(rtas.router, prefix="/rtas", tags=["Root Cause Analysis"])`
- **Impact**: Router inclusion must be removed

**File**: `src/api/routes/incidents.py`
- Line 160: `@router.get("/{incident_id}/rtas", response_model=RTAListResponse)`
- **Impact**: Endpoint must be updated to return Investigations

**File**: `src/api/routes/rtas.py`
- Full file with RTA CRUD endpoints
- **Impact**: Entire file must be removed

**File**: `src/api/schemas/rta.py`
- Classes: `RTABase`, `RTACreate`, `RTAUpdate`, `RTAResponse`, `RTAListResponse`
- **Impact**: Schemas must be removed or migrated

**File**: `src/domain/models/rta.py`
- Classes: `RTASeverity`, `RTAStatus`, `RTAAction`
- **Impact**: Models must be removed or migrated

**Total Source Files Affected**: 5

---

## 3. Breaking Change Confirmation

**EXPLICIT BREAKING CHANGE DECLARATION**:

The following endpoints will be **REMOVED** in this PR:
- `POST /api/v1/rtas/` - Create RTA
- `GET /api/v1/rtas/` - List RTAs
- `GET /api/v1/rtas/{rta_id}` - Get RTA
- `PATCH /api/v1/rtas/{rta_id}` - Update RTA

**Replacement**:
- New Investigation API: `/api/v1/investigations` and `/api/v1/investigation-templates`
- RCA becomes a section within Investigation templates/runs
- Investigations can be assigned to:
  - Road Traffic Collisions (`/api/v1/rta`)
  - Reporting Incidents (`/api/v1/incidents`)
  - Complaints (`/api/v1/complaints`)

**No Alias/Deprecation**: This is an intentional breaking change with no backward compatibility.

---

## 4. Files Requiring Updates in This PR

### Must Update (Same PR)

**Tests**:
1. `tests/integration/test_rta_api.py` - Replace with Investigation tests
2. `tests/integration/test_audit_events.py` - Update RTA references

**Documentation**:
1. `docs/modules/RTA.md` - Replace with Investigation module docs
2. `docs/contracts/runtime_contract_baseline.md` - Update contract

**Source Code**:
1. `src/api/__init__.py` - Remove RTA router inclusion
2. `src/api/routes/rtas.py` - Remove entire file
3. `src/api/routes/incidents.py` - Update `/incidents/{id}/rtas` endpoint
4. `src/api/schemas/rta.py` - Remove or migrate schemas
5. `src/domain/models/rta.py` - Remove or migrate models

**New Files Required**:
1. `src/domain/models/investigation.py` - New models
2. `src/api/routes/investigations.py` - New routes
3. `src/api/schemas/investigation.py` - New schemas
4. `alembic/versions/XXX_add_investigations.py` - Migration

---

## 5. Data Migration Assessment

**Database Check Required**: Determine if `root_cause_analysis` table exists and contains data.

**If Data Exists**:
- Migrate rows to new `investigation_runs` table
- Map `incident_id`/`complaint_id` to `assigned_entity_type` and `assigned_entity_id`
- Preserve RCA content in investigation run payload

**If No Data**:
- Record evidence and skip migration

---

## Gate 0 Assessment

**GATE 0 (HARD STOP)**: Stop if any consumer usage is found that would break silently without an explicit update in this PR.

**Result**: ✅ **GATE 0 MET**

**Findings**:
- All usage is internal (tests, docs, source code)
- No external consumers detected
- All affected files identified and will be updated in this PR
- No silent breakage risk

---

## Next Steps

Proceed to **Phase 1**: Data Model + Alembic Migration (Investigations)

---

## Evidence

**Commands Run**:
```bash
# Check OpenAPI paths
cat docs/contracts/openapi.json | python3.11 -c "import sys, json; data = json.load(sys.stdin); paths = [p for p in data.get('paths', {}).keys() if 'rta' in p.lower()]; print('\n'.join(sorted(paths)))"

# Search tests
grep -r "/api/v1/rtas" tests/

# Search docs
grep -r "/api/v1/rtas" docs/

# Search source
grep -r "class.*RTA\|router.*rta\|/api/v1/rtas" src/
```

**Commit SHA**: ae480fc (baseline)  
**Date**: 2026-01-05 15:10:00 GMT

---

## Summary

- **OpenAPI Paths Confirmed**: 5 paths containing "rta"
- **Test Files Affected**: 2
- **Doc Files Affected**: 3 (2 require updates)
- **Source Files Affected**: 5
- **Breaking Change**: Explicit and intentional
- **External Consumers**: None detected
- **Gate 0**: ✅ MET

**Ready to proceed to Phase 1**.
