# Change Ledger (CL-INV-C2-LEAD-AND-SOURCE-EVIDENCE)

> Adjacent, not fixed here: evidence added to the source *after* the investigation opens is still
> not auto-linked (C6 / INV-7). Narrative redaction remains C17. Findings are still a textarea (C7).

## 1) Summary
- **Feature / Change name:** INV-C2 — type a lead investigator; show source-record evidence on the investigation
- **User goal:** Complete an investigation when the lead is a person who is not on the employee roster, and see photos already uploaded on the incident / near miss / RTA / complaint without re-uploading them.
- **In scope:** EngineerPeoplePicker keeps typed names when a login is not required; Summary save writes `data.lead_investigator` and `assigned_to_user_id` when a colleague is picked; Evidence tab lists both investigation uploads and `linked_investigation_id` files.
- **Out of scope:** Late-arriving source evidence (C6); bulk Users; Entra; changing assignment pickers that require a login; pack content (C13).
- **Feature flag / kill switch:** None. Kill SHA = previous LIVE `f65f8ecc2ef8`.

## 2) Impact Map (what changed)
- **Frontend:** `EngineerPeoplePicker` no longer calls `onChange(null)` on every keystroke when `requireLogin={false}`. `InvestigationDetail` stores `assigned_to_user_id` on save. Evidence tab issues a second list query on `linked_investigation_id` and merges by asset id.
- **Backend:** none. The list endpoint already filtered on `linked_investigation_id`; the tab never sent it. PATCH already accepted `assigned_to_user_id`.
- **APIs:** no contract change. Additive use of existing query param and update field.
- **Database / flags:** none.
- **Workflows/jobs:** none.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Login-required pickers (case owners, action assignees) still clear on type, so those surfaces cannot skip the roster.
- **Breaking changes:** none.
- **Migration plan:** none.
- **Rollback strategy (DB):** Revert the squash. No data migration.
- **Write-path safety:** Typed names write only `data.lead_investigator` and set `assigned_to_user_id` to null so a stale FK cannot outlive a renamed lead. Roster picks still go through `_validate_investigation_user_ref`.

## Compliance Delta
- **PII touched?** Lead investigator name may be a free-text personal name stored on the investigation, as the field already allowed when filled from the roster. No new processor.
- **ISO 45001 10.2:** the investigation can now record who led it when that person is not a QGP user, which was blocking completion.
- **What this PR does not claim:** that typed names are identity-proofed; that source evidence added after investigation creation is auto-linked.

## 4) Acceptance Criteria (AC)
- [x] AC-01: With `requireLogin={false}`, typing a name that is not on the roster calls `onChange` with that label and does not call `onChange(null)`.
- [x] AC-02: With `requireLogin={true}`, typing still calls `onChange(null)` so assignment cannot skip the roster.
- [x] AC-03: Saving Summary with a typed name PATCHes `lead_investigator` and `assigned_to_user_id: null`.
- [x] AC-04: Saving Summary after picking a linked colleague PATCHes `assigned_to_user_id` to that user id.
- [x] AC-05: Opening the Evidence tab lists `source_module=investigation` uploads and `linked_investigation_id` source files, merged by id so a row that appears in both is not duplicated.
- [x] AC-06: Backend closure still accepts either the FK or `data.lead_investigator` (unchanged).

## 5) Testing Evidence (link to runs)
- [x] Frontend — EngineerPeoplePicker, investigationEvidenceQuery, InvestigationDetail, employeePickerUtils: 42 passed.
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator types "External investigator" as lead, saves Summary. PATCH carries the name. Completion is no longer blocked for want of a roster row.
- [x] CUJ-02: Operator picks a colleague with a login. PATCH carries `assigned_to_user_id`.
- [x] CUJ-03: Evidence uploaded on the parent incident (linked at create_from_record) appears on the investigation Evidence tab alongside files uploaded on the investigation itself.
- [x] CUJ-04: Case/action assignee pickers (`requireLogin`) still refuse free text.

## 7) Observability & Ops
- **Logs:** unchanged.
- **Runbook:** If a lead was typed, `assigned_to_user_id` is null and notifications will not fire — same as a roster-only employee with no login.

## 8) Release Plan
- **Staging:** Open an investigation created from an incident that has photos. Confirm they appear on Evidence. Type a non-roster lead, save, confirm completion checklist clears the lead item.
- **Prod post-deploy:** `/healthz`; `/api/v1/meta/version` `build_sha` == tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** assignment pickers accepting free text; Evidence tab hiding investigation-native uploads.
- **Rollback steps:** Revert the squash on `main` and redeploy previous LIVE SHA `f65f8ecc2ef8`.
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- No migration

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (existing list param and PATCH field; login-required pickers held)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 4:** Canary (N/A — no flag)
- [x] **Gate 5:** Production verification plan + monitoring ready
