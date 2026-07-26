# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Run021 Wave 2 — GROUP 5 search honesty (PX-181, PX-220, PX-130, PX-182)
- **User goal (1–2 lines):** Search must never lie: server failures show retry UI, library/register queries hit the server, and the header search control opens the palette for typing.
- **In scope:** Global search error honesty (verify on main + regression tests); documents library server `search` param; incident register server `search` param; header search click → palette + focus.
- **Out of scope:** Dependabot / #1307; semantic search ranking quality; GROUP 3 responsive tables; GROUP 7 metrics SSOT.
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `Documents.tsx` — pass `search` to list API; remove client-only filter that showed all rows when semantic returned `[]`.
  - `Incidents.tsx` — pass `search` to list API; remove page-only client filter + honesty banner.
  - `incidentsClient.ts` — optional `search` query param.
  - `Layout.tsx` — unchanged behaviour (button opens palette); PX-182 regression test added.
  - Global search (`useGlobalSearch` / `GlobalSearchPanel`) — verified on main (PX-181 already fixed).
- **Backend (handlers/services):**
  - `incidents.py` + `incident_service.py` — optional `search` ilike filter on title, reference, description.
- **APIs (endpoints changed/added):** `GET /api/v1/incidents/?search=` (new optional param). Documents list already supported `search`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None breaking.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.
- **Tests:** `GlobalSearchPalette.test.tsx` (PX-181), `Documents.test.tsx` (PX-220), `Incidents.test.tsx` (PX-130), `Layout.a11y.test.tsx` (PX-182), `test_incident_list_search.py`.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive query params; empty search omits filter (unchanged list).
- **Tolerant reader / strict writer applied?** Yes — frontend omits blank search; backend ignores unset param.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Revert deploy; no schema.

## 4) Acceptance Criteria (AC)
- [x] AC-01 (PX-181): Global search API failure shows `ErrorState` + retry, never "No results found".
- [x] AC-02 (PX-220): `/documents` nonsense query issues list `search=` request and shows empty state, not full library.
- [x] AC-03 (PX-130): `/incidents` search passes `search` to server and scans full register (not current page only).
- [x] AC-04 (PX-182): Header search button opens palette; input receives focus and typing.

## 5) Testing Evidence (link to runs)
- [x] Unit — vitest targets listed below (local)
- [x] Unit — pytest `test_incident_list_search.py` (local)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Cmd/Ctrl+K global search → API 503 → error banner + retry (regression test).
- [x] CUJ-02: Documents → type nonsense → network shows `search=` → empty library.
- [x] CUJ-03: Incidents → search reference on page 2 → server query, not page-only filter.
- [x] CUJ-04: Click header Search → palette opens → type query.

## 7) Observability & Ops
- **Logs:** None new.
- **Metrics:** None new.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Run four CUJs above on staging.
- **Canary plan:** Standard train.
- **Prod post-deploy checks:** Spot-check documents search + incidents search + header palette.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Search regressions or empty lists when data exists.
- **Rollback steps:** Revert this PR / redeploy previous frontend + API bake.
- **Owner:** Platform / QGP maintainers

## 10) Evidence Pack (links)
- CI run(s): (filled by CI on this PR)
- Base branch: `main`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — n/a, full promote
- [x] **Gate 5:** Production verification plan + monitoring ready

## Defects addressed (Run021 GROUP 5)

| ID | Root cause | Fix |
|---|---|---|
| **PX-181** | Search errors cleared results without error state | Already on main (`searchError` + `ErrorState`); regression test retained |
| **PX-220** | List API called without `search`; semantic `[]` skipped client filter → all rows | Pass `search` to list API; trust server-filtered rows |
| **PX-130** | Incidents filtered client-side on loaded page only | Backend + FE `search` param across register |
| **PX-182** | Reported dead header control | Verified button opens palette; added click+type regression test |
