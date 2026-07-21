# Change Ledger (CL-CES-ASSET-BOARD-W2)

## 1) Summary
- **Feature / Change name:** CES Calibrations Wave 2 — Safety Asset Register board UX
- **User goal (1–2 lines):** Managers see a Training-style asset board with clickable hero bands, rollups by engineer/vehicle/type, sort/filter, and Sheet kit drill-in — fed by the Wave 1 CES import.
- **In scope:** Board helpers (OK SSOT), full-register fetch, hero bands, view tabs, entity rollups + Sheet, CES upload as a view tab
- **Out of scope:** Last CES upload stamp / weekly ops / export chase lists (Wave 3); new aggregate API endpoint

## 2) Impact Surface
- **Frontend:** `SafetyAssetRegister.tsx`, `safetyAssets/safetyAssetBoardHelpers.ts`, `safetyAssetsClient.listAllAssetsForBoard`
- **Backend / APIs:** Reuses `GET /api/v1/assets/` (page_size ≤ 500) + engineers list for owner names
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

## 6) Threat Model (if authn/authz/data exposure)
- **Trust boundary:** Existing asset:read / asset:create permissions unchanged
- **Abuse cases:** Large board fetch (~2k assets) — capped pagination; no new write paths
- **Controls:** Reuses authenticated assets API

## 7) Observability
- **Logs/metrics/traces:** None new
- **Dashboards/alerts:** None

## 8) Rollout / Rollback
- **Rollout plan:** Merge → SWA deploy (FE-only)
- **Rollback trigger:** Board blank/erroring or performance regression on register page
- **Rollback steps:** Revert merge commit / redeploy prior SWA

## 9) Evidence Links
- Wave 0/1 canvases: CES asset register action plan + UX mockup
- Wave 1 live: PR #1230
