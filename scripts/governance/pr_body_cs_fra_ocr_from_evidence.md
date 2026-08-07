# Change Ledger (CL-CS-FRA-OCR-FROM-EVIDENCE)

## 1) Summary
- **Feature / Change name:** FRA OCR draft from occurrence evidence PDF (pipeline slice 4)
- **User goal (1–2 lines):** When an operator uploads a FRA PDF as occurrence evidence on an eligible obligation, create a pending FRA OCR draft from that blob (no second file picker) so review can proceed from the existing ingest panel.
- **In scope:** `POST …/records/{id}/fra-ocr/drafts/from-evidence`; nullable `evidence_asset_id` FK on OCR drafts; discard must not delete shared evidence blobs; PDF magic / 25 MiB / checksum gates; FE `onUploadComplete` widen + auto-trigger; alembic; unit + FE tests
- **Out of scope:** Slices 5–6 (CAPA / Risk); Doc Graph; flag default changes; Azure appsettings
- **Feature flag / kill switch:** Reuses existing `compliance_schedule_fra_ocr` (default off). Endpoint nested under FRA OCR router (404 when flag off).

## 2) Impact Map (what changed)
- **Frontend:** `EvidenceGallery` / `CaseEvidencePanel` optional `uploadedAssetIds`; `RecordEvidenceSection` auto from-evidence; `ComplianceScheduleDetail` refreshes FRA panel; client `createDraftFromEvidence`
- **Backend:** `ComplianceScheduleFraOcrService.create_draft_from_evidence_asset`; discard ownership via `evidence_asset_id`; route + schemas
- **APIs:** Additive `POST /api/v1/compliance-schedule/records/{record_id}/fra-ocr/drafts/from-evidence`; additive `evidence_asset_id` on draft response
- **Database:** Alembic `20261016_cs_fra_ocr_ev` — nullable `evidence_asset_id` FK → `evidence_assets` (SET NULL)
- **Config/env/flags:** None new
- **Dependencies:** None
- **Tests:** Named discard-does-not-delete-evidence-blob; from-evidence magic/size/checksum/happy path; FE auto-trigger

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API + nullable column; older clients ignore new field/endpoint
- **Tolerant reader / strict writer applied?** Yes — request `extra=forbid` on from-evidence body
- **Breaking changes:** None
- **Migration plan:** Expand-only nullable FK; safe to deploy before/after FE
- **Rollback strategy (DB):** Column may remain; revert app code. Downgrade drops FK/index/column if needed.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Occurrence PDF → FRA OCR | Separate obligation upload only | From-evidence reuses bound EvidenceAsset blob |
| Discard of from-evidence draft | Would delete staging key if treated as upload | Never deletes when `evidence_asset_id` set |
| PDF integrity before OCR | Upload path magic/size | Same magic/25 MiB + checksum vs EvidenceAsset |

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `POST …/from-evidence` with bound PDF creates pending draft with `evidence_asset_id` set and shared `source_storage_key`.
- [x] **AC-02:** Discard of from-evidence draft does **not** call storage delete (named unit test).
- [x] **AC-03:** Non-PDF magic, >25 MiB, or checksum mismatch → `ValidationError` / 400-class; no draft.
- [x] **AC-04:** FE auto-calls from-evidence for eligible PDF uploads when flag on + `fra_ocr_eligible`; skips non-PDF / ineligible.
- [x] **AC-05:** Upload-created drafts (`evidence_asset_id` null) still delete their staging blob on discard.

## 5) Testing Evidence
- [x] Unit — `test_compliance_schedule_fra_ocr_service.py` (12 passed locally, Python 3.11)
- [x] FE — `RecordEvidenceSection` + `EvidenceGallery.upload` (9 passed via vitest)
- [x] Lint — black/isort/flake8 on touched Python
- [ ] Full CI — after PR open

## 6) Critical Journeys (CUJ)
- [x] **CUJ-01:** Operator completes/opens an occurrence on an eligible FRA obligation (flag on), uploads a PDF as evidence → toast + pending draft appears in FRA ingest panel without a second picker.
- [x] **CUJ-02:** Operator discards that from-evidence draft → draft discarded; occurrence evidence PDF remains downloadable.

## 7) Observability & Ops
- **Logs:** Existing `fra_ocr draft created from evidence` / discard audit payload includes `evidence_asset_id` and `deleted_source_blob`
- **Runbook:** No flag flip required to deploy; enable `compliance_schedule_fra_ocr` when ready to expose write path

## 8) Release Plan
- Squash-merge to `main` → Main CI → Azure deploy → verify tip SHA on prod meta/version + health.
- No appsettings change; never full PUT of Azure appsettings.

## 9) Rollback Plan
- **Trigger:** From-evidence deletes evidence blobs, false OCR drafts on non-PDFs, or migration/deploy failure
- **Rollback owner:** Platform / on-call (sole operator: David Harris)
- **Steps:**
  1. Revert squash commit on `main` and redeploy prior tip image
  2. Leave nullable column in place if DB already migrated (safe); optional alembic downgrade only if required

## 10) Evidence Pack
- CI / staging / prod tip: linked after merge and LIVE verify

---

# Gate Checklist
- [x] Gate 0 — Scope lock + AC + Change Ledger (slice 4 only; stop before 5–6)
- [x] Gate 1 — Contracts (additive endpoint + response field + nullable FK)
- [ ] Gate 2 — CI green
- [ ] Gate 3 — Staging verification
- [ ] Gate 4 — Canary (N/A — flag default remains off)
- [x] Gate 5 — Rollback via revert documented
