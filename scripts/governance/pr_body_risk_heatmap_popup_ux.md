# Change Ledger (RISK-HEATMAP-POPUP-UX)

## 1) Summary
- **Feature / Change name:** Heat map cell popup UX (remove side drawer)
- **User goal (1–2 lines):** Drill into cell risks via a rich hover/focus popup with selectable risks; make placement/highlight controls self-explanatory.
- **In scope:** Remove Sheet drawer from heat map; interactive cell popup; segmented “Place on grid” / “Highlight” controls with tooltips; RiskRegister wiring cleanup; unit tests.
- **Out of scope:** Backend contract changes; new score models; legend/summary panel redesign.
- **Feature flag / kill switch:** None — FE-only UX.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/components/risk/RiskHeatMap.tsx`; `frontend/src/pages/RiskRegister.tsx`; `frontend/src/components/risk/__tests__/RiskHeatMap.test.tsx`.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** FE-only; existing heatmap matrix payload unchanged.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** Side drawer removed — drill-down is popup + Show in register / filter chip.
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable — revert application deploy.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Side drawer / Sheet for cell risks is removed from the heat map.
- [x] **AC-02:** Hover/focus on a populated cell opens a popup listing selectable risks that open detail.
- [x] **AC-03:** Placement and highlight controls are labeled groups with explanatory tooltips (After/Before controls, Movement; None/Outside appetite/Overdue).
- [x] **AC-04:** Unit tests cover popup risk select and absence of cell sheet.

## 5) Testing Evidence (link to runs)
- [x] `npx vitest run src/components/risk/__tests__/RiskHeatMap.test.tsx src/pages/__tests__/RiskRegister.test.tsx src/pages/__tests__/RiskRegister.a11y.test.tsx` — passed locally.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Risk Register → Heat Map → hover cell → click risk title → risk detail opens.
- [x] **CUJ-02:** Heat Map → popup “Show in register” filters register to that L×I band; clear chip restores.

## 7) Observability & Ops
- **Logs:** None new.
- **Metrics:** None new.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/risk-register?view=heatmap`; hover populated cell; open a risk; confirm no side drawer.
- **Canary plan:** Normal staging → prod deploy path.
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==LIVE; SWA serves new heat map controls/popup.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Popup unusable, heat map blank, or register navigation broken from cell actions.
- **Rollback steps:** Revert this PR and redeploy prior release.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** (filled after create)
- **CI run(s):** Added by GitHub Actions after PR creation.
- **Staging deploy evidence:** Pending deployment.
- **Canary evidence:** Pending deployment.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** FE-only; no migration.
- [x] **Gate 2:** Local unit + a11y tests pass.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
