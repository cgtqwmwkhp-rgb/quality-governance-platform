# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Compliance Schedule — Wave 0 (foundations) + Wave 1 (vertical slice)
- **User goal (1–2 lines):** Give a tenant one register of its recurring statutory obligations (fire risk assessment, gas safety, PAT, LOLER…) with a computed next-due date, so a lapse is visible before it happens instead of being discovered at audit.
- **In scope:** Obligation catalogue (25 UK org/location obligations), three tables, next-due policy functions, `/api/v1/compliance-schedule` API, register + detail + completion sheet UI, flag-gated nav, i18n, ADR-0020, rollout runbook.
- **Out of scope (Wave 2+):** Calendar feed, Celery due sweep, CAPA-from-record, library filing bridge, Export Center, OCR.
- **Feature flag / kill switch:** `COMPLIANCE_SCHEDULE_ENABLED`, default **off**. Kill switch closes the API within its TTL; nav is gated by the same flag.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** 2 new P2 routes — compliance schedule register and requirement detail (with completion sheet). Nav entry flag-gated. `PAGE_REGISTRY.yml` 115→117 total, 42→44 P2.
- **Backend (handlers/services):** `compliance_schedule_service` (requirement/record lifecycle, next-due computation), `compliance_schedule_policy` (pure functions: `compute_next_due`, anchor semantics), catalogue loader.
- **APIs (endpoints changed/added):** New router `/api/v1/compliance-schedule` — requirements list/create/update, records create, evidence attach. Permission tokens `compliance_schedule:read|create|update`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `src/api/schemas/compliance_schedule.py`. Two documented response asymmetries (`RecordResponse`, `RequirementResponse`) and two documented unreadable request fields (`evidence_asset_ids` on the evidence and record POSTs) registered in `tests/contract/_write_contract_baseline.py` — all server-owned or derived fields, none of them user-authored state that is silently dropped.
- **Database (migrations/entities/indexes):** `20260913_cs_wave0` ← `20260912_clear_junctions`. Single head, no branch. Creates `compliance_requirement_templates`, `compliance_requirements`, `compliance_records`; hardens the two tenant-owned tables under the `tenant_isolation` policy (ENABLE + FORCE, USING + WITH CHECK) and verifies its own outcome against `pg_policy`. `RLS_TABLES` 23→25.
- **Workflows/jobs/queues (if any):** None in this PR. The due sweep is Wave 2.
- **Config/env/flags:** `COMPLIANCE_SCHEDULE_ENABLED` (default off).
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive + Flagged. Three new tables, no existing table altered, no existing endpoint changed. Every new surface is behind a flag that defaults off.
- **Tolerant reader / strict writer applied?** Yes. Writes validate against the schema and reject unknown anchors in the service's own terms; reads tolerate the nullable server-owned columns (`filing_status`, `outcome`, `external_id`…) being absent on rows created before those fields were populated.
- **Breaking changes:** None.
- **Migration plan:** `alembic upgrade head` applies `20260913_cs_wave0` forward only. Rehearsed on a clean PostgreSQL **16.14** instance (matching production) — see §5. Table creation and RLS hardening are in one revision so a table cannot exist unprotected between two migrations.
- **Rollback strategy (DB):** Backward-compatible. The three tables are new and unreferenced by any pre-existing table, so leaving them in place after a code rollback is inert — nothing reads them when the flag is off. `downgrade()` drops the policies and the tables if a true schema rollback is wanted.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** A tenant can create a recurring requirement from the catalogue, complete it, and see the next due date recomputed from the correct anchor (completion vs schedule) without ever showing a status of "Expired".
- [x] **AC-02:** With `COMPLIANCE_SCHEDULE_ENABLED=false` the API returns 404 and the nav entry is absent; with the kill switch thrown the API closes within the TTL. Verified by integration tests.
- [x] **AC-03:** `compliance_requirements` and `compliance_records` are invisible across tenants under the least-privilege application role, and a write naming another tenant is rejected — not merely filtered on read. Verified behaviourally against real PostgreSQL, see §5.
- [x] **AC-04:** `compliance_requirement_templates` is a shared catalogue with `tenant_id IS NULL` by design, registered as a D11 catalog exception with a named owner rather than being silently grandfathered.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — `black --check` 1258 files unchanged; `isort --check-only` clean; `flake8` 0.
- [x] **Typecheck** — `mypy` Success, no issues in 536 source files.
- [x] **Build** — Storybook Build and Build Check green on CI.
- [x] **Unit tests** — 5571 passed, 0 failed, 72 skipped, 58 xfailed (local, full `tests/unit`).
- [x] **Integration tests** — `tests/integration/test_run026_rls_least_privilege_postgres.py` 12/12 passed, **0 skipped**, against PostgreSQL 16.14.
- [x] **Contract tests** — full `tests/contract` green in the same run as the unit suite.
- [x] **Migration drift** — `alembic upgrade head` then `alembic check`: *No new upgrade operations detected*, on a fresh PG 16.14. Drift ratchet exits 0: 1056 suppressed operations across 209 tables, all within the committed baseline, 0 `AddColumnOp`.
- [x] **Schema constraint (D11)** — 172 mapped models checked, 0 critical, 0 advisory, no new owned nullable `tenant_id`.
- [ ] **E2E Smoke (critical journeys)** — runs on CI for this PR; the flag is off in every deployed environment, so the new routes are not in the smoke path yet.

