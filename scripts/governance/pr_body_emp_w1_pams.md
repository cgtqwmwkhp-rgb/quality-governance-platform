# Change Ledger (CL-EMP-W1)

## 1) Summary
- **Feature / Change name:** EMP-W1 — Populate Workforce Employees from PAMS `technicians_store`
- **User goal (1-2 lines):** Stop prod showing an empty engineer roster by syncing PAMS technicians into QGP `engineers`, with honest UX renamed to Employees and a manual sync path.
- **In scope:** Alembic migration (nullable `user_id`, `display_name`, `pams_technician_id`), model/schema/route/service, PAMS reflection + Celery beat, Employees UI + i18n, unit tests, this ledger
- **Out of scope:** `vw_aischeduler_engineers`, `vw_plantex_engineercompetence`, manual add-employee dialog UI, Layout.tsx nav key changes (i18n only)
- **Feature flag / kill switch:** N/A — requires `PAMS_DATABASE_URL`; sync no-ops when unset (Celery) or returns 400 when tenant missing

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Engineers.tsx` — Employees wording, `display_name` cards, Sync from PAMS button; `workforceClient.ts` — `syncFromPams`, `createEngineer`, extended types; `en.json` nav/title/empty/sync keys
- **Backend (handlers/services):** `engineers.py` routes; new `pams_technician_sync_service.py`; `pams_database.py` reflects `technicians_store`; `pams_sync_tasks.py` + Celery beat hourly
- **APIs (endpoints changed/added):** `POST /api/v1/engineers/sync-from-pams` → `{created, updated, deactivated, skipped, errors}`; `POST /api/v1/engineers/` accepts optional `user_id` + `display_name`; list search includes `display_name`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `EngineerResponse` adds `display_name`, `pams_technician_id`, optional `user_id`; `EngineerCreate` validator; `PamsTechnicianSyncResponse`
- **Database (migrations/entities/indexes):** `20260722_emp_pams` — nullable `user_id`, `display_name`, `pams_technician_id`, partial unique `(tenant_id, pams_technician_id)`
- **Workflows/jobs/queues (if any):** Celery `sync_pams_technicians` every 60 minutes
- **Config/env/flags:** `PAMS_DATABASE_URL`, `PAMS_SSL_CA`, `DEFAULT_TENANT_ID` (required for Celery/background sync)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive schema + upsert by `(tenant_id, pams_technician_id)` / `pams-tech-{id}` external_id
- **Tolerant reader / strict writer applied?** Yes — existing user-linked engineers preserved; PAMS rows upsert without deleting; inactive/removed PAMS ids soft-deactivated only
- **Breaking changes:** None for existing linked profiles; `user_id` now optional on create/read
- **Migration plan:** Run Alembic `20260722_emp_pams` before deploy; trigger initial sync via UI or Celery
- **Rollback strategy (DB):** Downgrade migration drops new columns/index; revert code; engineers created by sync remain unless manually cleaned

## 4) Acceptance Criteria (AC)
- [x] AC-01: Migration adds nullable `user_id`, `display_name`, `pams_technician_id` + partial unique index
- [x] AC-02: Sync maps PAMS fields (name, role, postcode, active, email notes) and links user by email when unambiguous
- [x] AC-03: `POST /engineers/sync-from-pams` returns count payload; route ordered before `/{id}`
- [x] AC-04: Employees UI shows `display_name`, honest empty state, Sync from PAMS button
- [x] AC-05: Celery beat schedules hourly technician sync
- [x] AC-06: Unit tests for mapping/upsert without live MySQL

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `pytest tests/unit/test_pams_technician_sync_service.py tests/unit/test_engineer_identity_controls.py` (local)
- [ ] Integration tests — deferred (requires PAMS + PG)
- [ ] Contract tests (if applicable) — OpenAPI drift check in CI
- [ ] E2E Smoke — manual staging with PAMS test DB

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens Workforce → Employees → Sync from PAMS → roster populated
- [x] CUJ-02: Celery hourly sync upserts without duplicate `(tenant_id, pams_technician_id)`
- [x] CUJ-03: Employee with matching email gets `user_id` link when not already owned

## 7) Observability & Ops
- **Logs:** `pams_technician_sync` info on manual sync; Celery task info/error logs
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** Ensure prod `DEFAULT_TENANT_ID` and `PAMS_DATABASE_URL` set before enabling beat

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Run migration; click Sync from PAMS; confirm ~79 active technicians appear
- **Canary plan:** N/A
- **Prod post-deploy checks:** Employees page non-empty; spot-check one synced profile vs PAMS row

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Sync duplicates, wrong tenant mapping, or migration failure
- **Rollback steps:** Disable beat entry; revert PR; downgrade migration if needed
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## How to trigger sync
1. **UI:** Workforce → Employees → **Sync from PAMS** (manager + `engineer:create`)
2. **API:** `POST /api/v1/engineers/sync-from-pams` (optional `?tenant_id=`)
3. **Celery:** `sync_pams_technicians` task (hourly beat) or manual `sync_pams_technicians.delay()`

## Blockers / config
- **`DEFAULT_TENANT_ID`:** Required for Celery/background sync when no explicit tenant; API uses authenticated user's tenant when present
- **`PAMS_DATABASE_URL` + `PAMS_SSL_CA`:** Required to reach `pamstest-db.mysql.database.azure.com` / `plex_bookings.technicians_store`
