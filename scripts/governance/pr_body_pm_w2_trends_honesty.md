# Change Ledger (CL-PM-W2-TRENDS-HONESTY)

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkHelpers.ts`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_pm_w2_trends_honesty.md`

**Zero overlap** with parallel lanes: ComplianceAutomation*, Analytics*, Assessment*, Actions, Audits, Layout, App, client, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-W2 / PM-E2 — Planet Mark Trends section honesty
- **User goal:** Operators on `/planet-mark?section=trends` see YoY, scope, and Scope 3 category deltas only when the API returns recorded totals for both sides of a comparison; otherwise an honest empty state or a thin prior-year list — never fabricated tCO₂e.
- **In scope:** Trends view-model helpers; YoY card + historical table columns; scope/category delta tables; thin prior-year strip; scope3 fetch on trends tab; vitest; minimal `planet_mark.shell.trends.*` i18n
- **Out of scope:** Backend dashboard schema changes; monthly ingest; client.ts / Layout / App; legacy tab parity
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before (PM-W1) | After (PM-W2) |
|---------|----------------|---------------|
| Trends YoY | Historical totals table only | YoY per-FTE card when API provides `yoy_change_percent`; YoY total/per-FTE columns in historical table |
| Scope deltas | Not shown | Scope 1/2/3 current vs prior year when both sides have positive recorded totals |
| Category deltas | Not shown | Measured Scope 3 categories with current/prior totals when scope3 API returns data |
| Zero / missing totals | Rendered as `0.0` if API sent zero | Positive totals only for comparative panels; missing shown as `—` or “No emissions recorded” |
| Multi-year, no totals | Full empty state | Thin prior-year list when API returns years without enough recorded carbon |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only; consumes existing dashboard, years, and scope3 endpoints
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: YoY per-FTE delta shown when dashboard returns `yoy_change_percent` for selected year
- [x] AC-02: Historical table includes YoY total and YoY per-FTE columns computed from adjacent `historical_years` rows
- [x] AC-03: Scope delta table shown only when current and prior year both have positive scope totals
- [x] AC-04: Category delta table shown only for measured Scope 3 categories with recorded current/prior totals
- [x] AC-05: No fabricated tCO₂e — null/zero placeholders render as `—` or honest “No emissions recorded”
- [x] AC-06: Thin prior-year strip when multiple reporting years exist without comparative totals
- [x] AC-07: Honest full empty when no years, no totals, and no thin prior-year case applies
- [x] AC-08: Vitest covers helpers + page trends honesty scenarios

## 5) Testing Evidence

- [x] Vitest — `PlanetMark.test.tsx`, `planetMarkHelpers.test.ts` (21 tests)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Two years with live totals — YoY card, historical table, scope deltas visible
- [x] CUJ-02: Two years with zero/unset totals — thin prior-year list, no fake `0.0` tCO₂e
- [x] CUJ-03: Single year / empty historical — honest trends empty state

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-section-trends`, `planet-mark-trends-yoy`, `planet-mark-trends-historical`, `planet-mark-trends-scope`, `planet-mark-trends-category`, `planet-mark-trends-thin-prior`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/planet-mark?section=trends`

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

- [x] `cd frontend && npx vitest run src/pages/__tests__/PlanetMark.test.tsx src/pages/__tests__/planetMarkHelpers.test.ts`
- [ ] Manual: `/planet-mark?section=trends` — verify YoY/scope/category deltas with live data; thin prior-year and empty honesty without fake totals

---

# Path claim (PM-W2 exclusive)

| Path | Status |
|------|--------|
| `frontend/src/pages/PlanetMark.tsx` | **CLAIMED** |
| `frontend/src/pages/planetMarkHelpers.ts` | **CLAIMED** |
| `frontend/src/pages/__tests__/PlanetMark.test.tsx` | **CLAIMED** |
| `frontend/src/pages/__tests__/planetMarkHelpers.test.ts` | **CLAIMED** |
| `frontend/src/i18n/locales/en.json` | **CLAIMED** |
| `frontend/src/i18n/locales/cy.json` | **CLAIMED** |
| `scripts/governance/pr_body_pm_w2_trends_honesty.md` | **CLAIMED** |

**FORBIDDEN (parallel PRs):** ComplianceAutomation*, Analytics*, Assessment*, Actions, Audits, Layout, App, client, Alembic
