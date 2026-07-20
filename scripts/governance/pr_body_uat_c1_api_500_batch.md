# Change Ledger (CL-UAT-C1-API-500)

## Summary

- **Feature / Change name:** Wave C1 UAT API 500/404 batch — search mount, evidence list, trailing-slash aliases, signatures/policy-ack/feature-flags hardening
- **User goal:** Close highest-value UAT API failures on prod tip without boiling the ocean; staff/global search and evidence surfaces return honest 200/503 instead of 404/500
- **In scope:** ACT-020 search 404; ACT-021 evidence-assets 500; ACT-023 trailing-slash aliases (search + feature-flags); ACT-040/041/043 fail-soft + serialization fixes; unit tests; OpenAPI regen
- **Out of scope:** LIBRARY_DISPOSAL_EXECUTE; Alembic-on-App-Service-startup; ACT-042 vehicle-checklist PAMS integration (already structured 503 on tip — see residual)

## Impact Map

| ID | Surface | Before | After |
|---|---|---|---|
| ACT-020 | `GET /api/v1/search` (no slash) | 404 (`redirect_slashes=False`, route only on `/search/`) | Dual-mount alias → 200 search contract |
| ACT-021 | `GET /api/v1/evidence-assets` | 500 when any row has non-numeric `source_id` (e.g. `capa:12` action spine) | Response `source_id` typed as `str`; per-row fail-soft skip |
| ACT-023 | `GET /api/v1/feature-flags` (no slash) | 404 | Dual-mount alias → 200 list |
| ACT-040 | `GET /api/v1/feature-flags/` | 500 if `feature_flags` table missing (migration lag) | Fail-soft empty list + rollback |
| ACT-041 | `GET /api/v1/signatures/requests*` | 500 lazy-load `MissingGreenlet` on `request.signers` | `selectinload(SignatureRequest.signers)` on list/get/pending |
| ACT-043 | `GET /policy-acknowledgments/dashboard`, `/my-pending` | 500 on schema lag / deprecated serialization | Tenant-scoped counts; `model_validate`; fail-soft empty dashboard/list |
| ACT-042 | Vehicle checklists | — | **Residual** — tip already returns structured 503 when PAMS/cache unavailable |

## Compatibility

- Evidence `source_id` response widens int → string (numeric strings unchanged for incident/near-miss rows; action keys now valid)
- Dual-mount empty-string aliases use `include_in_schema=False`; canonical OpenAPI paths unchanged (`/search/`, `/feature-flags/`)
- No new env flags; `LIBRARY_DISPOSAL_EXECUTE` not enabled
- No Alembic revisions; no App Service startup migration hook

## Acceptance Criteria

- [x] AC-01: `GET /api/v1/search?q=…` (no trailing slash) returns 200 with `results`/`total`
- [x] AC-02: `GET /api/v1/evidence-assets` lists rows with action-key `source_id` without HTTP 500
- [x] AC-03: `GET /api/v1/feature-flags` (no slash) returns 200
- [x] AC-04: `GET /api/v1/signatures/requests` eager-loads signers (no async lazy-load 500)
- [x] AC-05: Policy ack dashboard/my-pending fail-soft on `ProgrammingError` (empty honest payload)
- [x] AC-06: Unit suite `tests/unit/test_wave_c_uat_api_fixes.py` green
- [ ] AC-07: CI gates (black/isort/mypy/openapi) green on PR
- [ ] AC-08: tip LIVE smoke after merge — prod UAT re-run for covered ACT IDs

## Testing Evidence

- [x] `pytest tests/unit/test_wave_c_uat_api_fixes.py -q` — 7 passed
- [x] `pytest tests/unit/test_evidence_asset.py tests/unit/test_vehicle_checklist_pams_unavailable.py -q` — regression green
- [x] `mypy` on touched route/service modules — clean
- [x] OpenAPI baseline + `docs/contracts/openapi.json` regenerated; self-compat check passed
- [ ] Full CI on PR

## Critical Journeys

- [x] CUJ-01: Global search from staff shell (`/api/v1/search?q=…`) resolves without 404
- [x] CUJ-02: Evidence library list after action-key uploads returns 200 (not 500)
- [x] CUJ-03: Admin feature-flag panel loads list (with or without trailing slash)
- [x] CUJ-04: Signatures inbox/list renders without server error on signers relation
- [x] CUJ-05: Policy compliance dashboard / my-pending returns empty honest state when tables unavailable
- [ ] CUJ-06: tip LIVE prod verification post-merge

## Observability

- Log keys: `Skipping evidence asset id=… — response validation failed`; `GET /feature-flags failed — feature_flags table unavailable`; `GET /policy-acknowledgments/… — table unavailable`
- Monitor 5xx rate drops on `/api/v1/search`, `/evidence-assets`, `/signatures/requests`, `/policy-acknowledgments/dashboard`

## Release Plan

1. Merge PR after CI + review (do **not** merge from authoring agent)
2. Deploy API tip to prod (standard conveyor — no Alembic-on-startup)
3. Re-run UAT Wave C1 probes for ACT-020/021/023/040/041/043

## Rollback Plan

- **Owner:** Platform / on-call release manager
- **Trigger:** Regression on search, evidence list, signatures, or policy-ack surfaces
- **Steps:** Revert squash-merge commit; redeploy previous prod tip (`76d016f3`)

## Evidence Pack

- Unit: `tests/unit/test_wave_c_uat_api_fixes.py`
- OpenAPI: `openapi-baseline.json`, `docs/contracts/openapi.json`
- This ledger: `scripts/governance/pr_body_uat_c1_api_500_batch.md`

---

# Gate Checklist

- [x] **Gate 0:** Scope, Change Ledger, AC, rollback reviewed; LIBRARY_DISPOSAL_EXECUTE off; no Alembic-on-startup
- [ ] **Gate 1:** black / isort / mypy / OpenAPI CI green
- [x] **Gate 2:** Focused unit suites green locally
- [ ] **Gate 3:** tip LIVE UAT re-probe after merge
- [x] **Gate 4:** No canary required — read-path hardening only
- [ ] **Gate 5:** Prod evidence attached post-deploy
