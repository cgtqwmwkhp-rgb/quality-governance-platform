# Change Ledger (CL-DS-6-CONSUMER)

**Path claim:** `path11/ds-consumer-cutover`

## File allowlist (exclusive)

- `src/domain/services/document_intelligence_service.py`
- `src/domain/services/planet_mark_pdf_ocr_service.py`
- `src/domain/services/external_audit_import_service.py`
- `tests/unit/test_document_intelligence_service.py`
- `tests/unit/test_planet_mark_pdf_ocr_service.py`
- `scripts/governance/pr_body_ds_consumer_cutover.md`

**Out of scope:** `frontend/DocumentDetail.tsx`, `DocumentVersionControlBar`, `DocumentControl.tsx`, DS-5 alembic versions, `document_version_service.py`, `gkb_control_library_link.py`, Azure DI prod enablement (DS-1b).

## 1) Summary

- **Feature / Change name:** DS-6 — Document Intelligence consumer cutover (Planet Mark / External Audit / UVDB / Customer Audit)
- **User goal:** Assurance consumers share one extraction spine via `DocumentIntelligenceService.process/extract_bytes(..., purpose=...)` instead of ad-hoc duplicate OCR paths.
- **In scope:** Purpose routing (`planet_mark` | `external_audit` | `uvdb` | `customer_audit`), Planet Mark year-reading OCR, external audit import OCR (covers UVDB + customer schemes)
- **Out of scope:** Frontend Document Control, library upload/index spine (DS-1/2), Azure DI prod enablement
- **Feature flag / kill switch:** Existing `external_audit_import_enabled`; OCR provider config unchanged

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Planet Mark PDF OCR | Direct `ExternalAuditOcrService.extract` | `DocumentIntelligenceService.extract_bytes(..., purpose="planet_mark")` |
| External audit import OCR | Direct `ExternalAuditOcrService.extract` | `DocumentIntelligenceService.extract_bytes` with scheme-mapped purpose |
| UVDB / customer audit attachments | Same import path, no separate extract fork | Purpose `uvdb` / `customer_audit` via `purpose_for_assurance_scheme` |
| Library uploads | Unchanged (DS-1/2) | Unchanged |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive purpose literals; consumer response shapes unchanged
- **Breaking changes:** None
- **Migration:** None
- **Rollback strategy:** Revert squash merge; consumers fall back to direct OCR collaborator

## 4) Acceptance Criteria (AC)

- [x] AC-01: `DocumentIntelligenceService` accepts `planet_mark`, `external_audit`, `uvdb`, `customer_audit` purposes
- [x] AC-02: Planet Mark OCR extract/apply schema unchanged (year-reading field parsing preserved)
- [x] AC-03: External audit import uses DIS with scheme-mapped purpose (UVDB → `uvdb`, customer → `customer_audit`)
- [x] AC-04: Azure DI remains optional enrichment on Planet Mark only; prod DI gate unchanged
- [x] AC-05: No changes to Document Control frontend or DS-5 version FK migrations

## 5) Testing Evidence

- [x] `pytest tests/unit/test_document_intelligence_service.py`
- [x] `pytest tests/unit/test_planet_mark_pdf_ocr_service.py`
- [x] `pytest tests/unit/test_external_audit_ocr_service.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Planet Mark OCR unit tests pass with DIS spine injection
- [x] CUJ-02: Audit merge purpose bypasses library thin-native skip
- [x] CUJ-03: `purpose_for_assurance_scheme` maps UVDB and customer schemes

## 7) Observability & Ops

- Extraction method / OCR provider status fields unchanged on import jobs and Planet Mark preview
- Purpose is routing-only (not persisted); existing job metadata fields suffice

## 8) Release Plan

1. Draft PR → CI green
2. Staging: Planet Mark OCR extract preview on sample PDF
3. Staging: External audit import on UVDB + ISO sample reports

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: Contracts
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [x] Gate 4: Canary (N/A ok)
- [ ] Gate 5: Production verification plan

**Do not merge** — awaiting Gate 2–5.
