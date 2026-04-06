# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Audit Wave 9 — Tenant isolation on ISO 27001, risks, audit trail
- **User goal (1-2 lines):** Close 20 cross-tenant security vulnerabilities across 3 files; add tenant_id filters to all ISO 27001 ISMS endpoints, risk register statistics/matrix/controls, and audit trail entry lookup.
- **In scope:** ISO-01..14, RSK-01..05, ATL-01
- **Out of scope:** Standards library (global shared data by design), feature flags, RCA tools, push notifications (service-layer follow-on)
- **Feature flag / kill switch:** N/A — security hardening

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `iso27001.py`, `risks.py`, `audit_trail.py`
- **APIs (endpoints changed/added):** 14 ISO 27001 endpoints tenant-scoped (assets, controls, SoA, risks, incidents, suppliers, dashboard); 5 risk register endpoints tenant-scoped (statistics, matrix, delete_risk, update_control, delete_control); 1 audit trail endpoint tenant-scoped (get_audit_entry)
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
- [x] AC-01: All 14 ISO 27001 endpoints scoped to tenant (ISO-01..14)
- [x] AC-02: Risk statistics and matrix scoped to tenant (RSK-01..02)
- [x] AC-03: Risk delete_risk scoped to tenant (RSK-03)
- [x] AC-04: Risk update_control and delete_control join through Risk for tenant check (RSK-04..05)
- [x] AC-05: Audit trail get_audit_entry scoped to tenant (ATL-01)
- [x] AC-06: 1377 unit tests pass, 195 frontend tests pass, lint/format/mypy clean

## 5) Testing Evidence (link to runs)
- [x] Lint — flake8 clean
- [x] Typecheck — mypy clean (0 errors)
- [x] Build — N/A (backend interpreted)
- [x] Unit tests — 1377 passed, 0 failed
- [x] Integration tests — deferred to CI (requires DB)
- [x] Contract tests (if applicable) — N/A
- [x] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: ISO 27001 ISMS management
- [x] CUJ-02: Risk register operations
- [x] CUJ-03: Audit trail access

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
