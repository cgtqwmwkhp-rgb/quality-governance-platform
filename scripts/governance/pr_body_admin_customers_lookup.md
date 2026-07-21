# Change Ledger (CL-ADMIN-CUSTOMERS-LOOKUP)

## 1) Summary
- **Feature / Change name:** Admin Customers lookup (SSOT for customer dropdowns)
- **User goal (1–2 lines):** Admins add/remove customers in Lookups; those options populate platform dropdowns (starting with Complaints intake).
- **In scope:** `customers` lookup category card + hints; catalog helper; Complaints picker prefers Customers lookup (Contracts fallback); i18n en/cy; tests
- **Out of scope:** Migrating Contracts admin away; CES asset upload (parallel track); seeding customers
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `LookupTables.tsx`, `customersCatalog.ts`, Complaints create customer picker, i18n, tests
- **Backend:** None — generic `lookup_options` category string
- **APIs:** Existing `GET/POST /api/v1/admin/config/lookup/customers`
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive lookup category; Complaints falls back to Contracts list if Customers lookup empty
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None (empty-state CTA now points to Lookups → Customers)
- **Migration plan:** Admin configures Customers; optional match to Contracts by name/code for `contract_id`
- **Rollback strategy (DB):** Revert PR; no schema impact

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin Lookups shows Customers card (`customers` category)
- [x] AC-02: Configure allows add options; suggested codes documented, not pre-seeded
- [x] AC-03: Complaints create dialog loads Customers lookup first for the customer dropdown
- [x] AC-04: Empty customers → honest CTA to Admin → Lookups → Customers
- [x] AC-05: Unit tests cover catalog + LookupTables Customers card/editor

## 5) Testing Evidence (link to runs)
- [x] Unit FE — customersCatalog + LookupTables
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Lookups → Customers → Configure → add UKPN
- [x] CUJ-02: Complaints → New → customer dropdown shows lookup options (or Contracts fallback)

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** Configure Customers in Admin Lookups before complaint intake

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Add 2–3 customers; open Complaints create; confirm dropdown
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same + seed known customers (UKPN, Openreach, etc.)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Lookups hub regression or Complaints create broken
- **Rollback steps:** Revert PR
- **Owner:** Platform / Admin Lookups

## 10) Evidence Pack (links)
- CI run(s): after open
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — FE registry over existing lookup API
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
