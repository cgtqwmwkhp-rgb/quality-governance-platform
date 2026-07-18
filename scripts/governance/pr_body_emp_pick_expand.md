# Change Ledger (CL-EMP-PICK-EXPAND)

## File allowlist (exclusive)
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/ComplaintDetail.tsx`
- `frontend/src/pages/investigation/InvestigationActions.tsx`
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx`
- `frontend/src/pages/__tests__/ComplaintDetail.test.tsx`
- `scripts/governance/pr_body_emp_pick_expand.md`

**Depends on:** #1137 (`path11/emp-roster-ui-picker`) — introduces `EngineerPeoplePicker`. This branch is based on that PR; merge #1137 first (or land this onto main after #1137).

**Out of scope / sibling:** RTADetail, Investigations list create, RiskProfile, ActionDetail reassignment — remaining `UserEmailSearch` surfaces for a later slice.

## 1) Summary
- **Feature / Change name:** EMP-PICK-EXPAND — Engineer people picker on remaining governance assignee surfaces
- **User goal:** When creating actions (or naming a lead investigator) from incident/complaint/investigation detail, pick from the active PAMS roster by name, not email-only user search.
- **In scope:** Wire `EngineerPeoplePicker` (`requireLogin`) into IncidentDetail lead investigator + action assignee, ComplaintDetail action assignee, InvestigationActions action assignee; update related test mocks.
- **Out of scope:** New picker component; roster/Employees UX; backend assignment APIs; RTA/Risk/Investigations list surfaces.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** Replaced `UserEmailSearch` with `EngineerPeoplePicker` on three detail assignee surfaces; tests mock picker + `workforceApi.listEngineers`.
- **Backend:** None
- **APIs:** Consumes existing GET `/engineers/?is_active=true` (same as #1137)
- **Schemas/contracts:** Unchanged — still posts `assigned_to_email` (login email) when selected
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** #1137 `EngineerPeoplePicker`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE UX swap; same email payload to actions create
- **Tolerant reader / strict writer applied?** Yes — unlinked engineers visible but not selectable (`requireLogin`)
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change

## 4) Acceptance Criteria (AC)
- [x] AC-01: IncidentDetail action assignee uses EngineerPeoplePicker
- [x] AC-02: IncidentDetail lead investigator uses EngineerPeoplePicker
- [x] AC-03: ComplaintDetail action assignee uses EngineerPeoplePicker
- [x] AC-04: InvestigationActions action assignee uses EngineerPeoplePicker
- [x] AC-05: Unlinked engineers not selectable for assign (`requireLogin`)
- [x] AC-06: Detail tests mock EngineerPeoplePicker + workforceApi like Complaints.test.tsx

## 5) Testing Evidence (link to runs)
- [x] Unit: IncidentDetail + ComplaintDetail tests updated/mocked
- [ ] CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incident detail → Add action → search employee → assign when linked
- [x] CUJ-02: Complaint detail → Add action → search employee → assign when linked
- [x] CUJ-03: Investigation actions → Add action → search employee → assign when linked

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open incident/complaint/investigation detail → add action → roster picker lists active employees; unlinked rows disabled.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same on tip SWA after #1137.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Action-create assignee regressions
- **Rollback steps:** Revert squash-merge; force_deploy prior SHA
- **Owner:** Tip-owner

## 10) Evidence Pack (links)
- Parent: #1137 EMP-UI roster + picker
- Canvas: `qgp-employees-pams-profiles-360`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — reuse EngineerPeoplePicker; assign needs login
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production verification plan ready
