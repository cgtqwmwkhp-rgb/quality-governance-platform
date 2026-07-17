# Change Ledger (CL-RR-HM-RAIL-PROFILE-404)

## 1) Summary
- **Feature / Change name:** RR-HM-RAIL + RR-PROFILE-404 — compact heat-map detail rail + fix false “Risk not found”
- **User goal:** Cell detail list is a fixed-height scroll window with dense rows; opening a risk from register/heatmap must show the profile when the risk exists.
- **In scope:** `RiskHeatMap.tsx` rail max-height + compact rows; `RiskProfile.tsx` load profile SSOT first then soft-fail secondary panels; Vitest; this ledger
- **Out of scope:** Alembic, App.tsx, Admin, Planet Mark, Action Plan→CAPA
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `RiskHeatMap.tsx`, `RiskProfile.tsx`, related Vitest
- **Backend / APIs / DB:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX + more tolerant FE load; profile 404 still honest
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Detail rail has fixed/max height (~22rem) and scrolls internally (`overflow-y-auto`)
- [x] AC-02: Risk rows are compact (title + one meta line + Open) — not tall field cards
- [x] AC-03: Profile load uses getProfile for not-found; secondary 404s do not blank the page
- [x] AC-04: Vitest covers compact rail + secondary-404 honesty

## 5) Testing Evidence (link to runs)
- [x] Frontend Vitest — RiskHeatMap + RiskProfile (17 passed, local)
- [ ] CI after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Heat map cell → compact scrollable list → Open → profile
- [x] CUJ-02: Open existing risk → profile hero loads even if notes/actions/upstream 404

## 7) Observability & Ops
- trackError on profile vs secondary load failures separately

## 8) Release Plan (Local → Staging → Canary → Prod)
- Staging: open Rare×Minor cell (many risks); confirm scroll window; Open one risk; confirm not “Risk not found”
- Prod: hard-refresh SWA after bake

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Profile load broken / heat map rail unusable
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform / Risk Register track

## 10) Evidence Pack (links)
- CI: linked after PR creation
- Tip base: `d0eae6f6`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Rail UX + profile load fix implemented
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Rollback plan verified
- [x] **Gate 5:** Evidence pack / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/components/risk/RiskHeatMap.tsx`
- `frontend/src/components/risk/__tests__/RiskHeatMap.test.tsx`
- `frontend/src/pages/RiskProfile.tsx`
- `frontend/src/pages/__tests__/RiskProfile.test.tsx`
- `scripts/governance/pr_body_rr_hm_rail_profile_404.md`
