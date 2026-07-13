# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Assessor Follow-up B — Exceptions inbox filters + related-doc deep links + CUJ proof scaffold
- **User goal (1–2 lines):** Operators can filter Knowledge Exceptions by entity/signal type honestly, deep-link to related documents’ Standards & Evidence tab, and follow a staging/prod CUJ checklist without claiming LIVE until verified.
- **In scope:** Exceptions entity_type (API) + signal_type (client) filters; related-doc `?tab=evidence` polish; CUJ proof runbook; client listExceptions params; light FE tests
- **Out of scope:** Backend coverage math; server `signal_type` query param; rebasing #922 isort on `test_governed_knowledge_service.py`
- **Feature flag / kill switch:** None (additive UI + docs)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `KnowledgeExceptions.tsx` filters + entity deep links; `StandardsAssessmentPanel.tsx` related-doc `?tab=evidence` + Exceptions hint
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** Client uses existing `GET /knowledge-bank/exceptions?entity_type=`; no new endpoints
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `listExceptions({ status?, entityType? })` options object
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** `docs/runbooks/ASSESSOR_EXCEPTIONS_CUJ_PROOF.md` (scaffold; not LIVE)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — signal filter only when `signal_type` present on rows
- **Breaking changes:** None (sole `listExceptions` call site updated to options object)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert FE/docs commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Exceptions inbox filters by entity type via API `entity_type` query
- [x] AC-02: Exceptions inbox filters by signal type client-side without fake facet counts
- [x] AC-03: Related KB document links open `/documents/{id}?tab=evidence`
- [x] AC-04: Operational entity rows deep-link to detail routes (incident/complaint/near_miss/rta/audit_finding)
- [x] AC-05: CUJ proof runbook exists and explicitly forbids LIVE until verified

## 5) Testing Evidence (link to runs)
- [ ] Lint / type / unit — CI on this PR
- [x] Local unit — knowledgeBankClient + KnowledgeExceptions helper tests
- [ ] Integration / E2E — deferred to staging CUJ checklist

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Assess incident → Exceptions shows proposed signal → confirm/reject (code path + runbook; staging LIVE pending)
- [x] CUJ-02: Filter Exceptions by entity type (API) and signal type (client)
- [x] CUJ-03: Related document link lands on Standards & Evidence tab

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** `docs/runbooks/ASSESSOR_EXCEPTIONS_CUJ_PROOF.md`

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Follow Assessor CUJ proof checklist; do not claim LIVE until filled
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** Same checklist on prod after tip==prod; version SHA

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Broken Exceptions page / wrong deep links / filter regressions
- **Rollback steps:** Revert this PR deploy; no DB rollback
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: pending CUJ checklist completion
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — uses existing exceptions API
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
