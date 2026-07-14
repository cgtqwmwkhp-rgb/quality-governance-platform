# Change Ledger (CL-PATH11-CUJ-RTA-STANDARDS-PARITY)

## File allowlist (exclusive)
- `frontend/src/pages/RTADetail.tsx`
- `frontend/src/pages/rtaStandardsTab.ts` (NEW)
- `frontend/src/pages/__tests__/rtaStandardsTab.test.ts` (NEW)
- `frontend/src/pages/__tests__/RTADetail.test.tsx`
- `scripts/governance/pr_body_cuj_rta_standards_parity.md`

**Zero overlap** with Complaint/Incident parity, exceptions-inbox-filters, document-evidence-deeplink, Layout.tsx.

## 1) Summary
- **Feature / Change name:** CUJ — RTADetail Standards tab Near Miss parity
- **User goal (1-2 lines):** RTA Standards tab matches Near Miss host pattern (`StandardsAssessmentPanel` + `mt-6`), opens via `?tab=standards`, and is tested.
- **In scope:** URL tab hydrate; panel host wrapper + spacing parity; unit tests
- **Out of scope:** Layout; Exceptions inbox; Complaint/Incident pages; API changes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `RTADetail.tsx`, `rtaStandardsTab.ts`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive URL `tab` query
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/rtas/:id?tab=standards` opens Standards tab
- [x] AC-02: Standards tab hosts panel with `entityType="rta"` and Near Miss `mt-6` spacing
- [x] AC-03: Helper + RTADetail tests cover parity

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — rtaStandardsTab + RTADetail standards host test
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Operator opens RTA Standards tab via deeplink
- [x] **CUJ-02:** Panel loads for rta entity (Near Miss host parity)
- [x] **CUJ-03:** Invalid `tab` falls back to overview

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Open `/rtas/{id}?tab=standards` and confirm panel
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check one RTA Standards deeplink

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Standards tab fails to render / wrong default tab
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
