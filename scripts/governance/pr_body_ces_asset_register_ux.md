# Change Ledger (CES Asset Register UX / PR-B)

## 1) Summary
- **Feature / change name:** Hide removed assets and make safety asset compliance KPIs status-exclusive.
- **User goal:** Keep day-to-day asset views focused on operational stock, while retaining an explicit Removed view and prominent active-fail alerts.
- **Depends on:** PR-A CES location brand strip (#1249).
- **In scope:** Hide-removed toggle, exclusive horizon KPIs, vehicle reg normalisation, active-fail row styling.
- **Out of scope:** Auto-creating Actions for fail assets; CES re-import.

## 2) Impact Map
| Area | Change |
|------|--------|
| `frontend/src/pages/SafetyAssetRegister.tsx` | Hide-removed toggle (localStorage), scoped board, active-fail styling |
| `frontend/src/pages/safetyAssets/safetyAssetBoardHelpers.ts` | Exclusive KPIs, hide-removed filter, vehicle key normalisation |
| Tests | Helper + register coverage for hide-removed / vehicle merge / fail rows |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Frontend-only; no API, schema, or migration changes.
- **Breaking changes:** None. Status values and backend contracts unchanged.
- **Data safety:** Toggle preference is client-local (`qgp.safetyAssets.hideRemoved`).

## 4) Acceptance Criteria
- [x] AC-01: “Hide removed” is on by default, persisted at `qgp.safetyAssets.hideRemoved`, and affects board scope.
- [x] AC-02: Removed assets are always visible when the Removed hero band is selected.
- [x] AC-03: Overdue, due, and in-date KPIs exclude decommissioned assets; the Removed KPI uses the full board.
- [x] AC-04: Search, bands, table, and engineer/vehicle/type rollups use the scoped asset collection.
- [x] AC-05: Vehicle rollups normalize registrations by removing whitespace and uppercasing.
- [x] AC-06: Quarantined asset rows and their hero tile use destructive visual treatment.

## 5) Testing Evidence
- [x] Unit: helper coverage for hide removed, decommissioned past-due exclusion, and `GF67 FWD` / `GF67FWD` merge.
- [x] Unit: register coverage for default hide and Removed-band force inclusion.
- [ ] CI: run after PR opens.

## 6) Critical Journeys
- [x] CUJ-01: Manager opens the register and sees active/quarantined assets without removed historical records.
- [x] CUJ-02: Manager selects Removed and can inspect all decommissioned assets without changing the preference.
- [x] CUJ-03: Manager identifies a quarantined asset immediately from the fail tile and destructive table row.

## 7) Observability & Ops
- No new backend metrics. UI behaviour is client-side only; verify via staging Asset Register hero counts.

## 8) Release Plan
1. Merge after PR-A and CI green.
2. Staging: confirm GY71SXM-style vehicle totals drop Removed kit with hide-removed on.
3. Prod tip==LIVE.

## 9) Rollback Plan
- **Trigger:** Hero KPIs or vehicle totals regress / hide-removed preference stuck.
- **Steps:** Revert this PR; clear `qgp.safetyAssets.hideRemoved` in browser if needed.
- **Owner:** Platform team.

## 10) Evidence Pack
- CI linked on PR; helper/register Vitest evidence above.
- Vehicle-count challenge (from PR-A ledger): CES GY71SXM ≈ 65 rows with ~32 Removed — hide-removed addresses inflated Assets totals.

---

# Gate Checklist
- [x] **Gate 0:** Scope locked, acceptance criteria defined, ledger complete.
- [x] **Gate 1:** No API/data contract change; existing status contract retained.
- [ ] **Gate 2:** CI green (lint/type/build/tests).
- [ ] **Gate 3:** Staging verification complete.
- [x] **Gate 4:** Canary not required.
- [x] **Gate 5:** Rollback and operational checks defined.
