# Change Ledger (CL-VAN-CL-503)

## File allowlist (exclusive)
- `src/api/routes/vehicle_checklists.py`
- `frontend/src/pages/VehicleChecklists.tsx`
- `frontend/src/pages/__tests__/VehicleChecklists.test.tsx`
- `tests/unit/test_vehicle_checklist_pams_unavailable.py`
- `scripts/governance/pr_body_van_cl_503.md`

**Zero overlap** with Layout/App/client.ts/`api/__init__.py`/Alembic/InvestigationDetail/planet_mark.

## 1) Summary
- **Feature / Change name:** VAN-CL-503 — Honest PAMS unavailable UI on daily checklist 503
- **User goal (1–2 lines):** When PAMS is down (or unconfigured) and the local cache is empty, `GET /api/v1/vehicle-checklists/daily` returns a clear structured 503, and Van Checklists shows an honest “PAMS unavailable” state instead of a silent empty dash.
- **In scope:** Vehicle-checklists list fail-soft 503 payload; VehicleChecklists unavailable banner/empty + retry; unit/Vitest.
- **Out of scope:** PAMS sync/Celery; Layout/App/client; Alembic; Investigation/Planet Mark lanes.
- **Feature flag / kill switch:** None (fail-soft honesty).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `VehicleChecklists.tsx` — PAMS unavailable banner, empty state, retry; helper `formatChecklistLoadError`.
- **Backend (handlers/services):** `vehicle_checklists.py` — standardised `SERVICE_UNAVAILABLE` 503 with `details.service=pams`.
- **APIs (endpoints changed/added):** `GET /daily`, `GET /monthly` (same contract; clearer error envelope when PAMS cannot serve).
- **Schemas/contracts:** Unchanged list DTO; error envelope uses existing DomainError mapping.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Fail-soft — structured 503 (not opaque 500). Cache-hit path unchanged.
- **Tolerant reader / strict writer applied?** FE clears items on error and never paints filter-empty as success.
- **Breaking changes:** None (clients already see 503 when PAMS is down).
- **Migration plan:** N/A.
- **Rollback strategy (DB):** N/A — revert PR.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Empty cache + PAMS unavailable → DomainError http_status 503, code `SERVICE_UNAVAILABLE`, message contains “PAMS unavailable”, details.service=`pams`
- [x] AC-02: Unexpected list failures masked as the same structured 503 (not raw 500)
- [x] AC-03: FE daily 503 → “PAMS unavailable” banner + empty state (not “No checklist data matches these filters”)
- [x] AC-04: Retry control reloads daily list
- [x] AC-05: Unit + Vitest coverage for the above

## 5) Testing Evidence (link to runs)
- [x] Backend unit — `tests/unit/test_vehicle_checklist_pams_unavailable.py` (local)
- [x] Frontend Vitest — VehicleChecklists PAMS honesty cases (local)
- [ ] CI after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01 / UAT CUJ-031: Open Van Checklists → daily load 503 → honest PAMS unavailable (no silent empty dash)
- [x] CUJ-02: Retry after PAMS recovery → records render

## 7) Observability & Ops
- Logger.exception retained on live query / list failures before structured 503
- Ops: restore `PAMS_DATABASE_URL` / connectivity or wait for cache sync

## 8) Release Plan (Local → Staging → Canary → Prod)
- Staging: open `/vehicle-checklists` with PAMS down or empty cache → confirm banner
- Prod: hard-refresh SWA after bake; spot-check daily tab

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Van Checklists blank for all users when cache has data, or false 503 rate up
- **Rollback steps:** Revert squash-merge (no migration)
- **Owner:** Platform / Vehicle Checklists track

## 10) Evidence Pack (links)
- CI: linked after PR creation
- Tip base: `05b90720`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE + BE honesty implemented
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified
- [x] **Gate 5:** Evidence pack / UAT-200 VAN-CL-503 noted

Made with [Cursor](https://cursor.com)
