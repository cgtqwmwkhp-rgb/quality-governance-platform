# Evidence Index

**Assessment Date**: 2026-03-07

This index lists all files referenced in the assessment, grouped by dimension and critical function. All paths are relative to repository root.

---

## By Critical Function

### CF1: Authentication & Authorization
| File | Relevance |
|------|-----------|
| `src/core/security.py` | JWT token creation/validation, password hashing |
| `src/core/azure_auth.py` | Azure AD JWKS validation |
| `src/api/routes/auth.py` | Auth endpoints (login, refresh, token-exchange, password reset) |
| `src/api/dependencies/__init__.py` | CurrentUser, CurrentActiveUser, CurrentSuperuser, require_permission |
| `src/core/uat_safety.py` | Production write protection middleware |
| `src/api/routes/tenants.py` | **FINDING F-001**: Auth guards commented out |
| `src/api/routes/compliance.py` | **FINDING F-002**: Missing authentication |
| `src/infrastructure/middleware/rate_limiter.py` | Per-endpoint rate limiting |

### CF2: Primary Business Workflows
| File | Relevance |
|------|-----------|
| `src/api/routes/incidents.py` | Incident CRUD + lifecycle; **FINDING F-003**: missing tenant filter |
| `src/api/routes/complaints.py` | Complaint CRUD; **FINDING F-003**: missing tenant filter |
| `src/api/routes/audits.py` | Audit template + run lifecycle |
| `src/api/routes/investigations.py` | Investigation lifecycle with optimistic locking |
| `src/api/routes/capa.py` | CAPA state machine |
| `src/api/routes/risk_register.py` | Enterprise risk register |
| `src/api/routes/actions.py` | Cross-entity action management |
| `src/domain/models/incident.py` | Incident domain model |
| `src/domain/models/audit.py` | Audit domain model (template-run pattern) |
| `src/domain/models/risk_register.py` | Enterprise risk model (ISO 31000) |
| `src/domain/models/complaint.py` | Complaint domain model |
| `src/domain/models/investigation.py` | Investigation model (optimistic locking) |

### CF3: Data Writes & State Transitions
| File | Relevance |
|------|-----------|
| `src/api/middleware/idempotency.py` | POST idempotency with SHA-256 |
| `src/infrastructure/database.py` | Transaction management, connection pooling |
| `src/domain/models/base.py` | Mixins (Timestamp, SoftDelete, AuditTrail) |
| `src/services/workflow_engine.py` | Workflow state machine |
| `src/services/risk_scoring.py` | Risk scoring engine |

### CF4: External Integrations
| File | Relevance |
|------|-----------|
| `src/infrastructure/storage.py` | Azure Blob / local FS storage |
| `src/domain/services/email_service.py` | Email service (SMTP, templates) |
| `src/infrastructure/cache/redis_cache.py` | Redis cache with fallback |
| `src/infrastructure/tasks/celery_app.py` | Celery task queue (5 queues, 7 periodic jobs) |
| `src/infrastructure/resilience/` | Circuit breakers, retry, bulkhead |
| `src/infrastructure/tasks/dlq.py` | Dead letter queue |
| `src/infrastructure/tasks/dlq_replay.py` | DLQ replay automation |

### CF5: Release/Deploy + Rollback
| File | Relevance |
|------|-----------|
| `.github/workflows/ci.yml` | 21+ CI jobs |
| `.github/workflows/deploy-staging.yml` | Staging deployment |
| `.github/workflows/deploy-production.yml` | Production deployment with 5-phase deploy proof |
| `.github/workflows/rollback-production.yml` | Rollback workflow |
| `scripts/verify_deploy_deterministic.sh` | Deterministic SHA verification |
| `scripts/governance/validate_release_signoff.py` | Release signoff validation |
| `scripts/governance/rollback_drill.py` | Rollback drill |
| `docs/evidence/release_signoff.json` | Release signoff evidence |
| `docs/evidence/environment_endpoints.json` | Environment registry |

---

## By Dimension

### D01 Product Clarity
- `README.md` — Project overview, modules, tech stack
- `src/main.py` — 21 OpenAPI tags defining API structure
- `frontend/src/App.tsx` — 82 lazy-loaded routes across 6 groups

### D02 UX Quality
- `frontend/package.json` — Radix UI, Framer Motion, TailwindCSS, Lucide icons
- `frontend/src/App.tsx` — Route groups, error boundaries, PageLoader

