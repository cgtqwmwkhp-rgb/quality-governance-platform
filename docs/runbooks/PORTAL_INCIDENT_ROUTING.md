# Portal Incident Routing Contract

## Overview

This document defines the canonical mapping between portal incident submission forms and their respective database tables and admin dashboards.

## Architecture

The Quality Governance Platform uses a **multi-table architecture** where each incident type has its own dedicated database table. This ensures:

1. **Strong isolation** - No cross-leakage between dashboards
2. **Auditability** - Clear traceability from submission to storage
3. **Type-specific fields** - Each entity type has specialized columns

## Mapping Contract

| Portal Route | Form | `report_type` | Database Table | Admin Dashboard | Reference Pattern |
|-------------|------|---------------|----------------|-----------------|-------------------|
| `/portal/report/incident` | PortalDynamicForm | `incident` | `incidents` | `/incidents` | `INC-YYYY-NNNN` |
| `/portal/report/near-miss` | PortalDynamicForm | `near_miss` | `near_misses` | `/near-misses` | `NM-YYYY-NNNN` |
| `/portal/report/complaint` | PortalDynamicForm | `complaint` | `complaints` | `/complaints` | `COMP-YYYY-NNNN` |
| `/portal/report/rta` | PortalRTAForm | `rta` | `road_traffic_collisions` | `/rtas` | `RTA-YYYY-NNNN` |

## Routing Flow

```
Portal Form → API POST /api/v1/portal/reports/
                    ↓
          report_type value?
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
"incident"       "rta"         "near_miss"       "complaint"
    ↓               ↓               ↓                 ↓
incidents    road_traffic_    near_misses        complaints
  table      collisions          table             table
                table
```

## Dashboard Isolation

Each admin dashboard queries **only its own API endpoint**, which queries **only its own table**:

- `RTAs.tsx` → `GET /api/v1/rtas/` → `road_traffic_collisions` table only
- `Incidents.tsx` → `GET /api/v1/incidents/` → `incidents` table only
- `NearMisses` → `GET /api/v1/near-misses/` → `near_misses` table only
- `Complaints` → `GET /api/v1/complaints/` → `complaints` table only

## Audit Traceability

All portal submissions include a `source_form_id` field for audit purposes:

| Report Type | `source_form_id` |
|------------|------------------|
| Incident | `portal_incident_v1` |
| Near Miss | `portal_near_miss_v1` |
| Complaint | `portal_complaint_v1` |
| RTA | `portal_rta_v1` |

### Audit Query Examples

Find all portal-submitted incidents:
```sql
SELECT * FROM incidents WHERE source_form_id = 'portal_incident_v1';
```

Find all portal-submitted RTAs:
```sql
SELECT * FROM road_traffic_collisions WHERE source_form_id = 'portal_rta_v1';
```

## Fail-Fast Behavior

Per ADR-0002, the portal API rejects unknown `report_type` values with HTTP 400:

```python
# employee_portal.py
else:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid report_type. Must be 'incident', 'complaint', 'rta', or 'near_miss'.",
    )
```

There is **no silent default to incident** - unknown types are explicitly rejected.

## Testing

Integration tests verify this contract in:
- `tests/integration/test_portal_routing_correctness.py`

Unit tests verify the mapping in:
- `tests/unit/test_portal_routing_mapping.py`

## Related ADRs

- **ADR-0001**: Migrations mandatory for schema changes
- **ADR-0002**: Fail-fast config validation

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-27 | Initial documentation of routing contract |
