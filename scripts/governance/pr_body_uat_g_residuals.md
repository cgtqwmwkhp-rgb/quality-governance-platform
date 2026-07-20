# Change Ledger (CL-UAT-WAVE-G-RESIDUALS)

## 1) Summary
- **Feature / Change name:** UAT Wave G — assessment register and create-form honesty residuals.
- **User goal:** Do not present unavailable assessment lookup data as valid empty data, and prevent creation when required reference data is unavailable.
- **In scope:** UAT-G-01 assessment register lookup warning; UAT-G-02 assessment register roster-outage state; UAT-G-03 assessment-create required lookup failure states; focused Vitest coverage.
- **Out of scope:** API contract changes, migrations, PAMS integration, employee-to-user linking (PX-056), ACT-032/033 product flags, and all Library disposal execution work.
- **Feature flag / kill switch:** None. Revert the PR to restore prior client behavior.

## 2) Impact Map
| ID | Surface | Before | After |
|---|---|---|---|
| UAT-G-01 | Workforce → Assessments register | Failed engineer/template/asset lookups silently left raw numeric IDs in the register. | A visible warning explains that labels are unavailable while records remain usable by ID. |
| UAT-G-02 | Workforce → Assessments register | A failed employee request was indistinguishable from a genuinely empty active roster. | The UI identifies the unavailable roster and disables the employee filter without claiming it is empty. |
| UAT-G-03 | Workforce → New Assessment | A failed template or employee request appeared as an empty required selector. | The UI identifies unavailable required data, disables the affected selector, and prevents starting an invalid assessment. |

- **Frontend:** `Assessments.tsx`, `AssessmentCreate.tsx`, focused Vitest coverage.
- **Backend/APIs/database/config/dependencies:** No changes.

## 3) Compatibility & Data Safety
- Additive client-only failure states; successful register and create behavior is unchanged.
- No write schema, persistence, migration, feature flag, permission, or API contract changes.
- Asset-type failure is non-blocking because the field is optional; required templates and employees fail closed.

## 4) Acceptance Criteria
- [x] AC-01: Assessment lookup failures display an explicit warning rather than silently showing only fallback IDs (UAT-G-01).
- [x] AC-02: Assessment records remain visible when supplemental lookup data is unavailable (UAT-G-01).
- [x] AC-03: A failed employee lookup is not presented as an empty assessment roster (UAT-G-02).
- [x] AC-04: New Assessment disables unavailable required template/employee controls and start action (UAT-G-03).
- [x] AC-05: Focused Vitest coverage proves both roster and create-form failure states.

## 5) Testing Evidence
- [x] `npm run lint -- --quiet` — passed.
- [x] `npx vitest run src/pages/workforce/__tests__/WfGate.test.tsx` — 10 passed.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Workforce → Assessments still lists existing rows when supplemental labels fail and explains fallback IDs.
- [x] CUJ-02: Workforce → Assessments distinguishes an unavailable employee service from a genuinely empty roster.
- [x] CUJ-03: Workforce → New Assessment identifies unavailable templates/employees and prevents invalid start.

## 7) Observability & Ops
- No telemetry, logging, or alert changes.
- Support can distinguish a reference-data outage from an empty employee roster from the on-screen message.

## 8) Release Plan
1. Merge only after required CI checks pass.
2. Deploy through the standard frontend conveyor.
3. In staging, block the template and employee lookups on Assessments and New Assessment; confirm the warning/error state and disabled create action.

## 9) Rollback Plan
- **Trigger:** An assessment register or New Assessment regression after deployment.
- **Steps:** Revert the merge commit and redeploy the prior frontend artifact.
- **Owner:** Platform release operator.

## 10) Evidence Pack
- Tests: `frontend/src/pages/workforce/__tests__/WfGate.test.tsx`.
- This ledger: `scripts/governance/pr_body_uat_g_residuals.md`.

---

## Gate Checklist
- [x] Gate 0: Scope, IDs, ACs, and Change Ledger complete; excluded work remains excluded.
- [x] Gate 1: FE-only failure-state hardening; no API or data contract change.
- [x] Gate 2: Focused tests and frontend lint pass locally.
- [ ] Gate 3: Hosted CI and staging UAT re-probe pending.
- [x] Gate 4: No canary required — additive presentation-only behavior.
- [x] Gate 5: Rollback and post-deploy checks documented.
