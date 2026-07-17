# Change Ledger (CL-RR-W5-SLT-DASHBOARD)

**Path claim:** `path11/rr-w5-slt-dashboard`

## File allowlist (exclusive)

- `src/api/routes/risk_register.py` (list DTO: `trend` + `updated_at` only)
- `frontend/src/api/riskRegisterClient.ts` (`RiskEntry.trend`)
- `frontend/src/pages/RiskRegister.tsx` (list columns + SLT panels)
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `frontend/src/pages/__tests__/RiskRegister.a11y.test.tsx`
- `frontend/src/i18n/locales/en.json` (soft-add keys only)
- `frontend/src/i18n/locales/cy.json` (soft-add keys only)
- `tests/unit/test_risk_register_list_slt.py`
- `scripts/governance/pr_body_rr_w5_slt_dashboard.md`

**Zero overlap** with parallel lanes: `RiskProfile.tsx` (RR-W3), `App.tsx`, `Layout.tsx`, Alembic, PlanetMark*, admin pages, `audit_service.py`, heat map write paths.

## 1) Summary

- **Feature / Change name:** Path11 RR-W5 — SLT dashboard parity on Enterprise Risk Register list
- **User goal:** SLT can see Excel-dashboard-style Top 10 residual risks, overdue reviews, and Trend / Last updated columns without inventing missing data.
- **In scope:** List DTO fields; register list columns; Top 10 + overdue honesty panels; soft en/cy keys; Vitest + unit tests; Change Ledger
- **Out of scope:** Risk Profile page; new Alembic; dedicated board export PDF; App/Layout navigation; heat map changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After (RR-W5) |
|---------|--------|---------------|
| List API | Scores + next_review_date | + `trend` (tag-persisted or null) + `updated_at` |
| Register table | No trend / last updated | Columns with honesty "—" when missing |
| SLT panels | Summary cards only | Top 10 residual + overdue reviews honesty |
| Overdue filter | Hero card only | SLT panel Filter overdue → hero filter |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive list DTO fields; no schema migration
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: List columns Trend + Last updated when list DTO provides data; "—" when not
- [x] AC-02: Top 10 risks panel by residual/net score with honesty scope note
- [x] AC-03: Overdue reviews honesty (`next_review_date` before today) + summary count
- [x] AC-04: Soft-union en/cy i18n keys for SLT/list columns
- [x] AC-05: Vitest coverage for Top 10, overdue filter, trend/updated columns
- [x] AC-06: List endpoint exposes `trend` + `updated_at` without Alembic

## 5) Testing Evidence

- [x] pytest — `tests/unit/test_risk_register_list_slt.py`
- [x] vitest — `frontend/src/pages/__tests__/RiskRegister.test.tsx` (SLT describe)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] **CUJ-01:** Open Risk Register → Top 10 panel lists highest residual scores
- [x] **CUJ-02:** Overdue panel Filter overdue → table shows only overdue rows
- [x] **CUJ-03:** Risk without trend/updated_at shows honesty "—" (not fabricated stable/today)

## 7) Observability & Ops

- **Playwright hooks:** `risk-slt-panels`, `risk-slt-top10`, `risk-slt-overdue`, `risk-slt-overdue-filter`, `risk-trend-*`, `risk-updated-*`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: register list columns + SLT panels with seeded overdue risk

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

- [x] `pytest tests/unit/test_risk_register_list_slt.py -q`
- [x] `cd frontend && npx vitest run src/pages/__tests__/RiskRegister.test.tsx`
- [ ] Manual: Risk Register → confirm Top 10 order, overdue filter, Trend/Last updated columns
