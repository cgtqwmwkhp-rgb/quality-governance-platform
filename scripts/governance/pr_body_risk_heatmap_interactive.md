# Change Ledger (RISK-HEATMAP-INTERACTIVE)

## 1) Summary
- **Feature / Change name:** Interactive Enterprise Risk heat map (P0–P2)
- **User goal (1–2 lines):** Turn the 5×5 residual heat map into an operational filter and executive view — clickable cells, honest KPIs, inherent/delta modes, focus overlays, trends, and board-pack export.
- **In scope:** Heatmap/summary/list contract parity; cell filters; tooltip + sheet drawer; score_type residual|inherent|delta; intensity/focus/appetite overlay; trends top movers; FE `RiskHeatMap` + `Sheet`.
- **Out of scope:** What-if drag scoring; legacy `/api/v1/risks/matrix`; new snapshot tables.
- **Feature flag / kill switch:** None — additive UI/API fields.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/RiskRegister.tsx`; `frontend/src/components/risk/RiskHeatMap.tsx`; `frontend/src/components/ui/Sheet.tsx`; `frontend/src/api/riskRegisterClient.ts`; tests + e2e mocks.
- **Backend (handlers/services):** `src/domain/services/risk_service.py` (`get_heat_map_data`, trends movers); `src/api/routes/risk_register.py` (list/summary/heatmap/trends).
- **APIs (endpoints changed/added):** `GET /risk-register/heatmap` (+ `status`, `score_type`); summary filters; list L×I filters; trends `include_movers`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `HeatMapCell` / `HeatMapSummary` / `HeatMapResponse` expanded.
- **Database (migrations/entities/indexes):** None (uses `risks_v2`, `risk_assessment_history`, `risk_appetite_statements`).
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive heatmap cell fields; legacy flat `cells` array retained; trends default remains a list.
- **Tolerant reader / strict writer applied?** Yes — FE consumes `matrix` authoritatively with label/score fallbacks.
- **Breaking changes:** Summary/engine high band aligned to 10–16 (was 12–16 / 5–11 medium).
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable — revert application deploy.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Heat map consumes API `matrix` and sidebar Total/Critical/High match heatmap summary for the same filters.
- [x] **AC-02:** Clicking a populated cell opens the sheet and can filter the register to that L×I band (clearable chip + URL params).
- [x] **AC-03:** Residual / Inherent / Delta modes, focus appetite/overdue, appetite overlay, trends/top movers, and board-pack export are available on the heat map view.
- [x] **AC-04:** Unit + FE tests cover banding, enriched cells, and heat map cell select.

## 5) Testing Evidence (link to runs)
- [x] Backend unit: `python3.11 -m pytest tests/unit/test_risk_heatmap_interactive.py tests/unit/test_risk_service.py::TestRiskScoringEngine` — passed.
- [x] Frontend: `npx vitest run src/components/risk/__tests__/RiskHeatMap.test.tsx src/pages/__tests__/RiskRegister.test.tsx src/pages/__tests__/RiskRegister.a11y.test.tsx` — passed.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Risk Register → Heat Map → click cell → sheet lists risks → Show in register filters the table.
- [x] **CUJ-02:** Category/department/status filters refresh summary + heatmap together; KPI Total remains honest when summary loads.

## 7) Observability & Ops
- **Logs:** None new.
- **Metrics:** Heatmap/summary `filters_applied` echo for support diagnosis.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/risk-register?view=heatmap`; confirm counts; click cell; toggle inherent; download board pack.
- **Canary plan:** Normal staging → prod deploy path.
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==LIVE; KPI Total equals heatmap Total; cell drill-down works.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Heat map blank/wrong totals, register filter stuck, or TypeScript/runtime regression on Risk Register.
- **Rollback steps:** Revert this PR and redeploy prior release.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1038
- **CI run(s):** Added by GitHub Actions after PR creation.
- **Staging deploy evidence:** Pending deployment.
- **Canary evidence:** Pending deployment.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** Additive API/UI; no migration required.
- [x] **Gate 2:** Local unit + FE tests pass.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
