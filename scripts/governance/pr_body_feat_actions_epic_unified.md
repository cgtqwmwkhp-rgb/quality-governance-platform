# Change Ledger (CL-ACTIONS-EPIC-001)

## 1) Summary
- **Feature / Change name:** Unified Actions epic — stable keys, display status, full CAPA feed, summary API, action profile
- **User goal (1-2 lines):** Give operators a trustworthy Actions hub: every row has a stable `action_key`, KPI-friendly `display_status`, tenant-wide summary counts, all CAPA-backed work items in the unified list, and a dedicated profile screen to view/update without `source_type` guesswork.
- **In scope:** Unified Actions API extensions; Actions / Dashboard / RTA detail consumers; OpenAPI + baseline; PostgreSQL partial unique index for audit-finding CAPAs; integration tests for new routes
- **Out of scope:** Fine-grained `require_permission` on Actions (needs role seeding); action-scoped activity stream; widening `evidence_assets.source_id`; IntegrityError retry in `_ensure_action_for_finding` (transaction/savepoint design)
- **Feature flag / kill switch:** N/A — additive API fields; clients must tolerate new JSON keys (already required fields in contract)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `App.tsx` (route `actions/item`), `ActionDetail.tsx` (new), `Actions.tsx`, `Dashboard.tsx`, `RTADetail.tsx`, `frontend/src/api/client.ts`
- **Backend (handlers/services):** `src/api/routes/actions.py`, `src/api/routes/_action_unified.py` (new helpers)
- **APIs (endpoints changed/added):** `GET /api/v1/actions/summary`; `GET /api/v1/actions/by-key`; `GET/PATCH /api/v1/actions/{id}` and `GET /api/v1/actions/` extended (response shape + CAPA source coverage); `POST /api/v1/actions/` response includes `action_key` / `display_status`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `ActionResponse` adds `action_key`, `display_status`; new `ActionsSummaryResponse`; `docs/contracts/openapi.json`, `openapi-baseline.json`
- **Database (migrations/entities/indexes):** `20260406_capa_audit_finding_unique.py` — partial unique index on `capa_actions (tenant_id, source_id)` WHERE `source_type = 'audit_finding'` (PostgreSQL only in upgrade)
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response fields; new optional query routes; list behaviour expands to include all tenant CAPA rows when no `source_type` filter
- **Tolerant reader / strict writer applied?** Yes — existing clients receive extra fields; `source_type` values `capa_incident` / `capa_complaint` distinguish CAPA rows from `incident_actions` / `complaint_actions`
- **Breaking changes:** Strict clients that reject unknown JSON keys may need updates (unusual). Status filtering: Actions list no longer passes `status` to the list API; filtering is client-side by `display_status` for the first 100 rows (documented limitation for very large tenants).
- **Migration plan:** Run Alembic upgrade on staging/production before relying on uniqueness; index creation fails if duplicate `(tenant_id, source_id)` audit-finding CAPAs already exist (resolve duplicates first).
- **Rollback strategy (DB):** Downgrade drops the partial unique index only (no column drops). Application rollback: revert deploy to prior SHA.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Every unified action response includes non-empty `action_key` and `display_status`
- [x] AC-02: `GET /actions/summary` returns `total` and `by_display_status` for the authenticated tenant
- [x] AC-03: `GET /actions/by-key?key=capa:{id}` returns the same logical row as list for that CAPA id (tenant-scoped)
- [x] AC-04: Unified list includes all `capa_actions` for the tenant when `source_type` is omitted; filters `ncr`, `capa_incident`, `capa_complaint`, etc. work via `capa_enum_from_api_filter`
- [x] AC-05: `GET/PATCH` accept CAPA API `source_type` values beyond assessment/induction/audit_finding (e.g. `ncr`) where rows exist
- [x] AC-06: Actions hub stat cards use summary API when available; row keys use `action_key`; link to `/actions/item?key=…`
- [x] AC-07: `make pr-ready` passes; integration tests extended for `/summary` and `/by-key` auth; frontend build passes

## 5) Testing Evidence (link to runs)
- [x] Lint / format — `black` on touched Python; `make pr-ready` gates
- [x] Typecheck — mypy as per repo `pr-ready`
- [x] Build — frontend `npm run build` OK
- [x] Unit tests — per `make pr-ready` / CI
- [x] Integration tests — `tests/integration/test_actions_api.py` (31 tests) including new route smoke
- [x] Contract tests (if applicable) — OpenAPI regenerated + baseline synced
- [ ] E2E Smoke (critical journeys) — staging after deploy (Actions list, profile, summary, audit deep link)

## 6) Critical Journeys Verified (CUJ)
- [ ] CUJ-01: Actions → open profile by key → PATCH status (staging UAT)
- [ ] CUJ-02: Actions summary totals align with expectations for a known tenant (staging UAT)
- [ ] CUJ-03: Audit-derived CAPA → Open audit run / import review from list and profile (staging UAT)
- [x] CUJ-04: Authenticated API contract — list/create/get/patch/summary/by-key paths registered (local integration tests)

## 7) Observability & Ops
- **Logs:** Existing logging on `actions` routes; failures in summary aggregates log warnings per source
- **Metrics:** Existing `track_metric` on create; `record_audit_event` on unified create/update (telemetry path per current `record_audit_event` implementation)
- **Alerts:** No change
- **Runbook updates:** Optional — document `/actions/summary` and `/actions/by-key` for support; note migration `20260406_capa_audit_finding_unique` for duplicate CAPA cleanup if index create fails

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Apply migrations; health/readiness/version; smoke Actions page, summary card numbers, open profile, PATCH status on audit CAPA and RTA action; verify no 404 on `/actions/summary` and `/actions/by-key`
- **Canary plan:** N/A (single SWA/API deploy as per existing process)
- **Prod post-deploy checks:** Health, readiness, version SHA match; quick Actions smoke; confirm Alembic revision applied

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Elevated 5xx on `/actions/*`, incorrect action counts blocking operations, or migration failure blocking deploy
- **Rollback steps:** Revert merge commit / redeploy previous image; if index was applied and must be removed, run Alembic downgrade for `d3e4f5a6b7c8` only in controlled window
- **Owner:** Platform / owning squad

## 10) Evidence Pack (links)
- CI run(s): Add GitHub Actions link after PR opens
- Staging deploy evidence: `docs/evidence/DEPLOY_EVIDENCE_staging_*.md` per runbook after staging
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts updated (OpenAPI + TS client)
- [ ] **Gate 2:** CI green (lint/type/build/tests) — confirm on PR
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + migration note documented above
