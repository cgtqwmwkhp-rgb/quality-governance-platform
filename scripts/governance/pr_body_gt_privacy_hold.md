# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Golden-Thread R91 + R94 — structured Art. 30 disclosure and matter legal holds
- **User goal (1-2 lines):** Improve auditor-readable ROPA structure without claiming a completed controller ROPA, and introduce a tenant-scoped matter-hold SSOT with explicit enforcement boundaries.
- **In scope:** R91 structured register status/source fields; R94 `matter_legal_holds` schema and hold-record API; public retention-disclosure honesty.
- **Out of scope:** Completing controller ROPAs, appointing a DPO, legal advice, bulk asset relabelling, and wiring retention workers to consume matter holds.
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** Matter-hold create/list/release routes; privacy disclosure enrichment.
- **APIs (endpoints changed/added):** `GET /api/v1/privacy/contact`; `GET /api/v1/privacy/data-processing-register`; `POST|GET /api/v1/legal-holds`; `POST /api/v1/legal-holds/{id}/release`.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Additive FastAPI request/response models for matter holds; additive public disclosure fields.
- **Database (migrations/entities/indexes):** Adds `matter_legal_holds`, tenant/matter and tenant/status indexes, and non-empty reference CHECK.
- **Workflows/jobs/queues (if any):** No worker change; retention enforcement is explicitly `not_yet_wired_to_retention_workers`.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints, table, and disclosure fields.
- **Tolerant reader / strict writer applied?** Yes — API trims and requires a non-empty matter reference; database repeats the invariant.
- **Breaking changes:** None.
- **Migration plan:** Apply `20260720_matter_holds` after `20260720_gt_src_sync`; no backfill because no prior matter-hold SSOT exists.
- **Rollback strategy (DB):** Downgrade drops only the new table/indexes; do not downgrade after production hold records exist without exporting them.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Art. 30 endpoint remains `article_30_stub` and adds activity-level source/review status.
- [x] AC-02: Documentary checklist states the structured fields do not complete controller ROPAs.
- [x] AC-03: Tenant-scoped matter hold records can be created, listed, and released by administrators.
- [x] AC-04: Public retention disclosure identifies the hold SSOT and does not claim worker enforcement.
- [x] AC-05: Migration revision ID is within the 32-character limit and is chained to the current head.

## 5) Testing Evidence (link to runs)
- [x] Lint — IDE diagnostics clean; `ruff` is not installed in this worktree.
- [x] Typecheck — `mypy src/api/routes/legal_holds.py src/domain/models/legal_hold.py src/api/routes/privacy.py` (0 errors).
- [ ] Build — N/A (backend interpreted).
- [x] Unit tests — `tests/unit/test_evidence_asset.py` (21 passed); golden-thread OpenAPI tests (6 passed).
- [x] Integration tests — `tests/integration/test_privacy_disclosure.py` (3 passed).
- [x] Contract tests (if applicable) — regenerated both OpenAPI artifacts; compatibility check passed.
- [ ] E2E Smoke (critical journeys) — not applicable; admin routes require authenticated tenant context.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Auditor reads an Art. 30 activity and sees source documents plus pending-controller-review status.
- [ ] CUJ-02: Tenant administrator records an active matter hold and later releases it.
- [ ] CUJ-03: Operator sees that the matter-hold schema/API is live but retention workers still require an operational pause.

## 7) Observability & Ops
- **Logs:** No new logs; normal API access logging applies.
- **Metrics:** No change.
- **Alerts:** No change.
- **Runbook updates:** `docs/privacy/data-retention-policy.md` documents the manual operational boundary until retention workers consume active holds.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Run migration; create/list/release a test matter hold as a tenant administrator; verify privacy disclosure fields.
- **Canary plan:** Enable only for an internal tenant administrator; do not remove operational purge pauses.
- **Prod post-deploy checks:** Confirm Alembic head, tenant isolation of hold listing, and the API's `not_yet_wired_to_retention_workers` disclosure.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Hold API breaks admin flows or migration fails.
- **Rollback steps:** Stop hold API use, export any newly created hold records, revert application commit; only downgrade migration after confirming records are no longer needed.
- **Owner:** Platform Engineering + privacy/legal operations.

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation.
- Staging deploy evidence: Linked after staging verification.
- Canary evidence (if applicable): Linked after internal-admin verification.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete.
- [ ] **Gate 1:** API/Data/UX contracts approved (privacy/legal owner to confirm operational release procedure).
- [x] **Gate 2:** Local lint/type/targeted tests green; CI pending.
- [ ] **Gate 3:** Staging verification complete (evidence linked).
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked).
- [x] **Gate 5:** Production verification plan + monitoring ready.
