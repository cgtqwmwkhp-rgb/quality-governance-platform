# Changelog

All notable changes to the Quality Governance Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [10.0.0] - 2026-02-21

### Added
- Tenant isolation: 53 additional endpoints across analytics (24), iso27001 (14), document_control (4), form_config (4), documents (3), employee_portal (4), global_search (1), evidence_assets (1), notifications (2)
- tenant_id column on InformationAsset, InformationSecurityRisk, SecurityIncident, SupplierSecurityAssessment, Document, EvidenceAsset, FormTemplate, Contract, SystemSetting, LookupOption models
- selectinload() on 9 list endpoints: incidents, complaints, policies, rtas, kri, investigations, documents, tenants, workflow
- Cache invalidation wired into 12 additional route files (56 mutation endpoints total)
- warmup_cache() called in app lifespan startup
- track_metric() wired into 12 route files + auth failure tracking in dependencies
- Pydantic response schemas: document_control.py (18 schemas), iso27001.py (20 schemas)
- response_model on 49 additional endpoints (telemetry, tenants, signatures, investigations, workflow, audits, analytics)
- 6 new frontend page smoke tests (AuditExecution, InvestigationDetail, ComplianceAutomation, AdvancedAnalytics, AuditTemplateBuilder, MobileAuditExecution)
- 2 new Playwright E2E specs: complaints (8 tests), policies (9 tests)
- SkeletonLoader wired into 10 main pages (Dashboard, RiskRegister, Incidents, Audits, Complaints, Policies, Investigations, RTAs, Documents, Standards)
- Flower URL in /readyz health check response
- Task queue depth monitoring (Celery Beat task, every 5 minutes)
- ISO 27001 helper functions: _generate_asset_id(), _calculate_risk_scores()
- AnalyticsService methods accept tenant_id parameter

### Changed
- signatures.py: All 16 endpoints migrated from Depends(get_db) to DbSession pattern
- Frontend coverage thresholds raised (statements: 8%, functions: 8%, lines: 8%)
- UAT tests now blocking in CI (removed || true)
- Quarantined backend E2E tests changed from skip to xfail(strict=False)
- Quarantine policy extended to 2026-03-23 for GOVPLAT-001 and GOVPLAT-002

### Removed
- Empty src/services/ directory (stub only)

## [9.5.0] - 2026-02-20

### Added
- tenant_id column on Incident, Risk, AuditTemplate, AuditRun, AuditFinding, Policy, Complaint models
- Tenant isolation filtering on incidents, risks, audits, policies, complaints routes (49 endpoints)
- Cache invalidation (invalidate_tenant_cache) wired into 8 route files on all mutation endpoints
- FailedTask model for DLQ database persistence
- ErrorCode integration in error handler middleware for structured API responses
- response_model on all endpoints in auditor_competence (14), executive_dashboard (5), compliance (7)
- Response schemas: auditor_competence.py, executive_dashboard.py (new schema files)
- 8 new frontend component/page test files (71 tests total)
- 4 Playwright E2E test files (dashboard, audits, risks, investigations user journeys)
- Frontend coverage enforcement with @vitest/coverage-v8 and thresholds
- Resource limits for flower and pgadmin Docker services

### Changed
- paginate() adopted in investigations.py, document_control.py, uvdb.py, tenants.py (8 patterns)
- apply_updates() adopted in audits.py, users.py, risks.py (6 patterns)
- get_or_404() adopted in audits.py, compliance.py (3 patterns)
- capa.py import fixed: src.api.deps -> src.api.dependencies
- Frontend tests now blocking in CI (continue-on-error removed)
- Backend unit test coverage threshold raised to 55%
- cleanup_old_telemetry documented as intentionally deferred

## [Unreleased]

