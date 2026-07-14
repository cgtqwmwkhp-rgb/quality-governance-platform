# Change Ledger (CL-PATH11-CUJ-EXCEPTIONS-INBOX-FILTERS)

## File allowlist (exclusive)
- `frontend/src/pages/KnowledgeExceptions.tsx`
- `frontend/src/pages/exceptionsInboxFilters.ts` (NEW)
- `frontend/src/pages/__tests__/exceptionsInboxFilters.test.ts` (NEW)
- `frontend/src/pages/__tests__/KnowledgeExceptions.test.tsx`
- `scripts/governance/pr_body_cuj_exceptions_inbox_filters.md`

**Zero overlap** with standards-parity PRs, document-evidence-deeplink, Layout.tsx, standards-map-inputs server work.

## 1) Summary
- **Feature / Change name:** CUJ — Knowledge Exceptions inbox filters with URL sync
- **User goal (1-2 lines):** Operators can filter Exceptions by status + entity_type + signal_type; filters hydrate from and write back to the URL for shareable inbox views.
- **In scope:** Status filter UI; URL sync for three filters; case deep-links to `?tab=standards`; unit tests
- **Out of scope:** Layout; server `signal_type` API (still client-side); DocumentDetail scroll
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `KnowledgeExceptions.tsx`, `exceptionsInboxFilters.ts`
- **Backend (handlers/services):** None (uses existing `status` + `entity_type` query params)
- **APIs (endpoints changed/added):** Consumes existing exceptions list
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive query params; defaults omitted from URL
- **Tolerant reader / strict writer applied?** Yes — unknown filter values fall back safely
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Status filter (inbox / proposed / needs_review) drives API `status` when not inbox
- [x] AC-02: entity_type + signal_type filters available; signal remains client-side
- [x] AC-03: Filters sync to URL (`status`, `entity_type`, `signal_type`)
- [x] AC-04: Case entity deep-links open Standards tab

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — exceptionsInboxFilters + KnowledgeExceptions href/URL tests
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Operator filters inbox by status + entity + signal
- [x] **CUJ-02:** Refresh preserves filters via URL
- [x] **CUJ-03:** Open case from exception lands on Standards tab href

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Apply filters, copy URL, reload, confirm same view
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Exceptions filter URL share

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Filters break inbox load or corrupt URLs
- **Rollback steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
