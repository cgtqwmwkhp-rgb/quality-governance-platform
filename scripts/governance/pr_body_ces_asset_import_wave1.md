# Change Ledger (CES-ASSET-IMPORT-W1)

**Path claim:** `ces-asset-import-wave1`

## 1) Summary
- **Feature / Change name:** CES Calibrations Wave 1 asset import spine
- **User goal:** Admins can dry-run and commit an `Equipment List` XLSX into the Safety Asset Register.
- **In scope:** CES parser, serial-number upsert service, protected XLSX endpoints, minimal register upload panel, tests.
- **Out of scope:** Asset board/drill-in UX, schema migrations, automatic location or owner creation.

## 2) Data safety
- Serial number is the upsert key. Multiple in-file or existing matches need equipment type and QR (when present) to resolve; otherwise dry-run reports `AMBIGUOUS_SERIAL`.
- No writes occur on dry-run. Commit re-validates the workbook and rejects any error rows.
- CES `Fail` becomes `quarantined`; `Removed From Service` becomes `decommissioned`; pass variants remain `active`.
- `Not Made Available` is imported as active and retained as a warning/metadata flag.
- Unknown engineer and site mappings are warnings: assets are not assigned speculatively.

## 3) Field mapping
- Location → company/engineer/site/UK vehicle registration extraction
- Equipment Type + Make + Model + Capacity → name; Equipment Type resolves existing Asset Type
- Serial → `serial_number` and create-time `asset_number`; QR → `qr_code_data`
- CES Next Inspection → `expiry_date`; Last Inspection and source context → metadata

## 4) Acceptance criteria
- [x] Equipment List XLSX parses using CES column layout
- [x] Dry-run reports creates, updates, warnings and row errors
- [x] Serial collisions fail safely as `AMBIGUOUS_SERIAL`
- [x] Commit creates or updates assets only after validation
- [x] Endpoints require `asset:create`
- [x] Register provides XLSX dry-run/commit controls

## 5) Testing evidence
- [x] `python3.11 -m pytest tests/unit/test_ces_asset_import_service.py tests/integration/test_asset_imports_api.py -q` (15 passed)
- [x] `npx vitest run src/api/safetyAssetsClient.test.ts src/pages/__tests__/SafetyAssetRegister.test.tsx` (8 passed)
- [x] `npm run lint`
- [x] `npm run build`
- [x] Supplied CES workbook parsed: 1,881 data rows; its 9 blank-status rows and 2 `Not Tested At Customers Request` rows remain explicit validation errors.

## 6) Release and rollback
1. Validate the supplied CES workbook with dry-run in staging.
2. Confirm warning mappings before committing.
3. Revert this commit to remove the import surface; imported assets remain auditable records and require manual correction/removal.
