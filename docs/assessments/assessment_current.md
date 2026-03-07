# Quality Governance Platform — World-Class Assessment (Round 1: Current State)

**Assessment Date**: 2026-03-07
**Assessor**: Automated World-Class App Assessor + Build Director
**Platform Version**: 1.0.0
**Prior Assessment**: N/A (first assessment)
**Delta**: N/A

---

## 1. Executive Summary

- **Average Maturity**: 3.4 / 5.0
- **Average World-Class Score (WCS)**: 6.5 / 10.0
- **Overall Confidence**: **Medium-High** — Direct evidence from 27 domain models, 48 route modules, 62 migrations, 21+ CI jobs, 10 infrastructure sub-modules. Gaps exist in runtime/operational evidence (no dashboards, no load test results, no external audit reports).

### Top 5 Strengths (Evidence-Based)
1. **D17 CI Quality Gates (WCS 10.0)** — 21+ CI jobs including Trojan source detection, Bandit blocking, API path drift, OpenAPI contract stability, deterministic deploy verification, audit acceptance packs. Evidence: `.github/workflows/ci.yml`
2. **D18 CD/Release Pipeline (WCS 10.0)** — 5-phase deploy proof, deterministic SHA verification (3 consecutive matches), DB backup before production deploy, release signoff validation, rollback workflow. Evidence: `deploy-production.yml`, `deploy-staging.yml`, `rollback-production.yml`
3. **D30 Build Determinism (WCS 10.0)** — Docker base image pinned by digest, lockfile-first install, SBOM generation (CycloneDX), lockfile freshness check, `PYTHONDONTWRITEBYTECODE=1`. Evidence: `Dockerfile`, `ci.yml` (sbom, lockfile-check jobs)
4. **D05 Reliability & Resilience (WCS 8.0)** — Dual circuit breaker implementations, retry with backoff, bulkhead pattern (auth=50, business=100 concurrent), DLQ with automated replay, health probes. Evidence: `src/infrastructure/resilience/`, `tasks/dlq.py`, `tasks/dlq_replay.py`
5. **D24 Data Integrity (WCS 8.0)** — Idempotency middleware (SHA-256 payload hash, 409 on mismatch), optimistic locking on investigations, audit trail with hash-chain verification, soft delete, RLS. Evidence: `middleware/idempotency.py`, `domain/models/investigation.py`

### Top 5 Deficits (Evidence-Based)
1. **D23 Operational Runbooks (WCS 3.0, PS 13.0)** — No runbooks, no incident response plan, no on-call procedures, no escalation documentation. Only indirect evidence: rollback workflow exists. Evidence gap: `docs/runbooks/` missing.
2. **D15 Testing Strategy (WCS 5.4, PS 12.3)** — Coverage threshold 35% in CI (pyproject.toml says 50), contract tests are stubs (`pass`), many unit tests use `skip_on_import_error`, most tests verify imports not behavior. Evidence: `ci.yml`, `tests/contract/test_api_contracts.py`, `pyproject.toml`
3. **D03 Accessibility (WCS 3.0, PS 6.5)** — Only ESLint jsx-a11y plugin and Radix UI primitives. No WCAG audit, no axe-core in CI, no a11y test suite, no screen reader testing. Evidence: `frontend/package.json`
4. **D26 Cost Efficiency (WCS 3.0, PS 6.5)** — No cost optimization docs, no right-sizing evidence. Only indirect: multi-stage Docker build, resource limits, cost alert scripts. Evidence: `scripts/infra/cost_alerts.py`
5. **D06 Security Engineering (WCS 7.2, PS 6.9)** — Despite strong scanning posture, critical auth gaps: tenants module auth commented out, compliance endpoints unauthenticated, incidents/complaints lack tenant filtering (cross-tenant data exposure risk). Evidence: `src/api/routes/tenants.py`, `src/api/routes/compliance.py`, `src/api/routes/incidents.py`

### Biggest Improvement vs Prior: N/A (first assessment)
### Biggest Regression vs Prior: N/A (first assessment)

### World-Class Breach List (WCS < 9.5)
D01 (7.2), D02 (4.5), D03 (3.0), D04 (5.4), D05 (8.0), D06 (7.2), D07 (5.4), D08 (7.2), D09 (8.0), D10 (8.0), D11 (8.0), D12 (8.0), D13 (7.2), D14 (8.0), D15 (5.4), D16 (5.4), D19 (8.0), D20 (8.0), D21 (6.0), D22 (5.4), D23 (3.0), D24 (8.0), D25 (5.4), D26 (3.0), D27 (4.5), D28 (5.4), D29 (5.4), D31 (5.4), D32 (5.4)

**29 of 32 dimensions breach the 9.5 threshold. 3 dimensions at world-class: D17, D18, D30.**

---

## 2. Critical Function Map

### CF1: Authentication & Authorization Boundaries

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `src/core/security.py` (JWT), `src/core/azure_auth.py` (Azure AD), `src/api/routes/auth.py` (endpoints), `src/api/dependencies/__init__.py` (DI guards), `src/core/uat_safety.py` (write protection) |
| **Dependent Services** | Azure AD (JWKS), Redis (token blacklist), PostgreSQL (user/role store) |
| **Current Risks** | **P0**: `src/api/routes/tenants.py` — auth guards commented out on multiple endpoints; **P0**: `src/api/routes/compliance.py` — several endpoints have no authentication; **P1**: `src/api/routes/incidents.py`, `complaints.py` — no tenant_id filtering (cross-tenant data exposure); **P1**: JWT uses HS256 (symmetric) — RS256 preferred for backend-to-backend; **P2**: No token revocation check on standard endpoints (only WebSocket copilot checks blacklist) |
| **Safety Gates Required** | Auth enforcement regression test on all 48 route modules; tenant isolation integration tests; periodic auth audit script |

### CF2: Primary Business Workflows (Top 3)

| Workflow | Blast Radius | Code Locations | Dependent Services |
|----------|-------------|----------------|-------------------|
| **Incident Lifecycle** (report → investigate → action → close) | **HIGH** | `routes/incidents.py`, `routes/investigations.py`, `routes/actions.py`, `models/incident.py`, `models/investigation.py` | PostgreSQL, Email (SMTP), Azure Blob (evidence) |
| **Audit Lifecycle** (template → run → response → finding → CAPA) | **HIGH** | `routes/audits.py`, `routes/capa.py`, `services/audit_service.py`, `models/audit.py` | PostgreSQL, AI (Gemini for question gen) |
| **Risk Assessment** (identify → assess → control → monitor → report) | **MEDIUM** | `routes/risk_register.py`, `services/risk_scoring.py`, `models/risk_register.py` | PostgreSQL, Analytics (dashboards) |

### CF3: Data Writes + State Transitions

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `middleware/idempotency.py` (POST dedup), `models/investigation.py` (optimistic locking), `services/workflow_engine.py` (state machine), `routes/capa.py` (CAPA state transitions), `routes/audits.py` (audit lifecycle states) |
| **Current Risks** | **P1**: Actions module uses in-memory pagination across 6 entity types — data loss risk on large datasets; **P1**: No explicit idempotency on PUT/PATCH (only POST with header); **P2**: Some write endpoints lack audit trail calls |

### CF4: External Integrations

| Integration | Blast Radius | Code Location | Current Risks |
|------------|-------------|---------------|---------------|
| Azure AD (SSO) | HIGH | `core/azure_auth.py` | JWKS cache TTL 1hr — no circuit breaker on JWKS fetch |
| Azure Blob Storage | MEDIUM | `infrastructure/storage.py` | Fallback to local FS in dev — no parity test |
| Email (IMAP/SMTP) | MEDIUM | `domain/services/email_service.py`, `tasks/email_tasks.py` | Retry 3x with backoff — adequate; no DLQ for email failures |
| Google Gemini AI | LOW | `domain/services/ai_*.py` | Non-critical path — failures don't block workflows |
| Redis | MEDIUM | `infrastructure/cache/redis_cache.py`, `tasks/celery_app.py` | Graceful fallback to in-memory — good; Celery broker failure = task queue outage |
| Push Notifications | LOW | `tasks/notification_tasks.py` | pywebpush VAPID — non-critical |

