# Change Ledger (CES Asset Register UX / PR-B)

## Summary
- **Feature / change name:** Hide removed assets and make safety asset compliance KPIs status-exclusive.
- **User goal:** Keep day-to-day asset views focused on operational stock, while retaining an explicit Removed view and prominent active-fail alerts.
- **Depends on:** PR-A CES import and safety asset board data.
- **Rollback:** Revert this PR; no API, schema, or database changes.

## Acceptance Criteria
- [x] AC-01: “Hide removed” is on by default, persisted at `qgp.safetyAssets.hideRemoved`, and affects board scope.
- [x] AC-02: Removed assets are always visible when the Removed hero band is selected.
- [x] AC-03: Overdue, due, and in-date KPIs exclude decommissioned assets; the Removed KPI uses the full board.
- [x] AC-04: Search, bands, table, and engineer/vehicle/type rollups use the scoped asset collection.
- [x] AC-05: Vehicle rollups normalize registrations by removing whitespace and uppercasing.
- [x] AC-06: Quarantined asset rows and their hero tile use destructive visual treatment.

## Critical User Journeys
- [x] CUJ-01: Manager opens the register and sees active/quarantined assets without removed historical records.
- [x] CUJ-02: Manager selects Removed and can inspect all decommissioned assets without changing the preference.
- [x] CUJ-03: Manager identifies a quarantined asset immediately from the fail tile and destructive table row.

## Mapping Note
- UI-to-helper mapping: `SafetyAssetRegister.tsx` applies `applyHideRemoved` before hero bands, search, rows, and rollups; `safetyAssetBoardHelpers.ts` defines removed/fail predicates, exclusive horizons, and normalized vehicle keys.

## Testing Evidence
- [x] Unit: helper coverage for hide removed, decommissioned past-due exclusion, and `GF67 FWD` / `GF67FWD` merge.
- [x] Unit: register coverage for default hide and Removed-band force inclusion.
- [ ] CI: run after PR opens.

---

# Gate Checklist
- [x] **Gate 0:** Scope locked, acceptance criteria defined, ledger complete.
- [x] **Gate 1:** No API/data contract change; existing status contract retained.
- [ ] **Gate 2:** CI green (lint/type/build/tests).
- [ ] **Gate 3:** Staging verification complete.
- [x] **Gate 4:** Canary not required.
- [x] **Gate 5:** Rollback and operational checks defined.
