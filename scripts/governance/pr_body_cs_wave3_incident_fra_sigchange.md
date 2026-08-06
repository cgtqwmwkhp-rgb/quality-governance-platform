# Change Ledger (CL-CS-W3-PR-INCIDENT-FRA-SIGCHANGE)

## 1) Summary
- **Feature / Change name:** Wave 3 — Incident → FRA significant-change prompt
- **User goal (1–2 lines):** After closing an incident that signals a premises significant change, the operator can create a site-scoped Fire Risk Assessment obligation or open the existing one, without treating organisation-wide FRAs as site cover.
- **In scope:** Eligibility helper (BE + FE); thin `POST /api/v1/incidents/{id}/fra-significant-change`; Incident Detail panel (Create / Open existing / Dismiss); route-chunk i18n; unit tests
- **Out of scope:** Bulk import, portal/mobile drill, OCR/PAS79, due-date pull-forward, incident↔requirement FK, notifications, ComplianceSchedule.tsx / import routes / import client methods
- **Feature flag / kill switch:** Existing `COMPLIANCE_SCHEDULE_ENABLED` + kill switch + `compliance_schedule:create` (+ incident read for case access)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `IncidentDetail.tsx` wires panel; new eligibility helper, panel, route-chunk i18n, FE unit tests
- **Backend (handlers/services):** New `incident_fra_review.py`; thin endpoint on `incidents.py`
- **APIs (endpoints changed/added):** `POST /api/v1/incidents/{incident_id}/fra-significant-change`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Inline request/response models on the incidents route (additive)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None new
- **Dependencies (added/removed/updated):** None
- **Tests:** `tests/unit/test_incident_fra_review.py`; `frontend/src/pages/__tests__/incidentFraSignificantChange.test.ts`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + opt-in UI (CS flag + closed + eligible + not dismissed)
- **Tolerant reader / strict writer applied?** Yes — panel soft-fails coverage lookup for “Open existing”; create path is activate-or-link idempotent on conflict
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit removes endpoint + panel

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Significant-change → FRA review | Catalogue copy states the rule; no operator prompt from Incident | Closed eligible incidents prompt Create FRA / Open existing / Dismiss |
| Site vs org-wide FRA honesty | Org-wide FRA could be mistaken for site cover | Site lookup requires `location_id`; org-wide rows excluded |
| Permission / flag boundary | N/A | CS enable + kill switch + `compliance_schedule:create` + incident read/tenant access |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Eligibility is true when `emergency_services` includes `fire`, OR (`property_damage`|`hazard` + `high`|`critical`), OR `is_sif`/`is_psif`; otherwise false (BE + FE helpers)
- [x] AC-02: `POST /api/v1/incidents/{id}/fra-significant-change` activates `fire_risk_assessment` for a premises/office `location_id`, or returns the existing site FRA; gated by CS enable + kill switch + `compliance_schedule:create` + incident access; site/workshop locations rejected
- [x] AC-03: Organisation-wide FRA (`location_id IS NULL`) does not count as site cover; concurrent activate conflict is treated as link-existing
- [x] AC-04: Incident Detail shows the panel when CS flag is on, status is closed, eligible, and not dismissed; Create / Open existing / Dismiss work; copy lives in route-chunk i18n (no shell `en.json`/`cy.json` growth)

## 5) Testing Evidence (link to runs)
- [x] Lint — `black` / `isort` on touched Python
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `pytest tests/unit/test_incident_fra_review.py`; FE vitest eligibility tests
- [ ] Integration tests — CI (additive route; no migration)
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator closes a fire-attended incident (CS on) → panel appears → Create FRA for a premises → navigates to the new obligation
- [x] CUJ-02: Site already has an active location-scoped FRA → Open existing (or POST returns `created=false`) without duplicating; org-wide-only FRA still allows Create for that site

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** CS enabled + create permission; close an eligible incident; create FRA for a premises; confirm coverage gap flips; second create/link opens existing detail
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same UI path on prod FQDN when CS is enabled; confirm `meta/version` `build_sha` matches tip before marking LIVE

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong site cover (org-wide counted), duplicate FRAs, or panel shown when CS is off
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
