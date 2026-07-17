# Change Ledger (CL-RR-HM-03)

## File allowlist (exclusive)

- `frontend/src/components/risk/RiskHeatMap.tsx`
- `frontend/src/components/risk/__tests__/RiskHeatMap.test.tsx`
- `frontend/src/pages/RiskRegister.tsx` (wire `riskDetails` + toggle select + Open→profile only)
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_rr_hm_03_detail_rail.md`

**Zero overlap** with parallel lanes: RR-W1 assess/trend (#1092), RR-W4 Excel import (#1093), `RiskProfile.tsx`, Alembic, `calendar_feed`, `App.tsx`, CAPA.

## 1) Summary

- **Feature / Change name:** Path11 HM-03 — Risk Register heat map cell detail rail
- **User goal:** Inspect all risks in a heat map cell without clipped hover popups; open Risk Profile from the rail.
- **In scope:** Replace absolute cell popup with click-sticky right-rail panel; FE-only `riskDetails` map from loaded register rows; vitest rail proofs; minimal en/cy i18n
- **Out of scope:** Backend heatmap builder changes, Risk Profile page, assess/trend flows, register table/dialog changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Heat map cell hover | Absolute popup dialog under cell (clips) | Hover ring/highlight only |
| Heat map cell click | Sets cell filter | Sticky selection; same cell or Clear toggles off |
| Layout | Matrix + legend/summary | Matrix \| detail rail (flex-1) \| Risk Levels + Summary |
| Detail rail empty | N/A | “Select a cell to inspect risks” |
| Detail rail selected | N/A | L×I header, counts, score, overdue/outside appetite, Show in register + Clear, scrollable risk cards with Open → `/risk-register/:id` |
| Risk cards | Title-only in popup (max 8) | Rich cards from `riskDetails` when on current page; fallback title from cell |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only; existing heatmap API unchanged
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Click populated cell → sticky selection with detail rail populated
- [x] AC-02: Click same cell again or Clear → selection cleared
- [x] AC-03: No absolute popup under cells (hover highlight only)
- [x] AC-04: Layout matrix \| detail rail \| legend/summary preserved
- [x] AC-05: Empty rail prompt “Select a cell to inspect risks”
- [x] AC-06: Rail header shows L×I, count, score, overdue/outside appetite + Show in register + Clear
- [x] AC-07: Scrollable risk cards for cell `risk_ids` with title/ref/date/category/owner/gross/net/status/next review when available
- [x] AC-08: Open navigates to `/risk-register/:id` via react-router
- [x] AC-09: Vitest covers rail (replaces hover-popup test)
- [x] AC-10: en/cy i18n for new rail strings

## 5) Testing Evidence

- [x] Vitest — `RiskHeatMap.test.tsx` (7 tests)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Operator opens heat map → selects populated cell → sees rail list without clipped popup
- [x] CUJ-02: Operator clicks Open on a risk card → navigates to Risk Profile
- [x] CUJ-03: Operator clicks same cell or Clear → rail returns to empty prompt

## 7) Observability & Ops

- **Playwright hooks:** `risk-heatmap-detail-rail`, `risk-heatmap-detail-empty`, `risk-heatmap-detail-header`, `risk-heatmap-detail-list`, `risk-heatmap-detail-card-{id}`, `risk-heatmap-detail-open-{id}`, `risk-heatmap-detail-show-register`, `risk-heatmap-detail-clear`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke Risk Register → Heat map → cell select → Open profile

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no spines)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/components/risk/__tests__/RiskHeatMap.test.tsx`
- [ ] Manual: heat map → click cell → rail shows risks; no hover popup
- [ ] Manual: Open → `/risk-register/:id`; Clear / re-click cell clears rail
