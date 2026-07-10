# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WCS-B05 — Import + Celery + DLQ ops runbook
- **User goal (1–2 lines):** Give operators a single runbook for external-audit import stalls, Celery worker checks, and DLQ list/retry/purge, linked from conveyor policy.
- **In scope:** `docs/runbooks/IMPORT_CELERY_DLQ_OPS.md`; link from `scripts/conveyor_policy.md`
- **Out of scope:** Code changes to Celery/DLQ/import; email/SMS/SMTP lanes; production Key Vault secret rotation
- **Feature flag / kill switch:** N/A (docs only)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None (documents existing DLQ/import/Celery behaviour)
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Docs:** New ops runbook + conveyor policy link

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Docs-only additive
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert doc commit if needed

## 4) Acceptance Criteria (AC)
- [x] AC-01: Runbook exists at `docs/runbooks/IMPORT_CELERY_DLQ_OPS.md` covering health, Celery inspect, DLQ list/retry/purge, import playbook, staging evidence pack, promote gate
- [x] AC-02: `scripts/conveyor_policy.md` links to the runbook (WCS-B05)
- [x] AC-03: No runtime/email/SMS code changes in this PR (conflict avoidance)

## 5) Testing Evidence (link to runs)
- [x] Lint — N/A docs
- [x] Typecheck — N/A docs
- [x] Build — N/A docs
- [x] Unit tests — N/A docs
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — N/A for docs; ops procedures validated against existing endpoints post-merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator can follow runbook from conveyor policy link to DLQ list/retry commands
- [x] CUJ-02: Staging evidence pack checklist is explicit for import/Celery verification before promote

## 7) Observability & Ops
- **Logs:** Documents existing DLQ logging/metrics thresholds (warn ≥10, critical ≥50)
- **Metrics:** References existing `dlq.size` / `dlq.alert`
- **Alerts:** No new alerts
- **Runbook updates:** This PR **is** the runbook update

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Docs merge does not require deploy; optional: exercise listed curl commands against staging with admin token
- **Canary plan:** N/A docs-only
- **Prod post-deploy checks:** N/A for docs; use runbook during next import/Celery incident or promote

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incorrect/dangerous operational guidance discovered
- **Rollback steps:** Revert the docs commit or amend the runbook in a follow-up PR
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation (change-ledger / docs checks)
- Staging deploy evidence: N/A docs-only
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — docs only
- [ ] **Gate 2:** CI green (lint/type/build/tests) — awaiting PR CI
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A docs-only (procedures reference live endpoints)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — runbook includes promote gate + post-promote DLQ check
