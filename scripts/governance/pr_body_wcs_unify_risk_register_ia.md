# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Unify Risk Register IA — deprecate `/risks` UI into Enterprise Risk Register
- **User goal (1–2 lines):** Give users a single Risk Register entry point in nav and routes so operational `/risks` no longer competes with `/risk-register`.
- **In scope:** Nav cleanup; `/risks` and `/risks/*` client redirects to `/risk-register` (query preserved); consolidation banner on Enterprise Risk Register; evidence deep-link map; IA doc note
- **Out of scope:** Migrating or deleting operational vs enterprise risk data models/APIs; bow-tie/KRI feature changes; full tabbed unification
- **Feature flag / kill switch:** N/A — additive IA redirect only; revert commit to restore dual nav/routes

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `App.tsx` (`/risks` → `/risk-register` redirect), `Layout.tsx` (remove Library `/risks` nav item), `RiskRegister.tsx` (consolidation banner), `ComplianceEvidence.tsx` (risk entity deep-link → `/risk-register`)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — `/api/v1/risks/` and `/api/v1/risk-register/` unchanged
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** `docs/ux/information-architecture.md` (duplicate-risks issue marked partially addressed)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (redirect + nav; pages/APIs retained)
- **Tolerant reader / strict writer applied?** Yes — bookmarks to `/risks` land on enterprise register; query string preserved
- **Breaking changes:** None for APIs/data. UI: Library “Risks” nav removed; `/risks` no longer renders the operational Risks page (redirects instead). Operational Risks page component remains in codebase for a later migration PR.
- **Migration plan:** No data migration in this PR
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: Sidebar exposes a single Risk Register entry (`/risk-register`); Library `/risks` entry removed
- [x] AC-02: Navigating to `/risks` and `/risks/*` redirects to `/risk-register` (search/query preserved)
- [x] AC-03: Enterprise Risk Register shows a short consolidation/deprecation notice
- [x] AC-04: No risk API or data-model migrations in this change

## 5) Testing Evidence (link to runs)
- [ ] Lint
- [ ] Typecheck
- [ ] Build
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — deferred to CI

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Authenticated user opens Risk Register from Enterprise nav and sees the consolidation banner
- [x] CUJ-02: Authenticated user hits `/risks` (bookmark/deep link) and lands on `/risk-register`

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/risk-register`, confirm banner; open `/risks`, confirm redirect; confirm Library nav has no Risks item
- **Canary plan:** N/A (frontend IA only)
- **Prod post-deploy checks:** Same as staging smoke on Risk Register nav + `/risks` redirect

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Users cannot reach Risk Register, redirect loops, or critical nav regression
- **Rollback steps:** Revert merge commit on `main` and redeploy previous frontend SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A for this PR
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — UI-only redirect; APIs untouched
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
