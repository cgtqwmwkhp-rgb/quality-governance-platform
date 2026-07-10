# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WCS C-01 Phase 1 — tenant_id nullability inventory + CI lint (no mass NOT NULL)
- **User goal (1–2 lines):** Stop the bleed of new owned entities with nullable `tenant_id`, and publish a full ORM inventory with Phase 2 backfill candidates (incidents/audits/risks), without migrating ~170 tables.
- **In scope:** Inventory script + Markdown report; grandfather baseline JSON; catalog/global exception list; CI lint wired into `schema-constraint-lint`; unit tests
- **Out of scope:** Alembic backfill / `NOT NULL` on existing tables; changing `apply_tenant_filter` (C-02); silent `tenant_id=1` defaults (C-03)
- **Feature flag / kill switch:** N/A — CI policy only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No migrations. Policy artifacts under `docs/governance/`
- **Workflows/jobs/queues (if any):** `.github/workflows/ci.yml` — new step on `schema-constraint-lint`
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — existing nullable columns grandfathered; only **new** owned tables are blocked
- **Breaking changes:** None for runtime. CI fails if a PR adds a new owned model with nullable `tenant_id` without baseline/catalog update
- **Migration plan:** None in Phase 1. Phase 2 requires env NULL counts = 0 before `NOT NULL` (see inventory Phase 2 candidates)
- **Rollback strategy (DB):** No DB change — revert commit / remove CI step

## 4) Acceptance Criteria (AC)
- [x] AC-01: Inventory lists all mapped models with nullable vs required `tenant_id` (`docs/governance/tenant_id_nullability_inventory.md`)
- [x] AC-02: Highest-risk Phase 2 candidates documented (incidents, audit_runs/findings, risks/risks_v2, complaints) — NOT NULL deferred pending data safety
- [x] AC-03: CI lint `scripts/validate_tenant_id_not_null.py` fails on **new** owned nullable `tenant_id` (grandfather + catalog exceptions)
- [x] AC-04: Catalog/global exceptions explicitly documented (`docs/governance/tenant_id_catalog_exceptions.json`)
- [x] AC-05: Unit tests cover pass path + synthetic new-owned failure

## 5) Testing Evidence (link to runs)
- [x] Lint — local scripts green
- [x] Typecheck — N/A for scripts/docs
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_tenant_id_not_null_lint.py` (3 passed)
- [ ] Integration tests — N/A (no runtime/DB change)
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — N/A for policy-only change; CI run linked after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Schema constraint CI job runs tenant_id NOT NULL Phase 1 lint without false positives on current ORM
- [x] CUJ-02: Adding a fake owned nullable `tenant_id` model is rejected by the lint (unit test)

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** `docs/governance/tenant_id_nullability_inventory.md` (Phase 2 readiness notes)

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** N/A — docs + CI only; no deploy-time schema change
- **Canary plan:** N/A
- **Prod post-deploy checks:** N/A

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CI lint false-positive blocking legitimate work
- **Rollback steps:** Revert this PR (or temporarily remove the CI step / add justified baseline entry with review)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — policy/docs only
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — N/A policy-only
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — N/A runtime
