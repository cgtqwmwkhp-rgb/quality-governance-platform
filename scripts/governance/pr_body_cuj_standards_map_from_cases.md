# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ Standards map ← operational cases
- **User goal (1-2 lines):** From Standards library / IMS, see inbound operational signal counts per clause linking to Knowledge Exceptions filtered by clause/standard.
- **In scope:** exceptions filters + operational-counts API, Standards clause links, KnowledgeExceptions URL filters, IMS hub destination, tests
- **Out of scope:** Layout.tsx, Workforce matrix/QR
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Standards.tsx`, `KnowledgeExceptions.tsx`, `IMSDashboard.tsx`, `knowledgeBankClient.ts`, href unit test
- **Backend:** `governed_knowledge.py` (clause/scheme/signal filters + `/exceptions/operational-counts`)
- **APIs:** Extended `GET /exceptions`; added `GET /exceptions/operational-counts`
- **Schemas:** Query params only
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive query params + endpoint
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Standards clause shows inbound operational signal count when >0
- [x] AC-02: Count links to Knowledge Exceptions filtered by clause/standard
- [x] AC-03: IMS hub surfaces Operational signals destination
- [x] AC-04: Unit tests for href contract + operational signal types

## 5) Testing Evidence (link to runs)
- [x] Backend unit — test_standards_ops_signal_filters.py passed
- [x] Frontend — standardsOpsSignalsHref.test.ts passed

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Standards → clause ops signals → Exceptions filtered
- [x] CUJ-02: IMS → Operational signals → Exceptions operational=1
- [x] CUJ-03: Exceptions banner shows clause/standard filter label

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- **Staging verification:** Standards with proposed operational links show counts
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + Standards/Exceptions smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Exceptions filters broken or Standards UI error
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
