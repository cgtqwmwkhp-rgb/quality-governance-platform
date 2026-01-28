# PR #103/104 Contract Provenance

## Purpose

This document provides complete traceability between frontend UI consumption, API client methods, backend endpoints, and their determinism guarantees.

## Contract Discovery Table

| Module | UI Call Site | Client Method | Endpoint | Response Shape | Ordering | Tie-breaker | Tests |
|--------|--------------|---------------|----------|----------------|----------|-------------|-------|
| Planet Mark | `PlanetMark.tsx:72-143` (useEffect) | `planetMarkApi.getDashboard()` | `GET /api/v1/planet-mark/dashboard` | `{current_year, emissions_breakdown, data_quality, certification, actions, targets, historical_years}` | `order_by(desc(year_number)).limit(3)` | N/A (limit 3) | `test_dashboard_returns_setup_required_when_empty` |
| Planet Mark | `PlanetMark.tsx:75-104` (yearsData) | `planetMarkApi.listYears()` | `GET /api/v1/planet-mark/years` | `{total: int, years: [{id, year_label, year_number, ...}]}` | `order_by(desc(year_number))` | `id` implicit | `test_years_ordered_by_year_number_desc` |
| Planet Mark | `PlanetMark.tsx:108-121` (actions) | `planetMarkApi.getActions(yearId)` | `GET /api/v1/planet-mark/years/{id}/actions` | `{year_id, summary, actions: [{id, action_id, ...}]}` | `order_by(time_bound)` | `id` implicit | `test_list_is_deterministic` |
| Planet Mark | `PlanetMark.tsx:123-139` (scope3) | `planetMarkApi.getScope3(yearId)` | `GET /api/v1/planet-mark/years/{id}/scope3` | `{year_id, categories: [15 GHG categories]}` | `order_by(category_number)` | Static (1-15) | `test_scope3_returns_default_categories` |
| UVDB | `UVDBAudits.tsx:55-71` (sections) | `uvdbApi.listSections()` | `GET /api/v1/uvdb/sections` | `{total_sections, sections: [{number, title, max_score, ...}]}` | Static array | N/A | `test_sections_stable_ordering` |
| UVDB | `UVDBAudits.tsx:72-75` (audits) | `uvdbApi.listAudits()` | `GET /api/v1/uvdb/audits` | `{total, audits: [{id, audit_reference, ...}]}` | `order_by(desc(audit_date), desc(id))` | `desc(id)` | `test_audits_ordered_by_date_desc` |
| UVDB | N/A (mapping tab) | `uvdbApi.getISOMapping()` | `GET /api/v1/uvdb/iso-mapping` | `{description, mappings, summary}` | Static data | N/A | `test_iso_mapping_returns_cross_mapping` |
| UVDB | N/A (dashboard) | `uvdbApi.getDashboard()` | `GET /api/v1/uvdb/dashboard` | `{summary, protocol, certification_alignment}` | N/A | N/A | `test_dashboard_returns_summary` |

## Frontend Mock Data Status

**IMPORTANT**: As of this PR, the frontend pages still use mock data:

| File | Lines | Mock Status | API Ready |
|------|-------|-------------|-----------|
| `PlanetMark.tsx` | 72-143 | `setTimeout()` with hardcoded data | ✅ `planetMarkApi` client added |
| `UVDBAudits.tsx` | 52-78 | `setTimeout()` with hardcoded data | ✅ `uvdbApi` client added |

Wiring the frontend to real APIs is a separate PR scope (Mock Data Eradication).

## Backend Route Implementations

### Planet Mark (`src/api/routes/planet_mark.py`)

| Endpoint | Line | Ordering Statement | Async Pattern |
|----------|------|--------------------|---------------|
| `/years` | 207 | `select(...).order_by(desc(CarbonReportingYear.year_number))` | ✅ SQLAlchemy 2.0 |
| `/dashboard` | 832 | `select(...).order_by(desc(CarbonReportingYear.year_number)).limit(3)` | ✅ SQLAlchemy 2.0 |
| `/years/{id}/actions` | 467 | `select(...).order_by(ImprovementAction.time_bound)` | ✅ SQLAlchemy 2.0 |
| `/years/{id}/scope3` | 416 | `select(...).order_by(Scope3CategoryData.category_number)` | ✅ SQLAlchemy 2.0 |
| `/years/{id}/sources` | 377 | `select(...).order_by(desc(EmissionSource.co2e_tonnes))` | ✅ SQLAlchemy 2.0 |

### UVDB (`src/api/routes/uvdb.py`)

| Endpoint | Line | Ordering Statement | Async Pattern |
|----------|------|--------------------|---------------|
| `/sections` | 465 | Static `UVDB_B2_SECTIONS` array | ✅ Static data |
| `/audits` | 516 | `select(...).order_by(desc(audit_date), desc(id))` | ✅ SQLAlchemy 2.0 |
| `/audits/{id}/responses` | 665 | `select(...).order_by(id)` | ✅ SQLAlchemy 2.0 |
| `/audits/{id}/kpis` | 726 | `select(...).order_by(desc(year))` | ✅ SQLAlchemy 2.0 |

## Determinism Guarantees

### Primary + Secondary Ordering

Every list endpoint that may return multiple rows uses:
1. **Primary sort**: Business-meaningful column (e.g., `year_number`, `audit_date`, `time_bound`)
2. **Secondary sort (tie-breaker)**: `id` or another unique column

Example from `/uvdb/audits`:
```python
stmt = stmt.order_by(desc(UVDBAudit.audit_date), desc(UVDBAudit.id))
```

### Static Data Endpoints

Some endpoints return static/constant data:
- `/uvdb/sections`: Returns `UVDB_B2_SECTIONS` constant (defined at module load)
- `/uvdb/protocol`: Returns static protocol structure
- `/uvdb/iso-mapping`: Returns computed-once mapping data

These are inherently deterministic.

## Error Response Contracts

All endpoints use consistent error responses:

| Status | Response Shape | When |
|--------|----------------|------|
| 200 | `{...data...}` | Success |
| 404 | `{"detail": "...not found"}` | Resource doesn't exist |
| 422 | `{"detail": [...validation errors...]}` | Input validation failed |
| 500 | `{"detail": "Internal server error"}` | Unexpected error (no stack traces) |

## Test Coverage

| Test File | Test Count | Coverage |
|-----------|------------|----------|
| `tests/integration/test_planet_mark_uvdb_contracts.py` | 19 | Endpoint contracts, ordering, error handling |
| `tests/e2e/test_planet_mark_uvdb_e2e.py` | 15 | User journeys, deterministic rendering |
| `tests/unit/test_quarantine_enforcement.py` | 5 | Quarantine script enforcement |

## Revision History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2026-01-27 | 1.0 | Platform Team | Initial provenance documentation |
