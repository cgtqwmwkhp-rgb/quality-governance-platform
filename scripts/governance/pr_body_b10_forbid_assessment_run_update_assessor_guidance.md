# Change Ledger (CL-B10-ASSESSMENT-RUN-UPDATE-ASSESSOR-GUIDANCE)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `AssessmentRunUpdate` and `AssessorGuidanceRequest` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **Depends on:** #1495 (AssessmentResponseUpdate / AssessmentRunCreate pair)
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 46→48, open ceiling 250→248); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion; conveyor edits; gate weakening
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None required for declared fields
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `PATCH /api/v1/assessments/{run_id}` and `POST /api/v1/ai-templates/assessor-guidance` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AssessmentRunUpdate`, `AssessorGuidanceRequest` → `additionalProperties: false`
- **Database (migrations/entities/indexes):** No migrations
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Strict writer for these two bodies only; declared fields unchanged
- **Tolerant reader / strict writer applied?** Yes — unknown keys rejected
- **Breaking changes:** Clients that relied on unknown fields being ignored on these two endpoints will now get 422 (correct failure mode)
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: `AssessmentRunUpdate` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `AssessorGuidanceRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS`
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 48**, **open ≤ 248**
- [x] AC-05: One open B-10 PR only; no gate weakening; no mass conversion

## 5) Testing Evidence (link to runs)
- [x] Lint — N/A beyond schema ConfigDict
- [x] Typecheck — N/A for ConfigDict + unit tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_assessment_run_update_extra_forbid.py`, `tests/unit/test_assessor_guidance_request_extra_forbid.py`, ratchet test updated
- [ ] Integration tests — N/A for schema-only; CI linked after open
- [ ] Contract tests — backlog membership updated; CI linked after open
- [ ] E2E Smoke — N/A for this slice

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Assessment run update with only declared fields still validates; an extra field raises ValidationError
- [x] CUJ-02: Assessor guidance request with only declared fields still validates; an extra field raises ValidationError

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** Inventory markdown refreshed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm normal payloads succeed; optional probe of unknown field → 422
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check if exercised

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Legitimate client sends a previously-ignored extra field on these two endpoints and is blocked in production
- **Rollback steps:** Revert this PR (restores ignore + prior baseline)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Staging deploy evidence: N/A until merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — strict-writer for two small write bodies
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A pre-merge; schema-only
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — spot-check plan above

## Measured baseline (post-#1495)
| Metric | Before | After |
| --- | ---: | ---: |
| `min_forbid_count` | 46 | 48 |
| `max_open_count` | 250 | 248 |
| Schemas converted | — | `AssessmentRunUpdate`, `AssessorGuidanceRequest` |

Made with [Cursor](https://cursor.com)
