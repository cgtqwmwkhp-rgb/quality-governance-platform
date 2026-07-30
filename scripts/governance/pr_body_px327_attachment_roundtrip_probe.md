# Change Ledger (CL-PX327-ATTACHMENT-ROUNDTRIP-PROBE)

## 1) Summary
- **Feature / Change name:** Board `w4-px327-probe` (PX-327) — attachment upload → re-read probe
- **User goal (1–2 lines):** Close the blind spot #1387 documented: write-contract guards cannot see attachments because they are absent from incident request/response schemas. Prove that an authenticated incident evidence upload remains readable on the owning record.
- **In scope:** New integration test `tests/integration/test_incident_attachment_roundtrip.py` only (upload via `/api/v1/evidence-assets/upload`, re-list/filter by `source_module=incident` + `source_id`, plus cross-incident non-leak).
- **Out of scope:** Portal intake (already covered by `test_portal_attachment_upload.py` / #1313); B-10 forbid baseline / `KNOWN_LAX`; alembic; schema changes to incident DTOs; frontend.
- **Feature flag / kill switch:** N/A — test-only; production path already round-trips (verified by the new probe).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None — no production fix required; staff evidence upload+list already honour `source_module`/`source_id`
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

New file:

| File | Purpose |
| --- | --- |
| `tests/integration/test_incident_attachment_roundtrip.py` | Fails if incident evidence is accepted (201) but not returned when listing that incident's evidence |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tests only
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Integration test creates an incident, uploads evidence with `source_module=incident`, and asserts the asset appears on `GET /api/v1/evidence-assets/?source_module=incident&source_id=…`
- [x] AC-02: Same suite asserts incident GET does not declare `attachments` (documents why schema guards cannot catch this class)
- [x] AC-03: Filter by a different incident's `source_id` must not return the uploaded asset
- [x] AC-04: No `src/` changes (bug already fixed for this path; probe was the remaining board gap)
- [x] AC-05: black/isort clean on the new file

## 5) Testing Evidence (link to runs)
- [x] Lint — black/isort check clean on new file
- [x] Typecheck — N/A (tests only; no src change)
- [x] Build — N/A
- [x] Unit tests — N/A for this lane
- [x] Integration tests — `pytest tests/integration/test_incident_attachment_roundtrip.py` → **2 passed** locally
- [x] Contract tests (if applicable) — N/A (this is the fixture-cost probe contract tests explicitly deferred)
- [ ] E2E Smoke (critical journeys) — covered by the integration probe; CUJ-06 e2e remains separate and env-dependent

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff attach a photo to an incident via evidence-assets upload; re-list by incident returns that asset (IncidentDetail load path)
- [x] CUJ-02: Evidence listed for incident B does not include an asset uploaded against incident A

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** N/A for test-only merge; CI integration job is the gate
- **Canary plan:** N/A
- **Prod post-deploy checks:** N/A — no runtime change

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Test flakes or false failures in CI
- **Rollback steps:** Revert commit on main
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (test-only)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — test-only probe of existing contracts
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked) — N/A test-only
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — N/A runtime; CI is the monitor
