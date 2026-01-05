# Stage 4.0: Investigation + RCA-in-Template - Progress Summary

**Date**: 2026-01-05  
**Status**: IN PROGRESS (Phases 0-2 Complete)

---

## Overview

Implementing breaking change to remove standalone `/api/v1/rtas` (Root Cause Analysis) and replace with Investigation system where RCA is a section within Investigation templates/runs, assignable to Road Traffic Collisions, Reporting Incidents, or Complaints.

---

## ✅ Phase 0: Baseline Inventory + Usage Scan (COMPLETE)

**Status**: GATE 0 MET

**Files Created**:
- `docs/evidence/STAGE4.0_PHASE0_BASELINE.md`

**Findings**:
- Confirmed `/api/v1/rtas` endpoints exist in OpenAPI (5 paths)
- Found 2 test files using `/api/v1/rtas`
- Found 3 documentation files referencing `/api/v1/rtas`
- Found 5 source files implementing RTA functionality
- No external consumers detected
- All affected files identified for update in this PR

**Evidence**: See STAGE4.0_PHASE0_BASELINE.md

---

## ✅ Phase 1: Data Model + Alembic Migration (COMPLETE)

**Status**: GATE 1 MET

**Files Created**:
1. `src/domain/models/investigation.py` (173 lines)
   - `InvestigationTemplate` model with JSON structure
   - `InvestigationRun` model with entity assignment
   - `InvestigationStatus` enum (DRAFT, IN_PROGRESS, UNDER_REVIEW, COMPLETED, CLOSED)
   - `AssignedEntityType` enum (ROAD_TRAFFIC_COLLISION, REPORTING_INCIDENT, COMPLAINT)

2. `alembic/versions/ee405ad5e788_add_investigation_templates_and_runs.py` (95 lines)
   - Creates `investigation_templates` table
   - Creates `investigation_runs` table
   - Creates enums for status and entity types
   - Includes proper indexes and foreign keys
   - Includes downgrade path

**Migration Applied**:
```
Running upgrade dfee008952ec -> ee405ad5e788, Add investigation templates and runs
```

**Tables Created**:
- `investigation_templates` ✅
- `investigation_runs` ✅

**Evidence**:
```bash
$ alembic upgrade head
INFO  [alembic.runtime.migration] Running upgrade dfee008952ec -> ee405ad5e788

$ sudo -u postgres psql -d qgp_db -c "\dt investigation*"
                  List of relations
 Schema |          Name           | Type  |  Owner   
--------+-------------------------+-------+----------
 public | investigation_runs      | table | qgp_user
 public | investigation_templates | table | qgp_user
```

---

## ✅ Phase 2: Investigation Template API (COMPLETE)

**Status**: GATE 2 MET

**Files Created**:
1. `src/api/schemas/investigation.py` (200 lines)
   - `InvestigationTemplateBase`, `InvestigationTemplateCreate`, `InvestigationTemplateUpdate`, `InvestigationTemplateResponse`
   - `InvestigationTemplateListResponse` with pagination
   - `InvestigationRunBase`, `InvestigationRunCreate`, `InvestigationRunUpdate`, `InvestigationRunResponse`
   - `InvestigationRunListResponse` with pagination
   - Field validators for entity types and statuses

2. `src/api/routes/investigation_templates.py` (250 lines)
   - `POST /api/v1/investigation-templates/` - Create template
   - `GET /api/v1/investigation-templates/` - List templates (paginated, deterministic ordering)
   - `GET /api/v1/investigation-templates/{id}` - Get template
   - `PATCH /api/v1/investigation-templates/{id}` - Update template
   - `DELETE /api/v1/investigation-templates/{id}` - Delete template (safe check for runs)
   - All endpoints return canonical error envelopes with request_id
   - Deterministic ordering by ID
   - Pagination enforced

**Files Modified**:
1. `src/api/__init__.py`
   - Added investigation_templates router import
   - Registered `/investigation-templates` prefix

**Endpoints Available**:
- `POST /api/v1/investigation-templates/` ✅
- `GET /api/v1/investigation-templates/` ✅
- `GET /api/v1/investigation-templates/{id}` ✅
- `PATCH /api/v1/investigation-templates/{id}` ✅
- `DELETE /api/v1/investigation-templates/{id}` ✅

**Canonical Error Envelopes**: ✅ Implemented
- 404: TEMPLATE_NOT_FOUND
- 400: TEMPLATE_IN_USE (when deleting template with runs)
- All errors include `error_code`, `message`, `details`, `request_id`

**Deterministic Ordering**: ✅ Implemented (ORDER BY id)

**Pagination**: ✅ Enforced (page, page_size, total, total_pages)

---

## ⏳ Phase 3: Investigation Run API + Assignment (IN PROGRESS)

**Status**: NOT STARTED

**Required**:
- Create `src/api/routes/investigations.py`
- Implement endpoints:
  - `POST /api/v1/investigations` (create with template_id and entity assignment)
  - `GET /api/v1/investigations/{id}` (get investigation run)
  - `GET /api/v1/investigations?entity_type=&entity_id=` (list for a case)
  - `PATCH /api/v1/investigations/{id}` (update RCA section fields)
- Validation: assigned entity must exist
- Deterministic ordering and pagination

---

## ⏳ Phase 4: Remove /api/v1/rtas (IN PROGRESS)

**Status**: NOT STARTED

**Required**:
- Remove `/api/v1/rtas` routes
- Remove RTA schemas/services
- Update tests to use Investigation API
- Update docs to reference Investigation API
- Regenerate OpenAPI snapshot

---

## ⏳ Phase 5: Data Migration (IN PROGRESS)

**Status**: NOT STARTED

**Required**:
- Detect if RootCauseAnalysis rows exist
- If present, migrate to InvestigationRuns
- Map incident_id/complaint_id/collision_id to assigned_entity_type/id
- Provide deterministic before/after counts

---

## ⏳ Phase 6: RBAC + Audit + Tests (IN PROGRESS)

**Status**: NOT STARTED

**Required**:
- RBAC deny-path tests (403 canonical envelope)
- Happy path tests for all entity types
- Audit event tests (create/update with request_id)
- Canonical error tests (404, 400)

---

## ⏳ Phase 7: OpenAPI + Acceptance Pack (IN PROGRESS)

**Status**: NOT STARTED

**Required**:
- Confirm OpenAPI drift/invariants green
- Create STAGE4.0_ACCEPTANCE_PACK.md
- Update release notes/changelog

---

## Summary

**Phases Complete**: 3/8 (0, 1, 2)  
**Gates Met**: 3/7 (Gate 0, Gate 1, Gate 2)  
**Files Created**: 6  
**Files Modified**: 1  
**Lines Added**: ~900  
**Migration ID**: ee405ad5e788

**Next Steps**:
1. Complete Phase 3: Investigation Run API + Assignment
2. Complete Phase 4: Remove /api/v1/rtas endpoints
3. Complete Phase 5: Data migration (if needed)
4. Complete Phase 6: RBAC + Audit + Tests
5. Complete Phase 7: OpenAPI + Acceptance Pack

**Commit SHA**: (pending - work in progress)

---

## Notes

- All new endpoints require authentication (JWT token)
- Investigation templates use JSON structure for flexible section definitions
- RCA is defined as a section within the template structure
- Investigation runs store responses in JSON data field matching template structure
- Entity assignment validation will be implemented in Phase 3
