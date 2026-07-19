# Change Ledger (CL-PM-PACKS-EXPORT)

**Path claim:** `path11/pm-packs-export`

## File allowlist (exclusive)

- `src/domain/services/planet_mark_export_service.py`
- `src/api/routes/planet_mark.py` (export route only)
- `tests/unit/test_planet_mark_export_service.py`
- `tests/unit/test_planetmark_uvdb_route_harness.py` (export route assertion)
- `tests/integration/test_planetmark_uvdb_api.py` (export contract)
- `frontend/src/api/planetMarkClient.ts` (`downloadExportPack` + blob helper)
- `frontend/src/api/planetMarkClient.test.ts`
- `frontend/src/pages/planetMarkHelpers.ts` (export pack honesty notes)
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/pages/PlanetMark.tsx` (export section uses API)
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/i18n/locales/en.json` (export honesty + button labels)
- `frontend/src/i18n/locales/cy.json` (export honesty + button labels)
- `scripts/governance/pr_body_pm_packs_export.md`

**Coordination:** Does not touch UVDB, campaigns, audits, or PDF writer. Branded PDF remains an honesty follow-on.

## 1) Summary

- **Feature / Change name:** Path11 PM-PACKS — authenticated JSON + XLSX export packs
- **User goal:** Operators download live Planet Mark year packs (year totals, Scope 3, actions, hotspot initiatives) via authenticated API instead of dead client-side URL.
- **In scope:** BE `GET /planet-mark/years/{id}/export?format=json|xlsx`; FE blob download; honesty copy (JSON+XLSX LIVE, PDF follow-on); pytest + vitest; en/cy
- **Out of scope:** Branded PDF writer; UVDB; campaigns; audits; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Export tab | Client-built JSON only; dead `/export` URL helper | Authenticated JSON + XLSX downloads from live API |
| API | No export endpoint | `GET /api/v1/planet-mark/years/{year_id}/export?format=json\|xlsx` |
| Honesty copy | PDF + XLSX “not wired” | JSON + XLSX LIVE; PDF follow-on |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive read endpoint + FE wiring; no schema changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Export pack assembles year detail, Scope 3, actions, hotspot initiatives (FE shape parity)
- [x] AC-02: `format=json` returns downloadable JSON attachment
- [x] AC-03: `format=xlsx` returns openpyxl workbook (Summary, Scope 3, Actions, Hotspot initiatives)
- [x] AC-04: FE Export tab calls authenticated blob download (JSON + XLSX buttons)
- [x] AC-05: Honesty copy states JSON+XLSX LIVE, branded PDF follow-on (en + cy)
- [x] AC-06: pytest + vitest cover service, route harness, integration contract, client, PlanetMark panel
- [ ] AC-07: CI green — this PR

## 5) Testing Evidence

- [x] pytest `tests/unit/test_planet_mark_export_service.py`
- [x] pytest route harness + integration export contract
- [x] vitest `planetMarkClient.test.ts`, `planetMarkHelpers.test.ts`, `PlanetMark.test.tsx`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Years → Export → Download JSON pack for selected year
- [x] CUJ-02: Years → Export → Download XLSX pack for selected year
- [x] CUJ-03: Missing year returns 404; auth required (inherits planet-mark read contract)

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-export-json`, `planet-mark-export-xlsx`, `planet-mark-export-honesty`, `planet-mark-export-error`
- **Audit:** `_audit("export_pack", …)`

## 8) Release Plan

- Single PR to `main`; no migration; no feature flag

## Test plan

- [x] `pytest tests/unit/test_planet_mark_export_service.py tests/unit/test_planetmark_uvdb_route_harness.py`
- [x] `pytest tests/integration/test_planetmark_uvdb_api.py -k export`
- [x] `cd frontend && npx vitest run src/api/planetMarkClient.test.ts src/pages/__tests__/planetMarkHelpers.test.ts src/pages/__tests__/PlanetMark.test.tsx`
