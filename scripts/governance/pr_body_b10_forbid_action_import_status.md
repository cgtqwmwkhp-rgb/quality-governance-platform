# Change Ledger (CL-B10-ACTION-IMPORT-STATUS)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two Planet Mark write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `ActionImportConfirm` and `ActionStatusUpdate` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **Depends on:** #1490 (AccessControlCreate / AcknowledgmentRequirementCreate pair)
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 36→38, open ceiling 260→258); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion; conveyor edits; gate weakening
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None required for declared fields
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `PUT /api/v1/planet-mark/years/{year_id}/actions/{action_id}` and `POST /api/v1/planet-mark/years/{year_id}/actions/import/confirm` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `ActionImportConfirm`, `ActionStatusUpdate` → `additionalProperties: false`
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
- [x] AC-01: `ActionStatusUpdate` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `ActionImportConfirm` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS`
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 38**, **open ≤ 258**
- [x] AC-05: One open B-10 PR only; no gate weakening; no mass conversion

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_action_status_update_extra_forbid.py`, `tests/unit/test_action_import_confirm_extra_forbid.py`, ratchet test updated
- [ ] Integration / contract / E2E — CI linked after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Action status update with only declared fields still validates; an extra field raises ValidationError
- [x] CUJ-02: Action import confirm with only declared fields still validates; an extra field raises ValidationError

## 7) Observability & Ops
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

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — strict-writer for two small write bodies
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Staging verification — N/A pre-merge; schema-only
- [x] **Gate 4:** Canary — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — spot-check plan above

## Measured baseline (post-#1490)
| Metric | Before | After |
| --- | ---: | ---: |
| `min_forbid_count` | 36 | 38 |
| `max_open_count` | 260 | 258 |
| Schemas converted | — | `ActionImportConfirm`, `ActionStatusUpdate` |

Made with [Cursor](https://cursor.com)
