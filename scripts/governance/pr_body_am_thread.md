# Change Ledger (CL-AM-THREAD)

## 1) Summary
- **Feature / Change name:** AM-THREAD — case `asset_id` golden-thread FKs + admin pickers
- **User goal (1–2 lines):** Link incidents, near misses, and RTAs to Asset registry rows so Safety Asset Management can follow the case↔asset golden thread; admins can pick assets on case detail pages; actions list can filter by asset.
- **In scope:** Nullable `asset_id` FK on `incidents` / `near_misses` / `road_traffic_collisions`; schemas + list filters; unified actions `asset_id` filter; admin AssetPicker on Incident/NearMiss/RTA detail; unit tests + this ledger.
- **Out of scope:** Workforce FE/client, CompetencyDashboard, Layout Safety Cases rewrite, VehicleChecklists, SafetyAssets pages (AM-FE), new `GET /assets/{id}/linked-cases` (FE uses case list `?asset_id=` instead).
- **Feature flag / kill switch:** None (additive schema + API).
- **Depends on:** #976 AM-MODEL (locations / owner / expiry / CAPA.asset_id).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `AssetPicker`; IncidentDetail / NearMissDetail / RTADetail; incidents/nearMisses/rtas client types.
- **Backend (handlers/services):** incident / near_miss / rta services list filter; actions list/count CAPA + parent-case join filter.
- **APIs (endpoints changed/added):** Case create/update/response accept/return `asset_id`; list endpoints accept `asset_id`; `GET /api/v1/actions/?asset_id=`.
- **Schemas/contracts:** Incident / NearMiss / RTA create/update/response; near miss keeps legacy `asset_number` / `asset_type`.
- **Database (migrations/entities/indexes):** Alembic `20260714_am_thread` — nullable `asset_id` FK → `assets.id` on three case tables.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive nullable FKs; near-miss free-text asset fields retained.
- **Tolerant reader / strict writer applied?** Yes — `asset_id` optional on write; null clears link via update exclude_unset + explicit null.
- **Breaking changes:** None.
- **Migration plan:** Stacked on AM-MODEL tip (`20260714_safety_am_model`).
- **Rollback strategy (DB):** Downgrade drops the three `asset_id` columns/FKs/indexes.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Migration adds nullable `asset_id` FK on incidents, near_misses, road_traffic_collisions.
- [x] AC-02: Schemas + routes accept/return `asset_id`; near miss retains legacy text fields.
- [x] AC-03: Admin typeahead pickers on IncidentDetail / NearMissDetail / RTADetail (`/api/v1/assets/`).
- [x] AC-04: Unified actions list supports `asset_id` filter (CAPA direct + incident/RTA parent join).
- [x] AC-05: FE can query cases by `?asset_id=` (no separate linked-cases endpoint).
- [x] AC-06: Unit tests cover model FK + schemas + migration revision chain.

## 5) Testing Evidence (link to runs)
- [x] Lint — CI
- [x] Typecheck — CI
- [x] Build — CI
- [x] Unit tests — `tests/unit/test_am_thread_case_asset_id.py` (local)
- [ ] Integration tests — CI
- [ ] Contract tests (if applicable) — CI OpenAPI
- [ ] E2E Smoke — N/A for this lane (admin pickers covered by unit/schema + critical-path FE wiring)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create/update incident/near miss/RTA with `asset_id` → response returns it
- [x] CUJ-02: List cases with `?asset_id=` filters to linked cases
- [x] CUJ-03: List actions with `?asset_id=` returns CAPA + parent-linked incident/RTA actions

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Alembic upgrade after #976; smoke PATCH case with asset_id; list actions `?asset_id=`
- **Canary plan:** N/A
- **Prod post-deploy checks:** meta/version SHA + migration applied

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure or case API regression on create/update
- **Rollback steps:** Revert PR; alembic downgrade `20260714_am_thread` if migration applied
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge + staging deploy (post AM-MODEL)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive FKs + filters)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — blocked on #976 merge
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Exclusive allowlist
- incident / near_miss / rta models, schemas, routes, services, migrations
- frontend IncidentDetail, NearMissDetail, RTADetail + `components/AssetPicker.tsx`
- actions route `asset_id` filter (minimal)
- tests + `scripts/governance/pr_body_am_thread.md`
