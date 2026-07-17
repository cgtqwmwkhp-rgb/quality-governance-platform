# Change Ledger (CL-CA-W1c-SCORE-KILL)

**Path claim:** `path11/ca-w1c-score-kill`

## File allowlist (exclusive)

- `frontend/src/pages/ComplianceAutomation.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_ca_w1c_score_kill.md`

**Zero overlap** with parallel lanes: `Investigations*` (#1069), `Documents*` (#1070), `PlanetMark*` (#1068), Layout/App/client.ts spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 CA-W1c — Kill faux zero score on Monitoring overview KPI
- **User goal:** When no live compliance score data exists, the hero card shows **—** and honest copy — not misleading `0%` / `+0%` demo signal. Score tab empty states from CA-W1 waves remain unchanged.
- **In scope:** `hasLiveComplianceScore` helper; overview KPI honesty; vitest; minimal i18n
- **Out of scope:** Remove Score tab; Layout nav rename; backend score API
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Score overview KPI (hero) | Always `0%` + `+0%` trend when API empty | **—** + “No live score yet” when no categories and overall is 0 |
| Score tab breakdown/gaps | Already honest empty (CA-W1) | Unchanged |
| Live score tenant | Shows % + trend delta | Unchanged |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** UI-only — same API reads
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Empty score API → overview shows `—`, not `0%`
- [x] AC-02: Empty score API → no `+0%` trend chip
- [x] AC-03: Categories or non-zero overall → live % + trend render
- [x] AC-04: Score tab honest empty states still pass existing tests
- [x] AC-05: Helper unit tested

## 5) Testing Evidence

- [x] Vitest — `ComplianceAutomation.test.tsx`, `complianceAutomationHelpers.test.ts`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fresh tenant `/compliance-automation` — hero score card honest empty
- [x] CUJ-02: Tenant with ISO9001 category score — hero shows live %

## 7) Observability & Ops

- **Playwright hooks:** `monitoring-score-overview`, `monitoring-score-overview-empty`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: Monitoring page hero card with/without score data

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: CA-W1b/W1d Monitoring honesty waves

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts`
- [ ] Manual: empty score tenant — hero shows — not 0%
- [ ] Manual: tenant with categories — hero shows live %
