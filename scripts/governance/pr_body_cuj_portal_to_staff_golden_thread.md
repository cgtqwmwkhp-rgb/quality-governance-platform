# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CUJ Portal → staff golden thread
- **User goal (1-2 lines):** After portal near-miss/incident submit, staff JWT sessions deep-link to the staff record; anonymous/portal-only sessions show tracking reference only (no silent staff CTA).
- **In scope:** QuickReportResponse golden-thread fields, OptionalCurrentUser on submit, NearMiss/Incident success screens, tests
- **Out of scope:** Layout.tsx, Workforce matrix/QR, portal DynamicForm (follow-on)
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `PortalNearMissForm.tsx`, `PortalIncidentForm.tsx`, `portalSubmitSuccess.ts` + tests
- **Backend:** `employee_portal.py` (`staff_golden_thread_fields`, response fields)
- **APIs:** Additive fields on `POST /api/v1/portal/reports/`
- **Schemas:** `QuickReportResponse` extended
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional response fields
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Authenticated staff submit returns staff_href + can_open_staff_record
- [x] AC-02: Anonymous submit returns tracking only (no staff CTA)
- [x] AC-03: Success UI deep-links when allowed else shows tracking honesty
- [x] AC-04: Unit tests for helper + FE offer logic

## 5) Testing Evidence (link to runs)
- [x] Backend — test_portal_staff_golden_thread.py passed
- [x] Frontend — portalSubmitSuccess.test.ts passed

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff portal near-miss submit → Open near-miss record
- [x] CUJ-02: Anonymous submit → tracking ref only
- [x] CUJ-03: Incident submit success mirrors near-miss golden thread

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan
- **Staging verification:** Portal submit with/without platform JWT
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health + portal submit smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Portal submit errors or wrong deep-links
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
