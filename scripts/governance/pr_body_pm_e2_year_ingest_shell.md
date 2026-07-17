# Change Ledger (CL-PM-E2-YEAR-INGEST-SHELL)

**Path claim:** `path11/pm-e2-year-ingest-shell`

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkHelpers.ts`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/pages/__tests__/planetMarkHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_pm_e2_year_ingest_shell.md`

**Zero overlap** with parallel lanes: ComplianceAutomation*, Analytics*, Assessment*, Actions, Audits, Layout, App, client.ts, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-E2 — Planet Mark Years ingest shell (prior-year honesty + MS XLSX placeholder)
- **User goal:** Operators on `/planet-mark?section=years` see honest empty states for reporting years without ingested carbon (including prior years), a disabled MS XLSX upload CTA placeholder when ingest is not wired, and live totals only when the API returns positive recorded values — never fabricated tCO₂e.
- **In scope:** Years section view-model helpers; KPI + all-years list honesty; prior-years-awaiting-ingest strip; MS XLSX upload placeholder (disabled); vitest; minimal `planet_mark.shell.years.*` i18n
- **Out of scope:** MS XLSX ingest API wiring; client.ts / backend routes; Trends/Monthly/Improve/Export changes; Layout/App
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before (PM-W2 tip) | After (PM-E2) |
|---------|-------------------|---------------|
| Year KPI cards | `0.0` when API sent zero | `—` unless positive recorded carbon total |
| All years list | `0.0 tCO₂e` for zero totals | “No emissions recorded” unless positive total |
| Selected year without ingest | KPI cards only | MS XLSX ingest placeholder card + disabled upload CTA |
| Prior years without ingest | Listed in all-years only | Dedicated “Prior years awaiting ingest” honesty strip |
| MS XLSX upload | N/A | Placeholder CTA (disabled) — ingest wired in follow-on |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only shell; existing Planet Mark APIs unchanged
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Selected year KPI cards use `—` when no positive carbon totals (no fake `0.0`)
- [x] AC-02: All-years list shows “No emissions recorded” for years without positive totals
- [x] AC-03: MS XLSX ingest placeholder shown when selected year lacks ingested carbon
- [x] AC-04: Upload CTA is disabled placeholder — no fake upload or fabricated totals
- [x] AC-05: Prior years without ingest listed in dedicated honesty strip
- [x] AC-06: Vitest covers helpers + page years ingest honesty scenarios

## 5) Testing Evidence

- [x] Vitest — `PlanetMark.test.tsx`, `planetMarkHelpers.test.ts`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Year with live totals — KPI cards and all-years list show formatted tCO₂e
- [x] CUJ-02: Year shell record without ingest — placeholder + disabled MS XLSX CTA, no fake numbers
- [x] CUJ-03: Multiple prior years without totals — prior-years-awaiting-ingest strip, honest labels

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-section-years`, `planet-mark-years-ingest-placeholder`, `planet-mark-years-prior-empty`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/planet-mark?section=years`

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
- [ ] Manual: `/planet-mark?section=years` — verify ingest placeholder, prior-year honesty, no fake `0.0` tCO₂e
