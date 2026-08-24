# Change Ledger (CL-EXPORT-W19-COMPLIANCE-SCHEDULE)

## 1) Summary
- **Feature / Change name:** Export Center W19 — compliance_schedule sync CSV module
- **User goal (1–2 lines):** Let admins download the compliance requirements register from Export Center as CSV (reference, title, next due, owner, active, statutory), matching other registers.
- **In scope:** `SUPPORTED_MODULES` / `_MODULE_SPECS` + row mapper; API `ExportModuleId` Literal; frontend `ExportModuleId`; unit tests
- **Out of scope:** Async export jobs, calendar feed, OCR, CAPA-from-record, flag changes
- **Feature flag / kill switch:** None new — export is additive catalog entry; schedule data still gated at its own API/nav by `COMPLIANCE_SCHEDULE_ENABLED`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `ExportCenter.tsx` — `ExportModuleId` union adds `compliance_schedule`
- **Backend (handlers/services):** `export_center_service.py` — module catalog + sync CSV for `ComplianceRequirement`
- **APIs (endpoints changed/added):** Existing `GET /api/v1/exports/catalog` and `POST /api/v1/exports` accept module `compliance_schedule` via schema Literal
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `src/api/schemas/exports.py` `ExportModuleId`
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Tests:** `tests/unit/test_export_center_service.py` catalog count + CSV/key-field proofs

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive module id; existing modules unchanged
- **Tolerant reader / strict writer applied?** Yes — unknown modules still rejected; new id explicitly listed
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert commit removes the module from catalog

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Export Center module coverage | Seven registers; compliance schedule not exportable | Eight modules including `compliance_schedule` |
| Key obligation fields in CSV | N/A | `reference_number`, `title`, `next_due_date`, `owner` (owner_id), `is_active`, `statutory` |
| Fail-closed unknown module | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `compliance_schedule` is in `SUPPORTED_MODULES` and `_MODULE_SPECS`
- [x] AC-02: Sync CSV header includes reference, title, next_due_date, owner, is_active, statutory
- [x] AC-03: API schema + frontend `ExportModuleId` accept `compliance_schedule`
- [x] AC-04: Unit tests cover catalog count and compliance_schedule CSV/row mapper

## 5) Testing Evidence (link to runs)
- [ ] Lint
- [ ] Typecheck
- [ ] Build
- [x] Unit tests — `python3.11 -m pytest tests/unit/test_export_center_service.py tests/unit/test_create_export_request_extra_forbid.py` (9 passed locally)
- [ ] Integration tests
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Catalog lists `compliance_schedule` with live count
- [x] CUJ-02: Sync CSV for `compliance_schedule` emits key fields for a requirement row

## 7) Observability & Ops
- **Logs:** N/A — existing export path
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** After merge, Export Center catalog shows Compliance Schedule; sync CSV downloads with expected headers when requirements exist
- **Canary plan:** N/A
- **Prod post-deploy checks:** Catalog includes module; sample export when flag/permissions allow reading requirements

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Corrupt CSV, wrong tenant bleed, or catalog regression
- **Rollback steps:** Revert this squash commit on `main`; redeploy prior image
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
