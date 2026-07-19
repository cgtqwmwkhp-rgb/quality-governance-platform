# Change Ledger (CL-CAMPAIGN-CUJ-POLISH)

**Path claim:** `feat/after-cuj-polish`

## 1) Summary
- **Feature / Change name:** Campaign CUJ polish — deferred signature reopen-to-sign
- **User goal (1-2 lines):** When an engineer defers sign-off pending an HSEQ answer, HSEQ can resolve the question and nudge the assignee to reopen and sign; roster/inbox surfaces signature disposition.
- **In scope:** `sign_deferred_assignment`, `request_assignment_signature`, resolve-question notify; roster filters (`review_needed`, `disposition`); question inbox signature context; API routes/schemas; unit tests; Change Ledger
- **Out of scope:** O-12 competence gate; DEF-PDF; UVDB; Planet Mark; Alembic (uses existing `signature_disposition` column on main)
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None in this PR (BE + contract polish)
- **Backend (handlers/services):** `document_campaign_service.py`; `document_campaign_notifications.py`; `document_campaign.py` routes; schemas
- **APIs (endpoints changed/added):**
  - `POST /document-campaigns/assignments/{id}/signature`
  - `POST /document-campaigns/questions/{thread_id}/request-signature`
  - Roster query params: `review_needed`, `disposition`
- **Schemas/contracts:** `SignAssignmentRequest/Response`, `RequestSignatureResponse`; roster/inbox/quiz submit fields
- **Database:** None (uses existing migration on main)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoints + optional response fields
- **Tolerant reader / strict writer applied?** Yes — new routes; existing clients ignore new fields
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** Revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Resolve question notifies deferred assignee to reopen and sign
- [x] AC-02: HSEQ can request signature via dedicated endpoint
- [x] AC-03: Assignee completes deferred signature via `POST .../signature`
- [x] AC-04: Roster supports `review_needed` and `disposition` filters; inbox exposes signature context
- [x] AC-05: Unit tests cover notify, request-signature, sign-deferred, roster/inbox fields

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_document_campaign_service.py` (70 passed locally)
- [ ] CI run — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Engineer defers sign → HSEQ resolves question → assignee notified
- [x] CUJ-02: HSEQ requests signature → assignee reopens assignment and signs
- [x] CUJ-03: Roster/inbox show signature disposition for triage

## 7) Observability & Ops
- **Logs:** Standard service logging on signature deferral/complete paths
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** None

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Deferred sign → resolve → reopen-to-sign happy path
- **Canary plan:** N/A
- **Prod post-deploy checks:** Smoke one deferred-signature assignment

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Signature completion regressions or incorrect notifications
- **Rollback steps:** Revert PR; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Builds on: main `signature_disposition` migration (#1167 wave)

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
