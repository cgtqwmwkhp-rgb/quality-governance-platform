# Change Ledger (CL-RR-W4-EXCEL-IMPORT)

**Path claim:** `path11/rr-w4-excel-import`

## File allowlist (exclusive)

- `src/domain/services/risk_register_import_service.py`
- `src/api/routes/risk_register_import.py`
- `src/api/schemas/risk_register_import.py`
- `src/api/__init__.py` (router include only)
- `frontend/src/api/riskRegisterClient.ts`
- `frontend/src/pages/RiskRegister.tsx` (list import UI only)
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `tests/unit/test_risk_register_import_service.py`
- `scripts/governance/pr_body_rr_w4_excel_import.md`

**Zero overlap** with parallel lanes: RiskProfile (#1092 RR-W1), assess routes, Alembic W2, CAPA W3, Layout, App.

## 1) Summary

- **Feature / Change name:** Path11 RR-W4 — Enterprise Risk Register Excel dry-run import (Register sheet)
- **User goal:** Operators upload the Plantexpand Risk Register v2.0 XLSX, preview creates/updates/errors via dry-run, then commit upserts `EnterpriseRisk` rows preserving `PELR*` references with Gross→inherent and Net→residual field parity.
- **In scope:** Import service; `/risk-register/import/dry-run` + `/commit` routes; minimal list-page import UI; unit tests with generated XLSX fixture; en/cy i18n; Change Ledger
- **Out of scope:** Action Plan sheet → CAPA create (W3); dedicated notes API (Comments → `review_notes`; TODO W2); RiskProfile.tsx; assess/trend endpoints; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After (RR-W4) |
|---------|--------|---------------|
| Risk Register list | Manual add + CSV export only | XLSX file picker + dry-run dialog + commit |
| Backend | No workbook ingest | Parse Risk Register sheet; dry-run report; upsert by PELR* ref |
| Field mapping | N/A | Ref→reference; Gross→inherent; Net→residual; Comments→review_notes |
| Action Plan sheet | N/A | Explicitly skipped (CAPA W3 follow-on) |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Upsert by tenant + reference; existing PELR rows updated in place
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge; imported rows remain unless manually reverted

## 4) Acceptance Criteria (AC)

- [x] AC-01: XLSX Risk Register sheet parsed with required column validation
- [x] AC-02: Dry-run returns creates, updates, row errors without DB writes
- [x] AC-03: Commit upserts EnterpriseRisk preserving PELR* references
- [x] AC-04: Gross/Net score columns map to inherent/residual likelihood×impact
- [x] AC-05: Comments stored in review_notes (notes API deferred to W2)
- [x] AC-06: Action Plan sheet not imported (documented skip)
- [x] AC-07: Minimal import UI on Risk Register list (not Risk Profile)
- [x] AC-08: Unit tests with generated XLSX fixture

## 5) Testing Evidence

- [x] pytest — `tests/unit/test_risk_register_import_service.py`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Upload valid workbook → dry-run shows 1 create, 0 errors
- [x] CUJ-02: Existing PELR ref → dry-run shows update action
- [x] CUJ-03: Invalid ref → dry-run blocked with row error; commit rejected

## 7) Observability & Ops

- **Playwright hooks:** `risk-import-xlsx-button`, `risk-import-dialog`, `risk-import-commit`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: upload sample XLSX dry-run + commit

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [x] `pytest tests/unit/test_risk_register_import_service.py -q`
- [ ] Manual: Risk Register list → Import Excel → dry-run → commit sample PELR row
