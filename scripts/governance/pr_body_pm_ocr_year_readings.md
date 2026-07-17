# Change Ledger (CL-PM-OCR-YEAR-READINGS)

## 1) Summary
- **Feature / Change name:** PM-OCR-W1 — Planet Mark Years OCR extract → Apply + evidence storage honesty
- **User goal:** Upload Measurement Report / Certificate PDFs that persist honestly; Scan → preview → Apply year readings without fabricating totals; MS XLSX remains SSOT unless force overwrite
- **In scope:** Evidence blob fail-closed; OCR spine reuse; preview/apply endpoints; Years FE panels; Azure DI E4-gated adapter honesty; additive en/cy
- **Out of scope:** Scope 1/2/3 table breakdown; enabling Azure DI in prod without E4 DPO; Alembic
- **Feature flag / kill switch:** `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD` (E4)

## 2) Impact Map (what changed)
- **Frontend:** Years evidence + OCR panels/helpers; PlanetMark Years mount; planetMarkClient; en.json/cy.json (additive PM keys)
- **Backend / APIs:** `planet_mark` OCR extract/apply routes + schemas; `planet_mark_pdf_ocr_service`; Azure DI readiness/live adapter
- **Config/env/flags:** Existing Azure DI env + E4 enable flag
- **Dependencies:** None new

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints + FE panels; upload path fails closed (safer)
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Blob upload failure does not create CarbonEvidence without `storage_key`
- [x] AC-02: Evidence list shows download when stored; storage-missing / certificate-missing honesty when not
- [x] AC-03: Scan & extract returns preview fields without writing year totals
- [x] AC-04: Apply writes only high-confidence extracted fields; never fabricates numbers
- [x] AC-05: When MS XLSX ingested, OCR totals skipped unless `force_overwrite_totals` confirmed
- [x] AC-06: Provenance stamped (`source=ocr_measurement_report` / `ocr_certificate`) on apply
- [x] AC-07: Azure DI readiness/meta probes never dial; live call only with credentials + enable flag
- [x] AC-08: en+cy strings for new UI copy

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_planet_mark_pdf_ocr*.py`
- [x] FE: planetMarkYear OCR/evidence Vitest
- [ ] CI after fix push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Upload Measurement Report PDF → stored with `storage_key` → download works
- [x] CUJ-02: Upload fails storage → 503, no phantom row, UI can retry
- [x] CUJ-03: Scan stored report → preview totals → Apply → year readings updated
- [x] CUJ-04: Year with MS XLSX → Apply blocked until overwrite confirmed
- [x] CUJ-05: Certificate missing status visible until certificate PDF successfully stored

## 7) Observability & Ops
- Existing logger warnings on Azure DI / storage download failures retained
- Azure DI readiness remains meta-only (no dial on probe)

## 8) Release Plan (Local → Staging → Canary → Prod)
- Staging/Prod: Years → upload PDF → Scan & extract → Apply; confirm certificate/download honesty; MS XLSX SSOT preserved

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** OCR apply corrupts year totals or evidence upload regresses
- **Rollback steps:** Revert squash-merge; no DB migration to undo
- **Owner:** Platform / Planet Mark track

## 10) Evidence Pack (links)
- Soft-conflict: flat `en.json`/`cy.json` additive PM keys only (#1105/#1106 may also touch i18n)
- Tip note: rebase onto main after tip moves; no Alembic

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** OCR extract/apply + evidence honesty implemented
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified
- [x] **Gate 5:** Evidence pack / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/planetMarkYearEvidencePanel.tsx`
- `frontend/src/pages/planetMarkYearEvidenceHelpers.ts`
- `frontend/src/pages/planetMarkYearOcrPanel.tsx`
- `frontend/src/pages/planetMarkYearOcrHelpers.ts`
- `frontend/src/pages/__tests__/planetMarkYear*`
- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/api/planetMarkClient.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `src/api/routes/planet_mark.py`
- `src/api/schemas/planet_mark.py`
- `src/domain/services/planet_mark_pdf_ocr_service.py`
- `src/infrastructure/external/azure_document_intelligence.py`
- `tests/unit/test_planet_mark_pdf_ocr*.py`
- `scripts/governance/pr_body_pm_ocr_year_readings.md`

Made with [Cursor](https://cursor.com)
