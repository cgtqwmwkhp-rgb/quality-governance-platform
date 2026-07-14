# Change Ledger (CL-001) — AM-MODEL

## 1) Summary
- **Feature / Change name:** AM-MODEL — Safety Asset Management spine (locations / owner / expiry / evidence / CAPA link).
- **User goal (1-2 lines):** Extend the existing Safety/equipment Asset registry so a non-standalone Safety Asset Management module can assign assets to sites/workshops XOR vehicles, track owners/expiry, attach photo evidence, and link CAPA actions — without a parallel `safety_assets` table and without touching ISO27001 `information_assets`.
- **In scope:** `locations`, `assets` column extensions, `asset_assignment_events`, SAFETY type seeds, `EvidenceSourceModule.ASSET`, `capa_actions.asset_id`, Asset service/API filters + XOR rule, minimal CAPA schema/create accept/return of `asset_id`, unit tests.
- **Out of scope:** Frontend pages, Layout, VehicleChecklists, workforce FE/client, PAMS sync core, incident/near_miss FKs (AM-THREAD).
- **Feature flag / kill switch:** None (additive schema + API).

## 2) Impact Map (what changed)
- **Frontend:** None (exclusive allowlist — zero overlap with WF-CLIENT).
- **Backend:** `asset_service.py`, `assets.py` routes, CAPA create schema (`asset_id`).
- **APIs:** Locations CRUD under `/assets/locations`; asset create/update/list accept new fields + filters (`location_id`, `vehicle_reg`, `owner_user_id`, `expiry_band`).
- **Schemas/contracts:** Asset + Location schemas; CAPAResponse / CAPACreate `asset_id`.
- **Database:** Alembic `20260714_safety_asset_model` — `locations`, `asset_assignment_events`, assets columns, capa `asset_id`, SAFETY seeds.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive only. Legacy `site`/`department` retained. Workforce `listAssetTypes`/`listAssets` prior fields still returned.
- **Tolerant reader / strict writer applied?** Yes — new fields nullable; XOR enforced on write in service.
- **Breaking changes:** None.
- **Migration plan:** Single Alembic revision from current main tip head.
- **Rollback strategy (DB):** Downgrade drops new tables/columns (seeds left as harmless global types).

## 4) Acceptance Criteria (AC)
- [x] AC-01: Locations CRUD (site|workshop) with asset:create/update/delete perms.
- [x] AC-02: Assets accept location_id / vehicle_reg / owner_user_id / expiry_date / photo_evidence_id; status includes quarantined.
- [x] AC-03: Location XOR vehicle assignment raises BadRequestError when both set.
- [x] AC-04: Assignment changes append `asset_assignment_events`.
- [x] AC-05: EvidenceSourceModule.ASSET accepted; CAPA.asset_id present on model + create/response.
- [x] AC-06: SAFETY seeds (Engineer Tool, Fire Extinguisher, First Aid Kit) idempotent by name+category.

## 5) Testing Evidence
- Unit: `tests/unit/test_am_model_safety_asset.py`, `tests/unit/test_evidence_asset.py` (ASSET enum).

## 6) Exclusive Allowlist
- `src/domain/models/asset.py`, `location.py`, `evidence_asset.py` (enum), `capa.py`, `__init__.py`
- `src/domain/services/asset_service.py`
- `src/api/routes/assets.py`, `src/api/schemas/asset.py`, CAPA schema/route `asset_id` only
- `alembic/versions/20260714_safety_asset_model.py`
- `tests/unit/test_am_model_safety_asset.py` (+ evidence enum expectation)
- `scripts/governance/pr_body_am_model.md`

## 7) R4 Integration Foundation
- Evidence `ASSET` source module + CAPA.`asset_id` enable downstream Safety AM / CAPA / evidence threading without WF-CLIENT overlap.
