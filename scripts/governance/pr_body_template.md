# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:**
- **User goal (1-2 lines):**
- **In scope:**
- **Out of scope:**
- **Feature flag / kill switch:** (name + default state)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
- **Backend (handlers/services):**
- **APIs (endpoints changed/added):**
- **Schemas/contracts (OpenAPI/Zod/DTO/types):**
- **Database (migrations/entities/indexes):**
- **Workflows/jobs/queues (if any):**
- **Config/env/flags:**
- **Dependencies (added/removed/updated):**

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive / Versioned / Flagged / Other
- **Tolerant reader / strict writer applied?** Yes/No (explain if No)
- **Breaking changes:** None / Yes (detail)
- **Migration plan:** (steps + rehearsal)
- **Rollback strategy (DB):** No DB change / backward-compatible / rollback steps

## 4) Acceptance Criteria (AC)
- [ ] AC-01:
- [ ] AC-02:
- [ ] AC-03:

## 5) Testing Evidence (link to runs)
- [ ] Lint
- [ ] Typecheck
- [ ] Build
- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01:
- [ ] CUJ-02:

## 7) Observability & Ops
- **Logs:**
- **Metrics:**
- **Alerts:**
- **Runbook updates:** link(s)

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:**
- **Canary plan:** traffic %, duration, thresholds, rollback triggers
- **Prod post-deploy checks:**

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:**
- **Rollback steps:**
- **Owner:**

## 10) Evidence Pack (links)
- CI run(s):
- Staging deploy evidence:
- Canary evidence (if applicable):

---

# Gate Checklist (must be complete before merge)
- [ ] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [ ] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [ ] **Gate 5:** Production verification plan + monitoring ready
