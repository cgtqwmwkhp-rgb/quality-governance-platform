# Change Ledger (CL-EMP-ROSTER-UI-PICKER)

## File allowlist (exclusive)
- `frontend/src/pages/workforce/Engineers.tsx`
- `frontend/src/components/EngineerPeoplePicker.tsx`
- `frontend/src/api/workforceClient.ts`
- `frontend/src/api/competenceGapClient.ts`
- `frontend/src/pages/Incidents.tsx`
- `frontend/src/pages/Complaints.tsx`
- `frontend/src/pages/workforce/Training.tsx`
- `frontend/src/pages/workforce/Calendar.tsx`
- `frontend/src/pages/__tests__/CompetenceGaps.test.tsx`
- `scripts/governance/pr_body_emp_roster_ui_picker.md`

**Out of scope / sibling:** EMP-LINK (`path11/emp-link-user-engineer`) — link APIs, QGP edit, auto-create Engineer on User create. Merge LINK first for richest picker emails (`linked_user`).

## 1) Summary
- **Feature / Change name:** EMP-UI — Active default + list/compact + Engineer people picker
- **User goal:** Employees defaults to active engineers; search/filter/views; incidents/complaints pick people from the roster (names visible even without login; assign requires link).
- **In scope:** Roster UX; shared `EngineerPeoplePicker`; Incidents/Complaints triage + complaint subject; display_name labels.
- **Out of scope:** Backend link endpoints (EMP-LINK); ActionDetail/InvestigationDetail email fields (follow-on).
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** Engineers view modes; default Active; create links via UserEmailSearch; EngineerPeoplePicker on Incidents/Complaints; display_name labels Training/Calendar/CompetenceGaps.
- **Backend:** None
- **APIs:** Consumes existing GET `/engineers/?is_active=true` (+ optional `linked_user` when LINK is live)
- **Schemas/contracts:** Tolerant `linked_user?` on EngineerProfile
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE
- **Tolerant reader / strict writer applied?** Yes — picker works without `linked_user`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Employees page defaults to Active filter
- [x] AC-02: Cards / List / Compact view toggles work
- [x] AC-03: Search + status filter remain available
- [x] AC-04: Incident/Complaint owner pickers list active engineers by name
- [x] AC-05: Unlinked engineers visible but not selectable for owner assign; selectable for complaint subject (`requireLogin=false`)
- [x] AC-06: Create employee can link via user search (not raw user id)

## 5) Testing Evidence (link to runs)
- [x] Unit: CompetenceGaps label test updated
- [ ] CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Employees → Active engineers → switch List/Compact → open profile
- [x] CUJ-02: Incident triage → search engineer name → assign when linked
- [x] CUJ-03: Complaint create → pick subject engineer without login (name stored)

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Employees views; incident assign from roster; complaint subject without login.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same on tip SWA.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Assign/triage regressions
- **Rollback steps:** Revert squash-merge; force_deploy prior SHA
- **Owner:** Tip-owner

## 10) Evidence Pack (links)
- Canvas: `qgp-employees-pams-profiles-360`
- Pair with EMP-LINK PR for full Person≠Login loop

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts — roster person picker; assign needs login
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary — N/A
- [ ] **Gate 5:** Production verification plan ready
