# Change Ledger (CL-LIB-F1-UPLOAD-VALIDATION)

## 1) Summary
- **Feature / Change name:** Library F-1 / L-41 — shared upload≡revise file validation + signed-URL scan gate
- **User goal (1–2 lines):** Stop unscanned / OLE2 / macro-bearing files entering the Governance Library and block signed URLs until scan status is clean.
- **In scope:** Wire `file_validation.validate_upload` into library upload + revise; refuse OLE2/macros; add `documents.malware_scan_status`; gate `GET …/signed-url`; unit tests.
- **Out of scope:** Real AV worker (v1 stub); Planet Mark / UVDB / evidence-asset upload paths; native editor; Function/PEL allocator.
- **Feature flag / kill switch:** None — security gate always on.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `src/infrastructure/file_validation.py`; `src/api/routes/documents.py` upload/revise/signed-url; `Document.malware_scan_status`
- **APIs (endpoints changed/added):** Behavior only — `POST /documents/upload`, `POST /documents/{id}/versions`, `GET /documents/{id}/signed-url` (409 when scan ≠ clean)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** No response schema change
- **Database (migrations/entities/indexes):** Alembic `20261024_lib_f1_malware_scan` — additive column + backfill default `clean`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — legacy rows default `clean`; new uploads set `clean` after shared validation
- **Breaking changes:** `.doc` / `.xls` / macro OOXML newly refused on library upload/revise (intentional)
- **Migration plan:** Run Alembic revision on deploy path
- **Rollback strategy (DB):** Downgrade drops column; revert code first if needed

## 4) Acceptance Criteria (AC)
- [x] AC-01: Upload and revise share one validation path (`_validate_library_upload` → `validate_upload`)
- [x] AC-02: OLE2 magic and `.doc`/`.xls` refused
- [x] AC-03: OOXML with `vbaProject.bin` / macro content-types refused
- [x] AC-04: Signed URL returns 409 when `malware_scan_status != clean` (no download-count bump)
- [x] AC-05: Successful upload/revise sets `malware_scan_status=clean`
- [x] AC-06: Unit tests green for validation + upload reference wiring + wave3 ingestion

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_file_validation.py` 8 passed
- [x] Unit — `tests/unit/test_document_upload_reference_number.py` + `test_wave3_document_ingestion.py` green (15 combined with file_validation)
- [ ] Full CI — on PR
- [ ] Staging / Prod tip verify — after merge (conveyor DONE gate)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: PDF upload still accepted after shared validation
- [x] CUJ-02: Legacy `.doc` rejected at validation
- [x] CUJ-03: Macro-bearing DOCX rejected
- [ ] CUJ-04: Prod signed-URL still works for backfilled `clean` rows — post-deploy

## 7) Observability & Ops
- **Logs:** Existing upload failure logging unchanged
- **Metrics:** Existing upload metrics unchanged
- **Alerts:** Watch 4xx spike on upload for `.doc` users during cutover
- **Runbook updates:** None required for stub scan; real AV is a follow-up

## 8) Release Plan (Local → Staging → Canary → Prod)
- Merge after CI green
- Azure deploy must succeed for tip SHA
- Verify MAIN tip = STG = PROD + `/healthz` 200
- Smoke: library PDF upload + signed-url; refuse a `.doc`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Legitimate uploads blocked incorrectly, or signed-URL mass 409
- **Rollback steps:** Revert merge commit; redeploy prior tip; optionally downgrade Alembic column
- **Owner:** Platform / Library conveyor

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging / Prod verify: Linked on conveyor heartbeat after LIVE

## Compliance Delta
- **Standards touched:** ISO 27001 A.5.12/A.5.33 (information classification / protection of records); ISO 9001 7.5.3.1 protection of documented information
- **Control impact:** Strengthens library ingress controls; no weakening of access or retention
- **Evidence:** Unit tests + post-deploy smoke on tip

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A normal path
- [ ] **Gate 5:** Production verification tip SHA + healthz
