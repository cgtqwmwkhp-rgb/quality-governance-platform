# Change Ledger (CL-PATH10-S10-STORAGE-READYZ)

## 1) Summary
- **Feature / Change name:** Path-to-10 S10 — Azure Blob upstream readiness on `/readyz`
- **User goal (1-2 lines):** Surface one more honest upstream channel (blob storage) beside OCR/AI and SMTP so ops can see attachment/evidence storage config without inventing credentials or failing the probe.
- **In scope:** Additive `upstream.storage` on root + API `/readyz`; unit tests; no secret leakage
- **Out of scope:** Dual-service refactors; `client.ts` bulk; coverage config; SMTP invent; live blob connectivity ping; forcing probe failure
- **Feature flag / kill switch:** N/A — informational readiness only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `src/infrastructure/upstream/storage_status.py`; wire into `health.py` + root `main.py` `/readyz`
- **APIs (endpoints changed/added):** Additive `/readyz` fields under `upstream.storage` (+ optional `upstream_storage_note`)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Additive JSON fields only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Reads existing `AZURE_STORAGE_CONNECTION_STRING` / `AZURE_STORAGE_CONTAINER_NAME`
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new fields optional for consumers
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert squash merge

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/readyz` reports `upstream.storage` status without secrets
- [x] AC-02: Status values are `not_configured` / `partial` / `configured`
- [x] AC-03: Missing blob config does not fail the readiness probe

## 5) Testing Evidence (link to runs)
- [x] Lint — deferred to CI
- [x] Typecheck — deferred to CI
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_upstream_storage_readiness.py`
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — staging/prod `/readyz` after promote

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/readyz` returns `upstream.storage` honesty fields
- [x] CUJ-02: Unconfigured blob storage leaves probe healthy (non-failing channel)
- [x] CUJ-03: Connection string never appears in readiness payload

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** Readyz payload gains storage channel
- **Alerts:** None (informational; does not 503 on missing blob)
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** `curl .../readyz` shows `upstream.storage`
- **Canary plan:** N/A
- **Prod post-deploy checks:** `/readyz` includes storage status; probe stays ready when AI/SMTP unchanged

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Readyz break, secret leakage, or unexpected probe failure after promote
- **Rollback steps:** Revert squash merge; redeploy prior SHA
- **Owner:** platform / Path-to-10 S10 lane

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: After auto-deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

Made with [Cursor](https://cursor.com)

<!-- ledger-refresh 2026-07-11T17:20Z -->
