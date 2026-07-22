# Change Ledger (CL-PULSE-CES-ADMIN)

## 1) Summary
- **Feature / Change name:** Pulse sparklines + recent-cases cascade + CES skip-error commit + Admin pending-lookup badge
- **User goal:** See weekly progression on Pulse tiles; switch Recent cases across Incidents/NM/Complaints/RTAs; CES import must create provisional Safety lookups even when some rows error; Admin nav must surface pending approval count.
- **In scope:** Exec-dashboard weekly series; FE sparklines + RecentCasesPanel; CES `can_commit` skip-error path; Layout Admin/Lookups badges; LookupTables UX honesty (form cards ≠ Safety CES panel)
- **Out of scope:** Form-builder Tools/Locations LookupOption seeding from CES; rewriting AMBIGUOUS_SERIAL matching rules beyond skip-on-commit

## 2) Impact Map
- **Backend:** `executive_dashboard.py` / schemas — weekly series for incidents, complaints, near misses, audits, training/tool compliance; `ces_asset_import_service.py` — `can_commit` + skip-error commit
- **Frontend:** PulseTrendsStrip sparklines; RecentCasesPanel; SafetyAssetRegister commit gate/copy; Layout pending badge; LookupTables clarifications
- **APIs:** Additive `can_commit` / `skipped_error_rows` on CES report; additive trend series keys on executive dashboard

## 3) Compatibility & Data Safety
- Additive response fields; commit of valid rows only (errors skipped); provisional lookups still commit-only
- Fail-honest sparklines: render only when ≥2 real points

## 4) Acceptance Criteria
- [x] AC-01: Pulse tiles show sparklines when weekly series ≥2 points
- [x] AC-02: Recent cases panel tabs: Incidents / Near misses / Complaints / RTAs
- [x] AC-03: CES dry-run with valid_rows>0 and row errors still enables Commit (skips error rows)
- [x] AC-04: Unresolved similar-lookup confirmations still block commit
- [x] AC-05: On commit, new types/locations land in Admin → Safety pending queue
- [x] AC-06: Admin hub + Lookups nav show pending Safety lookup count badge
- [x] AC-07: Form Tools/Locations/Assets cards clarify they are not CES Safety lookups

## 5) Testing Evidence
- [x] `pytest tests/unit/test_ces_asset_import_service.py tests/unit/test_executive_dashboard_response_hardening.py` — 17 passed
- [x] `vitest` Dashboard + PulseSparkline + Layout — 28 passed

## 6) Critical Journeys
- [x] Dry-run 1866 valid / 15 errors → Commit enabled → provisional Safety lookups queued → Admin badge increments
- [x] Dashboard org persona sees Pulse sparklines + Recent cases tabs

## 7–10) Ops / Release / Rollback
- FE+API additive; rollback by revert. No DB migration in this change.
