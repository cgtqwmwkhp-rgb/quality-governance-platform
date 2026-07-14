# Change Ledger (CL-AM-VAN)

## File allowlist (exclusive)
- `frontend/src/pages/VehicleChecklists.tsx`
- `frontend/src/pages/__tests__/VehicleChecklists.test.tsx`
- `src/domain/services/allocation_gate.py`
- `src/api/routes/vehicles.py` (thin `/{reg}/safety-assets` join only)
- `tests/unit/test_am_van_allocation_gate.py`
- `scripts/governance/pr_body_am_van.md`

**Depends on:** AM-MODEL PR **#976** (`path11/am-model`).

**Zero overlap** with Workforce FE/client, Layout, SafetyAssets pages (link-only to `/safety-assets/:id`), AM-THREAD case files, PAMS sync core.

## 1) Summary
- **Feature / Change name:** AM-VAN — Van kit compliance panel + allocation_gate Asset consult
- **User goal (1–2 lines):** Operators see vehicle-assigned safety kit assets (extinguisher / first-aid / tools) with expiry status on Van Checklists, and allocation/dispatch is blocked when linked or child Assets are VOR, quarantined, or overdue.
- **In scope:** `GET /vehicles/{reg}/safety-assets` thin join; dual-read expiry (prefer child Asset.expiry_date, keep registry columns); VehicleChecklists kit panel + `/safety-assets/:id` links; allocation_gate Asset status/expiry consult; unit tests.
- **Out of scope:** Safety Asset Register pages (AM-FE); incident/near-miss FKs (AM-THREAD); PAMS sync rewrites; workforce FE.
- **Feature flag / kill switch:** None (additive API + FE panel + gate rules).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `VehicleChecklists.tsx` kit compliance panel when Van filter set.
- **Backend (handlers/services):** `allocation_gate.py` consults linked `vehicle_registry.asset_id` + child assets by `vehicle_reg`.
- **APIs (endpoints changed/added):** `GET /api/v1/vehicles/{reg}/safety-assets`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Inline response models on vehicles route.
- **Database (migrations/entities/indexes):** None (uses AM-MODEL spine).
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. Legacy `vehicle_registry.fire_extinguisher_expiry` / `tooling_calibration_expiry` retained as dual-read fallbacks.
- **Tolerant reader / strict writer applied?** Yes — panel shows honest empty/error; gate only consults Assets when present.
- **Breaking changes:** None (gate may newly block vehicles that previously cleared when Asset status/expiry is bad — intentional R4 fix).
- **Migration plan:** None (depends on #976 schema).
- **Rollback strategy (DB):** Revert PR; no DB change in this lane.

## 4) Acceptance Criteria (AC)
- [x] AC-01: API lists child safety/kit assets by `vehicle_reg` with dual-read expiry fields.
- [x] AC-02: Van Checklists compliance panel shows kit assets + expiry status + link to `/safety-assets/:id`.
- [x] AC-03: Dual-read prefers child-asset expiry when present; registry columns remain.
- [x] AC-04: `allocation_gate` blocks/warns on linked or child Asset VOR / quarantined / overdue.
- [x] AC-05: Unit tests cover gate + panel render (mocked).

## 5) Testing Evidence (link to runs)
- [x] Lint — CI
- [x] Typecheck — CI
- [x] Build — CI
- [x] Unit tests — `tests/unit/test_am_van_allocation_gate.py`, `VehicleChecklists.test.tsx`
- [ ] Integration tests — CI
- [ ] Contract tests (if applicable) — CI OpenAPI (additive path)
- [ ] E2E Smoke — N/A (panel + gate unit coverage)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Filter Van Checklists by reg → kit panel loads assets / dual-read expiry / deep link
- [x] CUJ-02: Allocate vehicle with quarantined/VOR/overdue kit asset → gate blocks
- [x] CUJ-03: No child asset expiry → registry fire extinguisher / tooling columns still enforced

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** After #976 merge; hit `GET /vehicles/{reg}/safety-assets`; filter Van Checklists; dry-run allocate with quarantined kit asset
- **Canary plan:** N/A
- **Prod post-deploy checks:** meta/version SHA; sample van with kit assets shows panel

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Gate false-positives blocking active fleet at scale, or Van Checklists regression
- **Rollback steps:** Revert this PR (no migration)
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: After merge + staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved (additive join + dual-read)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
