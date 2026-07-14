# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ Admin Lookup Tables — Configure CTA + empty-state honesty
- **User goal (1-2 lines):** Admins can open a real Configure editor from “Not configured” lookup cards; empty counts are honest (API-backed, never fabricated).
- **In scope:** LookupTables hub cards, configure dialog CRUD via existing lookups API, FE tests
- **Out of scope:** Layout.tsx, Workforce matrix/QR, new backend endpoints
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/admin/LookupTables.tsx`, `frontend/src/pages/admin/__tests__/LookupTables.test.tsx`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** Uses existing `/api/v1/admin/config/lookup/{category}`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No schema changes
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI wiring to existing CRUD
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: “Not configured” cards show primary Configure CTA opening editor
- [x] AC-02: Counts load from API; failure shows “Count unavailable” (not silent zero)
- [x] AC-03: Empty-state honesty copy when total=0
- [x] AC-04: Unit tests cover CTA, editor open, unavailable counts

## 5) Testing Evidence (link to runs)
- [x] Unit tests — LookupTables.test.tsx (3 passed)
- [x] Backend — N/A
- [ ] Integration / E2E — deferred to CI

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin opens Lookup Tables → sees Not configured → Configure opens editor
- [x] CUJ-02: Load failure does not fabricate zero items
- [x] CUJ-03: Configured category shows item count from API

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Open /admin/lookups, configure empty category
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + admin lookups smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Admin lookups editor broken
- **Rollback steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
