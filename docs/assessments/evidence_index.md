# Evidence Index (Refreshed 2026-03-07)

This index lists the repository evidence used for the current assessment, grouped by Critical Function and Dimension.

## Evidence by Critical Function

### CF1 - Auth/session + authorization boundaries
- `src/api/dependencies/__init__.py`
- `src/core/security.py`
- `src/api/routes/users.py`
- `tests/security/test_owasp_comprehensive.py`
- `.github/workflows/deploy-production.yml` (post-deploy auth checks)

### CF2 - Primary business workflows
- `src/api/routes/employee_portal.py`
- `src/api/routes/audits.py`
- `src/api/routes/risks.py`
- `frontend/src/pages/AuditTemplateLibrary.tsx`
- `tests/e2e/test_portal_e2e.py`
- `tests/integration/test_audits_api.py`
- `tests/test_risk_scoring.py`

### CF3 - Data writes + transitions + side effects
- `src/api/routes/investigations.py`
- `src/main.py` (idempotency middleware registration)
- `alembic/env.py`
- `src/services/risk_scoring.py`
- `.github/workflows/ci.yml` (migrations in integration/smoke/e2e/uat jobs)

### CF4 - External integrations
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`
- `src/core/config.py` (Azure and external integration config)
- `scripts/governance/prod-dependencies-gate.sh`

### CF5 - Release/deploy + rollback + config changes
- `.github/workflows/ci.yml`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`
- `docs/runbooks/AUDIT_STRICT_RELEASE_GATES.md`
- `docs/runbooks/AUDIT_ROLLBACK_DRILL.md`
- `docs/evidence/environment_endpoints.json`
- `scripts/generate_lockfile.sh`
- `scripts/validate_ci_security_covenant.py`
- `scripts/governance/validate_release_signoff.py`

## Evidence by Dimension

### D01 Product clarity and user journeys
- `README.md`
- `src/api/routes/employee_portal.py`
- `frontend/src/pages/*`

### D02 UX quality and IA
- `frontend/src/pages/AuditTemplateLibrary.tsx`
- `frontend/src/App.tsx`

### D03 Accessibility
- `frontend/eslint.config.cjs`
- `frontend/src/pages/AuditTemplateLibrary.tsx`
- `.github/workflows/ci.yml` (frontend lint)

### D04 Performance FE and BE
- `frontend/.size-limit.json`
- `.github/workflows/ci.yml` (performance-budget)
- `src/main.py` (OpenAPI pre-warm)

### D05 Reliability and resilience
- `src/main.py` (`/healthz`, `/readyz`)
- `.github/workflows/ci.yml` (smoke/e2e/uat)
- `docs/runbooks/AUDIT_ROLLBACK_DRILL.md`

### D06 Security engineering
- `src/api/dependencies/__init__.py`
- `src/core/config.py`
- `.github/workflows/ci.yml` (security-scan)
- `.github/workflows/deploy-production.yml` (security verification)

### D07 Privacy and data protection
- `src/core/config.py` (pseudonymization and production validation)
- `src/api/routes/employee_portal.py`
- Evidence gap: dedicated privacy policy artifact set not found

### D08 Compliance readiness
- `docs/adr/ADR-0001-migration-and-ci-strategy.md`
- `docs/adr/ADR-0002-environment-and-config-strategy.md`
- `docs/STAGE2_COVENANTS.md`
- `.github/PULL_REQUEST_TEMPLATE.md`

### D09 Architecture modularity and boundaries
- `README.md` (project structure)
- `src/domain/*`
- `src/services/*`
- `src/infrastructure/*`

### D10 API design quality
- `src/api/routes/*`
- `src/api/middleware/error_handler.py`
- `tests/integration/test_openapi_contracts.py`

### D11 Data model quality
- `src/domain/models/risk.py`
- `src/domain/models/kri.py`
- `src/domain/models/investigation.py`

