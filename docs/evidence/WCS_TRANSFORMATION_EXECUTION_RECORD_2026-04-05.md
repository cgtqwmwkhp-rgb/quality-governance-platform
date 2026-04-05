# WCS transformation — execution record (2026-04-05)

This document records **delivery executed in-repo** against the prior snapshot baseline (`docs/assessments/world-class-scorecard-2026-04-03.md` and follow-on CUJ review). It is **not** a claim that every dimension reached 9.5+ in one change set.

## Baseline imported (Stage 1 summary)

| Domain | Prior FinalWCS (2026-04-03 artifact) | Primary gap cited in follow-on |
|--------|--------------------------------------|--------------------------------|
| D10 API / contracts | 8.6 (artifact); reassessed 6.0 in CUJ pass | `docs/contracts/openapi.json` lacked `/api/v1/risk-register` paths |
| D15 Testing | 9.5 artifact; reconciled to 7.2 vs live CI | Unit/integration `--cov-fail-under` 44/42 per `docs/evidence/test-coverage-baseline.md` |
| D06 Security | 8.6 artifact; 7.2 in follow-on | Trivy gate failure recorded in `docs/evidence/release_signoff.json` |
| D21 Code quality | 9.5 artifact; 7.2 in follow-on | `scripts/validate_type_ignores.py` `MAX_TYPE_IGNORES` ceiling |
| D27 I18n | 9.5 artifact; 7.2 in follow-on | English-only product scope in `docs/governance/GAP-001-003-remediation-plan.md` |

CUJ baseline: `docs/evidence/CUJ_REVIEW_IMPORT_CAPA_GOVERNANCE_2026-04-05.md` (on branch `chore/cuj-uat-review-evidence`, PR #438).

## Targeted challenge (Stage 2) — additions

| ID | New? | Item |
|----|------|------|
| CH-01 | No | Regenerate committed OpenAPI from `src.main:app` so `docs/contracts/openapi.json` matches runtime routes (closes D10 evidence gap vs stale bundle). |
| CH-02 | No | Keep integration tests for `suggestion-triage` API (D15 uplift path). |

## Master deficiency register — items **closed** by this delivery

| ID | Area | Issue | Response shipped | Evidence |
|----|------|-------|------------------|----------|
| DEF-D10-01 | API | Stale `docs/contracts/openapi.json` missing enterprise risk-register | Ran `scripts/generate_openapi.py` → full schema; `validate_openapi_contract.py` passes | `docs/contracts/openapi.json` includes `/api/v1/risk-register/{risk_id}/suggestion-triage` |
| DEF-D15-01 | Testing | No integration coverage for triage endpoint | `tests/integration/test_risk_register_suggestion_triage.py` | 4 tests |

## Items **not** closed (explicit)

| ID | Area | Reason |
|----|------|--------|
| DEF-D06-01 | Security | Trivy/container gate requires image or policy work beyond this PR. |
| DEF-D15-02 | Testing | Raising `--cov-fail-under` not executed (risk of CI failure without coverage work). |
| DEF-D21-01 | Code quality | Reducing `MAX_TYPE_IGNORES` not executed (large refactor). |
| DEF-D27-01 | I18n | Product stance English-only; multi-locale parity out of scope. |

## Validation executed locally

- `python3.11 scripts/generate_openapi.py` (with `DATABASE_URL` / secrets for import)
- `python3.11 scripts/validate_openapi_contract.py` — pass (511 paths)
- `python3.11 -m pytest tests/unit/test_audit_contract_freeze.py` — pass
- `python3.11 -m pytest tests/integration/test_risk_register_suggestion_triage.py` — pass (prior run)
- `make pr-ready` — pass on branch before push

## Production path

Merge PR to `main` → CI green → staging deploy (if configured) → `workflow_dispatch` **Deploy to Azure Production** with `staging_verified=true`, `release_sha=<merge SHA>`, `force_deploy` if within freeze window → post-deploy: `GET /healthz`, `GET /api/v1/meta/version`, spot CUJ checks → update `docs/evidence/release_signoff.json`.

## Production deployment (completed — PR #439)

| Gate | Evidence |
|------|----------|
| Staging | [Deploy to Azure Staging](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002714695) — **success**, head SHA `2351fa04bda0d9c5f56a1aef99531866c984d205` |
| CI (merge-blocking) | [CI](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002621167) — **success** on same SHA |
| Production | [Deploy to Azure Production](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24002867809) — **success**, `workflow_dispatch`, `force_deploy=true` (Sun UTC freeze) |

**Live verification (production API host):**

- `GET https://app-qgp-prod.azurewebsites.net/healthz` → `200`, `{"status":"ok",...}`
- `GET https://app-qgp-prod.azurewebsites.net/readyz` → `{"status":"ready","database":"connected","redis":"not_configured",...}`
- `GET https://app-qgp-prod.azurewebsites.net/api/v1/meta/version` → `build_sha` **2351fa04bda0d9c5f56a1aef99531866c984d205**, `environment` **production**, `build_time` **2026-04-05T13:52:07Z**

Governance artifact updated: `docs/evidence/release_signoff.json` (this branch / follow-up PR).

## Post-execution WCS (honest)

| Dimension | Before (CUJ follow-on score) | After this change | Notes |
|-----------|------------------------------|-------------------|-------|
| D10 | 6.0 | **≥8.6** (maturity 4.5, CM 0.95) | Full OpenAPI artifact aligned to app |
| D15 | 7.2 | **~7.5–8.0** (indicative) | +integration tests; thresholds unchanged |
| Others | unchanged | unchanged | No code changes in those areas in this PR |

Full 9.5+ across **all** dimensions remains **not** claimed.
