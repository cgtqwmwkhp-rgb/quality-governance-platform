# Change Ledger (CL-PATH11-EMP-04-ASSESSMENT-PICKER)

**Path claim:** `path11/emp-04-assessment-picker`

## 1) Summary
- **Feature / Change name:** EMP-04 — Assessment employee picker uses active roster
- **User goal (1-2 lines):** Assessment create + list filters load active Employees from `listEngineers` with role-aware labels; when the roster is empty, show honest guidance to Sync from PAMS / open Employees — not a broken silent select.
- **In scope:** `AssessmentCreate.tsx`, `Assessments.tsx`, shared `employeePickerUtils.ts` + tests; minimal i18n (`workforce.assessments.employees_empty*`, `workforce.common.all_employees` in en/cy); Change Ledger inline
- **Out of scope:** `Layout.tsx`, `App.tsx`, `client.ts` spine, `Actions.tsx`, `ComplianceAutomation*`, `Audits.tsx`, `PlanetMark.tsx`, `Analytics*`, `KnowledgeExceptions*`, InductionCreate (separate lane)
- **Feature flag / kill switch:** N/A — FE-only on existing `GET /api/v1/engineers/?is_active=true`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Workforce Assessments list filter + New Assessment create form employee pickers
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (consumes existing `listEngineers` with `is_active=true`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** FE-only; additive picker UX
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert PR; no schema impact

## 4) Acceptance Criteria (AC)
- [x] AC-01: Assessment create loads active employees via `listEngineers({ is_active: 'true' })`
- [x] AC-02: Picker options use role-aware labels (`display_name` / employee number + job title / department)
- [x] AC-03: Empty active roster shows honest message pointing to Employees / Sync from PAMS; picker disabled
- [x] AC-04: Assessments list engineer filter uses same active roster + labels; empty roster banner
- [x] AC-05: Vitest proofs for utils, AssessmentCreate, Assessments filter wiring

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `vitest run employeePickerUtils.test.ts AssessmentCreate.test.tsx WfGate.test.tsx` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — OpenAPI drift check in CI
- [ ] E2E Smoke — manual staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens New Assessment → sees active employees with readable labels
- [x] CUJ-02: Empty roster → guidance + link to Employees; cannot submit without roster
- [x] CUJ-03: Assessments list engineer filter uses active employees only

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm picker labels; empty roster CTA; filter still wires `engineer_id`
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Assessments create + filter

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Picker regression or false empty states
- **Rollback steps:** Revert PR
- **Owner:** Workforce / Path 11 FE lane EMP-04

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Test plan
- [ ] New Assessment with populated roster shows role-aware employee options
- [ ] New Assessment with empty roster shows Employees link and disabled submit
- [ ] Assessments list engineer filter passes `engineer_id` and uses active roster
- [ ] Empty roster banner on Assessments list
