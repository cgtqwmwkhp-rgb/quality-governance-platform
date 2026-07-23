## Summary
Close the remaining H&S field-honesty gaps: NearMiss HiPo, RTA third-party injury rollup, and first-class lessons learnt on case close — fully wired through API, portal/staff UI, Excel import, and H&S Performance.

## Change Ledger
| Area | Change |
|---|---|
| Schema | `near_misses.is_hipo`; `road_traffic_collisions.third_party_injured`; `lessons_learnt` on incidents/near_misses/RTAs/complaints |
| Near Miss | Portal HiPo control; staff create/detail/list badge; import `is_hipo`; KPI `hipo_near_misses` |
| RTA | Portal third-party injured + per-party toggles; staff sync; Excel `third_party_injury` persist + party seed |
| Lessons | Soft close confirm; investigation §7 promote; Excel notes mapping; SLT extract on H&S board |
| Migrations | `20260813_hs_hipo_rta` → `20260814_hs_lessons` |

## Impact Map
- Near Miss / RTA / Incident / Complaint detail + portal intake
- H&S Performance KPI cards/table + lessons extract
- Historic Excel import honesty for HiPo / third-party injury / notes

## Compatibility
- Defaults: `is_hipo=false`; `third_party_injured` null when unknown
- Soft close gate only (never hard-blocks CLOSED)
- Investigation promote fills empty case lessons only (no overwrite)

## Acceptance Criteria
- AC-01: Near-miss Excel HiPo lands on `NearMiss.is_hipo` and appears on H&S Performance HiPo count
- AC-02: RTA Excel `third_party_injury=Y` sets `third_party_injured` and seeds an injured party when JSON empty
- AC-03: Closing a case without lessons prompts confirm; with lessons saves without prompt
- AC-04: Investigation lessons text promotes to linked case when case field empty

## Testing Evidence
- `tests/unit/test_rta_injury_fields.py`
- `tests/unit/test_lessons_learnt_promote.py`
- `tests/integration/test_portal_submission_snapshots.py` (RTA injured)
- `node scripts/i18n-check.mjs`

## Critical Journeys
- CUJ-01: Portal near miss HiPo Yes → staff badge + KPI
- CUJ-02: Portal RTA third-party injured → rollup true on detail
- CUJ-03: Staff close without lessons → confirm; cancel keeps open edit

## Observability
- No new metrics; save/import failures via existing toast/HTTP paths

## Release Plan
1. Squash-merge to main
2. Alembic applies both migrations
3. Confirm tip==LIVE; smoke HiPo + RTA injury + lessons close
4. Historic Excel Commit remains ops-gated (Round 2/3 after D1–D6)

## Rollback Plan
- Owner: Platform / H&S
- Steps: revert deploy; optional alembic downgrade of `20260814` then `20260813`

## Evidence Pack
- PR diff + unit/integration tests + post-deploy tip==LIVE check

## Gate Checklist
- Gate 0: Scope locked (P0 field honesty + P1 lessons; no historic Commit)
- Gate 1: Schema + API + UI wired
- Gate 2: Unit/integration green
- Gate 3: CI green
- Gate 4: tip==LIVE
- Gate 5: Smoke AC-01–04
