# Change Ledger (CL-TRAINING-MATRIX-UPLOAD-OPS)

## 1) Summary
- **Feature / Change name:** Training Matrix weekly Atlas upload ops — last-upload audit, overwrite confirm, collapsible Admin, Friday in-app reminder
- **User goal (1–2 lines):** Make the weekly Atlas CSV upload robust and auditable: retain the latest snapshot until the next upload overwrites it, confirm before overwrite, show who/when last uploaded, collapse Admin sections so the frequency matrix is usable, and remind admins every Friday via the standard notification bell.
- **In scope:** Import response uploader fields; Admin last-upload panel + overwrite confirm + CSV-only messaging; collapsible Admin sections + taller frequency grid; Compliance gaps last-upload stamp + clearer % copy; Celery Friday in-app reminder to admins (deduped per ISO week); Employee Portal My Work personal training compliance (OK / needs attention / due dates / Open Atlas)
- **Out of scope:** Accepting XLSX; changing due-date / compliance math; fixing sparse Atlas Passed data that drives 0% fully-compliant; Planet Mark; deep-linking to a specific Atlas course page (hub login URL only)
- **Feature flag / kill switch:** Reminder admin role via `TRAINING_MATRIX_UPLOAD_ADMIN_ROLE` (default `admin`); disable by removing the beat entry / not running the worker

## 2) Impact Map (what changed)
- **Frontend:**
  - `trainingMatrix/TrainingMatrixPanels.tsx` — collapsible Admin sections; last-upload stamp; overwrite confirm; taller frequency matrix; gap board last-upload line + clearer compliance % label
  - `api/trainingMatrixClient.ts` — `uploaded_by_*` fields on `TrainingMatrixImport`
  - `pages/PortalWork.tsx` + `pages/Portal.tsx` — employee portal My Work training compliance section + home badge for training gaps
  - Workforce shell tests mock `getLatestImport`; PortalWork tests cover Atlas CTA
- **Backend:**
  - `src/api/schemas/training_matrix.py` — `uploaded_by_user_id` / `uploaded_by_name` / `uploaded_by_email` on import response
  - `src/api/routes/training_matrix.py` — `_import_response` join to User; clearer non-CSV validation message
  - `src/infrastructure/tasks/training_matrix_upload_reminder_tasks.py` (new) — Friday reminder helpers + Celery task
  - `src/infrastructure/tasks/celery_app.py` — register module + Friday 08:00 UTC beat
- **APIs:** Additive fields on `GET/POST /api/v1/training-matrix/imports*`
- **Schemas/contracts:** Additive optional fields only
- **Database:** None (uploader already stored on `training_matrix_imports`)
- **Workflows/jobs/queues:** New Celery beat `remind-training-matrix-upload` → `notifications` queue
- **Config/env/flags:** Optional `TRAINING_MATRIX_UPLOAD_ADMIN_ROLE`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response fields; persistence model unchanged (latest-import replaces prior cells; import metadata rows append)
- **Tolerant reader / strict writer applied?** Yes — older clients ignore new fields
- **Breaking changes:** None (still CSV-only; error message clarified)
- **Migration plan:** Deploy API/FE; ensure Celery beat/worker pick up the new schedule
- **Rollback strategy (DB):** N/A (no schema change)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin shows last upload time, uploader name/email, and filename when a snapshot exists
- [x] AC-02: Re-upload with an existing snapshot prompts overwrite confirmation before calling the API
- [x] AC-03: Non-CSV files are rejected with an Atlas CSV guidance message (FE pre-check + BE validation)
- [x] AC-04: Admin sections (Upload / Name mapping / Frequency matrix) are independently collapsible; frequency grid uses a taller scroll viewport
- [x] AC-05: Compliance gaps shows the Atlas snapshot stamp (or “none yet”)
- [x] AC-06: Friday Celery task creates one in-app notification per admin per ISO week, deep-linking to `/workforce/training?tab=admin`

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `pytest tests/unit/test_training_matrix_upload_reminder_tasks.py`
- [ ] Lint / typecheck / CI — after PR open
- [ ] Staging — confirm upload overwrite + last-upload stamp + Friday reminder (or manual task invoke)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin opens Training → Admin, sees last upload metadata, collapses name mapping, edits frequency matrix in the taller grid
- [x] CUJ-02: Admin uploads a new Atlas CSV when a prior snapshot exists → confirm dialog → cells replaced; stamp updates to new who/when
- [x] CUJ-03: Friday reminder task builds a standard in-app notification for admins with last-upload context and Admin deep link

## 7) Observability & Ops
- **Logs:** Reminder task logs created/skipped counts
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** Weekly ops = Friday notification → Admin → Upload CSV (overwrite)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Upload CSV as admin; confirm stamp; re-upload with confirm; collapse sections; invoke `remind_training_matrix_upload` once and check bell
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same; confirm Celery beat includes Friday entry

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Reminder spam or upload UX regression blocking weekly import
- **Rollback steps:** Revert PR; stop/remove beat entry if needed. No DB rollback required.
- **Owner:** Platform / Workforce Training track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- XLSX ingest
- Auto-opening name mapping when unmatched > 0 (starts collapsed so frequency matrix stays visible)
- Changing Overall % definition (still “every required module OK”)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Design locked (latest-import overwrite + confirm + last-upload stamp + Friday in-app reminder + collapsible Admin)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready
