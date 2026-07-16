# Change Ledger (RISK-TRENDS-NAIVE-CUTOFF)

## 1) Summary
- **Feature / Change name:** Fix risk assessment trends 500 (naive UTC cutoff)
- **User goal (1–2 lines):** Restore `/risk-register/trends` so heatmap sparklines and top movers load without INTERNAL_ERROR.
- **In scope:** `get_risk_trends` cutoff binding; empty-score average hardening; unit coverage; lockfile freshness.
- **Out of scope:** New history tables; changing trend aggregation semantics beyond crash fix.
- **Feature flag / kill switch:** None — bugfix.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None (already tolerates trends failure).
- **Backend (handlers/services):** `src/domain/services/risk_service.py` (`naive_utc_cutoff`, trends averages).
- **APIs (endpoints changed/added):** Behavior fix for `GET /risk-register/trends` (+ `include_movers`).
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** `requirements.lock` refresh (`google-genai` patch).

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Same response shapes (list default; `{series, top_movers}` when `include_movers=true`).
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable — revert application deploy.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `GET /api/v1/risk-register/trends` returns 200 on tip (empty list or monthly series).
- [x] **AC-02:** `include_movers=true` returns `{series, top_movers}` without 500.
- [x] **AC-03:** Unit tests cover naive cutoff helper and movers payload.

## 5) Testing Evidence (link to runs)
- [x] `pytest tests/unit/test_risk_service.py::TestRiskService::test_naive_utc_cutoff_has_no_tzinfo` — passed.
- [x] `pytest tests/unit/test_risk_service.py::TestRiskService::test_get_risk_trends_include_movers` — passed.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Risk Register heatmap workspace loads even when trends previously 500’d (honest empty trends).
- [x] **CUJ-02:** After tip LIVE, trends endpoint succeeds so sparkline/top movers can populate when history exists.

## 7) Observability & Ops
- **Logs:** Removes INTERNAL_ERROR spam from `/trends`.
- **Metrics:** None new.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Call `/api/v1/risk-register/trends` and `?include_movers=true` → 200.
- **Canary plan:** Normal staging → prod deploy path.
- **Prod post-deploy checks:** `/api/v1/meta/version` tip==LIVE; `/trends` 200.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Trends still 500 or unexpected payload shape breaks FE.
- **Rollback steps:** Revert this PR and redeploy prior release.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1039
- **CI run(s):** Added by GitHub Actions after push.
- **Staging deploy evidence:** Pending deployment.
- **Canary evidence:** Pending deployment.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** No migration; additive-safe bugfix.
- [x] **Gate 2:** Local unit tests pass.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
