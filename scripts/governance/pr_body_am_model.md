# Change Ledger (CL-AM-MODEL)

## 1) Summary
- **Feature / Change name:** AM-MODEL — Safety Asset Management spine (locations / owner / expiry / evidence / CAPA link)
- **User goal (1–2 lines):** Extend the existing equipment Asset registry so Safety Asset Management can assign assets to sites/workshops XOR vehicles, track owners/expiry, attach photo evidence, and link CAPA — without a parallel `safety_assets` table and without touching ISO27001 `information_assets`.
- **In scope:** `locations`, `assets` column extensions, `asset_assignment_events`, SAFETY type seeds, `EvidenceSourceModule.ASSET`, `capa_actions.asset_id`, Asset service/API filters + XOR rule, minimal CAPA schema accept/return of `asset_id`, unit tests.
- **Out of scope:** Frontend pages, Layout, VehicleChecklists, workforce FE/client, PAMS sync core, incident/near_miss FKs (AM-THREAD).
- **Feature flag / kill switch:** None (additive schema + API).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (zero overlap with WF-CLIENT).
- **Backend (handlers/services):** `asset_service.py`, `assets.py` routes, CAPA create/response `asset_id`.
- **APIs (endpoints changed/added):** Locations CRUD under `/assets/locations`; asset create/update/list accept new fields + filters (`location_id`, `vehicle_reg`, `owner_user_id`, `expiry_band`).
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Asset + Location schemas; CAPAResponse / CAPACreate `asset_id`.
- **Database (migrations/entities/indexes):** Alembic `20260714_safety_asset_model` — `locations`, `asset_assignment_events` (tenant_id NOT NULL), assets columns, capa `asset_id`, SAFETY seeds.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive only. Legacy `site`/`department` retained. Workforce `listAssetTypes`/`listAssets` prior fields still returned.
- **Tolerant reader / strict writer applied?** Yes — new fields nullable; XOR enforced on write; new owned tables require tenant_id.
- **Breaking changes:** None.
- **Migration plan:** Single Alembic revision from main tip.
- **Rollback strategy (DB):** Downgrade drops new tables/columns (global SAFETY seeds left as harmless types).

## 4) Acceptance Criteria (AC)
- [x] AC-01: Locations CRUD (site|workshop) with asset permissions; `locations.tenant_id` NOT NULL (D11).
- [x] AC-02: Assets accept location_id / vehicle_reg / owner_user_id / expiry_date / photo_evidence_id; status includes quarantined.
- [x] AC-03: Location XOR vehicle assignment raises BadRequestError when both set; assignment events require tenant_id.

## 5) Testing Evidence (link to runs)
- [x] Lint — CI
- [x] Typecheck — CI
- [x] Build — CI
- [x] Unit tests — `tests/unit/test_am_model_safety_asset.py`, `tests/unit/test_evidence_asset.py` (local 32 passed)
- [ ] Integration tests — CI
- [ ] Contract tests (if applicable) — CI OpenAPI
- [ ] E2E Smoke — N/A (API spine only)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create location (site/workshop) scoped to tenant → list/filter
- [x] CUJ-02: Create/update asset with owner/expiry/location XOR vehicle → assignment event recorded
- [x] CUJ-03: EvidenceSourceModule.ASSET + CAPA.asset_id accepted on model/schema

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Alembic upgrade; `/assets/locations` + asset filters smoke; CAPA create with asset_id
- **Canary plan:** N/A
- **Prod post-deploy checks:** meta/version SHA + migration applied

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure or asset API regression blocking Workforce asset-type dropdowns
- **Rollback steps:** Revert PR; alembic downgrade `20260714_safety_asset_model` if migration applied
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge + staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive spine)
- [ ] **Gate 2:** CI green (lint/type/build/tests) — in flight after D11 fix
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Exclusive allowlist (zero overlap with WF-CLIENT)
- `src/domain/models/asset.py`, `location.py`, `evidence_asset.py` (enum), `capa.py`, `__init__.py`
- `src/domain/services/asset_service.py`
- `src/api/routes/assets.py`, `src/api/schemas/asset.py`, CAPA schema/route `asset_id` only
- `alembic/versions/20260714_safety_asset_model.py`
- `tests/unit/test_am_model_safety_asset.py`, `tests/unit/test_evidence_asset.py`
- `scripts/governance/pr_body_am_model.md`
