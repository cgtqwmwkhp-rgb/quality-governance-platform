# Change Ledger (CL-AM-IMPORT)

## 1) Summary
- **Feature / Change name:** AM-IMPORT — CSV bulk import for engineer / safety tools
- **User goal (1–2 lines):** Admins can upload a CSV of tools/equipment, preview a dry-run validation report (row errors), then commit to create Asset registry rows.
- **In scope:** `AssetImportService`, `/asset-imports/dry-run` + `/commit`, schemas, fixtures, unit + API tests.
- **Out of scope:** Frontend pages, Layout, workforce, VehicleChecklists, incident FKs (AM-THREAD).
- **Feature flag / kill switch:** None (additive API).
- **Depends on:** #976 (AM-MODEL).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** `src/domain/services/asset_import_service.py` (new).
- **APIs (endpoints changed/added):** `POST /api/v1/asset-imports/dry-run`, `POST /api/v1/asset-imports/commit`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Asset import validation report + commit response schemas on `asset.py`.
- **Database (migrations/entities/indexes):** None (uses AM-MODEL spine).
- **Workflows/jobs/queues (if any):** None (synchronous validate/commit; mirrors external-audit dry-run-then-commit pattern without Celery).
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints only; existing asset CRUD unchanged.
- **Tolerant reader / strict writer applied?** Yes — dry-run never writes; commit fails closed on any row error (no partial import).
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert PR (no schema change).

## 4) Acceptance Criteria (AC)
- [x] AC-01: CSV columns supported — asset_number, name, type|asset_type, make, model, serial, owner_email|owner_user_id, location_name, vehicle_reg, expiry_date, status.
- [x] AC-02: Dry-run returns validation report with row errors (REQUIRED, UNKNOWN_TYPE, DUPLICATE_*, ASSIGNMENT_XOR, INVALID_*).
- [x] AC-03: Commit re-validates then creates assets via AssetService (location XOR vehicle enforced).
- [x] AC-04: Unit + API tests with fixtures under `tests/fixtures/asset_import/`.

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_asset_import_service.py`
- [x] API tests — `tests/integration/test_asset_imports_api.py`
- [ ] Lint / typecheck / full CI — on PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Dry-run valid CSV → ok=true, preview rows
- [x] CUJ-02: Dry-run invalid CSV → row error codes collected
- [x] CUJ-03: Commit with errors → HTTP 422 + report details; commit valid → created_count

## 7) Observability & Ops
- **Logs:** DomainError handler logs validation failures
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** After #976 merged — upload fixture CSV to dry-run then commit; confirm assets list
- **Canary plan:** N/A
- **Prod post-deploy checks:** OpenAPI shows `/asset-imports/*`; smoke dry-run

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Import endpoints 5xx or incorrect asset creation
- **Rollback steps:** Revert PR (no DB migration)
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge + staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive import API)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Exclusive allowlist
- `src/domain/services/asset_import_service.py`
- `src/api/routes/asset_imports.py` + register in `src/api/__init__.py`
- `src/api/schemas/asset.py` (import schemas only)
- `tests/unit/test_asset_import_service.py`
- `tests/integration/test_asset_imports_api.py`
- `tests/fixtures/asset_import/*`
- `scripts/governance/pr_body_am_import.md`