**Direct RLS proof (not via the test suite).** Under role `qgp_app` on PG 16.14, with one requirement seeded per tenant:

| `app.current_tenant_id` | Rows visible | Expected |
| --- | --- | --- |
| `901` | only tenant 901's row | correct |
| `902` | only tenant 902's row | correct |
| `''` (empty) | 0 | fail-closed |

An `INSERT` of a `tenant_id = 902` row while the GUC was `901` was rejected: *new row violates row-level security policy*. `pg_class` confirms `relrowsecurity` **and** `relforcerowsecurity` are both true on both tables, so the table owner is not exempt.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Register → add obligation from catalogue → record a completion with a historical date → next due recomputed from the completion anchor, status chip never reads "Expired".
- [x] **CUJ-02:** Tenant isolation — a user in tenant A cannot read, update or create a compliance requirement or record belonging to tenant B, enforced in the database rather than in the query layer.
- [x] **CUJ-03:** Flag off → route absent from nav, API 404; no partially-wired UI reachable by typing the URL.

## 7) Observability & Ops
- **Logs:** Service-layer logs on requirement creation and record completion carry `tenant_id` and reference number. The migration logs the policy count it verified against `pg_policy`, so a partial application is visible in the deploy log rather than inferred later.
- **Metrics:** No new metric in this PR. The due-sweep counters arrive with the Wave 2 job that has something to count.
- **Alerts:** None added. Deliberate — alerting on a register nobody is using yet would only produce noise; the alert lands with the sweep.
- **Runbook updates:** Compliance Schedule rollout runbook (added in Wave 0) and ADR-0020 for the anchor/next-due decision.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Deploy with the flag **off** and confirm no behaviour change. Then migrate, set `COMPLIANCE_SCHEDULE_ENABLED=true`, grant `compliance_schedule:read|create|update`, and enter a real Wickford FRA and fire drill with historical dates. Confirm next-due arithmetic against the runbook's worked examples and that no chip reads "Expired".
- **Canary plan:** Not applicable in the traffic-splitting sense — exposure is controlled by the flag, not by traffic share. The canary is staging with the flag on for one tenant. Rollback trigger is any incorrect next-due date or any cross-tenant read.
- **Prod post-deploy checks:** Migration reaches `20260913_cs_wave0`; `/health` green; flag confirmed **off**; the two new routes 404. No production enablement in this PR.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any cross-tenant visibility of a compliance requirement or record; any incorrect next-due computation; migration failure on apply.
- **Rollback steps:** (1) Set `COMPLIANCE_SCHEDULE_ENABLED=false` — this alone removes the entire surface, since the API 404s and the nav entry disappears, and it needs no deploy. (2) If a code rollback is needed, redeploy the previous image; the three new tables are unreferenced by anything older, so they are inert. (3) Only if a true schema rollback is required, `alembic downgrade 20260912_clear_junctions`, which drops the policies and the three tables.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks — all 8 previously failing checks addressed; see §5 for what was verified locally and how.
- Staging deploy evidence: pending — to be linked after the staging enablement described in §8.
- Canary evidence (if applicable): n/a, flag-gated rather than traffic-split.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (contract asymmetries documented with justification; ADR-0020 records the anchor decision)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — not started; this PR merges with the flag off
- [ ] **Gate 4:** Canary healthy (if used) — n/a, flag-gated
- [ ] **Gate 5:** Production verification plan + monitoring ready — plan in §8; production enablement is a separate, explicit decision
