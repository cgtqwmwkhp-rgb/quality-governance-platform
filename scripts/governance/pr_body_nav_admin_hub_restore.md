# Change Ledger (CL-PATH11-NAV-ADMIN-HUB)

## 1) Summary
- **Feature / Change name:** Path11 P0 — Restore Admin hub discoverability
- **User goal (1-2 lines):** Superusers with `admin_user_management` can reach Admin Console and related admin surfaces from the sidebar (and header Settings gear), not only User Management.
- **In scope:** `Layout.tsx` Admin hub children + header Settings target; `navItemIsActive` exact match for `/admin`; `Layout.test.tsx` / `assuranceHubHelpers.test.ts`; `en.json` / `cy.json` `nav.*` keys
- **Out of scope:** Assessor / GKB / Workforce domain code; route handlers/pages; RBAC changes; Dependabot
- **Feature flag / kill switch:** Existing `admin_user_management` gate unchanged — Admin hub still requires superuser + flag

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Admin hub children expanded to Console, Users, Audit Trail, Forms, Settings, Notifications, Lookups, Contracts (routes verified in `App.tsx`); header Settings gear → `/admin` for gated superusers; `/admin` nav active state is exact-only
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None (reuses `admin_user_management`)
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (nav discoverability only; routes/pages unchanged)
- **Tolerant reader / strict writer applied?** Yes — deep links to existing admin routes continue to work
- **Breaking changes:** None for APIs/data. UI: Admin hub lists more children; Settings gear lands on Admin Console instead of User Management
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin hub (superuser + `admin_user_management`) lists Console, Users, Audit Trail, Forms, Settings, Notifications, Lookups, Contracts for routes that exist in `App.tsx`
- [x] AC-02: Header Settings gear for gated superusers links to `/admin` (Admin Console)
- [x] AC-03: `navItemIsActive('/admin', …)` is exact-only so child admin routes do not keep Console highlighted
- [x] AC-04: Layout / helper unit tests cover expanded Admin children and Settings gear target

## 5) Testing Evidence (link to runs)
- [x] Lint — Layout / helpers allowlist only
- [x] Typecheck — TypeScript via vitest imports
- [x] Build — N/A (frontend-only nav)
- [x] Unit tests — `Layout.test.tsx` + `assuranceHubHelpers.test.ts` updated
- [x] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Superuser with flag expands Admin hub → sees Console and sibling admin links; clicks Console → `/admin`
- [x] CUJ-02: Superuser with flag clicks header Settings gear → lands on `/admin` (not only `/admin/users`)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — UI-only; no ops change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** As superuser with flag, expand Admin hub and confirm all eight children; confirm Settings gear → `/admin`; confirm non-superuser still lacks Admin hub
- **Canary plan:** N/A — low-risk frontend nav
- **Prod post-deploy checks:** Smoke Admin hub + Settings gear after merge

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Admin hub missing children, wrong Settings target, or Console incorrectly active on all `/admin/*` routes
- **Rollback steps:** Revert PR merge on `main`; redeploy previous SHA via standard CD pipeline
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — UI-only; routes/APIs untouched
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
