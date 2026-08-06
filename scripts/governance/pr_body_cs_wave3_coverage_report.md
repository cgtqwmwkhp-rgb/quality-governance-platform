# Change Ledger (CL-CS-W3-PR2-COVERAGE-GAPS)

## 1) Summary
- **Feature / Change name:** Wave 3 PR2 — Location FRA / fire-drill coverage gap report
- **User goal (1–2 lines):** Compliance managers see which active locations lack an active site-scoped Fire Risk Assessment and/or Fire Drill obligation, without treating organisation-wide rows as site coverage.
- **In scope:** `GET /api/v1/compliance-schedule/coverage/location-gaps`; service method; schemas; Compliance Schedule page panel; en/cy keys; unit + client path tests
- **Out of scope:** Bulk import, portal/mobile drill capture, OCR/PAS79 ingest, significant-change from Incident, exec dashboard changes, DB migrations
- **Feature flag / kill switch:** Existing `COMPLIANCE_SCHEDULE_ENABLED` + kill switch + `compliance_schedule:read` (same gate as other CS routes)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Coverage panel on `ComplianceSchedule.tsx` (soft-fail so register still loads); client method + types; test mocks; en/cy i18n
- **Backend (handlers/services):** `ComplianceScheduleService.get_location_coverage_gaps`
- **APIs (endpoints changed/added):** `GET /api/v1/compliance-schedule/coverage/location-gaps`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `LocationCoverageGapItem`, `LocationCoverageGapsResponse` (+ FE types)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None new
- **Dependencies (added/removed/updated):** None
- **Tests:** `tests/unit/test_compliance_schedule_location_coverage.py`; client path exercise; existing ComplianceSchedule vitest mocks

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + UI panel; no schema/DB breaks
- **Tolerant reader / strict writer applied?** Yes — FE soft-fails coverage fetch; clients that ignore the endpoint are unchanged
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit removes endpoint + panel

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Site FRA / drill coverage visibility | Managers must scan the full register manually | Explicit gap counts + per-location FRA/drill status on the CS page |
| Org-wide vs site-scoped honesty | Org-wide FRA could be mistaken for site cover | Org-wide (`location_id IS NULL`) deliberately excluded from coverage matches |
| Permission / flag boundary | N/A for this report | Same `compliance_schedule:read` + module enable/kill-switch as other CS routes |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `GET /api/v1/compliance-schedule/coverage/location-gaps` returns active locations with `has_fra` / `has_fire_drill` and aggregate missing counts, gated by CS enable + kill switch + `compliance_schedule:read`
- [x] AC-02: Organisation-wide FRA/drill requirements (`location_id IS NULL`) do not mark any location as covered
- [x] AC-03: Compliance Schedule page shows a coverage panel with totals and per-location gap/ok labels; coverage fetch failure does not blank the register
- [x] AC-04: Unit tests prove gap marking + org-wide exclusion; client path test exercises the versioned `/coverage/location-gaps` URL
- [x] AC-05: en/cy keys exist for coverage copy (with English fallbacks in the page)

## 5) Testing Evidence (link to runs)
- [x] Lint — `black` / `isort` clean on touched Python
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `python3.11 -m pytest tests/unit/test_compliance_schedule_location_coverage.py` (2 passed locally)
- [x] Frontend unit — `vitest run` paths + emptyVsError (8 passed locally)
- [ ] Integration tests — CI (additive route; no migration)
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Manager with CS open opens Compliance Schedule and sees location FRA/drill coverage gaps (including locations missing both)
- [x] CUJ-02: Site covered only by an organisation-wide FRA still shows as missing FRA for that location
- [x] CUJ-03: If coverage API fails, the obligation register still loads (soft-fail)

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** With CS enabled + read permission, open `/compliance-schedule`; confirm coverage panel totals; create/activate a location-scoped FRA and confirm the location flips to FRA covered; confirm an org-wide-only FRA does not clear the gap
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same UI + `GET /api/v1/compliance-schedule/coverage/location-gaps` on prod FQDN; confirm `meta/version` `build_sha` matches tip before marking LIVE

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong coverage (org-wide counted as site cover), tenant bleed, or panel blanks the register on coverage errors
- **Rollback steps:** Revert squash commit on `main`; redeploy prior image
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

Made with [Cursor](https://cursor.com)
