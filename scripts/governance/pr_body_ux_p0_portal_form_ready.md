# Change Ledger (CL-UX-P0-PORTAL-FORM-READY)

> **Start gate:** #1758 LIVE — tip `e4771f9a89f5`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Portal P0 form-ready + stable `field-contract` hook
- **User goal:** Employee incident and near-miss report CUJs must wait until the form is actually loaded, and the customer picker must be addressable as `field-contract` even when the admin template names it `customer`/`client`.
- **In scope:** `PortalDynamicForm` ready/loading testids; `portalFieldTestId` alias; workflow-audit wait uses the workflow budget instead of a hardcoded 5s field wait. No Entra. No Assist triad. No Exceptions cap.
- **Out of scope:** Raising the UX coverage HOLD policy; a11y P1s on admin-partner-webhooks / admin-forms-new.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| UX-P0-01 | Portal form load | No ready marker; CUJ waited 5s for `field-contract` during spinner | `portal-form-loading` / `portal-form-ready`; CUJ waits up to `max_duration_seconds` |
| UX-P0-02 | Customer picker testid | `field-${field.name}` only | `field-contract` for contract/customer/client names |
| UX-P0-03 | Coverage evidence | LIVE SHA `e4771f9` run 31880826656: 2 P0 timeouts on `field-contract` | Same CUJ, honest wait + stable hook |

## 3) Compatibility & Data Safety
- Additive testids. No schema, flag, or write-path change.
- **Rollback strategy:** Revert merge and redeploy prior tip `e4771f9a89f5`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| P0 portal incident / near-miss | Gate HOLD: 5s race vs staging form-config | Wait for form-ready then picker; still fail-closed if picker absent |
| TrapGuard / Entra | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Loaded portal form exposes `portal-form-ready`; loading exposes `portal-form-loading`.
- [x] AC-02: A first-step select named `customer` is `data-testid="field-contract"`.
- [x] AC-03: Workflow-audit form_fields wait uses the workflow duration budget, not a hardcoded 5s, and waits for `portal-form-ready` first.
- [x] AC-04: No Entra/Assist/Exceptions-cap change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `DynamicFormRenderer.test.tsx` alias; `PortalDynamicForm.lookupDegradation.test.tsx` ready marker
- [x] Measured P0: UX coverage `31880826656` on LIVE `e4771f9` — `portal-incident-report` step 4 and `portal-near-miss-report` step 3 timed out on `[data-testid='field-contract']`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incident form still renders `field-contract` when catalogs fail (existing degradation tests).
- [x] CUJ-02: Admin-named `customer` picker is the same CUJ hook.

## 7) Observability & Ops
- Coverage gate remains HOLD until this image is LIVE and the next UX run is measured. Do not tick Verified from merge.

## 8) Release Plan
1. Branch from LIVE tip `e4771f9a89f5`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Portal form never shows `portal-form-ready`; `field-contract` missing on fallback template; Entra/Assist invented.
- **Rollback steps:** Revert merge; redeploy `e4771f9a89f5`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1758** @ `e4771f9a89f5`
- UX P0: run `31880826656`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1758 LIVE
- [x] **Gate 1:** Focused tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
