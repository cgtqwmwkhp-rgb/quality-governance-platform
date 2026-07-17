# Change Ledger (CL-EMP-02-ROLES-CATALOG)

## 1) Summary
- **Feature / Change name:** EMP-02 — Admin workforce_roles lookup catalog
- **User goal (1-2 lines):** Admins configure the `workforce_roles` lookup category (engineer, field_engineer, supervisor, process_scheduler) via Settings → Lookup Tables; empty counts stay honest and standard codes are documented without pre-seeding.
- **In scope:** LookupTables `workforce_roles` card + editor hints; `workforceRolesCatalog.ts` constants; i18n (en/cy); vitest proofs; Change Ledger
- **Out of scope:** `AssessmentCreate.tsx`, `Assessments.tsx`, `employeePickerUtils.ts` (#1061); `Engineers.tsx` role filter (API has no role param — catalog admin surface is sufficient); backend/migrations; forbidden spines
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `LookupTables.tsx`, `workforceRolesCatalog.ts`, tests
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** Uses existing `GET/POST /api/v1/admin/config/lookup/workforce_roles`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None — generic `lookup_options` category row
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive Lookup Tables category; no fabricated seed data
- **Tolerant reader / strict writer applied?** Yes — counts from API; hints are documentation only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit; no schema impact

## 4) Acceptance Criteria (AC)
- [x] AC-01: Lookup Tables shows Workforce Roles card wired to `workforce_roles` category
- [x] AC-02: Not configured / count unavailable honesty unchanged for new category
- [x] AC-03: Card + editor document standard codes (engineer, field_engineer, supervisor, process_scheduler) without pre-seeding
- [x] AC-04: Configure opens editor; create uses existing lookups API
- [x] AC-05: i18n en/cy for workforce_roles desc + hint
- [x] AC-06: Unit tests cover card, editor hints, catalog constants

## 5) Testing Evidence (link to runs)
- [x] Unit tests — LookupTables.test.tsx + workforceRolesCatalog.test.ts (local)
- [ ] Lint / typecheck / build — CI after open
- [ ] Integration / E2E — deferred to CI

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Lookup Tables → Workforce Roles → Not configured + code hints
- [x] CUJ-02: Configure → empty editor lists suggested codes → Add option via API
- [x] CUJ-03: API failure shows Count unavailable (not fabricated zero)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open /admin/lookups; configure workforce_roles; confirm employee job_title can align manually
- **Canary plan:** N/A
- **Prod post-deploy checks:** Admin lookups smoke for workforce_roles card

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Lookup Tables regression or misleading role hints
- **Rollback steps:** Revert PR
- **Owner:** Workforce / Path 11 FE lane (EMP-02)

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

---

# Path claim (EMP-02 exclusive)
| Path | Status |
|------|--------|
| `frontend/src/pages/admin/LookupTables.tsx` | **CLAIMED** |
| `frontend/src/pages/admin/workforceRolesCatalog.ts` | **CLAIMED** |
| `frontend/src/pages/admin/__tests__/LookupTables.test.tsx` | **CLAIMED** |
| `frontend/src/pages/admin/__tests__/workforceRolesCatalog.test.ts` | **CLAIMED** |
| `frontend/src/i18n/locales/en.json` | **CLAIMED** (admin.lookups.workforce_roles_*) |
| `frontend/src/i18n/locales/cy.json` | **CLAIMED** (admin.lookups.workforce_roles_*) |
| `scripts/governance/pr_body_emp_02_roles_catalog.md` | **CLAIMED** |

**FORBIDDEN (parallel PRs / #1061):** AssessmentCreate.tsx, Assessments.tsx, employeePickerUtils.ts, ComplianceAutomation*, PlanetMark*, Analytics.tsx, Actions.tsx, Audits.tsx, Layout.tsx, App.tsx, client.ts, Alembic
