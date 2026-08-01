# Change Ledger (CL-B10-FORBID-SET-ROOT-CAUSE-FISHBONE)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two safe write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `SetRootCauseRequest` and `SetFishboneRootCauseRequest` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 28→30, open ceiling 268→266 on tip post-#1471); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion of remaining 266 open schemas; conveyor/merge allowlist edits; large create/update aggregates; `AddCommentRequest` (body/content alias compatibility); C-8 savepoint expansion; w2-enum-contract; gate weakening; Wave 1 attachments/audit census/owner-count; Wave 4 delete/archive files; Copilot surfaces
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None required — no in-repo FE client posts these two RCA set-root-cause endpoints; InvestigationDetail `contributing_factors` is a separate investigation field path
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `POST /api/v1/rca-tools/five-whys/{analysis_id}/set-root-cause` and `POST /api/v1/rca-tools/fishbone/{diagram_id}/set-root-cause` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `SetRootCauseRequest`, `SetFishboneRootCauseRequest` → `additionalProperties: false`
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
- [x] AC-01: `SetRootCauseRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `SetFishboneRootCauseRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS` so Guard 2 / round-trip enforce them
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 30**, **open ≤ 266**, forbid set includes the two new schemas
- [x] AC-05: Conveyor/merge allowlist untouched; no gate weakening; no mass conversion; Wave 4 delete/archive untouched; Copilot files untouched

## 5) Testing Evidence (link to runs)
- [x] Lint — black + isort on touched modules
- [x] Typecheck — N/A for ConfigDict + unit tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_set_root_cause_request_extra_forbid.py`, `tests/unit/test_set_fishbone_root_cause_request_extra_forbid.py`, `tests/unit/test_write_schema_extra_forbid_ratchet.py` (local pass)
- [ ] Integration tests — N/A for schema-only; CI run linked after open
- [ ] Contract tests — backlog membership updated; CI linked after open
- [ ] E2E Smoke — N/A for this slice; no in-repo FE posts these bodies

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: 5-Whys set-root-cause with only declared fields still validates; an extra field (e.g. `tenant_id`) raises ValidationError
- [x] CUJ-02: Fishbone set-root-cause with only declared fields still validates; an extra field (e.g. `tenant_id`) raises ValidationError

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** Inventory markdown refreshed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm RCA set-root-cause endpoints still succeed with normal payloads; optional probe of unknown field → 422
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check RCA tools set-root-cause if exercised

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

## Measured baseline (`origin/main` @ `04f7db41`, post-#1471)
| Metric | Before | After |
| --- | ---: | ---: |
| `min_forbid_count` | 28 | 30 |
| `max_open_count` | 268 | 266 |
| Schemas converted | — | `SetRootCauseRequest`, `SetFishboneRootCauseRequest` |
| Board close target (`forbid ≥ 62`) | 28 | 30 (32 remaining) |

## Selection notes
- **B-10:** inventory ratchet on main (#1452); #1454–#1471 merged through forbid floor 28. Next safe RCA pair after create/add/complete schemas: set-root-cause bodies for 5-Whys and fishbone (companions to already-strict `AddWhyRequest` / `AddCauseRequest` / `CompleteAnalysisRequest`). Skipped `AddCommentRequest` (body/content alias), large create/update aggregates, and Copilot files.
