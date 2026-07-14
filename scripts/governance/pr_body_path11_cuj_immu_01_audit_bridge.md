# Change Ledger (CL-PATH11-CUJ-IMMU-01-AUDIT-BRIDGE)

## 1) Summary
- **Feature / Change name:** CUJ-IMMU-01 — Domain Mutation Immutable Audit Bridge
- **User goal (1-2 lines):** Make Admin Audit Trail honest: CAPA / incident / complaint domain mutations persist hash-chained `AuditLogEntry` rows via `record_audit_event` → `AuditLogService`.
- **In scope:** Bridge `record_audit_event` to `AuditLogService.log(commit=False)`; pass `tenant_id` from CAPA/incident/complaint services; unit + integration audit contracts; Change Ledger
- **Out of scope:** Workforce / TrainingTicket matrix; Portal `/portal/work`; Ops intake triage; FE entity-detail audit links (Admin Audit Trail already queries `AuditLogEntry`); `regulatory_watch_actions.py` (not on main — follow-on when GKB WL2 lands)
- **Feature flag / kill switch:** N/A — persistence bridge; skip-with-warning when tenant unresolved

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (Admin Audit Trail already reads `audit_log_entries`)
- **Backend (handlers/services):** `audit_service.py` (persist bridge); `audit_log_service.py` (`commit=` flag); `capa_service.py` / `incident_service.py` / `complaint_service.py` (pass `tenant_id`)
- **APIs (endpoints changed/added):** None — existing mutations now populate Audit Trail
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** No schema changes — uses existing `audit_log_entries`
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive persistence behind existing `record_audit_event` API
- **Tolerant reader / strict writer applied?** Yes — optional `tenant_id` arg; falls back to request tenant ContextVar; warns + skips persist if neither present
- **Breaking changes:** None — callers without `tenant_id` keep working; observability retained
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only (new rows remain as historical audit)

## 4) Acceptance Criteria (AC)
- [x] AC-01: `record_audit_event` with tenant persists `AuditLogEntry` via `AuditLogService` (`commit=False`)
- [x] AC-02: CAPA create / status / delete pass `tenant_id` into the bridge
- [x] AC-03: Incident create / update / delete pass `tenant_id` into the bridge
- [x] AC-04: Complaint create / update pass `tenant_id` into the bridge
- [x] AC-05: Missing tenant → warning + no false Audit Trail row (honest skip)
- [x] AC-06: Unit + integration contracts assert hash-chained persistence for domain mutations

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_audit_event_bridge.py` (persist / delete map / skip / request-tenant)
- [x] Unit — CAPA service asserts `tenant_id` on create + status transition audit calls
- [x] Unit — existing `test_audit_log_service` / capa / incident / complaint suites green (48 related passed locally)
- [x] Integration — `tests/integration/test_audit_immutable_bridge.py` + updated `test_audit_events.py`
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Domain mutation (CAPA/incident/complaint) → immutable `AuditLogEntry` visible to Admin Audit Trail queries
- [x] CUJ-02: `record_audit_event` without tenant does not invent a trail row (honest skip + warning)
- [x] CUJ-03: Bridge flush shares caller transaction (`commit=False`) so `get_db` request-end commit owns durability

## 7) Observability & Ops
- **Logs:** `audit_bridge_skipped_no_tenant` warning when tenant unresolved
- **Metrics:** `audit_completed` now includes `persisted` (+ `audit_log_entry_id` when true)
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Create incident/CAPA/complaint → Admin Audit Trail filtered by entity shows new rows; hash chain verify endpoint still healthy
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Audit Trail after a known mutation; confirm no spike in `audit_bridge_skipped_no_tenant`

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Audit writes fail domain mutations, or Audit Trail spam / integrity errors
- **Rollback steps:** Revert merge commit on main and redeploy previous SHA (rows written while live remain)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive bridge; no API shape change
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
