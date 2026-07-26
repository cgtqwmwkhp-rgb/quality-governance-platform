# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Run021 Wave-next — portal honesty (hub, track, work, intake chrome)
- **User goal (1–2 lines):** Employees should see truthful portal badges, labels, and navigation; keyboard and screen-reader users can reach hub tiles; production builds must not spam debug logs; cold deep-links with a valid platform JWT should not bounce to login.
- **In scope:** Portal hub badge math + tile a11y; track title/date honesty; training summary copy; RTC witness gate; debug log removal; portal 404; auth bootstrap; customer title humanization API; focused unit/vitest coverage; this Change Ledger
- **Out of scope / deferred:** PX-121 publish gate; PX-129/132 admin parity; PX-158 legacy deprecation; PX-154 staff register naming; PX-278 reference-format unification; PX-310 duplicate campaign dedupe; PX-323 slug convention (report chooser only); PX-330/324 if not in lane pack
- **Feature flag / kill switch:** None — revert this PR

## 2) Impact Map (what changed)
- **Frontend hub:** `Portal.tsx` — focusable track/help buttons; My Work badge includes assigned actions + pending reading; removed Admin Login footer; removed infinite badge pulse; honest track tile subtitle
- **Frontend track/work:** `PortalTrack.tsx`, `portalHonestyHelpers.ts` — en-GB dates; humanized report titles; `PortalWork.tsx` — training next-due + Atlas reconciliation notes
- **Frontend intake:** `PortalDynamicForm.tsx`, `PortalRTAForm.tsx`, `PortalReport.tsx`, `PortalNearMissForm.tsx`, `PortalHelp.tsx`, `formLookupFields.ts` — dev-only logs; back-button labels; RTC witness required; complaint role banner fix; sorted customers; portal 404 route
- **Auth:** `PortalAuthContext.tsx` — expired portal session bootstraps from shared JWT (PX-167)
- **Backend:** `employee_portal.py` — `humanize_customer_code` / `format_portal_report_title` on my-reports + near-miss detail
- **Tests:** vitest + `tests/unit/test_portal_report_titles.py`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive display-layer and auth-bootstrap fixes; no schema changes
- **Tolerant reader / strict writer applied?** Yes — titles humanized at read/display; auth bootstraps only when platform JWT is valid
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy:** Revert merge

## 4) Acceptance Criteria (AC)
- [x] AC-01: Track My Report and Help & Support hub tiles are keyboard-focusable buttons (PX-295)
- [x] AC-02: My Work badge counts open assigned actions plus pending reading (PX-305)
- [x] AC-03: Track tile no longer promises a reference-number lookup field (PX-319)
- [x] AC-04: Admin Login footer removed from employee portal hub (PX-297)
- [x] AC-05: `[PortalDynamicForm] Route debug` logs gated to DEV only (PX-166, PX-331)
- [x] AC-06: RTC step 3 requires an explicit witness answer; step 5 still blocks empty description (PX-280, PX-277 evidence)
- [x] AC-07: Portal unknown routes render portal-scoped 404 with return paths (PX-311)
- [x] AC-08: Expired portal localStorage bootstraps from shared platform JWT (PX-167)
- [x] AC-09: Track dates use dd/mm/yyyy; generic titles humanize customer slugs (PX-317, PX-299, PX-318)
- [x] AC-10: Training summary prefers next upcoming due; Atlas/QGP conflict explained per card (PX-309, PX-308, PX-307 evidence via existing statusLabel)
- [x] AC-11: Training hub tile deep-links to `#training` (PX-321 — verified on main, covered by test)
- [x] AC-12: Dynamic form fields already use `portalFieldId` + `portalRequiredProps` (PX-301 — verified on main, no diff required)

## 5) Testing Evidence (link to runs)
- [x] Vitest — `portalHonestyHelpers`, `Portal.honesty`, `PortalRTAForm.validation`, `trainingMatrixBoardHelpers`
- [x] Unit — `pytest tests/unit/test_portal_report_titles.py` (2 passed, local python3.11)
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Hub My Work badge reflects actions + reading after parallel API loads
- [x] CUJ-02: Tab to Track / Help from `/portal` and activate with Enter
- [x] CUJ-03: Cold `/portal/report/incident` with valid admin JWT bootstraps portal session
- [x] CUJ-04: `/portal/unknown` shows portal 404 — not admin dashboard shell
- [x] CUJ-05: Track list shows `Plantexpand Ltd` not `plantexpand_ltd`

## 7) Observability & Ops
- **Logs:** Production portal form debug logs removed; auth bootstrap logs DEV-gated
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Hub badge vs `/portal/work`; tab through hub; portal 404; submit RTC skipping witnesses blocked; track title/date format
- **Canary plan:** Full promote after CI green
- **Prod post-deploy checks:** Same on purple-water

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Hub badge regression; auth bootstrap loop; track title corruption
- **Rollback steps:** Revert PR merge
- **Owner:** Platform engineering

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Base branch: `main`
- Already on main (documented, no diff): PX-277 RTA description validation; PX-301 dynamic form programmatic labels; PX-321 training deep-link

### PX claimed (22)
PX-166, PX-167, PX-277 (evidence), PX-280, PX-284, PX-295, PX-297, PX-298, PX-301 (evidence), PX-303, PX-304, PX-305, PX-307 (evidence), PX-308, PX-309, PX-311, PX-317, PX-318, PX-319, PX-321 (evidence), PX-322, PX-331, PX-299

### PX deferred (13)
PX-121, PX-129, PX-132, PX-154, PX-158, PX-278, PX-310, PX-323, PX-330, PX-324 — out of lane scope or requires admin/backend dedupe lanes

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — display helpers documented
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
