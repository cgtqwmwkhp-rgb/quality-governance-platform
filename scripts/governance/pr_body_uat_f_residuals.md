# Change Ledger (CL-UAT-WAVE-F-RESIDUALS)

## 1) Summary
- **Feature / Change name:** UAT Wave F — workforce register honesty residuals.
- **User goal:** Prevent workforce training screens from presenting unavailable reference data as valid empty data.
- **In scope:** UAT-F-01 Training lookup-load warning; UAT-F-02 New Training roster/template load failure honesty; focused Vitest coverage.
- **Out of scope:** API contract changes, migrations, PAMS integration, employee-to-user linking (PX-056), product flags, and all Library disposal execution work.
- **Feature flag / kill switch:** None. Revert the PR to restore prior client behavior.

## 2) Impact Map
| ID | Surface | Before | After |
|---|---|---|---|
| UAT-F-01 | Workforce → Training register | Failed engineer/template/asset lookups silently left raw numeric IDs in the register. | A visible warning explains that labels are unavailable while records remain usable by ID. |
| UAT-F-02 | Workforce → New Training | A failed employee request appeared as an empty roster and left a misleading create form. | The UI identifies the unavailable roster, does not claim it is empty, and disables required controls/start until data reloads. |

- **Frontend:** `Training.tsx`, `InductionCreate.tsx`, focused Vitest tests.
- **Backend/APIs/database/config/dependencies:** No changes.

## 3) Compatibility & Data Safety
- Additive client-only honesty states; existing successful register and create behavior is unchanged.
- No write schema, persistence, migration, feature flag, or permission behavior changes.
- Asset-type failure remains non-blocking because the field is optional; required templates/employees fail closed.

## 4) Acceptance Criteria
- [x] AC-01: Training lookup failures display an explicit warning rather than silently showing only fallback IDs.
- [x] AC-02: Training records remain visible when supplemental lookup data is unavailable.
- [x] AC-03: A failed employee lookup is not presented as an empty employee roster.
- [x] AC-04: New Training disables required inputs and submit when templates or employees cannot load.
- [x] AC-05: Focused Vitest coverage proves both failure states.

## 5) Testing Evidence
- [x] `npx vitest run src/pages/workforce/__tests__/WfGate.test.tsx src/pages/workforce/__tests__/InductionCreate.test.tsx` — 11 passed.
- [x] `npm run lint -- --quiet` — passed.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Workforce → Training still lists existing training rows when label lookups fail and explains the fallback IDs.
- [x] CUJ-02: Workforce → New Training distinguishes an unavailable employee service from a genuinely empty roster and prevents an invalid start.

## 7) Observability & Ops
- No telemetry, logging, or alert changes.
- Support can distinguish a data outage from an empty roster from the on-screen message.

## 8) Release Plan
1. Merge only after required CI checks pass.
2. Deploy through the standard frontend conveyor.
3. In staging, block the engineer lookup on Training and New Training; confirm the warning/error state and disabled create action.

## 9) Rollback Plan
- **Trigger:** A workforce training register or New Training regression after deployment.
- **Steps:** Revert the merge commit and redeploy the prior frontend artifact.
- **Owner:** Platform release operator.

## 10) Evidence Pack
- Tests: `frontend/src/pages/workforce/__tests__/WfGate.test.tsx`, `frontend/src/pages/workforce/__tests__/InductionCreate.test.tsx`.
- This ledger: `scripts/governance/pr_body_uat_f_residuals.md`.

---

## Gate Checklist
- [x] Gate 0: Scope, IDs, ACs, and Change Ledger complete; excluded work remains excluded.
- [x] Gate 1: FE-only failure-state hardening; no API or data contract change.
- [x] Gate 2: Focused tests and frontend lint pass locally.
- [ ] Gate 3: Hosted CI and staging UAT re-probe pending.
- [x] Gate 4: No canary required — additive presentation-only behavior.
- [x] Gate 5: Rollback and post-deploy checks documented.
