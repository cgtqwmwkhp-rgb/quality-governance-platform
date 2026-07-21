# Change Ledger (CL-CES-ASSET-BOARD-W2)

## 1) Summary
- **Feature / Change name:** CES Calibrations Wave 2 — Safety Asset Register board UX
- **User goal (1–2 lines):** Managers see a Training-style asset board with clickable hero bands, rollups by engineer/vehicle/type, sort/filter, and Sheet kit drill-in — fed by the Wave 1 CES import.
- **In scope:** Board helpers (OK SSOT), full-register fetch, hero bands, view tabs, entity rollups + Sheet, CES upload as a view tab
- **Out of scope:** Last CES upload stamp / weekly ops / export chase lists (Wave 3); new aggregate API endpoint
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `SafetyAssetRegister.tsx`, `safetyAssets/safetyAssetBoardHelpers.ts` (+ tests), `safetyAssetsClient.listAllAssetsForBoard`
- **Backend:** None
- **APIs:** Reuses `GET /api/v1/assets/` (page_size ≤ 500) + engineers list for owner display names
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI on existing register; Wave 1 CES import panel moved into Upload view tab
- **Tolerant reader / strict writer applied?** Yes — board is read-only rollups; KPI honesty retained (em dash on load failure)
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — FE-only; revert PR restores prior register table

## 4) Acceptance Criteria (AC)
- [x] AC-01: Clickable hero bands filter assets (all / overdue / due bands / in date / quarantine / removed)
- [x] AC-02: Views — Assets, By engineer, By vehicle, By type, CES upload
- [x] AC-03: % OK SSOT = active + not overdue (Training compliant|due_soon analogue)
- [x] AC-04: Entity tables support column sort + filter
- [x] AC-05: Sheet drill-in lists kit assets for a selected engineer/vehicle/type
- [x] AC-06: CES dry-run/commit remains available on Upload view
- [x] AC-07: Load failure shows em dashes for hero metrics (no silent zeros)

## 5) Testing Evidence (link to runs)
- [x] Unit: `safetyAssetBoardHelpers.test.ts` + `SafetyAssetRegister.test.tsx` (local vitest)
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Safety Asset Register → click hero band → asset list filters
- [x] CUJ-02: By engineer → row click → Sheet kit drill-in with OK/overdue/% strip

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** Use board views for weekly CES kit review; Upload tab for dry-run/commit

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open Safety Asset Register; confirm hero bands, engineer rollup, Sheet drill-in, Upload tab
- **Canary plan:** N/A (SWA FE deploy)
- **Prod post-deploy checks:** Spot-check register board + CES upload tab still works

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Board blank/erroring or performance regression on register page
- **Rollback steps:** Revert merge commit / redeploy prior SWA
- **Owner:** Platform / Safety Asset Register

## 10) Evidence Pack (links)
- CI run(s): after push
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
