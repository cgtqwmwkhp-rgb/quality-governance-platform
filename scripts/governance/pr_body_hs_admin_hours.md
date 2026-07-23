## Summary
Add Admin-managed **annual hours** for H&S reporting years so the Hours column (and LTIFR/AFR denominators) on Analytics → H&S Performance are driven by explicit manual entry, not only FTE pro-rata.

## Change Ledger
| Area | Change |
|---|---|
| Schema | `hs_reporting_periods.manual_hours` (nullable) |
| API | Periods list returns effective hours; PUT accepts `manual_hours` |
| KPI | Prefer `manual_hours` when set; else FTE pro-rata |
| Admin UI | `/admin/hs-reporting-hours` + nav + Admin Console card |
| Board UI | Hours source column + link to Admin |

## Impact Map
- H&S Performance board hours/rates
- Admin console navigation
- Alembic head → `20260811_hs_manual_hours`

## Compatibility
- Backward compatible: null `manual_hours` keeps calculated behaviour
- Existing periods continue to work without backfill

## Acceptance Criteria
- AC-01: Admin can open `/admin/hs-reporting-hours` and see reporting years with editable annual hours
- AC-02: Saving annual hours persists `manual_hours` and H&S Performance Hours column updates to that value with source “Manual”
- AC-03: When `manual_hours` is null, board continues to show FTE-calculated hours with source “Calculated”

## Testing Evidence
- Unit: `tests/unit/test_hs_kpi_service.py` (manual prefer + FTE fallback)
- Manual: Admin save year → refresh `/analytics/hs-performance` Hours/Source

## Critical Journeys
- CUJ-01: Admin updates 2025 hours → board Hours + AFR/LTIFR denominator refresh
- CUJ-02: Fresh tenant defaults still calculate hours until first manual save

## Observability
- No new metrics; API PUT failures surface as toast + HTTP error

## Release Plan
1. Merge squash to main
2. Alembic migrates `manual_hours`
3. Confirm tip==LIVE; Admin → H&S reporting hours; set Excel hours if desired

## Rollback Plan
- Owner: Platform / H&S admin
- Rollback steps: revert deploy; optional downgrade drops `manual_hours` (board returns to calculated)

## Evidence Pack
- PR diff + unit tests + Admin/Board screenshots post-deploy

## Gate Checklist
- Gate 0: Scope locked (manual hours admin only)
- Gate 1: Schema + API + UI wired
- Gate 2: Unit tests green
- Gate 3: CI green
- Gate 4: tip==LIVE
- Gate 5: Admin save verified on board