### D03 Accessibility
- `frontend/package.json` — eslint-plugin-jsx-a11y
- `frontend/src/App.tsx` — AccessibilityProvider

### D04 Performance
- `src/infrastructure/database.py` — pool_size=10, max_overflow=20, statement timeout 30s
- `src/main.py` — OpenAPI pre-warming
- `.github/workflows/ci.yml` — performance-budget job (size-limit)
- `src/infrastructure/cache/redis_cache.py` — LRU, configurable TTLs

### D05 Reliability
- `src/infrastructure/resilience/` — Circuit breakers, retry, bulkhead
- `src/infrastructure/tasks/dlq.py` — Dead letter queue
- `src/infrastructure/tasks/dlq_replay.py` — Automated replay
- `src/main.py` — /healthz, /readyz probes
- `Dockerfile` — HEALTHCHECK

### D06 Security
- `src/main.py` — SecurityHeadersMiddleware (8 headers), RateLimitMiddleware
- `src/core/config.py` — Production validation (placeholder key rejection)
- `.semgrep.yml` — 4 custom rules
- `SECURITY.md` — Vulnerability disclosure
- `src/infrastructure/encryption/` — Fernet field-level encryption
- `src/infrastructure/sanitization.py` — HTML sanitization (nh3)
- `src/infrastructure/file_validation.py` — Magic number verification
- `Dockerfile` — Non-root user, digest-pinned image

### D07 Privacy
- `src/core/config.py` — Pseudonymization pepper validation
- `src/infrastructure/logging/` — PIIFilter (regex scrubbing)
- `src/infrastructure/encryption/` — AES-128-CBC field encryption
- `src/domain/models/evidence_asset.py` — PII flagging, redaction

### D08 Compliance
- `src/domain/models/iso27001.py` — ISO 27001:2022 (93 controls)
- `src/domain/models/ims_unification.py` — Cross-standard mapping
- `src/domain/models/planet_mark.py` — GHG Protocol
- `src/domain/models/uvdb_achilles.py` — UVDB Verify B2
- `src/domain/models/loler.py` — LOLER 1998

### D09 Architecture
- Project structure: `src/api/`, `src/domain/`, `src/services/`, `src/infrastructure/`
- `src/api/__init__.py` — 48 route modules
- `pyproject.toml` — 27 mypy overrides (GOVPLAT-004)

### D10 API Design
- `src/main.py` — Versioned API (/api/v1/), OpenAPI config
- `src/api/middleware/idempotency.py` — POST idempotency
- `scripts/check_api_path_drift.py` — Path drift prevention
- `.github/workflows/ci.yml` — openapi-contract-check job

### D11 Data Model
- `src/domain/models/` — 27 model files
- `src/domain/models/base.py` — TimestampMixin, SoftDeleteMixin, AuditTrailMixin, ReferenceNumberMixin

### D12 Schema Versioning
- `alembic.ini` — Configuration (placeholder URL: C-003)
- `alembic/env.py` — Async-aware migration env
- `alembic/versions/` — 62 migrations (Jan 4 - Mar 6, 2026)

### D13 Observability
- `src/infrastructure/monitoring/azure_monitor.py` — 26+ business metrics, tracing
- `src/infrastructure/logging/` — Structured JSON, correlation IDs, PII filter
- `src/core/middleware.py` — Request ID propagation
- `scripts/infra/monitor_alerts.py` — Azure Monitor alert setup

### D14 Error Handling
- `src/api/middleware/error_handler.py` — Unified error envelope, DomainError handling
- `src/infrastructure/resilience/` — Circuit breaker fallbacks
- `src/main.py` — Readiness probe 503

### D15 Testing
- `pyproject.toml` — pytest config, coverage fail_under=50
- `.github/workflows/ci.yml` — 7 test jobs (unit, integration, smoke, e2e, uat-s1, uat-s2, contract)
- `tests/conftest.py` — Rich fixture set
- `tests/contract/test_api_contracts.py` — **FINDING F-005**: stub tests
- `tests/unit/` — **FINDING F-006**: skip_on_import_error

### D16 Test Data
- `tests/factories/core.py` — 9 factories (Tenant, User, Incident, Complaint, NearMiss, AuditTemplate, CAPAAction, Risk, Policy)
- `tests/conftest.py` — Data fixtures
- `tests/uat/conftest.py` — UAT seed data

