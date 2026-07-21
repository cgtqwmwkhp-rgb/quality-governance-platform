# Change Ledger (CL-GOV-LIB-W4B-DASHBOARDS)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W4b — Library / HSEQ dashboard and PEL dependency map
- **User goal (1–2 lines):** Give Library and Admin users honest, tenant-scoped counts for statutory documents, overdue reviews, and open review packs; expose a PEL reference's current tip and immutable superseded history.
- **Depends on:** #1181 LIVE (W4a on tip); W3 review packs/horizons
- **In scope:** Additive dashboard-summary and dependency-map APIs, thin Admin Dashboard HSEQ tiles, unit/contract coverage, Change Ledger
- **Out of scope:** W4a offer/campaign CTAs, migrations, new campaign/review-pack stacks, automatic dependency writes
- **Feature flag / kill switch:** None — read-only additive

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Admin Dashboard — three thin Library / HSEQ tiles
- **Backend (handlers/services):** `library_review_service.py` composes horizons + `is_statutory` + open packs
- **APIs (endpoints changed/added):** `GET /api/v1/library-review/dashboard-summary`; `GET /api/v1/library-review/dependencies/{pel_doc_ref}`
- **Schemas/contracts:** Additive `library_review` schemas + typed FE client
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None new

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive only
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin shows statutory / overdue-review / open-pack HSEQ tiles
- [x] AC-02: Dashboard summary composes horizon overdue + `is_statutory` + open packs
- [x] AC-03: Dashboard summary is tenant-scoped (no cross-tenant reads)
- [x] AC-04: PEL dependency endpoint returns current tip + superseded history
- [x] AC-05: Unknown PEL → existing not-found contract
- [x] AC-06: No migration / new type-ignore / second stack
- [x] AC-07: Portal / My Reading regression coverage retained
- [x] AC-08: Unit tests for summary + dependency filtering

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_gov_lib_w4b_dashboard_deps.py` (local)
- [x] Frontend — AdminDashboard + Portal Reading tests (local)
- [ ] CI — this PR
- [ ] Staging verification — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: HSEQ dashboard summary includes overdue count from W3 horizons
- [x] CUJ-02: Statutory + open packs contribute independently to tiles
- [x] CUJ-03: PEL ref returns current tip + only superseded history
- [x] CUJ-04: Portal Reading campaign path unchanged

## 7) Observability & Ops
- **Logs:** Existing API request/error logging; no new sensitive fields
- **Metrics:** Existing API latency/error rate
- **Alerts:** Existing API 5xx alerts; no new thresholds
- **Runbook updates:** Admin → Library / HSEQ tiles for statutory / overdue / open packs

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Call dashboard-summary; fetch known `pel_doc_ref` history; confirm Admin tiles render
- **Canary plan:** N/A — read-only additive
- **Prod post-deploy checks:** tip_match YES; Admin HSEQ tiles load; no 5xx spike on new routes

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incorrect tenant counts or dependency map exposing wrong history
- **Rollback steps:** Revert PR on main; force_deploy prior SHA
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After tip deploy
- Canary evidence (if applicable): N/A
- Unit evidence: `pytest tests/unit/test_gov_lib_w4b_dashboard_deps.py`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive-only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A, read-only additive
- [x] **Gate 5:** Production verification plan + monitoring ready