### CF5: Release/Deploy + Rollback

| Attribute | Detail |
|-----------|--------|
| **Blast Radius** | **HIGH** |
| **Code Locations** | `.github/workflows/deploy-staging.yml`, `deploy-production.yml`, `rollback-production.yml`, `scripts/verify_deploy_deterministic.sh`, `scripts/governance/validate_release_signoff.py` |
| **Current Risks** | **P2**: Rollback workflow exists but no evidence of regular drill execution; **P2**: ACI migration container — no rollback migration verification in CI |
| **Safety Gates** | Release signoff validation (governance lead + CAB), deterministic SHA verification (3 consecutive matches), 5-phase deploy proof, post-deploy security checks |

---

## 3. Scorecard Table

| ID | Dimension | Mat. (0-5) | WCS (0-10) | CM | Ev. Strength | Prev | Delta | WCS Gap | CW | PS | Effort | Value | Evidence Pointers |
|----|-----------|-----------|-----------|-----|-------------|------|-------|---------|----|----|--------|-------|-------------------|
| D01 | Product clarity & user journeys | 4 | 7.2 | 0.9 | Medium | N/A | N/A | 2.3 | 2 | 4.6 | M | M | README.md, main.py (21 OpenAPI tags), frontend/App.tsx (82 routes), STAGE2_COVENANTS.md |
| D02 | UX quality & IA | 3 | 4.5 | 0.75 | Weak | N/A | N/A | 5.0 | 1 | 5.0 | L | M | frontend/package.json (Radix UI, Framer Motion), App.tsx (route groups, error boundaries) |
| D03 | Accessibility | 2 | 3.0 | 0.75 | Weak | N/A | N/A | 6.5 | 1 | 6.5 | M | H | frontend/package.json (eslint-plugin-jsx-a11y), App.tsx (AccessibilityProvider) |
| D04 | Performance (FE+BE) | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | L | H | database.py (pool config), main.py (OpenAPI pre-warm), ci.yml (performance-budget), cache/redis_cache.py |
| D05 | Reliability & resilience | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 3 | 4.5 | M | H | infrastructure/resilience/, tasks/dlq.py, main.py (health probes), Dockerfile (HEALTHCHECK) |
| D06 | Security engineering | 4 | 7.2 | 0.9 | Strong | N/A | N/A | 2.3 | 3 | 6.9 | S | H | main.py (security headers), .semgrep.yml, SECURITY.md, encryption/, tenants.py (auth gap), compliance.py (auth gap) |
| D07 | Privacy & data protection | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | M | H | config.py (pseudonymization), logging/PIIFilter, encryption/, evidence_asset.py (PII flagging) |
| D08 | Compliance readiness | 4 | 7.2 | 0.9 | Medium | N/A | N/A | 2.3 | 2 | 4.6 | M | M | models/iso27001.py, ims_unification.py, planet_mark.py, uvdb_achilles.py, loler.py |
| D09 | Architecture modularity | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | M | M | Project structure, api/__init__.py, pyproject.toml (27 mypy overrides) |
| D10 | API design quality | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | S | M | main.py (OpenAPI), api/__init__.py, middleware/idempotency.py, check_api_path_drift.py |
| D11 | Data model quality | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | M | M | domain/models/ (27 files), base.py (4 mixins), CaseInsensitiveEnum |
| D12 | Schema versioning & migrations | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | S | M | alembic.ini, alembic/env.py, 62 migrations, ci.yml (migration runs) |
| D13 | Observability | 4 | 7.2 | 0.9 | Medium | N/A | N/A | 2.3 | 2 | 4.6 | M | H | monitoring/azure_monitor.py (26+ metrics), logging/, core/middleware.py (request_id) |
| D14 | Error handling & user-safe failures | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 3 | 4.5 | S | M | middleware/error_handler.py, infrastructure/resilience/, main.py (readiness 503) |
| D15 | Testing strategy | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 3 | 12.3 | L | H | pyproject.toml (coverage 50/35), ci.yml (7 test jobs), tests/conftest.py, contract tests = stubs |
| D16 | Test data & fixtures | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | M | M | tests/factories/core.py (9 factories), tests/conftest.py, tests/uat/conftest.py |
| D17 | CI quality gates | 5 | 10.0 | 1.0 | Strong | N/A | N/A | 0.0 | 3 | 0.0 | — | — | ci.yml (21+ jobs, final all-checks gate), scripts/ (12+ validation scripts) |
| D18 | CD/release pipeline | 5 | 10.0 | 1.0 | Strong | N/A | N/A | 0.0 | 3 | 0.0 | — | — | deploy-staging.yml, deploy-production.yml, rollback-production.yml, deploy proof v3 |
| D19 | Configuration management | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | S | M | core/config.py (production validation), .env.example, feature_flag.py, verify_env_sync.py |
| D20 | Dependency management | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 2 | 3.0 | S | M | requirements.txt, Dockerfile (lockfile-first), dependabot.yml, ci.yml (sbom, pip-audit) |
| D21 | Code quality & maintainability | 3 | 6.0 | 1.0 | Strong | N/A | N/A | 3.5 | 2 | 7.0 | L | H | pyproject.toml (27 mypy overrides = GOVPLAT-004), .semgrep.yml, validate_type_ignores.py |
| D22 | Documentation quality | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | M | H | README.md, CONTRIBUTING.md, SECURITY.md, STAGE2_COVENANTS.md, missing: ADRs, CHANGELOG |
| D23 | Operational runbooks | 2 | 3.0 | 0.75 | Weak | N/A | N/A | 6.5 | 2 | 13.0 | M | H | rollback-production.yml, scripts/governance/rollback_drill.py (indirect only) |
| D24 | Data integrity & consistency | 4 | 8.0 | 1.0 | Strong | N/A | N/A | 1.5 | 3 | 4.5 | S | M | middleware/idempotency.py, investigation.py (optimistic lock), audit_trail.py (hash chain) |
| D25 | Scalability & capacity | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 1 | 4.1 | L | M | database.py (pooling), cache/, resilience/ (bulkhead), scripts/infra/autoscaling.py |
| D26 | Cost efficiency | 2 | 3.0 | 0.75 | Weak | N/A | N/A | 6.5 | 1 | 6.5 | M | L | Dockerfile (multi-stage), docker-compose.yml (limits), scripts/infra/cost_alerts.py |
| D27 | I18n/L10n readiness | 3 | 4.5 | 0.75 | Weak | N/A | N/A | 5.0 | 1 | 5.0 | M | L | frontend/package.json (i18next), scripts/i18n-check.mjs, no backend i18n |
| D28 | Analytics/telemetry | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 1 | 4.1 | M | M | monitoring/azure_monitor.py (26+ metrics), routes/telemetry.py, web-vitals |
| D29 | Governance & decision records | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | S | H | STAGE2_COVENANTS.md, release_signoff.json, ci.yml (governance jobs), ADRs referenced but missing |
| D30 | Build determinism | 5 | 10.0 | 1.0 | Strong | N/A | N/A | 0.0 | 3 | 0.0 | — | — | Dockerfile (digest pin), verify_deploy_deterministic.sh, ci.yml (sbom, lockfile) |
| D31 | Environment parity | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | M | M | docker-compose.yml, docker-compose.sandbox.yml (PG15 vs PG16), environment_endpoints.json |
| D32 | Supportability & operability | 3 | 5.4 | 0.9 | Medium | N/A | N/A | 4.1 | 2 | 8.2 | M | M | main.py (health probes, /meta/version), logging/, audit_trail.py, no ops docs |

