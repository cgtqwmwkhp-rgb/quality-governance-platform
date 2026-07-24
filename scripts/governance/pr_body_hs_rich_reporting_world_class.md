# Change Ledger (CL-HS-RICH-WORLD-CLASS)

## 1) Summary

- **Feature / Change name:** HS-RICH-REPORTING-WORLD-CLASS — umbrella integration of shared case UI, Wave 0 security hardening, Portal Near Miss fidelity, and Near Miss `contract_id` SSOT.
- **User goal (1–2 lines):** Bring Incident / Near Miss / Complaint reporting to RTA-grade parity — tenant-safe evidence & view permissions, faithful portal Near Miss capture (no silent data loss), a single source of truth for Near Miss customer/contract linkage, and a consistent Photos + Witnesses experience across every case type.
- **In scope:**
  - Merge of `lane/hs-rich-shared-case-ui` (reusable `CaseEvidencePanel` / `CaseWitnessesPanel`, generalized `EvidenceGallery` upload).
  - Wave 0 security: tenant-scoped `evidence_assets` reads and explicit view-permission checks on Incident/Near Miss/Complaint GET + list routes.
  - Portal Near Miss fidelity: `employee_portal.py` now persists the full `reporter_submission` payload, promotes known fields onto the record, never overwrites an explicit occurrence datetime with "now", and links uploaded `attachment_ids` to the created case via `evidence_assets`.
  - Near Miss `contract_id` SSOT: FK column + backfill migration, resolver parity with Incident/Complaint, and a Complaints-style contract search on the Near Miss create/edit form.
  - `witnesses_structured` (JSON) added to Incident, Near Miss, and Complaint — mirroring the existing RTA shape — plus wiring `CaseEvidencePanel` (Photos tab) and `CaseWitnessesPanel` (Witnesses tab) onto `IncidentDetail`, `NearMissDetail`, and `ComplaintDetail`.
  - This Change Ledger.
- **Out of scope (explicitly not touched):** Audit challenge flows, `AITemplateGenerator`, and any `ai_templates` routes (reserved for a parallel workstream).
- **Feature flag / kill switch:** N/A — all changes are additive (new optional columns, new tabs, new permission checks that mirror existing patterns already enforced elsewhere in the codebase). No existing behaviour changes unless a request was already out of tenant scope or lacked view permission (previously an unintentional gap).

## 2) Impact Map (what changed)

- **Frontend (routes/screens/components):**
  - `IncidentDetail.tsx`, `NearMissDetail.tsx`, `ComplaintDetail.tsx` — new "Photos" and "Witnesses" tabs wired to the shared `CaseEvidencePanel` / `CaseWitnessesPanel`; `witnesses_structured` saved via each record's existing `update` endpoint.
  - `incidentStandardsTab.ts`, `complaintStandardsTab.ts` — added `photos` / `witnesses` to the deep-linkable tab lists.
  - `NearMisses.tsx` (+ create/edit form) — Complaints-style contract/customer `FuzzySearchDropdown` replacing free-text `contract`, resolving to `contract_id`.
  - `EvidenceGallery.tsx`, `components/case/CaseEvidencePanel.tsx`, `components/case/CaseWitnessesPanel.tsx` — merged from `lane/hs-rich-shared-case-ui` (opt-in upload, structured witnesses editor).
  - `incidentsClient.ts`, `complaintsClient.ts`, `nearMissesClient.ts` — added `witnesses_structured` to record + update types.
  - `PortalNearMissForm.tsx` — minor fidelity alignment with backend promote/persist behaviour.
- **Backend (handlers/services):**
  - `src/api/routes/employee_portal.py` — Near Miss submission now stores full `reporter_submission`, promotes known fields, preserves reporter-supplied datetime, and links uploaded attachments via `evidence_assets`.
  - `src/api/routes/incidents.py`, `near_miss.py`, `complaints.py` — explicit view-permission enforcement on GET/list.
  - `src/api/routes/evidence_assets.py` — tenant-scoped list/read queries.
  - `src/domain/services/near_miss_service.py` — `contract_id` resolver parity with Incident/Complaint services.
  - `src/domain/services/investigation_service.py` — minor near-miss/contract-aware adjustment.
  - `src/domain/models/incident.py`, `near_miss.py`, `complaint.py` — new `witnesses_structured: Optional[dict]` JSON column (free-text `witnesses`/`witness_names` retained for read compatibility).
