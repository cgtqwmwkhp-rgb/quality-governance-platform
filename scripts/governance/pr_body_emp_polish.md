# Change Ledger (CL-EMP-POLISH)

## 1) Summary
- **Feature / Change name:** EMP-POLISH — Employees roster UX polish + manual create CRUD
- **User goal (1-2 lines):** Finish the Employees rename in UI copy, let managers add employees manually via existing POST API, and filter active/inactive roster rows without touching backend spines.
- **In scope:** `Engineers.tsx` add-employee dialog + active filter; i18n (`nav.engineers`, `workforce.engineers.title/subtitle/empty` + create/filter keys in en/cy); `workforceClient.test.ts` engineer create path; `Engineers.test.tsx`; this ledger
- **Out of scope:** `Layout.tsx`, PAMS sync service, migrations, shared spines (`App.tsx`, `api/__init__.py`, `client.ts` beyond existing re-exports)
- **Feature flag / kill switch:** N/A — uses existing `POST /api/v1/engineers/` (#1047 contract: `display_name` and/or `user_id`)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Engineers.tsx` — Add employee dialog, active/inactive filter, header actions; route stays `/workforce/engineers`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (consumes existing `POST /api/v1/engineers/`, `GET /api/v1/engineers/?is_active=`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None (uses existing `EngineerCreatePayload` in `workforceClient.ts`)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** FE-only; additive UI on existing API
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert PR; no schema impact

## 4) Acceptance Criteria (AC)
- [x] AC-01: Nav + page title/subtitle/empty use Employees wording (en); cy parity for nav/title/subtitle/empty/sync
- [x] AC-02: Add employee dialog posts to `POST /api/v1/engineers/` with `display_name` and/or `user_id`
- [x] AC-03: Honest empty state still mentions Sync from PAMS
- [x] AC-04: Active/inactive filter passes `is_active` to list API
- [x] AC-05: `createEngineer` covered in `workforceClient.test.ts`
- [x] AC-06: `Engineers.test.tsx` covers empty state, filter, create validation + success

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `npm test -- Engineers.test.tsx workforceClient.test.ts` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — OpenAPI drift check in CI
- [ ] E2E Smoke — manual staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager opens Workforce → Employees → Add employee → profile opens
- [x] CUJ-02: Empty roster shows PAMS sync guidance + button
- [x] CUJ-03: Filter inactive employees without client-side-only filtering

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** None

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Add manual employee; confirm filter; confirm PAMS empty CTA unchanged
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Employees page labels + create flow

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Create dialog errors or filter regression
- **Rollback steps:** Revert PR
- **Owner:** Workforce / Path 11 FE lane

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

## Manual add employee
1. **UI:** Workforce → Employees → **Add employee** → fill display name (or portal user ID) → save
2. **API:** `POST /api/v1/engineers/` body `{ "display_name": "..." }` or `{ "user_id": 123 }`

## Notes
- Route path remains `/workforce/engineers` (i18n label only is Employees)
- PAMS bulk import still via **Sync from PAMS** (out of scope for this PR's service work)
