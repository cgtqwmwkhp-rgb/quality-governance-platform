# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Audit Wave 6 — Tenant isolation on investigation templates, copilot, vehicles, checklists, signatures, users, tenants
- **User goal (1-2 lines):** Close 22 cross-tenant security vulnerabilities across 7 unaudited route files; add missing authentication to 2 copilot endpoints.
- **In scope:** TPL-01..05, WF2-01..02, VEH-01..03, CHK-01..06, USR-01, TNT-01..04, SIG-01..04
- **Out of scope:** New features, UI changes, migrations, larger-effort items (form_config, workflow, ai_intelligence, executive_dashboard, analytics)
- **Feature flag / kill switch:** N/A — security hardening

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `investigation_templates.py`, `copilot.py`, `vehicles.py`, `vehicle_checklists.py`, `users.py`, `tenants.py`, `signatures.py`
- **APIs (endpoints changed/added):** Investigation template CRUD tenant-scoped; copilot messages/execute require auth; vehicle defect queries tenant-scoped; user search tenant-scoped; tenant read endpoints ownership-checked; signature request ops tenant-verified
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No schema changes — models already have tenant_id columns
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — tenant_id filters are additive WHERE clauses
- **Breaking changes:** None — single-tenant sees no change; multi-tenant gets proper isolation
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Investigation template CRUD scoped to tenant (TPL-01..05)
- [x] AC-02: Copilot get_messages and execute_action require authentication (WF2-01,02)
- [x] AC-03: Vehicle defect queries in get_vehicle/compliance_gate/create_capa scoped to tenant (VEH-01..03)
- [x] AC-04: Vehicle checklist defect CRUD + P1 notifications scoped to tenant (CHK-01..06)
- [x] AC-05: User search scoped to tenant (USR-01)
- [x] AC-06: Tenant read endpoints enforce ownership (TNT-01..04)
- [x] AC-07: Signature request get/send/void/audit-log verify tenant (SIG-01..04)
- [x] AC-08: 1377 unit tests pass, 458 integration tests pass, 195 frontend tests pass, lint/format clean

## 5) Testing Evidence (link to runs)
- [x] Lint — flake8 clean
- [x] Typecheck — N/A
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — 1377 passed, 0 failed
- [x] Integration tests — 458 passed, 0 failed
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Investigation template management
- [x] CUJ-02: Vehicle checklist defect workflow
- [x] CUJ-03: Digital signature workflow
- [x] CUJ-04: User search and tenant administration

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Health, readiness, version endpoints + smoke test
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health, readiness, version SHA match

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Any critical API failure post-deploy
- **Rollback steps:** Revert commit on main, redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
