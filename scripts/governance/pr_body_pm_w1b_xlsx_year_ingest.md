# Change Ledger (CL-PM-W1B-XLSX-YEAR-INGEST)

**Path claim:** `path11/pm-w1b-xlsx-year-ingest`

## File allowlist (exclusive)

- `src/domain/services/planet_mark_xlsx_ingest_service.py`
- `src/api/schemas/planet_mark.py` (MsXlsxYearIngestResponse only)
- `src/api/routes/planet_mark.py` (ingest-xlsx route only)
- `tests/unit/test_planet_mark_xlsx_ingest_service.py`
- `frontend/src/api/planetMarkClient.ts` (`ingestMsXlsx` + response type)
- `frontend/src/api/planetMarkClient.test.ts`
- `frontend/src/api/client.ts` (type export only)
- `frontend/src/pages/planetMarkYearXlsxIngestHelpers.ts`
- `frontend/src/pages/planetMarkYearXlsxIngestPanel.tsx`
- `frontend/src/pages/__tests__/planetMarkYearXlsxIngestHelpers.test.ts`
- `frontend/src/pages/__tests__/planetMarkYearXlsxIngestPanel.test.tsx`
- `frontend/src/pages/planetMarkHelpers.ts` (years VM panel flag)
- `frontend/src/pages/PlanetMark.tsx` (replace MS XLSX placeholder with panel)
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/i18n/locales/en.json` (soft-union ingest keys)
- `frontend/src/i18n/locales/cy.json` (soft-union ingest keys)
- `scripts/governance/pr_body_pm_w1b_xlsx_year_ingest.md`

**Coordination:** PR #1097 owns PDF Measurement Report + Certificate evidence on Years. This lane keeps MS XLSX as a separate panel and does not weaken PDF evidence wiring.

**Zero overlap** with RiskProfile/Register, admin pages, App.tsx, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-W1b — MS XLSX year carbon ingest
- **User goal:** Operators upload Planet Mark MS output XLSX (Member Copy) on Years and see real year totals (tCO₂e / scopes / FTE) — workbook is SSOT for numbers.
- **In scope:** BE parse+upsert; `POST /planet-mark/years/{id}/ingest-xlsx`; FE upload panel; honesty errors; pytest + vitest; en/cy
- **Out of scope:** PDF evidence (#1097); monthly series; Alembic; App.tsx
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Years tab MS XLSX | Disabled “coming soon” placeholder | Live upload + success/error honesty + ingested totals |
| API | No year XLSX ingest | `POST /api/v1/planet-mark/years/{id}/ingest-xlsx` |
| CarbonReportingYear | Manual / PDF-import sync only | Upserted from MS workbook Scope/Total CF sheets |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive endpoint + FE panel; uses existing `CarbonReportingYear` / `EmissionSource` (imported aggregates); no Alembic
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Parse Planet Mark MS Member Copy (`Scope (Market Based)` + `Total CF`)
- [x] AC-02: Upsert year totals + imported aggregate sources for selected year
- [x] AC-03: Filename YE label mismatch → honest 400 (no silent wrong-year write)
- [x] AC-04: Years tab replaces coming-soon with enabled Upload MS XLSX
- [x] AC-05: Success shows ingested totals; 503/timeout → inline Retry
- [x] AC-06: pytest + vitest cover parse/ingest + panel helpers
- [x] AC-07: en + cy soft-union keys for new copy

## 5) Testing Evidence

- [x] pytest `tests/unit/test_planet_mark_xlsx_ingest_service.py` (+ real YE2024 file when present)
- [x] vitest helpers/panel/PlanetMark/client
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Years → YE2024 → upload MS Member Copy → totals ~654.5 tCO₂e
- [x] CUJ-02: Upload YE2024 workbook onto YE2025 → mismatch error, no write
- [x] CUJ-03: PDF evidence panel from #1097 remains a separate surface (no conflict claim)

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-years-xlsx-ingest`, `planet-mark-years-xlsx-ingest-button`, `planet-mark-years-xlsx-ingest-totals`, `planet-mark-years-xlsx-ingest-error`, `planet-mark-years-xlsx-ingest-retry`
- **Audit:** `_audit("ingest_ms_xlsx", …)`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: Years → YE2024/YE2025 → upload Member Copy XLSX

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- Local MS workbooks: `Plantexpand_Planet Mark_MS output - YE2024/YE2025 - Member Copy.xlsx` (Downloads; not committed)
- CI run(s): linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** BE parse + ingest route
- [x] **Gate 2:** FE panel wired (no coming soon)
- [x] **Gate 3:** pytest + vitest
- [x] **Gate 4:** en/cy soft-union
- [ ] **Gate 5:** CI green (babysit)

## Test plan

- [x] `pytest tests/unit/test_planet_mark_xlsx_ingest_service.py -q`
- [x] `cd frontend && npx vitest run src/pages/__tests__/planetMarkYearXlsxIngestHelpers.test.ts src/pages/__tests__/planetMarkYearXlsxIngestPanel.test.tsx src/pages/__tests__/PlanetMark.test.tsx src/api/planetMarkClient.test.ts src/pages/__tests__/planetMarkHelpers.test.ts`
- [ ] Manual: Years → YE2024 → upload Member Copy → KPI cards refresh