---

## 4. Findings Register (P0/P1)

### F-001 — Tenants Module Authentication Disabled
- **Priority**: P0
- **Linked CF**: CF1 (Auth/Authorization)
- **Dimensions**: D06 (Security)
- **Impact**: Any unauthenticated user could create/modify/delete tenants, access tenant user lists, modify branding and feature flags. Complete multi-tenancy bypass.
- **Evidence**: `src/api/routes/tenants.py` — multiple endpoint functions lack `current_user: User = Depends(get_current_active_user)` parameter; auth dependency imports present but commented out or unused on several endpoints.
- **Root Cause**: Auth guards were likely commented out during development/debugging and never restored.
- **Containment**: Add `CurrentActiveUser` dependency to ALL tenant endpoints immediately. Add `CurrentSuperuser` to create/delete/modify tenant endpoints.
- **Fix**: Restore auth guards on all tenant endpoints; add integration test asserting 401 on unauthenticated access; add CI regression test.
- **Tests/Validation**: `test_tenants_require_auth()` — verify all tenant endpoints return 401 without token; verify 403 for non-superuser on admin endpoints.
- **Observability**: Add `tenant.auth_bypass_attempt` counter metric; alert on any unauthenticated tenant API access.
- **Risk of Change**: LOW — adding auth guards is additive, non-breaking.
- **Rollback**: Remove auth guards (revert commit).

