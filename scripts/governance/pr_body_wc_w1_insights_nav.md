# Change Ledger (CL-WC-W1-INSIGHTS-NAV)

## 1) Summary
- **Feature / Change name:** WC-W1 D-W1-05 — Insights nav hub (P0-UX-3)
- **User goal (1-2 lines):** Analytics, Calendar, Exports, and AI Intelligence routes are discoverable from the primary sidebar under an Insights hub instead of being orphaned deep links.
- **In scope:** `Layout.tsx` Insights hub; `Layout.test.tsx`; `en.json` `nav.insights` key
- **Out of scope:** List page URL sync; Actions routes; RiskRegister; backend; analytics sub-routes as separate nav children
- **Feature flag / kill switch:** N/A — sidebar IA only; revert commit to remove hub

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** New top-level **Insights** hub with four children linking to existing routes: `/analytics`, `/calendar`, `/exports`, `/ai-intelligence`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (nav discoverability only; routes/pages unchanged)
- **Tolerant reader / strict writer applied?** Yes — deep links to existing insight routes continue to work
- **Breaking changes:** None for APIs/data. UI: Insights hub appears in sidebar for all authenticated users
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Sidebar shows an Insights hub with Analytics, Calendar, Export Center, and AI Intelligence links
- [x] AC-02: Each link targets an existing route verified in `App.tsx` (`/analytics`, `/calendar`, `/exports`, `/ai-intelligence`)
- [x] AC-03: Hub matches existing nav visual language (expandable hub, same styling as sibling hubs)
- [x] AC-04: Layout unit tests cover Insights hub structure and link exposure; analytics subpaths remain unlisted

## 5) Testing Evidence (link to runs)
- [x] Lint — Layout allowlist only
- [x] Typecheck — TypeScript via vitest imports
- [x] Build — N/A (frontend-only nav)
- [x] Unit tests — `Layout.test.tsx` updated for Insights hub
- [ ] Integration tests — deferred to CI
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: User expands Insights hub → sees four children; clicks Analytics → `/analytics`
- [x] CUJ-02: User on `/calendar` or `/ai-intelligence` → Insights hub auto-expands with active child highlighted

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — UI-only; no ops change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Expand Insights hub; confirm four links navigate to correct pages; confirm analytics subpaths are not separate nav items
- **Canary plan:** N/A — low-risk frontend nav
- **Prod post-deploy checks:** Smoke Insights hub after merge

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Insights hub missing, wrong links, or sidebar regression
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
