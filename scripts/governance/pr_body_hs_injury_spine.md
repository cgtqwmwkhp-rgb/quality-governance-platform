# Change Ledger — H&S injury classification spine (PR-A)

## 1) Summary
- **Feature:** First-class injury / LTI / minor injury / body parts on Incident
- **User goal:** Staff can classify injuries for SLT KPIs; portal body-map promotes into columns
- **Out of scope:** H&S KPI board, historic import, RTA parity, live HSE filing

## 2) Impact Map
| Area | Change |
|------|--------|
| `incidents` table | Alembic `20260808_hs_injury` |
| Incident schemas/API | Create/Update/Response expose injury + RIDDOR fields |
| Portal create | Promote injuries → `is_injury` / `body_parts` |
| IncidentDetail | Injury & classification edit card |

## 3) Compatibility & Data Safety
- Additive columns with safe defaults (`false` / null)
- Existing portal snapshot retained in `reporter_submission`
- RIDDOR columns already existed; now writable via update schema

## 4) Acceptance Criteria
- [x] AC-01: Staff can set is_injury, minor, LTI, days_lost, body_parts, first aid
- [x] AC-02: Portal body-map promotes is_injury + body_parts
- [x] AC-03: Values persist via PATCH and return on GET
- [x] AC-04: Migration revises `20260807_ces_loc_brand`

## 5) Testing Evidence
- Unit: `tests/unit/test_incident_injury_promote.py`

## 6) Critical Journeys
- [x] CUJ-01: Staff edits injury classification on IncidentDetail and saves
- [x] CUJ-02: Portal report with injuries creates incident with is_injury true

## 7) Observability & Ops
- No new metrics

## 8) Release Plan
1. Merge after CI green
2. Staging migrate + smoke IncidentDetail injury card
3. Prod tip==LIVE

## 9) Rollback Plan
- **Trigger:** Incident update fails or migration issues
- **Steps:** Revert deploy; columns nullable-safe with defaults
- **Owner:** Platform team

## 10) Evidence Pack
- CI on PR

# Gate Checklist
- [x] Gate 0: Scope + AC + ledger
- [x] Gate 1: API/data contracts defined
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [ ] Gate 4: Canary N/A
- [x] Gate 5: Rollback defined