### F-002 — Compliance Endpoints Missing Authentication
- **Priority**: P0
- **Linked CF**: CF1 (Auth/Authorization)
- **Dimensions**: D06 (Security)
- **Impact**: ISO clause data, auto-tag results, and compliance coverage data accessible without authentication. Information disclosure risk for compliance posture.
- **Evidence**: `src/api/routes/compliance.py` — clauses listing, auto-tag, and coverage endpoints lack `CurrentUser` dependency.
- **Root Cause**: Endpoints may have been designed as "public" reference data but expose compliance posture which is sensitive.
- **Containment**: Add `CurrentUser` dependency to all compliance endpoints.
- **Fix**: Add authentication; if public access is intended for some endpoints, create explicit public/private split with documentation.
- **Tests/Validation**: `test_compliance_endpoints_require_auth()` — verify 401 without token.
- **Observability**: Log unauthenticated compliance access attempts.
- **Risk of Change**: LOW — may break frontend calls that don't send auth header; verify frontend sends JWT on compliance API calls.
- **Rollback**: Revert auth requirement if frontend breaks; fix frontend first.

### F-003 — Cross-Tenant Data Exposure (Incidents/Complaints)
- **Priority**: P0
- **Linked CF**: CF1, CF2
- **Dimensions**: D06 (Security), D07 (Privacy)
- **Impact**: Authenticated users in Tenant A could potentially query incidents/complaints from Tenant B. GDPR breach risk if PII is exposed.
- **Evidence**: `src/api/routes/incidents.py`, `src/api/routes/complaints.py` — list endpoints query by user email filter but do not filter by `current_user.tenant_id`. Compare with `src/api/routes/audits.py` which correctly applies `tenant_id` filtering.
- **Root Cause**: Tenant isolation was added to newer modules (audits, risk register) but not retrofitted to earlier modules.
- **Containment**: Add `tenant_id` filter to all incident and complaint queries: `.filter(Incident.tenant_id == current_user.tenant_id)`.
- **Fix**: Audit ALL route modules for tenant isolation; add `TenantScopedQuery` mixin or middleware.
- **Tests/Validation**: Multi-tenant integration test: create incidents in Tenant A and B, verify Tenant A user cannot see Tenant B data.
- **Observability**: Add `tenant.cross_tenant_query_attempt` metric; log and alert.
- **Risk of Change**: MEDIUM — may surface bugs if existing data has null tenant_id.
- **Rollback**: Remove tenant filter; run data migration to backfill null tenant_ids first.