### D12 Schema versioning and migrations
- `alembic/env.py`
- `alembic/versions/*`
- `.github/workflows/ci.yml` (migration steps)
- `.github/workflows/deploy-production.yml` (migration and revision checks)

### D13 Observability
- `src/main.py` (structured logging)
- `src/api/routes/audits.py` (`_record_audit_endpoint_event`)
- `docs/runbooks/AUDIT_OBSERVABILITY_ALERTS.md`

### D14 Error handling and user-safe failures
- `src/api/middleware/error_handler.py`
- `src/api/utils/errors.py`
- `src/api/routes/users.py`
- `src/api/routes/risks.py`
- `src/api/routes/audits.py`

### D15 Testing strategy
- `tests/unit/*`
- `tests/integration/*`
- `tests/e2e/*`
- `tests/security/*`
- `.github/workflows/ci.yml`

### D16 Test data and fixtures
- `tests/conftest.py`
- `tests/factories/*`
- `pyproject.toml`
- `pytest.ini`

### D17 CI quality gates
- `.github/workflows/ci.yml` (all-checks and gate jobs)

### D18 CD/release pipeline
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`
- `scripts/verify_deploy_deterministic.sh`

### D19 Configuration management
- `src/core/config.py`
- `.github/workflows/ci.yml` (config-drift-guard)
- `docs/adr/ADR-0002-environment-and-config-strategy.md`

### D20 Dependency management
- `requirements.txt`
- `requirements-dev.txt`
- `requirements.lock`
- `frontend/package-lock.json`
- `.github/workflows/ci.yml` (dependency-review, lockfile-check)

### D21 Code quality and maintainability
- `pyproject.toml`
- `.github/workflows/ci.yml` (black/isort/flake8/mypy)

### D22 Documentation quality
- `README.md`
- `docs/runbooks/*`
- `docs/adr/*`
- `.github/PULL_REQUEST_TEMPLATE.md`

### D23 Operational runbooks and incident response
- `docs/runbooks/AUDIT_OBSERVABILITY_ALERTS.md`
- `docs/runbooks/AUDIT_STRICT_RELEASE_GATES.md`
- `docs/runbooks/AUDIT_ROLLBACK_DRILL.md`

### D24 Data integrity and consistency
- `src/api/routes/investigations.py`
- `src/main.py` (idempotency middleware)
- `.github/workflows/ci.yml` and deploy workflows (migration flow)

### D25 Scalability and capacity
- Evidence gap: complete SLO/capacity load-test pack not found

### D26 Cost efficiency
- Evidence gap: explicit cost governance artifacts not found

### D27 I18n and L10n readiness
- `frontend/src/i18n/i18n.ts`
- `scripts/i18n-check.mjs`
- `.github/workflows/ci.yml` (i18n check step)

### D28 Analytics/telemetry and measurement
- `src/api/routes/audits.py` (audit endpoint telemetry)
- `docs/runbooks/AUDIT_OBSERVABILITY_ALERTS.md`

### D29 Governance and decision records
- `docs/STAGE2_COVENANTS.md`
- `docs/adr/ADR-0001-migration-and-ci-strategy.md`
- `docs/adr/ADR-0002-environment-and-config-strategy.md`
- `scripts/governance/*`

### D30 Build determinism and reproducibility
- `Dockerfile` (digest pinning)
- `scripts/verify_deploy_deterministic.sh`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`
- `.github/workflows/ci.yml` (lockfile and contract behaviors)

### D31 Environment parity
- `docs/evidence/environment_endpoints.json`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`
- Runtime probe evidence from assessment session:
  - `https://app-qgp-prod.azurewebsites.net/api/v1/meta/version`
  - `https://app-qgp-prod.azurewebsites.net/readyz`
  - staging/api/frontend host probe outcomes used for parity confidence rating

### D32 Supportability and operability
- `src/main.py` (health/readiness/version)
- `docs/runbooks/*`
- deploy proof artifact generation steps in deployment workflows

