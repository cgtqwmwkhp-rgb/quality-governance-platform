# Change Ledger (CL-B10-FORBID-ASSIGN-RECORD-ACKNOWLEDGMENT)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two safe write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `AssignAcknowledgmentRequest` and `RecordAcknowledgmentRequest` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 20→22, open ceiling 276→274 on tip post-#1462); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion of remaining 274 open schemas; conveyor/merge allowlist edits; large create/update aggregates; `AddCommentRequest` (body/content alias compatibility); `CompleteAssignmentRequest` (separate campaign complete body); C-8 savepoint expansion; w2-enum-contract; gate weakening
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None required — in-repo FE acknowledge posts only `acceptance_statement` (declared); no in-repo FE client for assign today
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `POST /api/v1/policy-acknowledgments/requirements/{requirement_id}/assign` and `POST /api/v1/policy-acknowledgments/{acknowledgment_id}/acknowledge` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `AssignAcknowledgmentRequest`, `RecordAcknowledgmentRequest` → `additionalProperties: false`
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
- [x] AC-01: `AssignAcknowledgmentRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `RecordAcknowledgmentRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS` so Guard 2 / round-trip enforce them
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 22**, **open ≤ 274**, forbid set includes the two new schemas
- [x] AC-05: Conveyor/merge allowlist untouched; no gate weakening; no mass conversion

## 5) Testing Evidence (link to runs)
- [x] Lint — black + isort on touched modules
- [x] Typecheck — N/A for ConfigDict + unit tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_assign_acknowledgment_request_extra_forbid.py`, `tests/unit/test_record_acknowledgment_request_extra_forbid.py`, `tests/unit/test_write_schema_extra_forbid_ratchet.py` (local pass)
- [ ] Integration tests — N/A for schema-only; CI run linked after open
- [ ] Contract tests — backlog membership updated; CI linked after open
- [ ] E2E Smoke — N/A for this slice; FE acknowledge already posts declared fields only

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Assign with only declared fields still validates; an extra field (e.g. `tenant_id`) raises ValidationError
- [x] CUJ-02: Record acknowledgment with only declared fields (including empty body) still validates; an extra field (e.g. `acknowledgment_id`) raises ValidationError

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** Inventory markdown refreshed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm policy-ack assign / acknowledge still succeed with normal payloads; optional probe of unknown field → 422
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check My Reading acknowledge if exercised

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

## Measured baseline (`origin/main` @ `75dea63a`, post-#1462)
| Metric | Before | After |
| --- | ---: | ---: |
| `extra="forbid"` write schemas | 20 | **22** |
| Open (non-forbid) write schemas | 276 | **274** |
| Converted this PR | — | `AssignAcknowledgmentRequest`, `RecordAcknowledgmentRequest` |

## Why this residual (selection notes)
- **B-10:** inventory ratchet on main (#1452); #1454–#1462 merged through forbid floor 20. Next safe Assign/Record pair in `policy_acknowledgment.py`: tiny assign body (`user_ids`, optional `policy_version`) and record body (all optional; FE posts only `acceptance_statement`). Skipped `AddCommentRequest` (body/content alias), large create/update aggregates, and `CompleteAssignmentRequest` (campaign complete path kept for a later slice).

Made with [Cursor](https://cursor.com)