### F-004 — Coverage Threshold Mismatch (pyproject.toml vs CI)
- **Priority**: P1
- **Linked CF**: CF5 (Release)
- **Dimensions**: D15 (Testing), D17 (CI)
- **Impact**: `pyproject.toml` sets `fail_under = 50` but CI enforces `--cov-fail-under=35`. The lower CI threshold is the effective gate, creating a false sense of coverage discipline. Test suite primarily verifies imports, not behavior.
- **Evidence**: `pyproject.toml` line 214: `fail_under = 50`; `ci.yml` unit-tests job: `--cov-fail-under=35`.
- **Root Cause**: Threshold was lowered in CI to unblock pipeline during rapid development; never restored.
- **Containment**: Align CI threshold to match `pyproject.toml` (`fail_under = 50`).
- **Fix**: Progressively raise coverage: 50% → 60% → 70% over 3 sprints; add behavioral tests for critical paths.
- **Tests/Validation**: CI pipeline must fail when coverage drops below threshold.
- **Observability**: Track coverage trend in quality trend report.
- **Risk of Change**: MEDIUM — raising threshold may block CI until new tests are written.
- **Rollback**: Lower threshold back to 35 if blocking.

### F-005 — Contract Tests Are Stubs
- **Priority**: P1
- **Linked CF**: CF2, CF4
- **Dimensions**: D15 (Testing), D10 (API Design)
- **Impact**: No contract stability verification between frontend and backend. API breaking changes could reach production without detection.
- **Evidence**: `tests/contract/test_api_contracts.py` — functions contain only `pass` statements.
- **Root Cause**: Contract testing was planned but implementation deferred.
- **Containment**: Implement contract tests for top 10 most-used endpoints (auth, incidents, audits, users, complaints).
- **Fix**: Generate contract schemas from OpenAPI spec; validate frontend API calls match contracts; run nightly.
- **Tests/Validation**: Contract tests must fail when endpoint schema changes incompatibly.
- **Observability**: CI job `contract-tests` already exists — populate it.
- **Risk of Change**: LOW — additive.
- **Rollback**: N/A (additive).

### F-006 — Test Harness Drift (skip_on_import_error)
- **Priority**: P1
- **Linked CF**: CF2, CF5
- **Dimensions**: D15 (Testing), D21 (Code Quality)
- **Impact**: Tests silently skip when imports fail due to model/API changes. Effective test count may be lower than reported. CI pass rate is misleading.
- **Evidence**: `tests/unit/test_models.py`, `test_services.py` — extensive use of `skip_on_import_error` and `skip_on_missing_enum` decorators.
- **Root Cause**: Models evolved faster than test updates; skip decorators were added as a workaround.
- **Containment**: Audit all skipped tests; fix import paths; remove skip decorators.
- **Fix**: Add CI check: count of skipped tests must not increase; existing skips must have linked tickets.
- **Tests/Validation**: Zero skipped tests in unit suite (or all skips have justification tickets).
- **Observability**: Report skipped test count in quality trend.
- **Risk of Change**: LOW — fixing imports is mechanical.
- **Rollback**: Re-add skip decorators if needed.

### F-007 — Missing ADR Documents
- **Priority**: P1
- **Linked CF**: CF5
- **Dimensions**: D29 (Governance), D22 (Documentation)
- **Impact**: ADR-0001 and ADR-0002 are referenced in code and CI but the actual documents don't exist. Decision rationale is lost; new team members lack architectural context.
- **Evidence**: `test_config_failfast.py` references ADR-0002; `prod-dependencies-gate.sh` references ADR-0001; `main.py` `/readyz` docstring references ADR-0003. No `docs/adr/` directory found.
- **Root Cause**: Decisions were made and referenced in code but formal documents were never written.
- **Containment**: Create `docs/adr/` directory with ADR-0001 through ADR-0003 based on code references.
- **Fix**: Write retrospective ADRs; establish ADR template and process in CONTRIBUTING.md.
- **Tests/Validation**: CI check: all ADR references in code have corresponding `docs/adr/ADR-NNNN.md` files.
- **Observability**: N/A (documentation artifact).
- **Risk of Change**: LOW — additive documentation.
- **Rollback**: N/A.

