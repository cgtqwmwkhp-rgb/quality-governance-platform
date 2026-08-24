# Change Ledger (CL-CS-W3-PR3-BULK-IMPORT)

## 1) Summary
- **Feature / Change name:** Wave 3 PR3 — Compliance Schedule bulk obligation CSV import
- **User goal (1–2 lines):** Managers fill site FRA/drill (and other catalogue) gaps by uploading a CSV that activates catalogue templates per location, with dry-run before commit.
- **In scope:** `POST /import/dry-run` + `/import/commit`; import service calling `activate_catalogue_template`; schemas; Compliance Schedule import dialog; route-chunk en/cy copy; unit + client path tests
- **Out of scope:** XLSX, OCR/PAS79, portal drill, freeform requirement create, upsert, auto-fill-from-gaps, org-wide rows, shell i18n growth
- **Feature flag / kill switch:** Existing `COMPLIANCE_SCHEDULE_ENABLED` + kill switch; permission `compliance_schedule:create`

## 2) Impact Map (what changed)
- **Frontend:** Import button + dry-run/commit dialog on `ComplianceSchedule.tsx`; client methods; path test; `complianceScheduleImportI18n.ts`
- **Backend:** `ComplianceScheduleImportService`; routes on `_enabled_router`
- **APIs:** `POST /api/v1/compliance-schedule/import/dry-run`, `POST /api/v1/compliance-schedule/import/commit`
- **Schemas:** Import report / commit response models
- **Database:** None
- **Config/env/flags:** None new
- **Tests:** `tests/unit/test_compliance_schedule_import_service.py`; client paths

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints + UI
- **Tolerant reader / strict writer applied?** Yes — fail-closed commit if any row error
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Bulk site FRA/drill activation | Manual one-by-one activate | CSV dry-run → commit via catalogue activate |
| Org-wide vs site honesty | Org-wide does not cover sites (#1612) | Import rejects rows without location |
| Duplicate activate | Already Conflict on activate | Row `DUPLICATE_ENTITY` blocks commit |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Dry-run and commit endpoints gated by CS enable + kill switch + `compliance_schedule:create`
- [x] AC-02: Valid rows call `activate_catalogue_template` with location required (org-wide rejected)
- [x] AC-03: Unknown location / inactive template / duplicate entity / in-file duplicate fail closed with row codes; commit with errors returns ValidationError
- [x] AC-04: Compliance Schedule page has Import CSV → validate → commit (commit disabled unless dry-run `ok`)
- [x] AC-05: Unit tests + client path tests cover new surface; import copy stays out of shell en/cy JSON

## 5) Testing Evidence (link to runs)
- [x] Lint — black/isort on touched Python
- [ ] Typecheck — CI
- [ ] Build — CI
- [x] Unit tests — `pytest tests/unit/test_compliance_schedule_import_service.py` (7 passed locally)
- [x] Frontend unit — paths + emptyVsError vitest locally
- [ ] Integration / E2E — CI

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: CSV with `fire_risk_assessment` + `location_id` dry-runs `ok` then commits a site-scoped obligation
- [x] CUJ-02: Missing location / unknown template / existing active obligation blocks commit with row errors

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Upload a one-row FRA CSV for a premises/office from coverage panel; dry-run then commit; coverage flips; second commit → DUPLICATE_ENTITY
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same on prod FQDN; tip `build_sha` catch before LIVE

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong-tenant activation, org-wide accepted, or silent partial commit
- **Rollback steps:** Revert squash on main; redeploy prior image
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
