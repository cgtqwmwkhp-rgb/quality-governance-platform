# Change Ledger — H&S Incident Model Excel gap closure (PR-A through E)

## 1) Summary
- **Feature:** Close Excel H&S Incident Model gaps so SLT can retire the spreadsheet
- **Includes:** Injury spine, RIDDOR staff workflow, H&S KPI board (per 100k hours), historic workbook import, RTA parity
- **Out of scope:** Live HSE filing, UVDB LTIFR unit change, auto-Actions for every injury

## 2) Impact Map
| PR | Area |
|----|------|
| A | Incident injury/LTI/minor/body_parts + portal promote + IncidentDetail |
| B | RIDDOR editable + prepare pack enrichment (HSE submit stays stubbed) |
| C | `hs_reporting_periods` + `/hs-kpis` + H&S Performance page |
| D | `/hs-imports/excel` dry-run/commit + import UI |
| E | RTA collision_type/drivable/LTI/RIDDOR + RTADetail |

## 3) Compatibility & Data Safety
- Additive migrations `20260808` → `20260810`
- Import idempotent on excel sheet/id keys
- SLT rates use **per 100,000 hours**; UVDB remains per 1,000,000

## 4) Acceptance Criteria
- [x] AC-01: Staff can edit injury classification on incidents
- [x] AC-02: Portal body-map promotes is_injury/body_parts
- [x] AC-03: RIDDOR flags editable; prepare pack uses case fields; submit honest stub
- [x] AC-04: H&S Performance shows injuries/near misses/RTAs/LTI/RIDDOR/LTIFR/AFR
- [x] AC-05: Workbook dry-run/commit routes types correctly and skips duplicates
- [x] AC-06: RTA detail exposes collision type, drivable, LTI, RIDDOR

## 5) Testing Evidence
- Unit: injury promote, RIDDOR honesty, KPI rates, RTA normalize, Excel parser (13 focused tests)

## 6) Critical Journeys
- [x] CUJ-01: Staff classifies injury + RIDDOR on IncidentDetail
- [x] CUJ-02: SLT opens H&S Performance for YTD tiles
- [x] CUJ-03: Ops dry-runs then commits historic workbook

## 7) Observability & Ops
- Import warnings for undated/unknown rows
- Rate unit labelled in API/UI

## 8) Release Plan
1. Merge + migrate
2. Staging: smoke IncidentDetail, H&S board, workbook dry-run
3. Prod tip==LIVE; optional workbook commit; archive Excel

## 9) Rollback Plan
- **Trigger:** Migration/import/KPI regression
- **Steps:** Revert deploy; imported rows identifiable via `hs_excel_v2`
- **Owner:** Platform team

## 10) Evidence Pack
- CI on PR; unit suite linked above

# Gate Checklist
- [x] Gate 0: Scope + AC + ledger
- [x] Gate 1: API/data/UX contracts
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary N/A
- [x] Gate 5: Rollback defined
