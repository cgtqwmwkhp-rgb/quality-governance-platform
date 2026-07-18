# Change Ledger (CL-FIX-STAGING-BLOB-STORAGE)

## File allowlist (exclusive)
- `src/infrastructure/storage.py`
- `tests/unit/test_storage_backend_selection.py`
- `scripts/governance/pr_body_fix_staging_blob_storage.md`

**Out of scope:** Document Spine UI; EMP lanes; Azure DI enable.

## 1) Summary
- **Feature / Change name:** Fix Library upload 500 on staging — Permission denied `storage`
- **User goal:** Document upload on staging/prod uses Azure Blob; never local `./storage` mkdir on App Service.
- **In scope:** `get_storage_service()` selection when `APP_ENV=staging` or connection string present.
- **Out of scope:** Changing Key Vault secrets; FE upload dialog.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** None
- **Backend:** Storage backend selection
- **APIs:** `/api/v1/documents/upload` (and any blob upload) no longer hits local disk on staging
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** Uses existing `AZURE_STORAGE_CONNECTION_STRING` (already set by staging deploy)
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive selection fix
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** Staging without blob connection string now fails closed at storage init (correct) instead of Errno 13 mid-upload
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit + redeploy

## 4) Acceptance Criteria (AC)
- [x] AC-01: Staging + connection string → AzureBlobStorageService
- [x] AC-02: Staging without connection string → StorageNotConfiguredError (not LocalFile)
- [x] AC-03: Development without connection string → LocalFileStorageService
- [x] AC-04: Unit tests cover selection

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_storage_backend_selection.py`
- [ ] CI — this PR
- [ ] Staging smoke: Library → Upload Document succeeds

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staging Library upload no longer returns Errno 13 Permission denied `storage`
- [x] CUJ-02: Production continues to use Azure Blob when connection string set
- [x] CUJ-03: Local development without Azure still uses `./storage`

## 7) Observability & Ops
- **Logs:** Existing AzureBlobStorageService init log
- **Metrics / Alerts:** N/A
- **Runbook updates:** If staging upload fails with StorageNotConfiguredError, check Key Vault `AZURE-STORAGE-CONNECTION-STRING` on staging App Service

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Upload a PDF on Library after deploy
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same upload path (already Azure); no behaviour change when connection string set

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Staging/prod upload regressions
- **Rollback steps:** Revert squash-merge; force_deploy prior SHA
- **Owner:** Tip-owner

## 10) Evidence Pack (links)
- User repro: `POST …/documents/upload` → 500 `[Errno 13] Permission denied: 'storage'`
- Root cause: `get_storage_service()` only used Azure when `APP_ENV=production`; staging used LocalFileStorage

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — blob required on staging/prod
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (upload smoke)
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production verification plan ready
