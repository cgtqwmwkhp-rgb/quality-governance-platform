## Summary

Wave 1 shippable PR for Planet Mark Years: honest evidence persistence + OCR extract preview → Apply year readings.

- **Persistence honesty**: CarbonEvidence upload no longer commits a phantom DB row when blob storage fails (503, nothing recorded). Download link shown only when `storage_key` exists; certificate/measurement missing status is explicit.
- **OCR → year readings**: Scan Measurement Report / Certificate via shared OCR spine (`ExternalAuditOcrService` → pdfplumber/native + `MistralOCRService`). Azure DI consulted only when configured; otherwise honest `stub_not_enabled` / not_configured. Preview fields (total tCO₂e, tCO₂e/FTE, FTE, certificate number, period, status cue) then user **Apply**. MS XLSX remains SSOT unless force overwrite confirmed.
- **Frontend**: Years OCR panel + evidence download/storage honesty; additive en+cy i18n.

## Change Ledger

### Gate 0 — Scope & allowlist
Exclusive paths only:
- `frontend/src/pages/planetMarkYearEvidencePanel.tsx`
- `frontend/src/pages/planetMarkYearEvidenceHelpers.ts`
- `frontend/src/pages/planetMarkYearOcrPanel.tsx` (new)
- `frontend/src/pages/planetMarkYearOcrHelpers.ts` (new)
- `frontend/src/pages/__tests__/planetMarkYear*` (new/update)
- `frontend/src/pages/PlanetMark.tsx` (Years mount only)
- `frontend/src/api/planetMarkClient.ts`
- `frontend/src/i18n/locales/en.json` / `cy.json` (additive PM keys only)
- `src/api/routes/planet_mark.py`
- `src/api/schemas/planet_mark.py`
- `src/domain/services/planet_mark_pdf_ocr_service.py` (new)
- `src/infrastructure/external/azure_document_intelligence.py` (gated live adapter + honest readiness)
- `tests/unit/test_planet_mark_pdf_ocr*.py` (new)
- `scripts/governance/pr_body_pm_ocr_year_readings.md` (new)

Soft-conflict note: flat `en.json`/`cy.json` — PM keys only additive (#1105/#1106 may also touch i18n).

### Gate 1 — Acceptance criteria
- **AC-01**: Blob upload failure does not create CarbonEvidence without `storage_key`.
- **AC-02**: Evidence list shows download when stored; storage-missing / certificate-missing honesty when not.
- **AC-03**: Scan & extract returns preview fields without writing year totals.
- **AC-04**: Apply writes only high-confidence extracted fields; never fabricates numbers.
- **AC-05**: When MS XLSX ingested, OCR totals skipped unless `force_overwrite_totals` confirmed.
- **AC-06**: Provenance stamped (`source=ocr_measurement_report` / `ocr_certificate`) on apply.
- **AC-07**: Azure DI readiness/meta probes never dial; live call only with credentials + `AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD`.
- **AC-08**: en+cy strings for new UI copy.

### Gate 2 — Critical user journeys
- **CUJ-01**: Upload Measurement Report PDF → stored with `storage_key` → download works.
- **CUJ-02**: Upload fails storage → 503, no phantom row, UI can retry.
- **CUJ-03**: Scan stored report → preview totals → Apply → year readings updated.
- **CUJ-04**: Year with MS XLSX → Scan → Apply blocked until overwrite confirmed.
- **CUJ-05**: Certificate missing status visible until certificate PDF successfully stored.

### Gate 3 — Tests
- Unit: `tests/unit/test_planet_mark_pdf_ocr_service.py` (parse/apply/spine/Azure honesty)
- FE: `planetMarkYearOcrHelpers.test.ts`, `planetMarkYearOcrPanel.test.tsx`, `planetMarkYearEvidenceHonesty.test.ts`
- Existing Azure DI credential-free tests remain green

### Gate 4 — Residual gaps
- Full Azure DI production enablement remains behind E4 DPO gate (`AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD`).
- Scope 1/2/3 breakdown from PDF tables not in Wave 1 (totals + cert metadata only).
- Data quality score not OCR-inferred (honesty: left unchanged unless separate ingest).

### Gate 5 — Risk / rollback
- Low blast radius: new endpoints + FE panels; upload path fails closed (safer than before).
- Rollback: revert PR; no Alembic migrations.

## Test plan
- [ ] `pytest tests/unit/test_planet_mark_pdf_ocr_service.py tests/unit/test_ocr_consensus.py -q`
- [ ] `cd frontend && npx vitest run src/pages/__tests__/planetMarkYearOcr* src/pages/__tests__/planetMarkYearEvidence*`
- [ ] Manual: Years → upload PDF → Scan & extract → Apply; verify certificate missing/download honesty
