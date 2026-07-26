# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Run 021 Wave 2 — Workforce display honesty (PX-238, PX-307, PX-189 verify)
- **User goal (1–2 lines):** Managers read employee names (not raw IDs) in the Skills Matrix; employees see training gaps without a QGP due date labelled honestly as "Not started" rather than "Overdue"; workforce dashboard copy stays user-facing.
- **In scope:** PX-238 (P1) engineer-matrix `display_name` join + CompetencyDashboard labels; PX-307 (P2) horizon/status honesty in shared training-matrix helpers (FE + BE) and portal training badge; PX-189 (P3) verified already fixed on main; unit tests; this Change Ledger
- **Out of scope:** PX-310 (document-campaign duplicate assignments — different module/API); PX-168 licensing; search/Layout/Documents/Incidents; portal forms; investigations closure; audits UVDB; `.size-limit.json`; Dependabot
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/pages/workforce/CompetencyDashboard.tsx` — matrix rows use `display_name` via `matrixEngineerLabel`
  - `frontend/src/pages/workforce/employeePickerUtils.ts` — new `matrixEngineerLabel` helper
  - `frontend/src/pages/workforce/trainingMatrix/trainingMatrixBoardHelpers.ts` — `horizonForRow` / `statusLabel` no longer treat null-due gaps as overdue
  - `frontend/src/pages/PortalWork.tsx` — training badge variant respects null QGP due date (consumes shared helpers)
- **Backend (handlers/services):**
  - `src/api/routes/wdp_analytics.py` — engineer-matrix rows include `display_name`
  - `src/domain/services/training_matrix_board.py` — mirror horizon fix for manager board overdue counts
- **APIs (endpoints changed/added):** `GET /api/v1/wdp-analytics/engineer-matrix` — additive `display_name` on each engineer row
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `WDPEngineerMatrixRow.display_name`; `WdpEngineerMatrix` TS type
- **Database (migrations/entities/indexes):** None — reads existing `Engineer.display_name`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **i18n:** None (PX-189 honesty copy already user-facing on main)
- **Tests:**
  - `frontend/src/pages/workforce/__tests__/CompetencyDashboard.test.tsx`
  - `frontend/src/pages/workforce/employeePickerUtils.test.ts`
  - `frontend/src/pages/workforce/trainingMatrix/trainingMatrixBoardHelpers.test.ts`
  - `frontend/src/pages/__tests__/PortalWork.test.tsx`
  - `tests/unit/test_wdp_analytics_controls.py`
  - `tests/unit/test_training_matrix_board.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API field (`display_name` optional/nullable); tolerant FE fallbacks to employee number then `#id`
- **Tolerant reader / strict writer applied?** Yes — FE handles null `display_name`; horizon logic only counts past-due when `qgp_due_on` exists
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert deploy

## 4) Acceptance Criteria (AC)
- [x] AC-01 (PX-238): Skills Matrix row labels show `display_name` when present; fall back to employee number, never raw `#id` when a name exists in API
- [x] AC-02 (PX-307): Training rows with `qgp_due_on == null` and gap status render "Not started" (not "Overdue"); manager/portal overdue counts exclude them
- [x] AC-03 (PX-189): Workforce dashboard honesty note uses user language (no `role_key` / `job_title = role_key` developer copy) — verified on main, regression asserted in CompetencyDashboard test

## 5) Testing Evidence (link to runs)
- [x] Unit — `npx vitest run` on CompetencyDashboard, employeePickerUtils, trainingMatrixBoardHelpers, PortalWork (52 passed)
- [x] Unit — `python3.11 -m pytest tests/unit/test_training_matrix_board.py tests/unit/test_wdp_analytics_controls.py` (22 passed)
- [ ] Full CI — linked after PR checks
- [ ] Staging smoke — deferred to Gate 3

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open `/workforce/dashboard` → Skills Matrix shows employee display names → cell drill-down to profile
- [x] CUJ-02: Open `/portal/work` → Training compliance "Needs attention" → module with no Atlas Passed date shows "Not started", not "Overdue"

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Supervisor login → Competency Dashboard matrix names; portal employee → Training compliance gap badges for unscheduled modules
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Matrix readable by name; portal overdue headline not inflated by never-scheduled modules

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Matrix labels blank; overdue counts drop incorrectly for genuinely past-due modules
- **Rollback steps:** Revert FE + BE deploy / merge revert of this PR
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Defect pack: QGP Run 021 — PX-238, PX-307, PX-189
- Staging deploy evidence: pending

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — additive `display_name`; horizon semantics documented in AC
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
