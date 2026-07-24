# Change Ledger (CL-CAPA-TABS-PARITY)

## Summary
- Align Incident / Near Miss / Complaint CAPA Actions tabs with the RTA pattern via a shared `CaseCapaActionsPanel`, including Near Miss create/update/complete modals and Actions workspace `near_miss` filter.

## Change Ledger

| ID | Change | Risk | Mitigation |
|----|--------|------|------------|
| CAPA-01 | Shared `CaseCapaActionsPanel` on Incident/NM/Complaint/RTA | Low | Reuses existing CAPA APIs |
| CAPA-02 | Near Miss in-context action create/update/complete | Medium | Same validation paths as RTA |
| CAPA-03 | `handoffLinks` complaint + near_miss support | Low | Additive |
| CAPA-04 | Actions workspace near_miss filter/create | Low | Additive |
| CAPA-05 | en/cy i18n + unit + Playwright parity CUJ | Low | Checks green locally |

## Acceptance criteria
- [x] Incident / Near Miss / Complaint Actions tabs match RTA UX pattern
- [x] Near Miss can create/update/complete CAPA without leaving case
- [x] Actions list filters/creates near_miss sources
- [x] i18n check + unit tests + Playwright spec

## Test plan
- [x] Unit tests for panel/handoffLinks/details
- [x] `npm run i18n:check`
- [x] Playwright `capa-case-tabs-parity.spec.ts`
- [ ] Post-deploy smoke: open Incident/NM/Complaint Actions tabs

## Gate 0
- [x] Scope lock + AC defined + Change Ledger complete
