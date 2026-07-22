# Change Ledger — Catalog SSOT PR1 (Customers + Assets + Roles)

## 1) Summary
- **Feature / Change name:** Catalog SSOT alignment — Customers, Assets, Workforce Roles
- **User goal:** One admin SSOT for organisation customers (retire Contracts nav), Safety asset types under Lookups → Assets, workforce roles only, and stop stuffing customer codes into incident/complaint `department`.
- **In scope:** AC-01..AC-08
- **Out of scope:** Severity/types/medical form wiring (PR2); Employees naming sweep (PR2); DB column renames; dropping `contracts` table
- **Feature flag / kill switch:** N/A — additive lookup migration; UI redirect only

## 2) Impact Map
| File | Change |
|------|--------|
| `alembic/versions/20260806_catalog_ssot_customers_roles.py` | Copy `contracts` → `lookup_options.customers`; `roles` → `workforce_roles`; seed default `severity_levels` |
| `frontend/src/pages/admin/LookupTables.tsx` | Hub: customers, workforce_roles, medical_assistance, Assets→`asset_types`; remove Tools/Locations/Departments/risk_categories |
| `frontend/src/components/Layout.tsx` / `App.tsx` | Remove Contracts nav; `/admin/contracts` → Lookups Customers |
| `frontend/src/pages/admin/AdminDashboard.tsx` | Active Customers from lookups |
| `frontend/src/pages/PortalDynamicForm.tsx` | Customers + workforce_roles; near_miss customer via submission/department bridge; no incident department stuffing |
| `frontend/src/pages/PortalIncidentForm.tsx` / `PortalNearMissForm.tsx` | Live customers/roles; near_miss `reporter_submission.contract` |
| `frontend/src/pages/NearMisses.tsx` / `Complaints.tsx` | Customers lookup SSOT |
| `frontend/src/components/DynamicForm/DynamicFormRenderer.tsx` | Options for `customer` or `contract` fields |
| `src/api/routes/employee_portal.py` | NearMiss.contract from `reporter_submission.contract` (legacy department bridge) |
| i18n en/cy + Vitest updates | Customer wording; Layout/Complaints/LookupTables/AdminDashboard/NearMisses |
| `scripts/governance/pr_body_catalog_ssot_pr1.md` | This ledger |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive — keep `contracts` table/API for complaint `contract_id` FK; UI retired
- **Migration:** Non-destructive copy; downgrade is no-op
- **Near miss:** Column remains `contract`; value is customer **code**
- **Incidents/complaints:** Customer stays in `reporter_submission.contract` / complainant company label — not `department`

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin Lookups → Customers is the SSOT; Contracts nav retired with redirect
- [x] AC-02: Alembic copies active contracts → customers lookup codes
- [x] AC-03: Portal/staff Near Miss customer dropdowns use `customers` lookup
- [x] AC-04: Portal Role dropdown uses `workforce_roles` only (no silent FALLBACK roles)
- [x] AC-05: Lookups Assets reads/writes Safety `asset_types`
- [x] AC-06: Orphan Tools/Locations/Departments/risk_categories cards removed from Lookups hub
- [x] AC-07: Portal incident/complaint submit does not set `department` from customer
- [x] AC-08: Portal near miss sets NearMiss.contract from customer code (`reporter_submission` preferred)

## 5) Testing Evidence
- [x] `vitest` NearMisses.a11y, Complaints, Layout, LookupTables, AdminDashboard
- [ ] CI green (Gate 2)

## 6) Critical Journeys (CUJ)
- [x] CUJ-01: Admin adds Customer in Lookups → portal Near Miss Select Customer shows it
- [x] CUJ-02: Portal near miss submit stores customer code on NearMiss.contract
- [x] CUJ-03: Lookups Assets count matches Safety asset types (not empty unused lookup_options)

## 7) Observability & Ops
- No new metrics; empty customers/roles show honest admin CTA (not fake lists)

## 8) Release Plan
1. Squash-merge after CI green
2. Staging: run Alembic; verify Customers populated from contracts; portal dropdown live
3. Prod tip==LIVE after deploy SHA match

## 9) Rollback Plan
- **Trigger:** Portal/staff cannot load customers after migrate, or Assets editor broken
- **Steps:** Revert deploy/commit; leave copied lookup rows (safe); Contracts page still reachable via API if needed
- **Owner:** Platform team

## 10) Evidence Pack
- CI run(s): Linked after PR creation
- Staging: confirm Lookups Customers + Assets counts post-migrate

---

# Gate Checklist
- [x] Gate 0: Scope lock + AC + Change Ledger complete
- [x] Gate 1: API/Data/UX contracts approved (lookups + asset_types; contracts table retained)
- [ ] Gate 2: CI green
- [ ] Gate 3: Staging verification
- [ ] Gate 4: Canary (N/A)
- [x] Gate 5: Production verification plan ready

## Out of scope (PR2)
- Wire `severity_levels` / incident_types / complaint_types across staff forms
- Medical assistance portal options from Lookups
- Employees naming sweep / portal My assets labels
