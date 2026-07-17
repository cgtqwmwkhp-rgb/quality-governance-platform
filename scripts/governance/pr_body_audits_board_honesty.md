# Change Ledger (CL-AUDITS-BOARD-HONESTY)

## File allowlist (exclusive)

- `frontend/src/pages/Audits.tsx`
- `frontend/src/pages/__tests__/Audits.test.tsx`
- `scripts/governance/pr_body_audits_board_honesty.md`

**Zero overlap** with parallel lanes: ComplianceAutomation, documents, calendar, engineers, Layout, Actions My Work, GKB audit-pack, SWA. Prefer English literals / `t(..., default)` (no `en.json`/`cy.json` edits).

## 1) Summary

- **Feature / Change name:** Path11 — Audits board empty-state honesty (KPI vs empty theatre)
- **User goal:** Operators never see “21 Total Audits” alongside global “No audits found”; empty copy reflects global vs filtered vs board-lane reality.
- **In scope:** Board/list empty-state branching in `Audits.tsx`; vitest honesty suite; Change Ledger
- **Out of scope:** ComplianceAutomation, documents, calendar, engineers; locale file edits; backend API
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Board (global empty) | Four columns each showed “No audits found” while KPI tiles could show totals | Single global empty when `scopedAudits.length === 0` |
| Board (filtered empty) | Misleading global empty when search/KPI filters hid all rows | Single “No audits match filters” when totals/search scope still has audits |
| Board (lane mismatch) | Columns repeated “No audits found” for draft/cancelled-only datasets | Board-level “No board-visible audits” + per-column lane copy |
| List empty row | Always “No audits found” title even when hero filter active | Honest global vs filter-empty titles/descriptions |
| Tests | No KPI/empty contradiction proof | Vitest board honesty describe block |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UX copy branching only
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Global empty only when `scopedAudits.length === 0`
- [x] AC-02: Filter/search/hero empty uses “No audits match filters” when KPI total > 0
- [x] AC-03: Board never repeats global “No audits found” in columns when audits exist
- [x] AC-04: Draft/cancelled-only datasets get board-lane honesty, not fake global empty
- [x] AC-05: Vitest covers global, positive KPI, filter-empty, lane-empty cases

## 5) Testing Evidence

- [x] Vitest `Audits.test.tsx` — `Audits board empty-state honesty` describe block
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Board default view — KPI totals never contradict global empty theatre
- [x] CUJ-02: Hero filter → list — filter-empty copy when rows hidden but totals positive
- [x] CUJ-03: Non-board statuses — lane-empty honesty instead of four “No audits found”

## 7) Observability & Ops

- **Playwright hooks:** `audits-board-empty`, `audits-board-filter-empty`, `audits-board-lane-empty`, `audits-list-empty`, `audits-list-filter-empty`, `audits-list-unavailable`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip + smoke `/audits` board

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

- [ ] `cd frontend && npx vitest run src/pages/__tests__/Audits.test.tsx`
- [ ] Manual: `/audits` board with mixed statuses — no KPI + global empty contradiction
- [ ] Manual: hero filter with zero matches — filter-empty copy, total KPI unchanged
