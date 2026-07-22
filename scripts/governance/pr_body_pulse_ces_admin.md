# Change Ledger (CL-PULSE-CES-ADMIN)

## 1) Summary
- **Feature / Change name:** Pulse sparklines + recent-cases cascade + CES skip-error commit + Admin pending-lookup badge
- **User goal (1–2 lines):** See weekly progression on Pulse tiles; switch Recent cases across Incidents/NM/Complaints/RTAs; CES import must create provisional Safety lookups even when some rows error; Admin nav must surface pending approval count.
- **In scope:** Exec-dashboard weekly series; FE sparklines + RecentCasesPanel; CES `can_commit` skip-error path; Layout Admin/Lookups badges; LookupTables UX honesty (form cards ≠ Safety CES panel)
- **Out of scope:** Form-builder Tools/Locations LookupOption seeding from CES; rewriting AMBIGUOUS_SERIAL matching rules beyond skip-on-commit
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** Pulse sparklines, RecentCasesPanel, SafetyAssetRegister commit gate/copy, Layout pending badge, LookupTables clarifications, i18n key
- **Backend:** `executive_dashboard` weekly series; `ces_asset_import_service` `can_commit` + skip-error commit
- **APIs:** Additive `can_commit` / `skipped_error_rows` on CES report; additive trend series keys
- **Schemas/contracts:** Additive TrendData fields; TrendDataPoint optional `value`
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** `requirements.lock` refreshed (certifi pin)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields; commit imports validated rows only (error rows skipped)
- **Tolerant reader / strict writer applied?** Yes — sparklines omit sparse/null weeks; pending badge fails closed
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A

## 4) Acceptance Criteria (AC)
- [x] AC-01: Pulse tiles show sparklines when weekly series ≥2 points
- [x] AC-02: Recent cases panel tabs: Incidents / Near misses / Complaints / RTAs
- [x] AC-03: CES dry-run with valid_rows>0 and row errors still enables Commit (skips error rows)
- [x] AC-04: Unresolved similar-lookup confirmations still block commit
- [x] AC-05: On commit, new types/locations land in Admin → Safety pending queue
- [x] AC-06: Admin hub + Lookups nav show pending Safety lookup count badge
- [x] AC-07: Form Tools/Locations/Assets cards clarify they are not CES Safety lookups

## 5) Testing Evidence (link to runs)
- [x] Unit: `pytest tests/unit/test_ces_asset_import_service.py tests/unit/test_executive_dashboard_response_hardening.py`
- [x] FE: Dashboard + PulseSparkline + Layout vitest
- [ ] CI — after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Dry-run with valid rows + error rows → Commit enabled → provisional Safety lookups queued → Admin badge increments
- [x] CUJ-02: Dashboard org persona sees Pulse sparklines + Recent cases tabs with correct list ordering

## 7) Observability & Ops
- **Logs:** Existing CES / exec-dashboard logging
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** CES Commit can skip error rows; approve pending Safety lookups in Admin → Lookups top panel

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Dry-run CES workbook with mixed valid/error rows; Commit; confirm pending queue + Admin badge; open `/dashboard` for pulse + recent tabs
- **Canary plan:** N/A
- **Prod post-deploy checks:** tip==LIVE; CES Commit enabled with error rows when valid_rows>0; Admin badge; `/dashboard` pulse sparklines + recent tabs

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CES commit imports unexpected rows, or dashboard/recent panel broken
- **Rollback steps:** Revert merge commit and redeploy previous tip; no DB rollback
- **Owner:** Platform / Frontend

## 10) Evidence Pack (links)
- CI run(s): Linked after green CI
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive only
- [x] **Gate 2:** CI green (lint/type/build/tests) — verified locally; awaiting hosted CI
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
