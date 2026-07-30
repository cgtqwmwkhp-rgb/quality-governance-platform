# Change Ledger (CL-B10-FORBID-ASK-REPLY-ASSIGNMENT-QUESTION)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two safe write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `AskAssignmentQuestionRequest` and `QuestionReplyRequest` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 24→26, open ceiling 272→270 on tip post-#1464); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion of remaining 270 open schemas; conveyor/merge allowlist edits; large create/update aggregates; `AddCommentRequest` (body/content alias compatibility); C-8 savepoint expansion; w2-enum-contract; gate weakening; Wave 1 attachments/audit census/owner-count
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None required — My Reading / Portal Reading ask-question posts only `title`/`body`; HSEC inbox reply posts only `body`
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `POST /api/v1/document-campaigns/assignments/{assignment_id}/questions` and `POST /api/v1/document-campaigns/questions/{thread_id}/reply` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AskAssignmentQuestionRequest`, `QuestionReplyRequest` → `additionalProperties: false`
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
- [x] AC-01: `AskAssignmentQuestionRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `QuestionReplyRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS` so Guard 2 / round-trip enforce them
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 26**, **open ≤ 270**, forbid set includes the two new schemas
- [x] AC-05: Conveyor/merge allowlist untouched; no gate weakening; no mass conversion

## 5) Testing Evidence (link to runs)
- [x] Lint — black + isort on touched modules
- [x] Typecheck — N/A for ConfigDict + unit tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_ask_assignment_question_request_extra_forbid.py`, `tests/unit/test_question_reply_request_extra_forbid.py`, `tests/unit/test_write_schema_extra_forbid_ratchet.py` (local pass)
- [ ] Integration tests — N/A for schema-only; CI run linked after open
- [ ] Contract tests — backlog membership updated; CI linked after open
- [ ] E2E Smoke — N/A for this slice; FE already posts declared fields only

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Ask assignment question with only declared fields still validates; an extra field (e.g. `tenant_id`) raises ValidationError
- [x] CUJ-02: Question reply with only `body` still validates; an extra field (e.g. `thread_id`) raises ValidationError

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** Inventory markdown refreshed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm document-campaign ask-question / reply still succeed with normal payloads; optional probe of unknown field → 422
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check My Reading ask-question and HSEC inbox reply if exercised

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Legitimate client sends a previously-ignored extra field on these two endpoints and is blocked in production
- **Rollback steps:** Revert this PR (restores ignore + prior baseline)
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A until merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — strict-writer for two low-surface bodies
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A pre-merge; schema-only
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — spot-check plan above

## Measured baseline (`origin/main` @ `4695d2dc`, post-#1464)
| Metric | Before | After |
| --- | ---: | ---: |
| `extra="forbid"` write schemas | 24 | **26** |
| Open (non-forbid) write schemas | 272 | **270** |
| Converted this PR | — | `AskAssignmentQuestionRequest`, `QuestionReplyRequest` |

## Why this residual (selection notes)
- **B-10:** inventory ratchet on main (#1452); #1454–#1464 merged through forbid floor 24. Next safe campaign question pair after `CompleteAssignmentRequest` (#1464): ask body (`title` optional + `body`) and reply body (`body` only); FE posts only declared fields (My Reading / Portal Reading / HSEC inbox). Skipped `AddCommentRequest` (body/content alias), large create/update aggregates, and Wave 1 lanes.

Made with [Cursor](https://cursor.com)
