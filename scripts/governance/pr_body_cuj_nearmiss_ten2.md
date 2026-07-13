# Change Ledger (CL-CUJ-NEARMISS-TEN2)

## File allowlist (exclusive)
- `src/domain/models/near_miss.py`
- `alembic/versions/20260713_near_misses_tenant_not_null.py` (NEW)
- `docs/data/near-misses-tenant-backfill.md` (NEW)
- `docs/governance/tenant_id_nullability_inventory.md`
- `tests/unit/test_near_misses_tenant_isolation.py` (NEW)

**Overlap check:** Does not touch frontend Layout/Incident/Actions/Complaints/UVDB.

## 1) Summary
- **Feature / Change name:** Safety CUJ Near-miss TEN2 parity — fail-safe `tenant_id` NOT NULL + isolation suite
- **User goal (1-2 lines):** Close the Safety hub near-miss TEN2 gap vs RTAs (#681/#842): harden parent core `near_misses.tenant_id` without inventing `tenant_id=1`, and prove application-layer cross-tenant denial on FORCE-RLS near misses.
- **In scope:** Alembic fail-safe migration, ORM `nullable=False`, backfill runbook, inventory update, Preferred S9 isolation unit tests
- **Out of scope:** Frontend; Layout; Incident/Actions/Complaints/UVDB pages; `near_miss_running_sheet_entries`; inventing default tenants; token_version
- **Feature flag / kill switch:** N/A — tenancy hardening

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None (exercises existing `NearMissService` get/list/update/delete in tests)
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** `20260713_nm_tenant_nn` fail-safe backfill + conditional NOT NULL on `near_misses.tenant_id`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Documentation:** `docs/data/near-misses-tenant-backfill.md`; inventory Phase 2 row for `near_misses`

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Fail-safe — residual NULLs leave column nullable
- **Tolerant reader / strict writer applied?** Yes — creator backfill only when attributable; never invent `tenant_id=1`
- **Breaking changes:** None when fail-safe path taken (residual NULLs remain nullable)
- **Migration plan:** Backfill from `users` via `created_by_id`; align mismatches; enforce NOT NULL only when post-backfill NULL count is zero
- **Rollback strategy (DB):** Downgrade restores nullable; attribution data kept

## 4) Acceptance Criteria (AC)
- [x] AC-01: Migration `20260713_nm_tenant_nn` revises `20260712_capa_src_check` and never invents `tenant_id=1`
- [x] AC-02: ORM `NearMiss.tenant_id` is `nullable=False`
- [x] AC-03: `near_misses` confirmed in FORCE-RLS catalog (`RLS_TABLES`) with non-null ORM `tenant_id`
- [x] AC-04: Cross-tenant `get_near_miss` raises `LookupError` (existence-indistinguishable)
- [x] AC-05: `list_near_misses` SQL uses exact `tenant_id` equality (no NULL-inclusive OR)
- [x] AC-06: Cross-tenant `update_near_miss` / `delete_near_miss` raise `LookupError` with tenant-scoped SQL
- [x] AC-07: Backfill runbook and inventory Phase 2 row present for `near_misses`

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_near_misses_tenant_isolation.py` (6 passed locally)
- [ ] CI — linked after PR creation
- [x] Integration / E2E — N/A for this slice (unit isolation + fail-safe migration pattern)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Near-miss ownership inherits creator user tenant when attributable (fail-safe backfill)
- [x] CUJ-02: Tenant A cannot read Tenant B near miss by id (`LookupError`)
- [x] CUJ-03: Tenant A cannot update/delete Tenant B near miss by id (`LookupError`)

## 7) Observability & Ops
- **Logs:** Migration prints FAIL-SAFE warning when leaving nullable
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** `docs/data/near-misses-tenant-backfill.md`

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Alembic upgrade + readiness SQL counts from backfill doc
- **Canary plan:** N/A — schema fail-safe
- **Prod post-deploy checks:** Health/readyz + version SHA; optional NULL count query

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Unexpected migration failure or near-miss read/write regressions
- **Rollback steps:** Revert merge; alembic downgrade restores nullable if needed
- **Owner:** Platform / governance lane

## 10) Evidence Pack (links)
- CI run(s): Linked via PR checks
- Staging deploy evidence: After merge/staging
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — TEN2 parent-backfill pattern match (incidents/RTA parity)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Test plan
- [x] Near-miss isolation unit suite (6 passed locally)
- [ ] CI full suite green on this PR
- Do **not** merge until conveyor review; Safety CUJ Near-miss TEN2 parity only
