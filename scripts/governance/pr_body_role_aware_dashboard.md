# Change Ledger (CL-ROLE-AWARE-DASHBOARD)

## 1) Summary
- **Feature / Change name:** Role-aware "living" Dashboard (Live Highlight Rail, My Day, Pulse & trends, Org Command)
- **User goal (1–2 lines):** Replace the static admin Dashboard with a persona-aware landing page — linked engineers see their day (tools/van/training/actions) first, admins/managers see org-wide pulse + command signals first, and dual-role users get both.
- **In scope:** `frontend/src/pages/Dashboard.tsx` recomposition; new `frontend/src/pages/dashboard/*` components/hook/pure-logic module; persona detection via `engineersApi.getByUserMe()` + existing `hasRole`/`isSuperuser`; fail-honest rendering everywhere (no fabricated zeros)
- **Out of scope:** Backend changes (none required — reuses existing endpoints, including `portalComplianceApi` merged in #1236); CES plan files; DashboardBuilder (custom dashboards feature); notification delivery changes
- **Feature flag / kill switch:** N/A — pure FE recomposition of an existing authenticated route (`/dashboard`)

## 2) Impact Map (what changed)
- **Frontend:**
  - `pages/Dashboard.tsx` — rewritten to compose the sections below instead of a static KPI grid
  - `pages/dashboard/dashboardMetrics.ts` — pure, framework-free helpers: `Metric<T>` fail-honest wrapper, persona derivation, highlight-chip builder, risk-trend direction, 7-day window counter
  - `pages/dashboard/useDashboardData.ts` — persona-aware data-fetching hook; only fetches what each persona needs; converts every `Promise.allSettled` result into a `Metric<T>`
  - `pages/dashboard/HighlightRail.tsx` — Live Highlight Rail: priority chips, clickable deep-links, auto-scroll pause-on-hover/focus, renders an honest "all clear" state instead of nothing when there are no priority items
  - `pages/dashboard/MyDaySection.tsx` — My Day stage (tools/van clear-to-work, training, my actions), mirrors `Portal.tsx` clear-to-work visual language
  - `pages/dashboard/PulseTrendsStrip.tsx` — 6 tenant-wide pulse metrics (training compliance, tool compliance, incidents/complaints/near-misses 7d, audit score), each a drill-down link
  - `pages/dashboard/OrgCommandStrip.tsx` — manager-facing unassigned intake / risk+forecast / asset health tiles, with a `compact` mode for dual-role users
  - `index.css` — `@keyframes highlight-rail-scroll` + `.animate-highlight-rail` utility (disabled under `prefers-reduced-motion`)
  - `pages/__tests__/Dashboard.test.tsx` — rewritten for the new composition (persona switch, fail-honest, drill-down link coverage)
  - `pages/dashboard/__tests__/dashboardMetrics.test.ts` — new unit tests for the pure logic module
- **Backend:** None
- **APIs:** None — reuses `engineersApi.getByUserMe`, `portalComplianceApi.myCompliance`, `trainingMatrixApi.myTraining`/`getSummary`, `actionsApi.viewCounts`, `incidentsApi`/`complaintsApi`/`nearMissesApi`.list, `auditsApi.listRuns`, `riskRegisterApi.getSummary`/`getTrends`, `assetHealthAnalyticsApi.getSummary`, `notificationsApi.getUnreadCount`
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive/replacement at the FE route level only; no API contract changes. If `portalComplianceApi` or any other dependency is unavailable, the dashboard degrades gracefully per-tile (see AC-07).
- **Tolerant reader / strict writer applied?** Yes — every remote call is read via `Promise.allSettled` + a `Metric<T>` wrapper (`ok` | `unavailable`); a rejected/skipped fetch is never coerced into a displayed `0`.
- **Breaking changes:** None. `/dashboard` route and its guard (`isAuthenticated`) are unchanged.
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — FE-only change; revert deploy/PR to restore the previous static Dashboard.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Live Highlight Rail shows priority chips with clickable deep-links; pauses auto-scroll on hover/focus; shows an explicit "all clear" state (not a blank/loading gap) when there is nothing urgent
- [x] AC-02: Linked engineer (no admin/manager role) sees **My Day** first — tools/van clear-to-work, training, my actions — with no org/pulse strip
- [x] AC-03: Admin/manager without an engineer link sees **Org first** — Pulse & trends strip + Org Command strip — with no My Day section
- [x] AC-04: Dual-role user (linked engineer AND admin/manager) sees **My Day first** followed by a **compact** Org Command strip
- [x] AC-05: Pulse & trends strip surfaces all 6 signals (training compliance, tool compliance, incidents 7d, complaints 7d, near misses 7d, audit score), each a working drill-down link
- [x] AC-06: Org Command strip surfaces unassigned intake, risk + forecast (trend direction), and asset health, each a working drill-down link
- [x] AC-07: Fail-honest — any failed/skipped fetch renders "—" / an explicit unavailable message, never a fabricated `0`; zero-value *real* metrics are treated as healthy (no false-alarm chip), never confused with "unavailable"
- [x] AC-08: Persona detection uses `engineersApi.getByUserMe()` (`linked`) plus existing `hasRole('admin'|'manager'|'supervisor')`/`isSuperuser()` — no new backend endpoint required

## 5) Testing Evidence (link to runs)
- [x] Unit: `frontend/src/pages/dashboard/__tests__/dashboardMetrics.test.ts` (24 tests — Metric wrapper, persona matrix, highlight-chip fail-honest behavior, risk-trend direction, 7d window counter)
- [x] FE component: `frontend/src/pages/__tests__/Dashboard.test.tsx` (9 tests — persona layout ×3, fail-honest rendering ×2, pulse drill-down links ×2, smoke ×2)
- [x] Full FE suite: `npx vitest run` — 247 files / 1336 tests passed (no regressions)
- [x] Lint: `npx eslint src/ --max-warnings 0` — clean
- [x] Typecheck: `npx tsc --noEmit` — clean
- [x] Build: `npm run build` — succeeds
- [ ] CI — after push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Linked engineer logs in → lands on Dashboard → sees My Day first (tools/van/training/actions) with deep-links into `/portal/tools`, `/portal/van`, `/portal/work#training`, `/actions?view=my`
- [x] CUJ-02: Admin/manager (no engineer link) logs in → lands on Dashboard → sees Pulse & trends + Org Command first, with deep-links into `/incidents`, `/risk-register?hero=outside_appetite`, `/safety-assets/analytics`, `/workforce/dashboard`
- [x] CUJ-03: Dual-role user (linked engineer + admin/manager) logs in → sees My Day first, then a compact Org Command strip beneath it

## 7) Observability & Ops
- **Logs:** No new server-side logging (FE-only)
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A — if a tile shows "unavailable", check the underlying API health (portal-compliance, training-matrix, asset-health, risk-register); the dashboard itself needs no special runbook

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Log in as (a) a linked-engineer-only user, (b) an admin/manager with no engineer link, (c) a dual-role user; confirm persona-correct layout and that every drill-down link resolves
- **Canary plan:** N/A
- **Prod post-deploy checks:** `/dashboard` loads for all three personas without console errors; Highlight Rail never shows a `0`-value chip; unavailable tiles show "—" instead of `0` when an upstream API is degraded

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Dashboard fails to render for any persona, or a fail-honest tile silently shows a fabricated value
- **Rollback steps:** Revert this PR's merge commit and redeploy the previous frontend build; no DB/API rollback required
- **Owner:** Platform / Frontend

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — reuses existing contracts only
- [x] **Gate 2:** CI green (lint/type/build/tests) — verified locally (see §5); awaiting hosted CI
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
