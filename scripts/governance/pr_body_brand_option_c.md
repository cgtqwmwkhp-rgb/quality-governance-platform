# Change Ledger (CL-BRAND-OPTION-C)

## 1) Summary
- **Feature / Change name:** Sidebar/login brand Option C + unblock tip==LIVE SWA
- **User goal:** Replace QGP/PRO chip with mark-dominant Planexpand branding; ensure purple-water talks to prod API.
- **In scope:** BrandMark PNG tile, Layout Option C copy, Login brand lines, staging-verification flaky networkidle timeout fix.
- **Out of scope:** Renaming residual QGP copy elsewhere; staging schema repair (separate).

## 2) Impact Map
- Frontend Layout/Login/BrandMark + i18n; staging UI verification e2e timeout hygiene.

## 3) Acceptance Criteria
- [x] AC-01: Sidebar shows Quality Governance Platform + Planexpand Limited; no QGP/PRO chip.
- [x] AC-02: Brand mark uses uploaded transparent PNG.
- [x] AC-03: Staging verification static-assets test no longer relies on networkidle (60s budget).

## 4) Ops note
Emergency prod API bake was deployed to purple-water via SWA CLI to restore SSO Library (prior main push left staging bake after UI gate flake).

## Gate Checklist
- [x] Gate 0 ledger
- [ ] Gate 2 CI