### Added
- Alert threshold definitions for Azure Monitor integration (error rate, latency, queue depth, cache, DB pool, auth failures)
- Dead letter queue handler for permanently failed Celery tasks
- Cache invalidation strategy with tenant-scoped pattern-based key deletion
- Cache warmup on startup for frequently accessed standards data
- Shared query filter utilities (search, status, date range)
- SkeletonLoader, TableSkeleton, CardSkeleton UI components
- Code splitting with React.lazy for all 49 page components
- Frontend test job in CI pipeline (Vitest + jsdom)
- Frontend component/hook/store tests (useAppStore, useNotificationStore, useDataFetch)
- Structured error codes module (ErrorCode class)
- CAPA response schemas with response_model on all endpoints
- CAPA (Corrective and Preventive Action) module with full lifecycle management
- Cross-standard ISO mapping CRUD API
- JWT token revocation with database blacklist
- Celery background task system (email, notifications, reports, cleanup)
- OpenTelemetry instrumentation with Azure Monitor integration
- Business metrics tracking (incidents, audits, CAPA, risks, auth)
- File upload security validation with magic number verification
- PII scrubbing filter for structured logging
- React Error Boundaries (generic + page-level)
- Zustand global state management (notifications, preferences, app)
- useDataFetch hook for standardized data fetching
- Accessibility improvements (skip-to-content, ARIA labels, axe-core)
- 8 Architecture Decision Records (ADR-0006 through ADR-0013)
- CONTRIBUTING.md, SECURITY.md, ARCHITECTURE.md, LOCAL_DEVELOPMENT.md
- Disaster recovery and scaling documentation

### Changed
- Added tenant_id filtering to all data route files (CAPA, investigations, near_miss, RTAs, risk_register, compliance, workflow, KRI)
- Enhanced get_or_404 utility with optional tenant_id scoping parameter
- Added CurrentUser auth to all 14 UVDB endpoints (previously unprotected)
- Added token blacklist checks to WebSocket endpoints (realtime, copilot) and get_optional_current_user
- Implemented refresh token revocation on token refresh
- Added JTI to password reset tokens for revocation support
- Added Content-Security-Policy, COOP, CORP security headers
- Unified dependency imports across all route files (deps -> dependencies)
- Standardized pagination across 20+ files using paginate() utility
- Standardized entity lookups across 12+ files using get_or_404
- Standardized field updates across 4+ files using apply_updates
- Replaced all numeric HTTP status codes with fastapi.status constants across 13 files
- Standardized pagination response field names (total_pages -> pages)
- Consolidated duplicate frontend API clients (services/api.ts deprecated, api/client.ts primary)
- Added Celery retry policies with exponential backoff (3 retries, jitter)
- Completed data retention service (audit entries, notifications cleanup)
- Added 6 new observability metrics (error rate, cache, DB pool, Celery failures/queue depth, auth failures)
- Added Docker Compose resource limits for all services
- Removed postgresql-client from Dockerfile runtime
- Raised CI coverage thresholds (unit: 65%, integration: 45%)
- Refactored all 47 route files to use shared utilities (pagination, entity lookup, updates)
- Moved business logic from routes to service layer (risk scoring, investigation templates)
- Consolidated service directory (src/services/ merged into src/domain/services/)
- Consolidated workflow engine into single module
- Enhanced health checks with Redis and Celery worker verification
- Database connection pooling optimized (pool_recycle, pool_pre_ping, pool_size)
- Raised test coverage thresholds (unit: 70%, integration: 50%)

### Security
- Added authentication to all previously unprotected endpoints
- Added WebSocket JWT validation for realtime and copilot endpoints
- Replaced all hardcoded tenant/user IDs with authenticated user context
- Added admin (superuser) checks on all destructive operations
- Added tenant isolation verification on tenant-scoped routes
- Fixed token revocation stub (revoke_all_user_tokens now functional)
- Added security headers (HSTS, X-Frame-Options, CSP)
- Rate limiting with Redis backend
- Dependency vulnerability scanning (pip-audit, safety, bandit)

### Fixed
- Token revocation service revoke_all_user_tokens was a no-op stub
- Audit trail endpoints were publicly accessible without authentication
- Copilot routes used hardcoded tenant_id=1 and user_id=1
- Inconsistent pagination parameters (per_page, size) standardized to page_size
- Workflow route handlers used dict type annotation instead of CurrentUser

## [1.0.0] - 2026-02-01

### Added
- Initial release of Quality Governance Platform
- ISO 9001, 14001, 27001, 45001 compliance management
- Incident reporting and investigation management
- Risk register with bow-tie analysis
- Audit and inspection management
- Document control system
- Workflow engine with approval chains
- Multi-tenant architecture
- React frontend with TypeScript
- FastAPI backend with PostgreSQL
