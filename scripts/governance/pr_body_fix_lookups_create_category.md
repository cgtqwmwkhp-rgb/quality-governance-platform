# Change Ledger (CL-FIX-LOOKUPS-CREATE-CATEGORY)

## 1) Summary
- **Feature / Change name:** Fix Admin Lookup Tables create contract + wire key consumers
- **User goal (1–2 lines):** Admins can add/remove lookup options (e.g. DEFRA under Customers) without 422; Incidents/Complaints read configured lookups.
- **In scope:** FE create injects `category`; BE `LookupOptionCreate.category` optional (path authoritative); list `is_active` omit=all; Admin Remove; Incidents type/severity + Complaints topics merge; tests
- **Out of scope:** Wiring risk_categories/departments/tools/assets/workforce_roles into every form; Portal roles fallback migration
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `lookupsClient.ts`, legacy `services/api.ts`, `LookupTables.tsx`, `lookupSelectOptions.ts`, Incidents/Complaints create selects, tests
- **Backend:** `LookupOptionCreate` schema, lookup list/create routes, form_config_service create
- **APIs:** `POST /api/v1/admin/config/lookup/{category}` accepts body without category; `GET` omit `is_active` returns all
- **Schemas/contracts:** category optional on create (backward compatible)
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Clients that still send body `category` continue to work; path always wins
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** List without `is_active` now returns inactive options too (Admin editor intent). Callers wanting active-only already pass `?is_active=true`.
- **Migration plan:** None
- **Rollback strategy (DB):** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: POST lookup without body category returns 201 with path category (DEFRA / customers case)
- [x] AC-02: FE create always includes category; Admin toast shows API error detail
- [x] AC-03: Admin editor can Remove an option (DELETE)
- [x] AC-04: Incidents create loads incident_types + severity_levels (defaults if empty)
- [x] AC-05: Complaints topics merge complaint_types lookups (extra codes appear)
- [x] AC-06: Unit/smoke coverage for create-without-category + merge helper

## 5) Testing Evidence (link to runs)
- [x] Local FE unit — lookupsClient, LookupTables, lookupSelectOptions, Complaints, Incidents
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Lookups → Customers → Add DEFRA succeeds
- [x] CUJ-02: Complaints → New → customer/topic options reflect lookups
- [x] CUJ-03: Incidents → New → type/severity reflect lookups when configured

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** After deploy, configure Customers (and other categories) in Admin Lookups

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Add DEFRA; confirm list + Complaints dropdown
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same (purple-water tip==LIVE)

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Lookup create/list regressions or Incidents/Complaints create broken
- **Rollback steps:** Revert PR
- **Owner:** Platform / Admin Lookups

## 10) Evidence Pack (links)
- CI run(s): after open
- Staging deploy evidence: after merge

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
