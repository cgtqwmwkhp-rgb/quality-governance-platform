# Change Ledger (CL-VAN-PAMS-503)

## 1) Summary
- **Feature / Change name:** VAN — PAMS 503 Honest UI
- **User goal (1-2 lines):** Make van checklist list responses and UI honest about cached vs live PAMS data, and expose retry affordances when checklist loads fail.
- **In scope:** Additive list response metadata, cache/live route annotations, external-service error code alignment, Vehicle Checklists stale-data banner and retry button, focused backend/frontend tests.
- **Out of scope:** Navigation/layout changes, generated client types, Alembic/database schema, investigation screens, broader PAMS sync behavior.
- **Feature flag / kill switch:** N/A — additive API fields and non-blocking UI messaging only.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/VehicleChecklists.tsx` reads additive list metadata locally, shows "Data may be stale" for cache responses, and offers Retry for checklist load errors.
- **Backend (handlers/services):** `src/api/routes/vehicle_checklists.py` marks cache responses as `source="cache"` with `cache_as_of`; live responses as `source="live"`; PAMS unavailable helper uses `EXTERNAL_SERVICE_ERROR` with HTTP 503.
- **APIs (endpoints changed/added):** Existing `GET /api/v1/vehicle-checklists/daily` and `GET /api/v1/vehicle-checklists/monthly` responses gain optional `source` and `cache_as_of` fields.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `ChecklistListResponse` adds optional `source: Optional[str] = None` and `cache_as_of: Optional[str] = None`.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tolerant-reader API fields; existing consumers can ignore `source` and `cache_as_of`.
- **Tolerant reader / strict writer applied?** Yes — frontend casts the response locally and does not require generated client type changes.
- **Breaking changes:** None.
- **Migration plan:** No migration required.
- **Rollback strategy (DB):** No DB changes; revert code commit if needed.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `ChecklistListResponse` includes optional `source` and `cache_as_of` fields.
- [x] AC-02: Cache list path returns `source="cache"` and `cache_as_of` as max returned row `synced_at`, or `None`.
- [x] AC-03: Live PAMS list path returns `source="live"` and `cache_as_of=None`.
- [x] AC-04: PAMS unavailable helper keeps HTTP 503 and uses `EXTERNAL_SERVICE_ERROR`.
- [x] AC-05: Vehicle Checklists UI tracks source/cache timestamp from list responses without editing generated client types.
- [x] AC-06: Cache responses show a non-blocking amber "Data may be stale" banner with cache timestamp when present.
- [x] AC-07: Checklist load errors show a Retry button that calls `loadChecklists` again.
- [x] AC-08: Backend and frontend tests cover cache metadata, live failure error code, stale banner, and retry UI.
- [x] AC-09: Exclusive allowlist observed: `src/api/schemas/vehicle_checklist.py`, `src/api/routes/vehicle_checklists.py`, `tests/unit/test_vehicle_checklists_pams_honesty.py`, `frontend/src/pages/VehicleChecklists.tsx`, `frontend/src/pages/__tests__/VehicleChecklists.test.tsx`, `scripts/governance/pr_body_van_pams_503.md`.

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after PR creation.
- [ ] Typecheck — CI after PR creation.
- [ ] Build — CI after PR creation.
- [x] Unit tests — targeted backend and frontend tests run locally.
- [ ] Integration tests — deferred to CI/staging with configured PAMS/cache data.
- [ ] Contract tests (if applicable) — OpenAPI/contract checks in CI.
- [ ] E2E Smoke — staging checklist smoke after merge/deploy.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens Daily Van Checklists served from cache and sees "Data may be stale" with cache timestamp.
- [x] CUJ-02: Manager opens Monthly/Daily Van Checklists served live and does not see a stale-cache warning.
- [x] CUJ-03: Manager hits a checklist load failure and can retry from the error banner without leaving the tab.

## 7) Observability & Ops
- **Logs:** Existing PAMS live query exception logging retained.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Open `/vehicle-checklists`, verify cache banner appears when list response reports `source="cache"`; simulate/observe 503 and confirm retry button appears.
- **Canary plan:** N/A.
- **Prod post-deploy checks:** Confirm checklist data loads and source metadata does not break existing consumers; spot-check cached response timestamp.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Checklist page fails to render, list API response validation fails, or error envelope regression is detected.
- **Rollback steps:** Revert this commit and redeploy previous SHA; no DB rollback required.
- **Owner:** Platform / Vehicle Compliance track.

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation.
- Staging deploy evidence: N/A until deployment.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable).
- [ ] **Gate 2:** CI green (lint/type/build/tests).
- [ ] **Gate 3:** Staging verification complete (evidence linked).
- [ ] **Gate 4:** Canary healthy (if used).
- [x] **Gate 5:** Production verification plan + monitoring ready.

## Exclusive Allowlist
- `src/api/schemas/vehicle_checklist.py`
- `src/api/routes/vehicle_checklists.py`
- `tests/unit/test_vehicle_checklists_pams_honesty.py`
- `frontend/src/pages/VehicleChecklists.tsx`
- `frontend/src/pages/__tests__/VehicleChecklists.test.tsx`
- `scripts/governance/pr_body_van_pams_503.md`
