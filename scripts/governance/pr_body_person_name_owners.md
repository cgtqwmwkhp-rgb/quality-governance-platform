# Change Ledger (CL-PERSON-NAME-OWNERS)

## 1) Summary
- **Feature / Change name:** Lane P-Owners — employeesOnly owners/assignees + Lead Investigator policy lock
- **User goal (1–2 lines):** CAPA/action assignees and risk create owner use the shared people controls; document that IncidentDetail lead investigator stays employeesOnly while InvestigationDetail summary lead stays hybrid (PX-168).
- **In scope:** `ActionDetail` assignee → `EngineerPeoplePicker requireLogin`; Near Miss / RTA CAPA “Assign to” parity; RiskRegister create `ownerDraft` → `PersonNameField` hybrid; `docs/governance/lead_investigator_policy.md`; colocated test mocks
- **Out of scope:** IncidentDetail `lead_investigator` (unchanged employeesOnly); InvestigationDetail `summaryLead` (unchanged hybrid); Portal*; EvidenceGallery; DocumentPreview; ComplianceSchedule bulk/import; RiskRegister accept-dialog `UserEmailSearch`; backend/schema
- **Feature flag / kill switch:** N/A
- **Dependency note:** Prefer merge after #1618 / #1622 if those land first (this branch tip includes `PersonNameField` history). Self-contained against `main` is OK.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `ActionDetail` — plain email `Input` → `EngineerPeoplePicker` (`requireLogin`, maps to `assigned_to_email`)
  - `NearMissDetail` / `RTADetail` — CAPA assign `UserEmailSearch` → `EngineerPeoplePicker` (`requireLogin`) for parity with Incident/ComplaintDetail
  - `RiskRegister` create detail — `ownerDraft` plain `Input` → `PersonNameField` hybrid → `risk_owner_name` (accept dialog unchanged)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** `docs/governance/lead_investigator_policy.md`
- **Tests:** mocks for `EngineerPeoplePicker` on ActionDetail / NearMissDetail / RTADetail suites

## 3) Compatibility & Data Safety
- **Compatibility strategy:** UX-only; payloads still use existing email / `risk_owner_name` string fields
- **Tolerant reader / strict writer applied?** Yes — assignee save still requires a selected linked-user email; risk create owner remains optional display name
- **Breaking changes:** None (operators must pick an employee with login for CAPA assignees instead of free-typing email)
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert FE commit

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| ActionDetail assignee honesty | Free-text email `Input` | `EngineerPeoplePicker` employeesOnly (`requireLogin`) → `assigned_to_email` |
| NM/RTA CAPA assignee parity | `UserEmailSearch` | Same employeesOnly picker as Incident/ComplaintDetail |
| Risk create owner | Plain name `Input` | `PersonNameField` hybrid (`risk_owner_name`); import accept dialog still `UserEmailSearch` |
| **IncidentDetail `lead_investigator`** | `EngineerPeoplePicker requireLogin=true` (employeesOnly) | **Unchanged — locked employeesOnly** (closure needs linked QGP user) |
| **InvestigationDetail `summaryLead`** | `EngineerPeoplePicker requireLogin=false` (hybrid / PX-168) | **Unchanged — hybrid retained** (roster-only `assignee_name` allowed) |
| Agent guardrail | Easy to “hybrid-ise” incident lead for parity | Policy documented in PR + `docs/governance/lead_investigator_policy.md` |

### Lead Investigator POLICY (locked)

1. **IncidentDetail investigation `lead_investigator`** — keep **employeesOnly** (`EngineerPeoplePicker requireLogin=true`). Closure gate needs a linked QGP user. Do **NOT** switch to hybrid free-text.
2. **InvestigationDetail `summaryLead`** — keep **hybrid** (`requireLogin=false`) so roster-only names via `assignee_name` remain allowed (existing PX-168 behaviour).
3. Future agents must not hybrid-ise the incident closure lead in the name of “parity”.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `ActionDetail` assignee uses `EngineerPeoplePicker` with `requireLogin` (or equivalent employeesOnly) mapping to `assigned_to_email`
- [x] AC-02: `NearMissDetail` and `RTADetail` CAPA “Assign to” use `EngineerPeoplePicker requireLogin=true`
- [x] AC-03: `RiskRegister` create `ownerDraft` uses `PersonNameField` hybrid for `risk_owner_name`; accept-dialog `UserEmailSearch` untouched
- [x] AC-04: **IncidentDetail `lead_investigator` remains employeesOnly** (`requireLogin=true`) — not changed by this PR
- [x] AC-05: **InvestigationDetail `summaryLead` hybrid retained** (`requireLogin=false`) — not rewritten
- [x] AC-06: Lead Investigator policy recorded in Compliance Delta + `docs/governance/lead_investigator_policy.md`
- [x] AC-07: No Portal* / EvidenceGallery / DocumentPreview / ComplianceSchedule / backend schema changes

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `npx vitest run` ActionDetail / NearMissDetail / RTADetail / RiskRegister / RTADetail.a11y (passed locally)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — CI / staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Action detail — select employee with login → Assign saves `assigned_to_email`
- [x] CUJ-02: Near Miss / RTA CAPA create — Assign to uses employeesOnly picker (parity with Incident/Complaint)
- [x] CUJ-03: Risk create — hybrid owner name; Incident lead still employeesOnly; Investigation summary lead still hybrid

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A (policy doc added)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Assign CAPA from ActionDetail / NM / RTA with roster login user; create risk with typed vs roster owner name; confirm Incident investigation lead still requires login
- **Canary plan:** N/A
- **Prod post-deploy checks:** Confirm `meta/version` `build_sha` matches tip; spot-check assignee pickers

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Assignee/owner picker regressions blocking CAPA assignment or risk create
- **Rollback steps:** Revert squash commit on `main`; redeploy prior image
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

Made with [Cursor](https://cursor.com)
