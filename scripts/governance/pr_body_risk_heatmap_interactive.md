# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Interactive Enterprise Risk heat map (P0–P2)
- **User goal (1–2 lines):** Make the 5×5 residual heat map an operational filter and executive view — clickable cells, honest KPIs, inherent/delta modes, focus overlays, trends, and board-pack export.
- **In scope:** Heatmap/summary/list contract parity; cell filters; tooltip + sheet drawer; score_type residual|inherent|delta; intensity/focus/appetite overlay; trends top movers; FE `RiskHeatMap` + `Sheet`.
- **Out of scope:** What-if drag scoring; legacy `/api/v1/risks/matrix`; new snapshot tables.
- **Feature flag / kill switch:** None — additive UI/API fields.

## 2) Impact Map
- **Frontend:** `RiskRegister.tsx`, `components/risk/RiskHeatMap.tsx`, `components/ui/Sheet.tsx`, `riskRegisterClient.ts`
- **Backend:** `risk_service.get_heat_map_data`, `risk_register` list/summary/heatmap/trends routes, schemas
- **APIs:** `GET /risk-register/heatmap` (+ status, score_type); summary filters; list L×I filters; trends `include_movers`
- **Database:** None (uses `risks_v2`, `risk_assessment_history`, `risk_appetite_statements`)
- **OpenAPI:** Regen baseline if CI requires

## 3) Compatibility & Data Safety
- Additive heatmap cell fields; legacy `cells` flat array retained.
- Canonical banding: low ≤4, medium 5–9, high 10–16, critical ≥17 (summary aligned).
- Trends default response remains a list; movers only when `include_movers=true`.

## 4) Test plan
- Unit: banding + heatmap enriched cells / inherent / delta
- FE: heat map cell select + filters (where covered)
- Manual: tip LIVE — KPI Total == heatmap Total; click cell → register filter; tooltip; inherent toggle; board pack download