### D17 CI Quality Gates
- `.github/workflows/ci.yml` — 21+ jobs, all-checks final gate
- `scripts/validate_type_ignores.py` — Type-ignore ceiling
- `scripts/validate_ci_security_covenant.py` — CI security rules
- `scripts/check_api_path_drift.py` — API path enforcement
- `scripts/check_mock_data.py` — Mock data eradication

### D18 CD/Release
- `.github/workflows/deploy-staging.yml` — Staging pipeline
- `.github/workflows/deploy-production.yml` — 5-phase deploy proof
- `.github/workflows/rollback-production.yml` — Rollback workflow
- `scripts/verify_deploy_deterministic.sh` — SHA verification
- `scripts/governance/validate_release_signoff.py` — Release signoff

### D19 Configuration
- `src/core/config.py` — Pydantic BaseSettings, production validation
- `.env.example` — Configuration template
- `src/domain/models/feature_flag.py` — Feature flags
- `scripts/verify_env_sync.py` — Environment sync validation

### D20 Dependencies
- `requirements.txt` — Pinned versions
- `Dockerfile` — Lockfile-first install
- `.github/dependabot.yml` — Weekly updates
- `.github/workflows/ci.yml` — sbom, lockfile-check, pip-audit, dependency-review

### D21 Code Quality
- `pyproject.toml` — Black, isort, mypy, pytest configs; **FINDING F-008**: 27 mypy overrides
- `.semgrep.yml` — Custom static analysis rules
- `scripts/validate_type_ignores.py` — Type-ignore ceiling (200)

### D22 Documentation
- `README.md`, `CONTRIBUTING.md`, `SECURITY.md`
- `docs/STAGE2_COVENANTS.md` — Stage 2.0 covenants
- `.github/PULL_REQUEST_TEMPLATE.md` — PR template
- **FINDING F-007**: ADR documents missing
- **EVIDENCE GAP EG-07**: CHANGELOG.md missing

### D23 Operational Runbooks
- `.github/workflows/rollback-production.yml` — Rollback workflow exists
- `scripts/governance/rollback_drill.py` — Drill script exists
- **EVIDENCE GAP EG-06**: No actual runbook documents

### D24 Data Integrity
- `src/api/middleware/idempotency.py` — SHA-256 idempotency
- `src/domain/models/investigation.py` — Optimistic locking (version field)
- `src/api/routes/audit_trail.py` — Hash-chain verification

### D25 Scalability
- `src/infrastructure/database.py` — Connection pooling
- `src/infrastructure/cache/redis_cache.py` — Caching with LRU
- `src/infrastructure/resilience/` — Bulkhead pattern
- `scripts/infra/autoscaling.py` — Azure auto-scaling

### D26 Cost Efficiency
- `Dockerfile` — Multi-stage build
- `docker-compose.yml` — Resource limits
- `scripts/infra/cost_alerts.py` — Cost monitoring

### D27 I18n/L10n
- `frontend/package.json` — i18next, browser language detector
- `scripts/i18n-check.mjs` — Key completeness validation

### D28 Analytics/Telemetry
- `src/infrastructure/monitoring/azure_monitor.py` — 26+ business metrics
- `src/api/routes/telemetry.py` — Telemetry endpoints
- `frontend/package.json` — web-vitals

### D29 Governance
- `docs/STAGE2_COVENANTS.md` — 5 non-negotiable covenants
- `docs/evidence/release_signoff.json` — Release signoff
- `.github/workflows/ci.yml` — Governance jobs
- `pyproject.toml` — GOVPLAT-004 tracking

### D30 Build Determinism
- `Dockerfile` — Digest-pinned base image, lockfile-first, PYTHONDONTWRITEBYTECODE
- `scripts/verify_deploy_deterministic.sh` — 3-match SHA verification
- `.github/workflows/ci.yml` — sbom, lockfile-check

### D31 Environment Parity
- `docker-compose.yml` — Dev environment
- `docker-compose.sandbox.yml` — **CONTRADICTION C-002**: PG15 vs PG16
- `docs/evidence/environment_endpoints.json` — Environment registry
- `scripts/verify_env_sync.py` — Config sync validation

### D32 Supportability
- `src/main.py` — /healthz, /readyz, /api/v1/meta/version
- `src/infrastructure/logging/` — Structured logging with correlation
- `src/api/routes/audit_trail.py` — Audit trail module
