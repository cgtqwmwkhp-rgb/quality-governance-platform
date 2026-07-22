# Change Ledger — Catalog SSOT PR2 (Severity, Types, Medical, Labels)

## 1) Summary

- **Feature / Change name:** Catalog SSOT alignment — severity/types/medical assistance and employee/asset labels
- **User goal:** Admin Lookups control presentation labels for fixed API enum options, medical assistance uses its catalog in portal forms, and workforce/asset UI terminology is consistent.
- **In scope:** AC-01..AC-08
- **Out of scope:** New API enum codes, RTA severity, route/API/board-role renames, database migrations
- **Feature flag / kill switch:** N/A — lookup label overlays retain hardcoded API-enum fallbacks.

## 2) Impact Map

| File                                                                  | Change                                                                             |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `NearMisses.tsx`                                                      | `severity_levels` labels overlay fixed low/medium/high/critical create options     |
| `IncidentDetail.tsx`                                                  | Edit incident severity/type defaults match Incident API enums and overlay Lookups  |
| `Complaints.tsx` / `ComplaintDetail.tsx`                              | Priority and complaint type labels overlay `severity_levels` / `complaint_types`   |
| `PortalDynamicForm.tsx` / `DynamicFormRenderer.tsx`                   | `medical_assistance` catalog options injected into dynamic templates with fallback |
| `PortalIncidentForm.tsx`                                              | Medical assistance lookup with five-code fallback                                  |
| `PortalNearMissForm.tsx`                                              | Preserve selected low/medium/high/critical severity in submitted payload           |
| `Portal.tsx`, `PortalMyTools.tsx`, `Dashboard.tsx`, dashboard helpers | User-facing My assets naming only; routes and API names retained                   |
| `en.json` / `cy.json`                                                 | Competency directory label is Employees / Cyflogeion                               |
| `NearMisses.a11y.test.tsx`                                            | Lookup label overlay coverage                                                      |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Fixed lists remain the API enum contract; `mergeLookupSelectOptions` changes labels only and never appends admin-defined codes.
- **Fallback:** Lookup failures or empty catalog responses leave the existing fixed defaults, including five medical-assistance codes.
- **No schema/API changes:** `/portal/tools`, portal-compliance API names, and workforce board role codes remain unchanged.

## 4) Acceptance Criteria (AC)

- [x] AC-01: Near Miss create uses `severity_levels` labels over low/medium/high/critical defaults.
- [x] AC-02: Incident detail edit type/severity options match Incident API enums, including negligible severity.
- [x] AC-03: Complaint create/edit priority labels overlay fixed critical/high/medium/low defaults.
- [x] AC-04: Complaint detail type labels overlay fixed complaint enum defaults.
- [x] AC-05: Dynamic portal forms load `medical_assistance` and retain the fallback set when unavailable.
- [x] AC-06: Portal incident form loads `medical_assistance` and retains the fallback set when unavailable.
- [x] AC-07: Portal Near Miss sends selected low/medium/high/critical severity unchanged.
- [x] AC-08: Workforce directory and portal/dashboard asset terminology is updated without changing routes or API names.

## 5) Testing Evidence

- [ ] `vitest` targeted catalog/portal tests (run before merge)
- [ ] `npm run i18n:check` (run before merge)
- [ ] CI green (Gate 2)

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Admin relabels High severity; Near Miss, Incident edit, and Complaint priority show the new label but submit `high`.
- [x] CUJ-02: Admin adds an unsupported severity/type code; no unsupported option appears in enum-bound forms.
- [x] CUJ-03: Admin updates medical assistance; portal incident and dynamic form show its code/label; catalog outage falls back safely.
- [x] CUJ-04: Employee opens Portal/Dashboard assets; My assets wording is shown while `/portal/tools` still works.

## 7) Observability & Ops

- Lookup failures are fail-safe for enum fields: fixed defaults remain usable.
- Dynamic portal form retains its existing catalog warning behavior for Customers/Roles.

## 8) Release Plan

1. Merge after targeted Vitest, i18n check, and CI pass.
2. Staging: relabel existing severity/type/medical lookup values and verify labels in each affected form.
3. Verify submissions retain API enum codes and unsupported lookup codes cannot be selected.

## 9) Rollback Plan

- **Trigger:** A form cannot render or an enum API rejects a selection.
- **Steps:** Revert this commit; hardcoded defaults remain in the previous release.
- **Owner:** Platform team.

## 10) Evidence Pack

- CI run(s): add after PR creation.
- Staging: screenshots/API payloads for severity, type, and medical assistance label overlays.

---

# Gate Checklist

- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: API/Data/UX contracts reviewed (label overlays only; fixed enum values)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [ ] Gate 4: Canary (N/A)
- [x] Gate 5: Production verification plan ready
