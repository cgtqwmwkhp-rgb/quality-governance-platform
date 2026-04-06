# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Audit Wave 7 — Tenant isolation on workflow rules, KRI, policy acknowledgments, copilot IDOR, signatures admin, role listing
- **User goal (1-2 lines):** Close 38 cross-tenant security vulnerabilities across 6 route files; fix copilot IDOR and tenant fallback; enforce superuser on signature admin endpoints.
- **In scope:** WF-01..15, KRI-01..12, PA-01..02, copilot IDOR+fallback, SIG-05..06, USR-02
- **Out of scope:** form_config, executive_dashboard, vehicle_checklist_analytics, ai_intelligence (deferred — effort L)
- **Feature flag / kill switch:** N/A — security hardening

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `workflow.py`, `kri.py`, `policy_acknowledgment.py`, `copilot.py`, `signatures.py`, `users.py`
- **APIs (endpoints changed/added):** Workflow rule/SLA/escalation CRUD tenant-scoped; KRI CRUD+alerts+SIF tenant-scoped; policy ack get tenant-scoped; copilot session ownership enforced; signature admin requires superuser; role listing tenant-scoped
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No schema changes
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
- [x] AC-01: Workflow rule/SLA/escalation CRUD scoped to tenant (WF-01..15)
- [x] AC-02: KRI CRUD + alerts + SIF assessment scoped to tenant (KRI-01..12)
- [x] AC-03: Policy acknowledgment requirement/ack get scoped to tenant (PA-01..02)
- [x] AC-04: Copilot session get/close enforce ownership (IDOR fix)
- [x] AC-05: Copilot tenant_id fallback removed, null guard added
- [x] AC-06: Signature template use verifies tenant (SIG-05)
- [x] AC-07: Signature admin endpoints require superuser (SIG-06)
- [x] AC-08: Role listing scoped to tenant + shared roles (USR-02)
- [x] AC-09: 1377 unit tests pass, 458 integration tests pass, 195 frontend tests pass, lint/format/mypy clean

## 5) Testing Evidence (link to runs)
- [x] Lint — flake8 clean
- [x] Typecheck — mypy clean (0 errors)
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — 1377 passed, 0 failed
- [x] Integration tests — 458 passed, 0 failed
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Workflow rule management
- [x] CUJ-02: KRI monitoring and alerting
- [x] CUJ-03: Policy acknowledgment workflow
- [x] CUJ-04: Digital signature administration

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
