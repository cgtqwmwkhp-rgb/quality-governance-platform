# Change Ledger (CL-CES-ASSET-IMPORT-W1)

## 1) Summary
- **Feature / Change name:** CES Calibrations Wave 1 — Safety Asset Register XLSX import
- **User goal (1–2 lines):** Admins upload the weekly CES Equipment List workbook, dry-run validation, then commit creates/updates into the Asset Register.
- **In scope:** CES parser (Location split, status map, serial upsert), `/asset-imports/ces/dry-run|commit`, Admin upload panel on Safety Asset Register, tests
- **Out of scope:** Wave 2 board/hero/drill-in UX; auto-creating Locations/Engineers; schema migrations
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `safetyAssetsClient.ts` CES multipart APIs (5m timeout), `SafetyAssetRegister.tsx` upload panel, FE tests
- **Backend:** `ces_asset_import_parser.py`, `ces_asset_import_service.py`, asset_imports routes, CES report schemas
- **APIs:** `POST /api/v1/asset-imports/ces/dry-run`, `POST /api/v1/asset-imports/ces/commit` (`asset:create`)
- **Schemas/contracts:** Additive CES import response DTOs
- **Database:** None (uses existing Asset fields + metadata_json)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** openpyxl (already in stack via risk import); `requirements.lock` refreshed for Lockfile Freshness (upstream google-auth/genai pins)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints; CSV AM-IMPORT unchanged
- **Tolerant reader / strict writer applied?** Yes — dry-run before commit; ambiguous serials hard-fail; unmapped owner/location warn
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert PR removes import surface; already-imported rows remain (manual cleanup if needed)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Equipment List XLSX parses CES columns (Location…Status)
- [x] AC-02: Dry-run reports creates/updates/errors/warnings without writes
- [x] AC-03: Serial collisions without unique type(+QR) → `AMBIGUOUS_SERIAL`
- [x] AC-04: Commit upserts only after validation; Fail→quarantined; Removed→decommissioned
- [x] AC-05: Register UI supports choose file → Dry-run → Commit
- [x] AC-06: Updates preserve existing `asset_number` and merge CES metadata keys
- [x] AC-07: Commit is single-transaction (create/update flush, one commit; rollback on failure)
- [x] AC-08: Same serial + different type with one existing asset → update matching type, create for mismatch
- [x] AC-09: Updates omit unmapped owner/location/vehicle so warnings do not clear existing assignments

## 5) Testing Evidence (link to runs)
- [x] Unit/integration CES import tests locally
- [x] FE client + SafetyAssetRegister tests
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Safety Asset Register → CES upload → dry-run summary
- [x] CUJ-02: Commit creates/updates assets by serial after clean dry-run

## 7) Observability & Ops
- **Logs:** Validation errors return structured report (`CES_ASSET_IMPORT_VALIDATION_FAILED`)
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** Weekly CES Equipment List → dry-run first; map unknown engineers/locations before commit when needed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Dry-run supplied CES workbook; confirm warning/error counts; small commit subset if needed
- **Canary plan:** N/A
- **Prod post-deploy checks:** Dry-run only first; then commit after ops review

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Import corrupting asset data or endpoint 5xx on commit
- **Rollback steps:** Revert merge commit / redeploy prior SWA+API; leave imported assets for manual correction
- **Owner:** Platform / Safety Asset Register

## 10) Evidence Pack (links)
- CI run(s): after push
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
