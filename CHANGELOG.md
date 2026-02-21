# Changelog

All notable changes to the Quality Governance Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
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
- Refactored all 47 route files to use shared utilities (pagination, entity lookup, updates)
- Standardized pagination parameter names (page_size) across all APIs
- Replaced all numeric HTTP status codes with fastapi.status constants
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
