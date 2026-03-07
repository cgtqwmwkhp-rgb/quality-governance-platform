# Evidence Index

**Assessment Date:** 2026-03-07 (Post Top-15 Uplift)

## By Critical Function

| CF | Files Referenced |
|----|-----------------|
| CF1 Auth | `src/api/routes/auth.py`, `src/core/auth.py`, `src/api/dependencies/`, `src/infrastructure/middleware/rate_limiter.py:253` |
| CF2a Incidents | `src/api/routes/incidents.py`, `src/domain/models/incident.py`, `src/domain/services/incident_service.py`, `tests/unit/test_auth_enforcement.py` |
| CF2b Audits | `src/api/routes/audits.py`, `src/domain/models/audit.py`, `src/domain/services/audit_service.py` |
| CF2c Risks | `src/api/routes/risks.py`, `src/domain/models/risk.py` |
| CF3 Data Writes | `src/api/middleware/idempotency.py`, `src/domain/models/base.py`, `src/api/routes/employee_portal.py` |
| CF4 External | `src/infrastructure/monitoring/azure_monitor.py`, `requirements.txt:48-52`, `src/core/config.py` |
| CF5 Release | `.github/workflows/ci.yml`, `.github/workflows/deploy-production.yml`, `scripts/governance/validate_release_signoff.py`, `docs/evidence/release_signoff.json` |

## By Dimension

| Dimension | Evidence Files |
|-----------|---------------|
| D01 Product clarity | `docs/user-journeys/`, `README.md`, `src/api/__init__.py` (59 route modules) |
| D02 UX quality | `frontend/src/components/ui/Breadcrumbs.tsx`, `EmptyState.tsx`, `SkeletonLoader.tsx`, `frontend/src/contexts/ToastContext.tsx` |
| D03 Accessibility | `frontend/package.json:59,62` (jsx-a11y, jest-axe), `docs/accessibility/wcag-checklist.md`, `frontend/src/components/ui/LiveAnnouncer.tsx` |
| D04 Performance | `frontend/package.json` (web-vitals, size-limit, @lhci/cli), `src/main.py:234` (GZipMiddleware) |
| D05 Reliability | `src/main.py:453-507` (/readyz DB+Redis), `src/api/routes/health.py`, `src/infrastructure/middleware/request_logger.py` |
| D06 Security | `src/main.py:23-56` (SecurityHeadersMiddleware, CSP), `src/infrastructure/middleware/rate_limiter.py`, `requirements.txt:20` (nh3), `.github/workflows/ci.yml` (Bandit, pip-audit) |
| D07 Privacy | `docs/privacy/dpia-incidents.md`, `src/core/config.py:131-141` (pseudonymization_pepper) |
| D08 Compliance | `src/domain/models/` (ISO 9001/14001/27001/45001), `docs/evidence/release_signoff.json` |
| D09 Architecture | `src/api/__init__.py`, `src/domain/exceptions.py`, `src/api/utils/errors.py`, `src/api/middleware/error_handler.py` |
| D10 API design | `src/api/routes/incidents.py` (api_error, transitions, pagination), `src/api/routes/risks.py`, `src/api/routes/complaints.py` |
| D11 Data model | `src/domain/models/risk.py:66-76` (JSON columns), `src/domain/models/incident.py` (composite indexes), `src/domain/models/complaint.py`, `src/domain/models/audit.py` |
| D12 Schema | `alembic/versions/` (63 migrations), `.github/workflows/ci.yml` (down-migration test) |
| D13 Observability | `src/infrastructure/monitoring/azure_monitor.py:1-25`, `src/infrastructure/middleware/request_logger.py`, `docs/observability/slo-definitions.md`, `src/api/routes/slo.py` |
| D14 Error handling | `src/api/routes/incidents.py` (api_error + transitions), `src/api/routes/auth.py:78-207` (plain strings), `src/domain/exceptions.py`, `frontend/src/api/client.ts` (429 handling, toast) |
| D15 Testing | `tests/` (unit, integration, e2e, uat, smoke, contract), `pyproject.toml:217` (fail_under=35), `frontend/package.json` (@playwright/test) |
| D16 Test data | `requirements-dev.txt:7` (factory-boy), `conftest.py` |
| D17 CI gates | `.github/workflows/ci.yml` (22 jobs: code-quality, workflow-lint, smoke-gate, unit-tests, integration-tests, security-scan, etc.) |
| D18 CD/release | `.github/workflows/deploy-staging.yml`, `deploy-production.yml`, `scripts/governance/validate_release_signoff.py` |
| D19 Configuration | `src/core/config.py` (Pydantic BaseSettings, production validators), `docker-compose.yml` |
| D20 Dependencies | `requirements.txt`, `requirements.lock`, `frontend/package-lock.json`, `.github/dependabot.yml` |
| D21 Code quality | `pyproject.toml` (black, isort, flake8, mypy — 30 overrides), `src/api/routes/auth.py` (inconsistent error format) |
| D22 Documentation | `README.md`, `docs/adr/` (8 files, 4 collisions), `docs/runbooks/`, `docs/privacy/` |
| D23 Runbooks | `docs/runbooks/incident-response.md`, `docs/runbooks/escalation.md`, `docs/runbooks/AUDIT_ROLLBACK_DRILL.md` |
| D24 Data integrity | `src/api/middleware/idempotency.py`, `src/api/routes/incidents.py` (status transitions), `src/domain/models/base.py` (AuditTrailMixin, ReferenceNumberMixin) |
| D25 Scalability | `src/infrastructure/database.py:35-56` (pool_size=10, max_overflow=20), `Dockerfile` |
| D26 Cost efficiency | No evidence files found |
| D27 I18n | `frontend/src/i18n/i18n.ts`, `frontend/src/i18n/locales/en.json` (2000+ keys), `scripts/i18n-check.mjs` |
| D28 Analytics | `frontend/src/hooks/useWebVitals.ts`, `src/api/routes/slo.py`, `src/api/routes/telemetry.py` |
| D29 Governance | `docs/adr/` (8 files, 4 number collisions), `CHANGELOG.md`, `docs/evidence/release_signoff.json` |
| D30 Build determinism | `Dockerfile:5` (digest pin), `requirements.lock`, `.github/workflows/ci.yml` (sbom job, lockfile-check) |
| D31 Environment parity | `docker-compose.yml`, `src/core/config.py` (app_env), `.github/workflows/deploy-staging.yml` vs `deploy-production.yml` |
| D32 Supportability | `src/infrastructure/middleware/request_logger.py`, `src/api/routes/health.py`, `src/main.py` (/readyz, /healthz, /health) |
