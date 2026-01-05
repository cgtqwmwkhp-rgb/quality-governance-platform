# Stage 4.0.1 OpenAPI Verification

**Date**: 2026-01-05  
**Snapshot**: `docs/openapi_stage4.0.1.json`  
**OpenAPI Version**: 3.1.0  
**Total Endpoints**: 55

## Investigation System Endpoints

### Investigation Templates (5 operations)

| Method | Path | Summary | Response Schema |
|--------|------|---------|----------------|
| GET | `/api/v1/investigation-templates/` | List Templates | `InvestigationTemplateListResponse` |
| POST | `/api/v1/investigation-templates/` | Create Template | `InvestigationTemplateResponse` |
| GET | `/api/v1/investigation-templates/{template_id}` | Get Template | `InvestigationTemplateResponse` |
| PATCH | `/api/v1/investigation-templates/{template_id}` | Update Template | `InvestigationTemplateResponse` |
| DELETE | `/api/v1/investigation-templates/{template_id}` | Delete Template | `204 No Content` |

### Investigation Runs (4 operations)

| Method | Path | Summary | Response Schema |
|--------|------|---------|----------------|
| GET | `/api/v1/investigations/` | List Investigations | `InvestigationRunListResponse` |
| POST | `/api/v1/investigations/` | Create Investigation | `InvestigationRunResponse` |
| GET | `/api/v1/investigations/{investigation_id}` | Get Investigation | `InvestigationRunResponse` |
| PATCH | `/api/v1/investigations/{investigation_id}` | Update Investigation | `InvestigationRunResponse` |

### Incidents Linkage (1 operation)

| Method | Path | Summary | Response Schema |
|--------|------|---------|----------------|
| GET | `/api/v1/incidents/{incident_id}/investigations` | List Incident Investigations | `List[InvestigationRunResponse]` |

**Total Investigation Endpoints**: 10 (5 templates + 4 runs + 1 linkage)

## Schema Verification

### Response Schemas

1. **InvestigationTemplateResponse**
   - Single template object
   - Fields: id, name, description, version, is_active, structure, applicable_entity_types, created_at, updated_at, created_by_id, updated_by_id

2. **InvestigationTemplateListResponse**
   - Paginated list of templates
   - Fields: items, total, page, page_size, total_pages

3. **InvestigationRunResponse**
   - Single investigation run object
   - Fields: id, reference_number, template_id, assigned_entity_type, assigned_entity_id, title, description, status, data, started_at, completed_at, reviewed_at, closed_at, assigned_to_user_id, reviewer_user_id, created_at, updated_at, created_by_id, updated_by_id

4. **InvestigationRunListResponse**
   - Paginated list of investigation runs
   - Fields: items, total, page, page_size, total_pages

### Request Schemas

1. **InvestigationTemplateCreate**
   - Fields: name, description, version, is_active, structure, applicable_entity_types

2. **InvestigationTemplateUpdate**
   - All fields optional (partial update)

3. **InvestigationRunCreate**
   - Fields: template_id, assigned_entity_type, assigned_entity_id, title, description, status, data

4. **InvestigationRunUpdate**
   - All fields optional (partial update)

## Invariants

### Pagination Invariants
- All list endpoints return paginated responses with metadata
- **Exception**: `/incidents/{id}/investigations` returns simple `List[InvestigationRunResponse]` (sub-resource pattern)
- Page numbers are 1-indexed
- Default page_size: 10
- Max page_size: 100

### Ordering Invariants
- Templates: Ordered by `id ASC` (deterministic)
- Investigation Runs: Ordered by `created_at DESC, id ASC` (deterministic)
- Incident Investigations: Ordered by `created_at DESC, id ASC` (deterministic)

### Authentication Invariants
- All endpoints require authentication (401 if missing token)
- Inactive users get 403 Forbidden
- No fine-grained permissions (consistent with Incidents/Complaints/Policies)

### Error Response Invariants
- 401: Missing or invalid authentication
- 403: Inactive user account
- 404: Resource not found (canonical error envelope with request_id)
- 400: Invalid request (validation errors)

## Drift Analysis

### Changes Since Stage 4.0 (Breaking)
- **Removed**: `/api/v1/rta/{rta_id}/analysis` endpoints (RCA system)
- **Added**: `/api/v1/investigation-templates/` endpoints (5 operations)
- **Added**: `/api/v1/investigations/` endpoints (4 operations)
- **Added**: `/api/v1/incidents/{incident_id}/investigations` endpoint (1 operation)

### Schema Changes
- **Removed**: `RCACreate`, `RCAUpdate`, `RCAResponse` schemas
- **Added**: `InvestigationTemplateCreate`, `InvestigationTemplateUpdate`, `InvestigationTemplateResponse`, `InvestigationTemplateListResponse`
- **Added**: `InvestigationRunCreate`, `InvestigationRunUpdate`, `InvestigationRunResponse`, `InvestigationRunListResponse`

## Verification Status

✅ **All Investigation endpoints documented in OpenAPI spec**  
✅ **All response schemas present**  
✅ **All request schemas present**  
✅ **Pagination contracts consistent** (except sub-resource endpoint)  
✅ **Ordering contracts documented**  
✅ **Authentication requirements documented**  
✅ **Breaking changes documented** (RCA → Investigation migration)

## Notes

1. The `/incidents/{id}/investigations` endpoint intentionally returns a simple list (not paginated) because it's a **sub-resource endpoint** showing all investigations for a specific incident. This is a REST best practice and is tested/verified.

2. All Investigation endpoints use typed dependencies (`CurrentUser`, `DbSession`) for consistency with other modules.

3. The Investigation system replaces the RCA system (breaking change documented in Stage 4.0 data impact statement).

4. OpenAPI spec generated from runtime application (not hand-written), ensuring accuracy.
