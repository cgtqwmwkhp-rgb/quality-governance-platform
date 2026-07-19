# Change Ledger (CL-BRAND-OPTION-C)

## 1) Summary
- **Feature / Change name:** Sidebar/login brand Option C + tip==LIVE SWA recovery
- **User goal:** Replace QGP/PRO chip with mark-dominant Planexpand branding; keep purple-water on prod API with Microsoft Entra configured.
- **Depends on:** Prod tip with gov-lib schema + category-tree hotfix (`5097ae2e5888` lineage).
- **In scope:** BrandMark PNG tile, Layout Option C copy, Login brand lines, staging-verification flaky `networkidle` timeout fix, emergency production SWA bake workflow job (Entra VITE secrets required).
- **Out of scope:** Renaming residual QGP copy elsewhere; staging DB schema repair.

## 2) Impact Map
- **Frontend:** `BrandMark.tsx`, `Layout.tsx`, `Login.tsx`, i18n `brand.*`, Login unit/a11y tests.
- **CI/CD:** `azure-static-web-apps-purple-water-03205fa03.yml` emergency bake + staging verification timeout hygiene.
- **APIs / DB:** None.

## 3) Compatibility & Data Safety
- Additive UI/branding only; no schema or API contract changes.
- Emergency bake is opt-in via `workflow_dispatch` input `force_production_bake=true`.

## 4) Acceptance Criteria
- [x] AC-01: Sidebar shows Quality Governance Platform + Planexpand Limited; no QGP/PRO chip.
- [x] AC-02: Brand mark uses uploaded transparent PNG on Layout and Login.
- [x] AC-03: Staging verification static-assets test no longer depends on `networkidle` (60s budget).
- [x] AC-04: Emergency production bake job builds with `VITE_AZURE_*` secrets + prod API URL.

## 5) Testing Evidence
- [x] Unit: `vitest` Layout tests (13 pass locally).
- [x] Login tests updated for Option C heading.
- [x] Live SWA bake verified: prod API host + Entra client id inlined; Option C brand present.
- [ ] CI: PR checks green after this revision.

## 6) Critical Journeys
- [x] CUJ-01: User opens login → sees Planexpand mark + product/company lines → Microsoft SSO configured (no “not configured” banner when Entra baked).
- [x] CUJ-02: Authenticated user sees Option C brand in sidebar; Library navigates to `/documents`.

## 7) Rollback Plan
- **Owner:** Platform release operator
- **Rollback steps:**
  1. Revert this PR on main (or redeploy prior SWA artifact).
  2. Run Emergency Production SWA Bake on prior SHA if purple-water must be restored immediately.
  3. No DB rollback required.

## 8) Observability & Operations
- **Metrics:** SWA deploy success; login SSO error rate; Library 5xx.
- **Logs:** Browser console must not show staging API host for Library calls after prod bake.
- **Alerts:** Existing API 5xx / SWA deploy failures.
- **Runbook:** If SSO banner returns, confirm bake included `VITE_AZURE_CLIENT_ID` / `VITE_AZURE_AUTHORITY`; use emergency bake job (never deploy a local bake without Entra secrets).

## 9) Release Plan
- Merge PR → push triggers SWA staging path; if staging UI gate flakes, run `force_production_bake=true`.
- Confirm purple-water console hits `app-qgp-prod` and Microsoft login works.

## 10) Evidence Pack
- Live bundle checks (prod API + Entra client present).
- Screenshots: Option C login brand; prior staging-API Library failure (resolved by prod bake).

---

# Gate Checklist
- [x] **Gate 0:** Scope lock, AC, CUJs, Change Ledger complete.
- [x] **Gate 1:** Reuses existing Layout/Login/BrandMark; no second brand stack.
- [ ] **Gate 2:** CI green.
- [ ] **Gate 3:** Prod/SWA evidence linked after merge.
- [x] **Gate 4:** N/A canary (static FE brand).
- [x] **Gate 5:** Rollback + observability documented.
