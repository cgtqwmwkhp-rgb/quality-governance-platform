# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Operational Standards Assessor
- **User goal (1–2 lines):** Assess incidents, complaints, near misses, RTAs, and audit findings against ISO/standards with signal types so AI maps ops inputs without polluting certification evidence.
- **In scope:** Assess/list APIs; signal_type on CEL; incident create/update hooks; Standards tabs on case detail; Exceptions signal display; unit tests; migration
- **Out of scope:** Full IMS coverage re-weighting; complaint/RTA/near-miss auto-hooks; recurrence clustering; PagerDuty
- **Feature flag / kill switch:** None (additive `/knowledge-bank/entities/*`; assess failures never block incident save)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `StandardsAssessmentPanel`; Incident/Complaint/NearMiss/RTA detail Standards tabs; KnowledgeExceptions signal badges; knowledgeBankClient assess APIs
- **Backend (handlers/services):** `GovernedKnowledgeService.assess_operational_entity`; `governed_knowledge` routes; incident create/update assess hook
- **APIs (endpoints changed/added):** `POST/GET /api/v1/knowledge-bank/entities/{type}/{id}/assess|assessment`; exceptions `entity_type` filter
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** AssessEntityResponse + signal_type on evidence link responses
- **Database (migrations/entities/indexes):** `20260713_op_assess` adds `signal_type` on `compliance_evidence_links`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — signal_type nullable; operational links always proposed
- **Breaking changes:** None
- **Migration plan:** Alembic upgrade `20260713_op_assess` on staging then prod
- **Rollback strategy (DB):** Column nullable; drop via migration down(); revert app

## 4) Acceptance Criteria (AC)
- [x] AC-01: Assess endpoint maps operational entity to proposed CEL rows with signal_type
- [x] AC-02: Operational assessments never auto-confirm (always proposed)
- [x] AC-03: Incident detail Standards tab can run Assess / confirm / reject
- [x] AC-04: Incident create/update triggers assess without failing save
- [x] AC-05: Unit tests cover classify + never-auto-confirm path

## 5) Testing Evidence (link to runs)
- [x] Lint / format (local black after push)
- [x] Unit tests — `tests/unit/test_governed_knowledge_service.py` 27 passed
- [ ] Integration / E2E — deferred to CI + staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens incident → Standards → Assess against standards → proposed links appear
- [x] CUJ-02: Operator confirms/rejects link from panel or Knowledge Exceptions inbox
- [x] CUJ-03: Create/update incident does not fail if assess throws

## 7) Observability & Ops
- **Logs:** AiDecisionLog action `operational_standards_assess`
- **Metrics:** Existing knowledge-bank / readiness
- **Alerts:** None new
- **Runbook updates:** None (PagerDuty remains separate human unlock)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Migrate; assess one staging incident; check Exceptions
- **Canary plan:** Full promote after staging green
- **Prod post-deploy checks:** `/api/v1/meta/version` SHA; smoke Assess on one non-critical case

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Assess 5xx spike; bad links flooding inbox; migration failure
- **Rollback steps:** Revert deploy; leave nullable column; optionally no-op assess hook via hotfix
- **Owner:** David Harris / Platform ops

## 10) Evidence Pack (links)
- CI run(s): PR #922 checks
- Staging deploy evidence: pending after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
