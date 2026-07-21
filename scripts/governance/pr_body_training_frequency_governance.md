# Change Ledger (CL-TRAINING-FREQ-GOVERNANCE)

## 1) Summary
- **Feature / Change name:** Training frequency matrix — hide non-mandated + dual-control approval
- **User goal (1–2 lines):** Admins can focus the frequency grid on mandated courses; frequency cell edits require approval by David Harris before they apply; Restore template is locked/removed from Admin UI.
- **In scope:** Hide non-mandated toggle; remove Restore button; propose / list / approve / reject APIs; notify approver; migration for change requests
- **Out of scope:** Changing who owns Atlas uploads; LMS completion; competency passport
- **Feature flag / kill switch:** N/A (hard dual-control)

## 2) Impact Map (what changed)
- **Frontend:** `TrainingMatrixPanels.tsx` Admin frequency section — toggle, Propose, pending approvals UI; Restore removed
- **Backend:** `training_matrix.py` routes + `TrainingMatrixFrequencyChangeRequest` model
- **APIs:** `POST .../matrix/propose`, `GET .../matrix/proposals`, approve/reject; direct `POST .../matrix` locked; seed locked to superuser
- **Schemas/contracts:** Additive frequency change-request schemas
- **Database:** `training_matrix_frequency_change_requests` (Alembic `20260803_tm_freq_cr`)
- **Workflows/jobs/queues:** In-app + email notification to approver on propose
- **Config/env/flags:** Approver email constant `david.harris@plantexpand.com`
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Direct matrix save returns authorization error; clients must use propose
- **Tolerant reader / strict writer applied?** Yes (FE Propose path)
- **Breaking changes:** Admin UI no longer calls Restore or direct Save
- **Migration plan:** Alembic upgrade creates change-request table
- **Rollback strategy (DB):** Downgrade drops table; pending proposals lost (none applied until approved)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Toggle hides courses where all role cells are non-mandated (—)
- [x] AC-02: Restore April 2024 frequencies control removed from Admin UI; seed API locked to superuser
- [x] AC-03: Frequency dropdown changes are proposed, not applied immediately
- [x] AC-04: Only David Harris (or superuser) can approve/reject; approval applies cells
- [x] AC-05: Approver receives notification when a proposal is submitted

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_training_matrix_frequency_governance.py`
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin edits cells → Propose for approval → pending list shows
- [x] CUJ-02: Approver Approve → live matrix updates; Reject → no apply

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** If matrix cannot be edited live — use Propose; David approves in Training → Admin

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Propose a cell change as non-David admin; approve as David; confirm grid + compliance update
- **Canary plan:** N/A
- **Prod post-deploy checks:** Restore button absent; hide toggle works; propose/approve path works

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Frequency edits blocked incorrectly or approvals 5xx
- **Rollback steps:** Revert merge / redeploy prior API+SWA
- **Owner:** Platform / Training

## 10) Evidence Pack (links)
- CI run(s): after push
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