### F-008 — Mypy Type Safety Debt (GOVPLAT-004)
- **Priority**: P1
- **Linked CF**: CF2, CF3
- **Dimensions**: D21 (Code Quality), D09 (Architecture)
- **Impact**: 27 modules have mypy error codes disabled via `pyproject.toml` overrides. Type errors in these modules (attr-defined, arg-type, return-value, union-attr) indicate potential runtime bugs, especially in AI services, workflow engine, risk scoring, and route handlers.
- **Evidence**: `pyproject.toml` lines 50-198 — 27 `[[tool.mypy.overrides]]` blocks tagged GOVPLAT-004.
- **Root Cause**: Rapid feature development outpaced type annotation effort; overrides added to unblock CI.
- **Containment**: Prioritize fixing type errors in critical-path modules: `workflow_engine.py`, `risk_scoring.py`, `audit_service.py`.
- **Fix**: Resolve type errors module by module; remove overrides; set ceiling on override count.
- **Tests/Validation**: mypy CI job must pass with progressively fewer overrides.
- **Observability**: Track override count in quality trend report.
- **Risk of Change**: LOW to MEDIUM — type fixes may reveal actual bugs.
- **Rollback**: Re-add override for specific module if fix causes regression.

---

## 5. Evidence Gaps

| # | What's Missing | Why It Blocks | Where It Should Live | Minimal Content |
|---|---------------|--------------|---------------------|-----------------|
| EG-01 | User journey maps / persona docs | Blocks D01 confidence to Strong | `docs/user-journeys/` | Persona definitions, top 5 journey maps with steps, decision points, error paths |
| EG-02 | WCAG audit report / a11y test results | Blocks D03 scoring above 2 | `docs/accessibility/` | axe-core scan results, WCAG 2.1 AA checklist, remediation plan |
| EG-03 | Load test results / performance benchmarks | Blocks D04/D25 confidence | `docs/performance/` | k6/Locust results for top 5 endpoints, P95 latency, throughput, error rates |
| EG-04 | DPIA / data classification policy | Blocks D07 scoring above 3 | `docs/privacy/` | Data inventory, classification levels, DPIA for incident/complaint PII, DSAR process |
| EG-05 | ADR documents (0001-0003+) | Blocks D29 scoring above 3 | `docs/adr/` | ADR template, retrospective ADRs for referenced decisions |
| EG-06 | Operational runbooks | Blocks D23 scoring above 2 | `docs/runbooks/` | Incident response, escalation, DB recovery, deployment, rollback procedures |
| EG-07 | CHANGELOG | Blocks D22/D29 | `CHANGELOG.md` | Keep-a-changelog format, retroactive entries for major versions |
| EG-08 | External audit/certification reports | Blocks D08 confidence | `docs/compliance/` | ISO certification status, external audit findings, remediation tracking |
| EG-09 | Cost analysis / FinOps report | Blocks D26 scoring above 2 | `docs/cost/` | Azure spend breakdown, right-sizing analysis, cost optimization plan |
| EG-10 | SLO/SLI definitions | Blocks D13 scoring above 4 | `docs/observability/` | SLO targets per CF (availability, latency, error rate), SLI definitions, error budgets |

---

## Appendix A: Contradictions Resolver

### C-001 — Coverage Threshold Contradiction
- **Docs say**: `pyproject.toml` `fail_under = 50`
- **Code does**: `ci.yml` enforces `--cov-fail-under=35`
- **Resolution**: Align to 50 (the documented standard); treat as P1 item (F-004)

### C-002 — Postgres Version Mismatch
- **Docs say**: README specifies PostgreSQL 16+
- **Code does**: `docker-compose.sandbox.yml` uses `postgres:15-alpine`
- **Resolution**: Update sandbox to `postgres:16-alpine`; treat as P2 item

### C-003 — alembic.ini Placeholder URL
- **Docs say**: alembic.ini has `sqlalchemy.url = driver://user:pass@localhost/dbname`
- **Code does**: `alembic/env.py` overrides URL from settings at runtime
- **Resolution**: Document in alembic.ini that URL is overridden; low risk but confusing for new devs
