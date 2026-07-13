# Change Ledger (CL-IA-W5-LIBRARY-NAV)

## 1) Summary
- **Feature / Change name:** IA-W5 — Layout single-nav Library entry
- **User goal (1-2 lines):** Collapse separate Documents and Policies sidebar children into one Library entry that lands on `/documents`, matching the unified Library shell from IA-W4 (#902).
- **In scope:** `Layout.tsx`, `Layout.test.tsx`, and `en.json` `nav.*` keys only (IA plan allowlist)
- **Out of scope:** Route changes (`/documents`, `/policies` unchanged); `LibraryShell` / page content; SMTP/PagerDuty (#853); Dependabot merges; backend APIs
- **Feature flag / kill switch:** N/A — sidebar IA only; revert commit to restore dual Library hub children

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Sidebar Library hub replaced with a single first-level `NavLink` to `/documents`; manual active state when path is `/documents` or `/policies` (RR 6.30 — no `isActive` render prop)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (nav consolidation; routes and pages unchanged)
- **Tolerant reader / strict writer applied?** Yes — bookmarks to `/documents` and `/policies` continue to work; Library shell tabs handle in-page switching
- **Breaking changes:** None for APIs/data. UI: sidebar no longer lists separate Documents/Policies children under an expandable Library hub
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Sidebar shows one Library entry (not separate Documents/Policies children); link targets `/documents`
- [x] AC-02: Library nav item is active when the current route is `/documents` or `/policies` (including subpaths)
- [x] AC-03: `/documents` and `/policies` routes and LibraryShell tab UX from #902 remain unchanged

## 5) Testing Evidence (link to runs)
- [x] Lint — frontend Layout allowlist only
- [x] Typecheck — TypeScript via vitest imports
- [x] Build — N/A (frontend-only nav)
- [x] Unit tests — `Layout.test.tsx` updated for single Library entry and manual active state
- [x] Integration tests — deferred to CI
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Governance user clicks Library in sidebar → lands on `/documents` with Library shell and Documents tab active
- [x] CUJ-02: Governance user deep-links to `/policies` → Library sidebar entry shows active; in-page Policies tab works via LibraryShell

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A — UI-only; no ops change

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Confirm single Library sidebar entry; click lands on `/documents`; visit `/policies` and confirm Library nav active + tab switch
- **Canary plan:** N/A — low-risk frontend nav
- **Prod post-deploy checks:** Smoke Library nav on prod after merge; version SHA match (post #902)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Library nav missing, wrong active state, or users cannot reach Documents/Policies
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
