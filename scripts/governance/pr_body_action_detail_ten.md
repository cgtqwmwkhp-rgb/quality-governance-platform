# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Action Detail — ten UX enhancements
- **User goal (1-2 lines):** Improve the action detail page for owner commentary, evidence, and status: clearer errors, sharing, sorting, limits, keyboard shortcuts, and context at a glance.
- **In scope:** `ActionDetail.tsx`, optional `getApiErrorMessage` fallback parameter in `client.ts`
- **Out of scope:** Backend API changes, new endpoints
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/ActionDetail.tsx`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `getApiErrorMessage(error, fallback?)` optional second argument
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit; no DB

## 4) Acceptance Criteria (AC)
- [x] AC-01: Action detail loads; notes and evidence errors show API-derived messages where available
- [x] AC-02: Note draft respects 16k cap with counter; Cmd/Ctrl+Enter submits when valid
- [x] AC-03: Copy key and copy page URL work; evidence list sort toggles display order
- [x] AC-04: `make pr-ready` passes locally

## 5) Testing Evidence (link to runs)
- [x] Lint — `make pr-ready` / frontend lint
- [x] Typecheck — `tsc` via `npm run build`
- [x] Build — `npm run build` (frontend)
- [x] Unit tests — via `make pr-ready`
- [x] Integration tests — N/A for this UI-only change
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open action by key, read metadata and completion notes, add owner note
- [x] CUJ-02: Upload and sort evidence; download/delete with clear errors on failure
- [x] CUJ-03: Change status; Save enabled only when draft differs from server

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Deploy frontend; smoke action detail page
- **Canary plan:** N/A
- **Prod post-deploy checks:** SWA/App Service SHA alignment per runbook

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** UI regression on action detail
- **Rollback steps:** Revert commit, redeploy previous frontend artifact
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
