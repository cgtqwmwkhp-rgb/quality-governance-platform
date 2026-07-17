# Change Ledger (CL-PM-E4-MONTHLY-EVIDENCE)

**Path claim:** `path11/pm-e4-monthly-evidence`

## File allowlist (exclusive)

- `frontend/src/pages/PlanetMark.tsx`
- `frontend/src/pages/planetMarkMonthlyEvidenceHonesty.ts`
- `frontend/src/pages/__tests__/planetMarkMonthlyEvidenceHonesty.test.ts`
- `frontend/src/pages/__tests__/PlanetMark.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_pm_e4_monthly_evidence.md`

**Zero overlap** with parallel lanes: MAP-W2 builders*, Calendar*, AuditExecution* (#1076), Portal* (#1077), Complaint* (#1078), PM-W3 export already shipped (#1072). Soft i18n only. No Layout/App/client.ts / Alembic.

## 1) Summary

- **Feature / Change name:** Path11 PM-E4 — Planet Mark Monthly evidence upload honesty + forecast follow-on
- **User goal:** On `/planet-mark?section=monthly`, operators see an honesty shell: year evidence API availability, monthly emission ingest shell-only, and forecast-vs-5% S1&2 as follow-on — never a fabricated monthly grid or trajectory.
- **In scope:** Monthly section honesty panel + capability rows; helper; vitest; i18n (update monthly empty copy)
- **Out of scope:** Real monthly ingest UI; forecast charts; export pack redo (PM-W3); UVDB/ISO clone shell; client.ts spine
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Monthly tab | Generic empty “not connected” | Honesty panel + capability statuses + forecast follow-on copy |
| Year evidence | Invisible on Monthly | Explicit “API available” when year selected |
| Forecast | Implied by empty | Explicit follow-on vs 5% S1&2 |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only honesty shell; no new API calls required
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Monthly tab shows PM-E4 honesty panel when section=monthly
- [x] AC-02: Capability rows distinguish year evidence API / monthly ingest / forecast follow-on
- [x] AC-03: Forecast follow-on copy visible; no invented trajectory
- [x] AC-04: Select-year empty when no reporting year; ingest empty when year selected
- [x] AC-05: Vitest covers helper + PlanetMark monthly panel
- [x] AC-06: en + cy flat keys (≥95% cy for new keys); no export-pack redo

## 5) Testing Evidence

- [x] Vitest — planetMarkMonthlyEvidenceHonesty + PlanetMark monthly E4
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Planet Mark → Monthly → honesty panel + capability rows
- [x] CUJ-02: Monthly with selected year → ingest empty + forecast follow-on (no fake series)

## 7) Observability & Ops

- **Playwright hooks:** `planet-mark-section-monthly`, `planet-mark-monthly-e4-panel`, `planet-mark-monthly-e4-honesty`, `planet-mark-monthly-e4-capabilities`, `planet-mark-monthly-e4-forecast`
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: `/planet-mark?section=monthly` honesty panel

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback trigger:** Monthly honesty regression post-deploy
- **Rollback steps:** Revert squash commit; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)

- PR diff + vitest proofs in this branch
- Living tracker checklist id **PM-E4**

## 11) Gate Checklist

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive PlanetMark* allowlist respected
- [x] **Gate 2:** Local vitest green
- [ ] **Gate 3:** Required CI green on PR
- [ ] **Gate 4:** Squash-merge to main (serial tip LIVE)
- [ ] **Gate 5:** Staging smoke Monthly honesty panel

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/planetMarkMonthlyEvidenceHonesty.test.ts src/pages/__tests__/PlanetMark.test.tsx`
- [ ] Manual: `/planet-mark?section=monthly` — capability rows + forecast follow-on
