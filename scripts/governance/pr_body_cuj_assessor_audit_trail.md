# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ Assessor audit trail (assess/confirm/reject)
- **User goal (1-2 lines):** Persist and show audit trail entries when standards assess/confirm/reject runs, with a minimal Audit trail control on StandardsAssessmentPanel.
- **In scope:** AiDecisionLog on confirm/reject, assessment-trail API, panel UI + tests
- **Out of scope:** Layout.tsx, Workforce matrix/QR, CEL confirmed_by column migration
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `StandardsAssessmentPanel.tsx`, `knowledgeBankClient.ts`, `client.ts` types, panel test
- **Backend:** `governed_knowledge.py` confirm/reject logging + `GET .../assessment-trail`
- **APIs:** Added assessment-trail; confirm/reject now write AiDecisionLog
- **Schemas:** Trail response dict
- **Database:** Uses existing `ai_decision_logs`
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive logging + read API
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit (log rows remain harmless)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Confirm/reject persist AiDecisionLog entries
- [x] AC-02: Trail endpoint returns assess/confirm/reject for entity
- [x] AC-03: Panel Audit trail toggle shows history
- [x] AC-04: Unit/FE tests cover trail contract + panel toggle

## 5) Testing Evidence (link to runs)
- [x] Backend — test_assessor_audit_trail.py passed
- [x] Frontend — StandardsAssessmentPanel.test.tsx passed

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Assess → trail shows Assessed
- [x] CUJ-02: Confirm/Reject → trail entries with actor/clause
- [x] CUJ-03: Panel Audit trail toggle reveals history

## 7) Observability & Ops
- **Logs:** AiDecisionLog rows for evidence_confirm/reject
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- **Staging verification:** Confirm/reject on Standards tab → Audit trail
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + assessor smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Confirm/reject errors or trail API failures
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
