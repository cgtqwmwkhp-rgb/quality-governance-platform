# Change Ledger (CL-PM-PDF-YEAR-EVIDENCE)

**Path claim:** `path11/pm-pdf-year-evidence`

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkYearEvidenceHelpers.ts`
- `frontend/src/pages/planetMarkYearEvidencePanel.tsx`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkYearEvidenceHelpers.test.ts`
- `frontend/src/pages/__tests__/planetMarkYearEvidencePanel.test.tsx`
- `frontend/src/api/planetMarkClient.ts`
- `frontend/src/api/planetMarkClient.test.ts`
- `frontend/src/api/client.ts` (type exports only)
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `src/api/routes/planet_mark.py` (certification checklist types)
- `scripts/governance/pr_body_pm_pdf_year_evidence.md`

**Zero overlap** with parallel lanes: RiskProfile, RiskHeatMap, risk_register import, admin harden, App.tsx, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-PDF — Measurement Report + Certificate upload on Years tab
- **User goal:** Operators upload official Planet Mark Measurement Report PDF and Certificate PDF per reporting year (YE2024/YE2025/YE2026) without waiting for MS XLSX carbon ingest.
- **In scope:** Years tab evidence card; `listEvidence` + `uploadEvidence` wire; inline Retry on 503/timeout; honest empty state; MS XLSX placeholder unchanged; vitest; en/cy i18n; optional BE checklist types
- **Out of scope:** MS XLSX year ingest; App.tsx; Alembic; Risk/admin lanes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Years tab | Disabled “Upload MS XLSX (coming soon)” only | **Planet Mark reports & certificate** card with two PDF upload slots + evidence list |
| Evidence API | Backend live, no Years UX | `listEvidence` / `uploadEvidence` wired with loading + inline Retry |
| MS XLSX ingest | Honest placeholder | Unchanged — still “coming soon” |
| Certification checklist | No report/certificate types | `measurement_report` + `planet_mark_certificate` optional checklist rows |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Uses existing multipart evidence endpoints — no schema/Alembic changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Years tab shows “Planet Mark reports & certificate” card whenever a year is selected
- [x] AC-02: Measurement Report upload uses `document_type=measurement_report`, `evidence_category=certification`
- [x] AC-03: Certificate upload uses `document_type=planet_mark_certificate`, `evidence_category=certification`
- [x] AC-04: Evidence list shows name, type, size, uploaded_at with honest empty state
- [x] AC-05: 503/timeout → inline Retry; no toast spam
- [x] AC-06: MS XLSX placeholder remains separate and honesty-labeled “coming soon”
- [x] AC-07: Vitest covers upload panel empty/list/error states
- [x] AC-08: en + cy flat keys for new copy

## 5) Testing Evidence

- [x] Vitest — planetMarkYearEvidenceHelpers + planetMarkYearEvidencePanel + PlanetMark shell
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Years → select YE2024 → see evidence card + empty list → upload Measurement Report PDF → list refreshes
- [x] CUJ-02: Years → evidence list 503 → inline Retry → list loads
- [x] CUJ-03: Years with no carbon → MS XLSX placeholder still visible alongside evidence card

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-years-evidence-panel`, `planet-mark-years-evidence-upload-measurement-report`, `planet-mark-years-evidence-upload-certificate`, `planet-mark-years-evidence-list-empty`, `planet-mark-years-evidence-list-error`, `planet-mark-years-evidence-list-retry`

## 8) Checklist id

**PM-PDF-YEAR-EVIDENCE** (living tracker)

## Gate 0–5

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API client `listEvidence` / `uploadEvidence` typed + exported
- [x] **Gate 2:** UX card + upload slots + list + empty/error honesty
- [x] **Gate 3:** Vitest empty/list/error states
- [x] **Gate 4:** en/cy i18n union
- [ ] **Gate 5:** CI green (babysit)
