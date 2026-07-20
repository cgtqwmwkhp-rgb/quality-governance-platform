# Change Ledger (CL-ASSURANCE-CERT-SHELF-WAVE-A)

## 1) Summary
- **Feature / Change name:** Assurance Certificate Shelf — Wave A foundation.
- **User goal:** See expiry-driven readiness across owned Library masters and external assurance systems of record in one Assurance surface, without duplicating Achilles/Planet Mark as QGP SoR.
- **In scope:** Aggregated shelf API, Assurance nav page, Monitoring cross-link, readiness status (valid / due soon / expired), Library and external hyperlinks where already supported.
- **Out of scope:** UVDB v11.8 protocol bank ingest, Training Matrix files, certificate CRUD POST/PATCH, Celery expiry notifications, `library_document_id` FK on register rows.
- **Feature flag / kill switch:** None. Revert PR to remove shelf route and page.

## 2) Impact Map
| ID | Surface | Before | After |
|---|---|---|---|
| ASSURE-CERT-01 | Assurance nav | Certs scattered across Monitoring tab, Planet Mark, UVDB only. | `/assurance/certificates` lists unified shelf with expiry readiness and deep links. |
| ASSURE-CERT-02 | Monitoring → Certificates tab | Partial register list; Add Certificate button unwired. | Cross-link to Assurance certificate shelf; register rows still visible locally. |
| ASSURE-CERT-03 | API | Read-only register list + summary only. | `GET /compliance-automation/certificates/shelf` aggregates register, Planet Mark, UVDB, Library expiries. |

- **Backend:** `assurance_cert_shelf_service.py`, `compliance_automation.py` route.
- **Frontend:** `AssuranceCertShelf.tsx`, helpers, nav/route/registry, Monitoring handoff link, API client.
- **Database/migrations:** None.

## 3) Compatibility & Data Safety
- Additive read-only API and UI; no schema or write-path changes.
- External SoR rows (Planet Mark, UVDB) remain authoritative; QGP hyperlinks out rather than re-hosting.
- Library documents with `expiry_date` appear as owned masters; tenant-scoped query only.

## 4) Acceptance Criteria
- [x] AC-01: Assurance nav exposes Certificate shelf at `/assurance/certificates`.
- [x] AC-02: Shelf API returns aggregated items with `readiness_status` valid | due_soon | expired | unknown.
- [x] AC-03: Shelf includes register, Planet Mark (expiry set), UVDB (expiry/next audit due), and Library documents with expiry.
- [x] AC-04: Rows link to module detail paths and Library/external URLs where present.
- [x] AC-05: Monitoring Certificates tab links to the Assurance shelf.
- [x] AC-06: Unit, Vitest, and e2e contract tests cover shelf readiness and API shape.

## 5) Testing Evidence
- [x] `pytest tests/unit/test_assurance_cert_shelf_service.py` — readiness + summary logic.
- [x] `npx vitest run frontend/src/pages/__tests__/AssuranceCertShelf.test.tsx` — page render + empty state.
- [x] `pytest tests/e2e/test_compliance_automation.py::TestCertificateTracking::test_get_assurance_cert_shelf` — API contract.
- [ ] Hosted CI — pending PR checks.

## 6) Critical Journeys
- [x] CUJ-01: Assurance → Certificate shelf loads summary cards and filtered list.
- [x] CUJ-02: Planet Mark / UVDB rows show External SoR badge and Open module link.
- [x] CUJ-03: Library master with expiry shows Library link to `/documents/{id}`.
- [x] CUJ-04: Monitoring → Certificates → Open certificate shelf navigates to unified view.

## 7) Observability & Ops
- No new telemetry; standard API access logs apply to `/certificates/shelf`.
- Support can verify empty shelf vs upstream module data by checking scheme filters and source modules.

## 8) Release Plan
1. Merge after required CI checks pass.
2. Deploy backend + frontend through standard conveyor.
3. Staging smoke: open `/assurance/certificates`, confirm summary counts and scheme/status filters; confirm Monitoring handoff link.

## 9) Rollback Plan
- **Trigger:** Shelf aggregation errors or incorrect readiness classification in production.
- **Steps:** Revert merge commit; redeploy prior artifacts.
- **Owner:** Platform release operator.

## 10) Evidence Pack
- Service: `src/domain/services/assurance_cert_shelf_service.py`
- UI: `frontend/src/pages/AssuranceCertShelf.tsx`
- Tests: `tests/unit/test_assurance_cert_shelf_service.py`, `frontend/src/pages/__tests__/AssuranceCertShelf.test.tsx`, `tests/e2e/test_compliance_automation.py`
- Ledger: `scripts/governance/pr_body_assurance_cert_shelf_wave_a.md`

---

## Gate Checklist
- [x] Gate 0: Scope, ACs, and Change Ledger complete; Training Matrix and UVDB v11.8 ingest excluded.
- [x] Gate 1: Additive read API + Assurance UI; no migration.
- [x] Gate 2: Focused unit/Vitest/e2e tests added.
- [ ] Gate 3: Hosted CI and staging smoke pending.
- [x] Gate 4: No canary required — read-only aggregation.
- [x] Gate 5: Rollback plan documented.
