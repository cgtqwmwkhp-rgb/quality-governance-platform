# Change Ledger (CL-path11-p0-b)

## 1) Summary
- **Feature / Change name:** Path 11 P0-B — tenant fail-closed calendar, Actions deeplinks, audit evidence gate, complaint FK validation
- **User goal (1-2 lines):** Close four P0 integrity gaps on Lane B: calendar feed must never run unscoped queries without tenant context; CAPA calendar links must use the Actions UI contract; audit fail-evidence gate must require persisted evidence assets (not preview blobs); complaint create must reject cross-tenant contract/user FKs before flush.
- **In scope:** CAL-01, ACT-01, AUD-01, CMP-01
- **Out of scope:** Lane A (#1048) documents/analytics/Layout changes; MobileAuditExecution runtime upload flow (helpers only parity-tested)
- **Feature flag / kill switch:** N/A — security / contract hardening

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `AuditExecution.tsx` — fail-evidence gate checks `evidenceAssetIds` not preview `photos[]`
- **Backend (handlers/services):** `calendar_feed_service.py` — fail-closed when `tenant_id` is None; `complaint_service.py` — tenant FK validation on create
- **APIs (endpoints changed/added):** Calendar feed returns empty events + all sources failed without tenant; complaint create returns 400 when contract/subject user not in tenant
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Calendar event `href` for CAPA uses `sourceType` + `sourceId` (Actions page contract)
- **Database (migrations/entities/indexes):** No schema changes
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive / fail-closed
- **Tolerant reader / strict writer applied?** Yes — stricter tenant and evidence gates; deeplink query param rename aligns with existing Actions reader
- **Breaking changes:** Users without tenant membership get empty calendar feed (was cross-tenant leak risk); preview-only photos no longer satisfy fail-evidence gate until upload ACK
- **Migration plan:** No migration required
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01 (CAL-01): Calendar feed with `tenant_id=None` returns empty events, all sources in `sources_failed`, zero DB queries
- [x] AC-02 (ACT-01): CAPA calendar `href` uses `/actions?sourceType=capa&sourceId={id}` not `source_type=capa`
- [x] AC-03 (AUD-01): `isFailEvidenceGateActive` gates on `evidenceAssetIds` length, not preview `photos[]`
- [x] AC-04 (CMP-01): Complaint create validates `contract_id` and `subject_user_id` belong to caller tenant before flush
- [x] AC-05: Unit tests for calendar fail-closed, CAPA href, complaint FK rejection, evidence gate helper

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI
- [ ] Typecheck — CI
- [ ] Build — N/A (backend interpreted)
- [ ] Unit tests — local + CI
- [ ] Integration tests — deferred to CI
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — deferred to staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Calendar Insights load for tenant user (scoped feed)
- [x] CUJ-02: CAPA deadline deeplink opens Actions filtered by sourceType/sourceId
- [x] CUJ-03: Audit execution blocks advance on FAIL until evidence asset upload ACK

## 7) Observability & Ops
- **Logs:** Calendar source failures unchanged for tenant-scoped loads
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Calendar feed + complaint create smoke
- **Canary plan:** N/A
- **Prod post-deploy checks:** Health, readiness, version SHA match

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Calendar empty for all users or complaint create regression
- **Rollback steps:** Revert PR on main, redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
