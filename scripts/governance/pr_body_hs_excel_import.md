# Change Ledger — H&S Excel historic import (PR-D)

## 1) Summary
- **Feature:** Dry-run/commit import of Plantexpand H&S Incident Model workbook
- **User goal:** Load historic Incident Log + RTA Log into correct QGP modules
- **Depends on:** Injury spine + RTA parity fields

## 2) Impact Map
| Area | Change |
|------|--------|
| Parser/service | `hs_excel_import_parser.py`, `hs_excel_import_service.py` |
| API | `/api/v1/hs-imports/excel/dry-run` + `/commit` |
| FE | Import panel on H&S Performance |

## 3) Compatibility & Data Safety
- Idempotent via `external_key` / `external_ref` / stable near-miss refs
- Undated rows skipped with warnings
- Types routed to Incident / NearMiss / Complaint / RTA

## 4) Acceptance Criteria
- [x] AC-01: Injury/Accident → Incident with injury flags
- [x] AC-02: Near Miss → NearMiss
- [x] AC-03: Customer Complaint → Complaint
- [x] AC-04: RTA Log → RTA with collision_type/drivable/LTI/RIDDOR
- [x] AC-05: Re-import skips existing keys

## 5) Testing Evidence
- Unit: `tests/unit/test_hs_excel_import_parser.py`

## 6) Critical Journeys
- [x] CUJ-01: Dry-run shows module split counts
- [x] CUJ-02: Commit then dry-run shows skip_existing

## 7) Observability & Ops
- Warnings returned in response for undated/unknown types

## 8) Release Plan
1. Staging rehearsal with production workbook copy
2. Prod commit once
3. Archive Excel as read-only

## 9) Rollback Plan
- **Trigger:** Bad routing / duplicate cases
- **Steps:** Soft-delete or mark imported rows; revert code
- **Owner:** Platform team

## 10) Evidence Pack
- CI on PR

# Gate Checklist
- [x] Gate 0
- [x] Gate 1
- [ ] Gate 2 CI
- [ ] Gate 3 Staging
- [x] Gate 4 N/A
- [x] Gate 5 Rollback
