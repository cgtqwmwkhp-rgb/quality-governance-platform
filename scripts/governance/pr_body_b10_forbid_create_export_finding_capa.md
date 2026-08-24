# Change Ledger (CL-B10-FORBID-CREATE-EXPORT-FINDING-CAPA)

## 1) Summary
- **Feature / Change name:** Board B-10 (`w4-extra-forbid`) — convert two safe write schemas to `extra="forbid"`
- **User goal (1–2 lines):** Stop `CreateExportRequest` and `CreateFindingCapaRequest` from silently ignoring unknown body fields (PX-168 class), with unit regression locks and a tightened inventory ratchet.
- **In scope:** `ConfigDict(extra="forbid")` on those two schemas; remove them from `KNOWN_LAX_WRITE_SCHEMAS`; refresh B-10 baseline/inventory (forbid floor 8→10, open ceiling 288→286 on tip post-#1456); unit tests for unknown-field rejection
- **Out of scope:** Mass conversion of remaining 286 open schemas; conveyor/merge allowlist edits; schemas already targeted by open #1457 (`AddCauseRequest`, `AllocationRequest`); C-8 savepoint expansion; w2-enum-contract (`severity_levels` is not a clean 1:1 enum pairing — known gaps for `negligible` on complaint/near-miss); gate weakening
- **Feature flag / kill switch:** N/A — request-body validation only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None — in-repo FE already posts only declared fields (`module`/`format` for exports; optional `title`/`description`/`assignee_email` for finding CAPA)
- **Backend (handlers/services):** None beyond schema config
- **APIs (endpoints changed/added):** Behaviour change only for unknown fields on `POST /api/v1/exports` and `POST /api/v1/audits/findings/{finding_id}/capa` (now 422 instead of silent drop)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `CreateExportRequest`, `CreateFindingCapaRequest` → `additionalProperties: false`
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
- [x] AC-01: `CreateExportRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-02: `CreateFindingCapaRequest` declares `extra="forbid"` and rejects an unknown field in unit tests
- [x] AC-03: Both schemas removed from `KNOWN_LAX_WRITE_SCHEMAS` so Guard 2 / round-trip enforce them
- [x] AC-04: B-10 ratchet baseline refreshed — **forbid ≥ 10**, **open ≤ 286**, forbid set includes the two new schemas
- [x] AC-05: Conveyor/merge allowlist untouched; no gate weakening; no mass conversion; no overlap with #1457 schema files (`rca_tools.py`, `vehicles.py`)

## 5) Testing Evidence (link to runs)
- [x] Lint — black + isort on touched modules
- [x] Typecheck — N/A for ConfigDict + unit tests
- [x] Build — N/A
- [x] Unit tests — `tests/unit/test_create_export_request_extra_forbid.py`, `tests/unit/test_create_finding_capa_request_extra_forbid.py`, `tests/unit/test_write_schema_extra_forbid_ratchet.py` (local pass)
- [ ] Integration tests — N/A for schema-only; CI run linked after open
- [ ] Contract tests — backlog membership updated; CI linked after open
- [ ] E2E Smoke — N/A for this slice; FE payloads already match declared fields

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Export create with only declared fields still validates; an extra field (e.g. `tenant_id`) raises ValidationError
- [x] CUJ-02: Finding CAPA create with only declared fields (including empty body) still validates; an extra field (e.g. `finding_id`) raises ValidationError

## 7) Observability & Ops
- **Logs:** None
- **Metrics:** None
- **Alerts:** None
- **Runbook updates:** Inventory markdown refreshed

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Confirm export download and finding CAPA create still succeed with normal payloads; optional probe of unknown field → 422
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Export Center download and audit finding → CAPA if exercised

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

## Measured baseline (`origin/main` @ `53c7ef48`, post-#1456)
| Metric | Before | After |
| --- | ---: | ---: |
| `extra="forbid"` write schemas | 8 | **10** |
| Open (non-forbid) write schemas | 288 | **286** |
| Converted this PR | — | `CreateExportRequest`, `CreateFindingCapaRequest` |

## Why this residual (selection notes)
- **#1457 still open** (`AddCauseRequest`, `AllocationRequest`) — deliberately avoids `rca_tools.py` and `vehicles.py`. Shared conflict surface is only ratchet docs + `_write_contract_baseline.py` + ratchet unit test. If #1457 lands first (or after this), baseline needs a sibling rebase bump of **+2 forbid / −2 open**.
- **w2-enum-contract thin expansion:** scaffolding exists for `complaint_types` / `incident_types` only. Next candidate `severity_levels` is **not** a clean 1:1 enum contract — skipped.
- **B-10:** inventory ratchet already on main (#1452); #1454/#1455/#1456 merged. These two schemas are fixed-field Create bodies (export sync + finding CAPA overrides), low blast radius; in-repo FE posts only declared keys. Skipped `AddCommentRequest` (body/content alias compatibility) and large create/update aggregates.