- **APIs (endpoints changed/added):** No new endpoints. `IncidentUpdate`/`IncidentResponse`, `NearMissUpdate`/`NearMissResponse`, `ComplaintUpdate`/`ComplaintResponse` gain an optional `witnesses_structured` field. Near Miss create/update now accepts `contract_id`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `witnesses_structured` added to the three case schemas above (mirrors `RTA.witnesses_structured`: `{ witnesses: [{ name, phone, email, statement, willing_to_provide_statement }] }`).
- **Database (migrations/entities/indexes):**
  - `20260816_nm_contract_fk` — adds `near_misses.contract_id` FK, backfills from legacy `contract` string.
  - `20260817_case_witnesses_structured` — adds `witnesses_structured` JSON column to `incidents`, `near_misses`, `complaints`.
  - Single linear head; no branching.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None introduced by this PR (package-lock churn is from merging `origin/main`'s unrelated esbuild bump, not this work).

## 3) Compatibility & Data Safety

- **Compatibility strategy:** All new columns are nullable/optional; existing free-text fields (`witnesses`, `witness_names`, legacy `contract` string) are retained for read compatibility — nothing is deleted or overwritten destructively. Portal Near Miss submissions that previously omitted `reporter_submission` still work; the fidelity fix only changes what gets *persisted going forward*.
- **Tolerant reader / strict writer applied?** Yes — Near Miss `contract_id` resolution falls back gracefully when no match is found (keeps the legacy string); `witnesses_structured` is optional on both read and write paths; view-permission checks return the existing 403/404 patterns already used elsewhere in the codebase (no new error shapes).
- **Breaking changes:** None. Tenant-scoping and view-permission enforcement are the only behaviour changes — a request that was previously allowed across tenants or without view permission will now be correctly denied; this closes a security gap rather than breaking an intended workflow.
- **Migration plan:** Two forward-only Alembic migrations (`20260816_nm_contract_fk`, `20260817_case_witnesses_structured|`), both additive/backfilling, each independently reversible via `downgrade()`.
- **Rollback strategy (DB):** `alembic downgrade -1` twice, or revert the PR; both migrations only add nullable columns/FKs, so downgrade is safe and lossless for any field not yet populated by the new code paths.

## 4) Acceptance Criteria (AC)

- [x] AC-01: `feat/hs-rich-reporting-world-class` is up to date with `origin/main` and includes `lane/hs-rich-shared-case-ui` merged cleanly.
- [x] AC-02: Incident/Near Miss/Complaint GET and list routes enforce tenant scope + view permission; `evidence_assets` reads are tenant-scoped. Covered by `tests/unit/test_case_view_permissions.py` (14 tests) and `tests/unit/test_evidence_tenant_isolation.py` (9 tests).
- [x] AC-03: Portal Near Miss submissions persist the full `reporter_submission`, promote known fields onto the record, never clobber an explicit occurrence datetime, and link uploaded attachments. Covered by `tests/integration/test_portal_near_miss_fidelity.py` (10 tests).
- [x] AC-04: Near Miss has a `contract_id` FK (backfilled from legacy `contract`), a resolver mirroring Incident/Complaint, and a Complaints-style contract search on the FE create/edit form. Covered by `frontend/src/pages/__tests__/NearMisses.contractSsot.test.tsx`.
- [x] AC-05: `CaseEvidencePanel` (Photos tab, upload-enabled) and `CaseWitnessesPanel` (Witnesses tab, structured add/edit/save) are wired onto `IncidentDetail`, `NearMissDetail`, and `ComplaintDetail`, each persisting `witnesses_structured` via the record's existing update endpoint and each evidence upload going through the tenant-scoped `evidence_assets` API.
- [x] AC-06: No edits to audit challenge flows, `AITemplateGenerator`, or `ai_templates` routes.
- [x] AC-07: Full regression sweep — backend unit + integration suites and full frontend Vitest suite — green aside from pre-existing, unrelated failures (documented below).

## 5) Testing Evidence (link to runs)

- [x] Backend — `pytest tests/unit tests/integration -q`: **3780 passed, 18 skipped, 5 failed** (all 5 pre-existing/unrelated — reproduce identically with none of this PR's files in scope; see "Known gaps" below).
- [x] Backend (focused) — `pytest tests/unit/test_case_view_permissions.py tests/unit/test_evidence_tenant_isolation.py tests/integration/test_portal_near_miss_fidelity.py -q`: **33/33 passed**.
- [x] Backend (module regression) — `pytest tests/unit -k "near_miss or incident or complaint or evidence" -q`: **364 passed, 1 skipped**.
- [x] Frontend — `npx vitest run` (full suite): **262 files / 1430 tests passed**.
- [x] Frontend (focused) — `npx vitest run ComplaintDetail.test.tsx NearMissDetail.test.tsx IncidentDetail.test.tsx`: **25/25 passed**, including new Photos/Witnesses coverage.
- [x] Alembic — `alembic heads`: single linear head (`20260817_case_witnesses_structured`), no branch conflicts.

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: A user from tenant A cannot list or read tenant B's incidents/near-misses/complaints or their evidence assets.
- [x] CUJ-02: A user without case view permission is denied on GET/list even within their own tenant.
- [x] CUJ-03: An employee submits a Near Miss via the portal with a photo attachment and a past occurrence date — the record retains the reporter's original datetime, the full submission payload is preserved for audit, and the photo is visible on the case's Photos tab afterwards.
- [x] CUJ-04: Creating/editing a Near Miss via the FE form resolves the selected customer/contract to `contract_id` exactly like Complaints, with the legacy string kept for display.
- [x] CUJ-05: On Incident, Near Miss, and Complaint detail pages, a user can open the Witnesses tab, add/edit/save structured witnesses, and open the Photos tab to upload/view/delete evidence — all three case types behave consistently.

## 7) Observability & Ops

- **Logs:** No new log lines; existing structured request/audit logging on the touched routes is unchanged.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local → Staging → Canary → Prod)

- **Staging verification:** Run the two new Alembic migrations against a staging snapshot; spot-check that pre-existing Near Miss `contract` strings backfill to the correct `contract_id`, and that a portal-submitted Near Miss round-trips through to the detail page's Photos/Witnesses tabs.
- **Canary plan:** Standard rollout — additive schema + permission tightening; monitor 403/404 rates on case GET/list routes post-deploy for any unexpected tenant/permission regressions.
- **Prod post-deploy checks:** Confirm `alembic heads` shows a single head; spot-check one Incident, Near Miss, and Complaint in prod for Photos/Witnesses tab rendering.

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Unexpected 403/404s on previously-working case GET/list requests, or portal Near Miss submissions failing/losing data.
- **Rollback steps:** Revert this PR; `alembic downgrade` the two migrations (both additive/nullable, safe to reverse) if already applied.
- **Owner:** H&S Rich Reporting track.

## 10) Evidence Pack (links)

- CI run(s): linked after PR creation / on the PR checks tab.
- Staging deploy evidence: pending first staging deploy of this branch.
- Canary evidence: N/A — pending rollout.

### Known gaps (pre-existing, unrelated — not introduced by this PR)

- `tests/integration/test_audits_api.py::test_list_audit_templates` / `test_list_audit_runs` / `test_filter_audit_templates_by_category` and `tests/integration/test_external_audit_imports_api.py::test_external_audit_import_job_creation_queue_and_drafts` fail with `sqlite3.OperationalError: no such table: uvdb_iso_cross_mapping` — a pre-existing UVDB test-schema gap, reproduced identically with none of this PR's files present.
- `tests/integration/test_health.py::test_readyz_returns_503_when_redis_required_and_missing` fails only in full-suite ordering (passes in isolation) — pre-existing test-isolation flakiness unrelated to this PR.
- Portal Near Miss fidelity and Near Miss `contract_id` SSOT are net-new persistence behaviours; historical Near Miss records created before this change will show `witnesses_structured: null` and rely on the backfilled `contract_id` — both expected and handled by the tolerant-reader UI (free-text/legacy fallback still renders).

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [x] **Gate 1:** No unreviewed backend/API surface added beyond the documented optional fields and permission checks; no touches to audit challenge / `AITemplateGenerator` / `ai_templates`.
- [ ] **Gate 2:** CI green (lint/type/build/tests) — pending remote CI run; local backend/frontend suites green aside from documented pre-existing failures.
- [ ] **Gate 3:** Staging verification — pending first deploy of this branch.
- [x] **Gate 4:** Rollback plan verified (additive/nullable migrations, revert-safe).
- [ ] **Gate 5:** Evidence pack linked — pending CI run link.
