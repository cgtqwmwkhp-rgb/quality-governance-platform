# Fortune 500 Production Readiness Audit Plan

**Audit Date**: 2026-01-19  
**Auditor**: AI Fortune-500 Production Readiness Auditor  
**Status**: IN PROGRESS

---

## 1. CONTEXT

### 1.1 Repository
- **Repo**: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform
- **Default Branch**: main
- **Current Commit**: a9e4c1e (after QA hardening PRs #32, #33)

### 1.2 Application Stack
| Component | Technology |
|-----------|------------|
| Backend Framework | FastAPI (Python 3.11) |
| ORM | SQLAlchemy 2.0 + SQLModel |
| Database | PostgreSQL 16 (async via asyncpg) |
| Authentication | JWT (PyJWT) + bcrypt |
| Migrations | Alembic |
| Container | Docker (Python 3.11-slim) |
| Cloud | Azure (App Service, Container Registry, Key Vault) |
| Frontend | React/TypeScript (Azure Static Web Apps) |

### 1.3 Environments
| Environment | URL | Key Vault | Resource Group |
|-------------|-----|-----------|----------------|
| Staging | https://${AZURE_WEBAPP_NAME}.azurewebsites.net | kv-qgp-staging | rg-qgp-staging |
| Production | https://${PROD_AZURE_WEBAPP_NAME}.azurewebsites.net | kv-qgp-prod | rg-qgp-prod |

### 1.4 CI/CD System
- **Platform**: GitHub Actions
- **Workflows**:
  - `ci.yml` - Code quality, tests, security scan (8 gates)
  - `deploy-staging.yml` - Auto-deploy to staging on main push
  - `deploy-production.yml` - Manual approval + release tags
  - `azure-static-web-apps-*.yml` - Frontend deployment

---

## 2. SCOPE

### 2.1 IN SCOPE
- Backend API (`src/`)
- Database migrations (`alembic/`)
- CI/CD pipelines (`.github/workflows/`)
- Existing tests (`tests/`)
- Deployment manifests and scripts
- Security configuration
- Health/readiness probes

### 2.2 OUT OF SCOPE
- Frontend application (separate SPA)
- Azure infrastructure provisioning (IaC)
- Third-party integrations (email ingestion, blob storage) beyond config validation

---

## 3. CRITICAL USER JOURNEYS (TOP 10)

| # | Journey | API Endpoints | Current Test Coverage |
|---|---------|---------------|----------------------|
| 1 | **User Authentication** | POST /auth/login, GET /auth/me, POST /auth/refresh | Unit: ✅ Integration: ⚠️ |
| 2 | **Incident CRUD + Audit Trail** | POST/GET/PATCH/DELETE /incidents | Unit: ✅ Integration: ✅ |
| 3 | **Complaint CRUD + Status Tracking** | POST/GET/PATCH /complaints | Unit: ✅ Integration: ✅ |
| 4 | **Risk Assessment CRUD** | POST/GET/PATCH/DELETE /risks | Unit: ✅ Integration: ✅ |
| 5 | **Policy Lifecycle Management** | POST/GET/PATCH /policies | Unit: ✅ Integration: ✅ |
| 6 | **Standards Library Management** | POST/GET/PATCH /standards | Unit: ⚠️ Integration: ✅ |
| 7 | **Audit Template + Run Execution** | CRUD /audits/templates, /audits/runs | Unit: ⚠️ Integration: ✅ |
| 8 | **RTA (Root Cause Analysis) Workflow** | CRUD /rtas | Unit: ✅ Integration: ✅ |
| 9 | **Investigation Template + Execution** | CRUD /investigations | Unit: ⚠️ Integration: ✅ |
| 10 | **Employee Self-Service Portal** | POST /portal/report, GET /portal/track | Unit: ⚠️ Integration: ⚠️ |

---

## 4. TEST COMMANDS

### 4.1 Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term --cov-report=xml

# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Specific test file
pytest tests/integration/test_incident_api.py -v
```

### 4.2 Code Quality
```bash
# Format check
black --check src/ tests/
isort --check-only src/ tests/

# Lint
flake8 src/ tests/

# Type check
mypy src/ --ignore-missing-imports
```

### 4.3 Security Scan
```bash
# Dependency audit
pip-audit -r requirements.txt

# Static analysis
bandit -r src/ -ll
```

### 4.4 CI Gates (as per ci.yml)
1. code-quality
2. config-failfast-proof
3. unit-tests
4. integration-tests
5. security-scan
6. build-check
7. ci-security-covenant
8. all-checks

---

## 5. EVIDENCE SOURCES

| Source | Location | Purpose |
|--------|----------|---------|
| CI Runs | GitHub Actions | Verify gate status, test results |
| Test Reports | junit-*.xml (CI artifacts) | Detailed test outcomes |
| Coverage Reports | coverage.xml (CI artifacts) | Code coverage metrics |
| Code Quality | black/isort/flake8/mypy output | Style/type compliance |
| Security Scans | pip-audit/bandit output | Vulnerability detection |
| Application Logs | Azure App Service logs | Runtime behavior |
| Health Endpoints | /healthz, /readyz | Deployment verification |
| OpenAPI Spec | /openapi.json | Contract compliance |

---

## 6. STOP CONDITIONS

### 6.1 Success Criteria (ALL must be true)
- [ ] All 10 critical journeys have automated test coverage
- [ ] All 8 CI gates pass on main branch
- [ ] No S0/S1 issues remain unfixed
- [ ] Smoke tests defined and runnable post-deploy
- [ ] Each identified issue has: reproduction → RCA → fix → tests → verification

### 6.2 Blocking Conditions
If blocked by missing access, document:
- What is blocked
- Why it's blocked
- Minimum access/data needed
- Highest-value work completed regardless

---

## 7. AUDIT EXECUTION STAGES

### Stage 0 — Pre-Flight + Audit Plan ✅
- [x] Repository context confirmed
- [x] Stack and environments documented
- [x] Critical journeys identified
- [x] Test commands documented
- [x] Audit plan created

### Stage 1 — Baseline Health (IN PROGRESS)
- [ ] Local build/run verification
- [ ] CI workflow inspection
- [ ] Gate status assessment
- [ ] Baseline health report

### Stage 2 — Functional E2E Validation
- [ ] Journey mapping (frontend → API → DB)
- [ ] Test coverage analysis per journey
- [ ] Gap identification
- [ ] Test additions/improvements

### Stage 3 — Non-Functional + Production Readiness
- [ ] Reliability/resilience review
- [ ] Performance review
- [ ] Security review
- [ ] Observability review
- [ ] Ops readiness review

### Stage 4 — Issue Register + RCA
- [ ] Issue register creation
- [ ] Root cause analysis
- [ ] Fix prioritization

### Stage 5 — Fix Implementation
- [ ] Implement fixes (smallest safe)
- [ ] Add/repair tests
- [ ] Update documentation

### Stage 6 — GitHub PR Workflow + Verification
- [ ] Create PRs with full context
- [ ] Ensure CI passes
- [ ] Define smoke checklists

### Stage 7 — Final Pack
- [ ] Executive summary
- [ ] Engineering pack
- [ ] Sign-off

---

## 8. CURRENT STATUS

**Stage**: 0 → 1 (Transitioning to Baseline Health)

**Next Actions**:
1. Run full test suite locally (via CI proxy since local Python is 3.9)
2. Inspect all CI workflow gates
3. Identify missing gates and coverage gaps
4. Produce Baseline Health Report

---

*Document Version: 1.0*  
*Last Updated: 2026-01-19T09:30:00Z*
