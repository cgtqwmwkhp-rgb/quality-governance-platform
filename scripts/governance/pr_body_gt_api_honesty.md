# Change Ledger (CL-GT-API-HONESTY)

## File allowlist (exclusive)

- `src/api/__init__.py`
- `src/api/routes/actions.py`
- `src/api/routes/risks.py`
- `src/api/schemas/risk.py`
- `src/main.py`
- `openapi-baseline.json`
- `docs/contracts/openapi.json`
- `tests/unit/test_gt_api_honesty_contract.py`
- `scripts/governance/pr_body_gt_api_honesty.md`

**Zero overlap** with FE risk/CUJ (#1025), schema migrations, or global error-vocabulary standardisation.

## 1) Summary

- **Feature / Change name:** fix(gt) — API honesty residuals (R24/R25/R57/R58/R59)
- **User goal:** Make the committed partner contract explicit about action discriminators, risk-history pagination, and the two separate risk APIs without breaking existing consumers.
- **In scope:** Freeze required action-detail `source_type`; publish paginated assessment-history endpoint; preserve legacy raw array; distinguish Operational vs Enterprise Risk OpenAPI tags; clarify cross-source action paging behaviour.
- **Out of scope:** Migrations; raw-array removal; list-level `linked_risk_ids`; global error-vocabulary changes.
- **Root cause:** Contract/docs under-specified pagination and dual risk API tags; assessment array silently capped.

## 2) Impact Map

| Flag | Before | After |
|------|--------|-------|
| R24 | Detail discriminator existed but was not contract-frozen | `/actions/{action_id}` OpenAPI test asserts required query `source_type` |
| R25 | Description could imply all-source paging occurred wholly in SQL | Docs state bounded per-source fetch + merge/slice; page metadata remains accurate |
| R57 | Assessment endpoint said pagination but silently capped a raw array at 100 | Legacy array returns full history; `/assessments/paged` provides explicit page metadata |
| R58 | Controls had a paginated object while assessments only had a raw array | New additive paginated assessment object; legacy array remains for compatibility |
| R59 | `/risks` tag could be confused with `/risk-register` EnterpriseRisk API | Tags are `Operational Risk Register` and `Enterprise Risk Register` |

## 3) Compatibility & Data Safety

- No migration and no persistence change.
- Existing `GET /api/v1/risks/{risk_id}/assessments` remains a raw array; removal of its historical 100-row cap is additive.
- New clients should use `GET /api/v1/risks/{risk_id}/assessments/paged?page=1&page_size=50`.
- `GET/PATCH /api/v1/actions/{action_id}` keep their existing required `source_type` query.

## 4) Acceptance Criteria

- [x] AC-01: Action detail contract requires `source_type`.
- [x] AC-02: Operational and Enterprise risk paths have unambiguous OpenAPI tags.
- [x] AC-03: Paginated assessment history reports `items`, `total`, `page`, `page_size`, and `pages`.
- [x] AC-04: Existing assessment-array consumers remain supported.
- [x] AC-05: Baseline and published OpenAPI artifacts are regenerated together.
- [ ] AC-06: tip==LIVE squash merge and UAT canvas re-score.

## 5) Testing Evidence

- Unit: `tests/unit/test_gt_api_honesty_contract.py`
- Regression: `tests/unit/test_gt_openapi_list_routes.py`
- [ ] CI green post-push

## 6) Critical Journeys

- [x] CUJ-01: Partner fetches action detail with required `source_type` discriminator
- [x] CUJ-02: Partner pages risk assessment history via `/assessments/paged` with accurate totals

## 7) Observability

- No new metrics; OpenAPI/docs honesty only. Contract tests fail CI if tags/discriminator regress.

## 8) Release Plan

- Squash-merge only when this PR is based on current `main` (tip==LIVE); no migration or SWA bake required for API-only change.

## 9) Rollback Plan

- Owner: GT remediation owner
- Rollback steps: Revert the squash commit. Legacy assessment array behaviour remains available throughout.

## 10) Evidence Pack

- Canvas GT UAT flags R24/R25/R57/R58/R59
- Prior tip: `2b9d7066` schema wave (#1024)
- Deferred: R39, R88/R89

---

# Gate Checklist

- [x] **Gate 0:** Scope + compatibility + rollback
- [x] **Gate 1:** Focused unit contract coverage
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (auto after merge)
- [x] **Gate 4:** Canary N/A (API contract; no FE bake)
- [ ] **Gate 5:** tip==LIVE + canvas update
