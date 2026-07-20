# Change Ledger (CL-TRAINING-MATRIX-COMPLIANCE)

## 1) Summary
- **Feature / Change name:** Training Matrix compliance layer (Atlas SoR + QGP frequency rules)
- **User goal (1–2 lines):** Treat Training as compliance (requirements, due dates, gaps, My Training + Atlas CTA), not an LMS. Atlas weekly CSV is completion source of truth; QGP owns role/dept → module frequency and gap views.
- **In scope:** Alembic tables + import/parser; name-map + requirements CRUD; compliance engine (Passed + frequency years); `/api/v1/training-matrix/*`; Training shell tabs (gaps / mine / inductions / admin); Atlas Hub CTA; EN/CY i18n; unit + Vitest proofs; this Change Ledger
- **Out of scope:** Building an LMS; auto-sync Atlas API; using Atlas Expiry as primary due date; Induction/Assessment product redesign beyond sibling tab retention; UVDB training clauses
- **Feature flag / kill switch:** N/A — additive Training surface; existing inductions remain under Inductions tab

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/pages/workforce/Training.tsx` — tab shell (gaps / mine / inductions / admin)
  - `frontend/src/pages/workforce/trainingMatrix/TrainingMatrixPanels.tsx` — gap board, My Training, Admin upload/maps/requirements
  - `frontend/src/pages/workforce/TrainingInductionsPanel.tsx` — prior inductions UI extracted
  - `frontend/src/api/trainingMatrixClient.ts` + `client.ts` export
  - Vitest: `Training.shell.test.tsx`
  - i18n: `en.json` / `cy.json` `workforce.training_matrix.*`
- **Backend (handlers/services):**
  - Models: `src/domain/models/training_matrix.py`
  - Parser / import / compliance services under `src/domain/services/training_matrix_*.py`
  - Routes: `src/api/routes/training_matrix.py`
  - Schemas: `src/api/schemas/training_matrix.py`
- **APIs (endpoints changed/added):** `/api/v1/training-matrix/*` — imports, QA, name-maps, requirements, courses, compliance, `/me`
- **Schemas/contracts:** New Pydantic schemas for training matrix
- **Database:** Alembic `20260731_training_matrix.py` (revises `20260730_api_idem`)
- **Workflows/jobs/queues:** None (manual weekly CSV upload)
- **Config/env/flags:** None (Atlas Hub URL constant in compliance service)
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tables + APIs; Training page restructured with Inductions preserved as a tab
- **Tolerant reader / strict writer applied?** Import tolerates sparse Atlas cells; compliance treats Expiry-without-Passed as incomplete (QA surfaced)
- **Breaking changes:** Training default view becomes Compliance gaps (not induction list). Inductions remain at `?tab=inductions`
- **Migration plan:** Run Alembic upgrade; admin uploads Atlas CSV; configure name maps + role/dept frequency rules
- **Rollback strategy (DB):** Revert PR; down-migration drops new training_matrix_* tables (no change to engineers/inductions)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin can upload Atlas Training Matrix CSV; import persists persons/courses/cells + QA counts
- [x] AC-02: Name-only Atlas ↔ employee mapping via admin name-map API/UI
- [x] AC-03: Role/dept → course + frequency (1/2/3y) requirements CRUD in Admin
- [x] AC-04: Due date = Atlas Passed + QGP frequency years (not Atlas Expiry as primary)
- [x] AC-05: Manager gap board + employee My Training list compliance rows with Atlas Hub CTA
- [x] AC-06: Inductions remain available as sibling tab on Training
- [x] AC-07: Parser unit tests + Training shell Vitest pass locally

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_training_matrix_parser.py` (4 passed local)
- [x] Unit tests — `Training.shell.test.tsx` (1 passed local)
- [ ] Integration tests — N/A this PR
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (compliance config + weekly upload lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Training → Admin → upload Atlas CSV → latest import/QA available
- [x] CUJ-02: Admin maps Atlas person name → employee; adds role/dept frequency rule → gap board shows due/overdue
- [x] CUJ-03: Employee → Training → My training → incomplete row opens Atlas Hub CTA
- [x] CUJ-04: Training → Inductions tab still lists/creates induction runs

## 7) Observability & Ops
- **Logs:** Import persist failures surface as API errors (existing patterns)
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Weekly Atlas CSV export → Admin upload; enter 2024 PDF role×module rules in Admin after first upload

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Migrate DB; upload sample Training Matrix Report.csv; map 2–3 people; add 1–2 requirements; confirm gap board due dates from Passed+years; confirm My Training + Atlas link; Inductions tab
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same as staging with live weekly export; confirm expiry-without-passed QA count is non-blocking

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Training page unusable; import corrupts tenant data; migration failure blocks deploy
- **Rollback steps:** Revert merge commit on main; redeploy previous SWA/API SHA; run Alembic downgrade for `20260731_train_mtx` if tables were applied
- **Owner:** Platform / Workforce Training track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- Atlas API auto-sync (weekly CSV remains)
- Full Welsh UX polish beyond new keys
- Bulk auto-map heuristics beyond exact normalized name match
- Manager email digests / scheduled gap reports

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Compliance-layer design locked (Atlas SoR, QGP frequency, Passed+years due)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready
