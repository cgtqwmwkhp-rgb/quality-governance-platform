# Test Strategy (D15)

This document defines how the Quality Governance Platform plans, layers, and gates automated testing. It aligns the **test pyramid**, repository layout, coverage roadmap, data discipline, CI enforcement, flakiness handling, mutation testing, and property-based testing with the existing codebase and pipelines.

---

## 1. Test pyramid (target mix)

We target the following **effort and suite composition** (not a strict line count): a strong unit base, a meaningful integration middle, and a smaller, high-value E2E/UAT slice.

| Layer | Target share | Purpose |
|--------|----------------|--------|
| **Unit** | **60%** | Fast feedback on domain logic, services, and pure functions without I/O. |
| **Integration** | **25%** | API + database + Redis + migrations; validates wiring and contracts against real dependencies where practical. |
| **E2E + UAT** | **15%** (combined) | End-user journeys, acceptance scenarios, and regression gates on critical workflows. |

**Rationale:** Unit tests keep cost per change low. Integration tests catch ORM, auth, and middleware issues. E2E/UAT are expensive; we keep them focused on governance-critical paths and baseline-backed gates.

---

## 2. Test layers (repository layout)

Tests are organised under `tests/` by concern. **Use these directories** (create suites here; do not scatter ad-hoc roots):

| Directory | Role |
|-----------|------|
| `tests/unit/` | Isolated tests; mocks/stubs for external systems; fastest feedback. |
| `tests/integration/` | Postgres + Redis (where applicable), Alembic, HTTP/API against the app. |
| `tests/e2e/` | Full journeys; baseline expectations documented under `docs/evidence/e2e_baseline.json`. |
| `tests/uat/` | User acceptance stages (e.g. staged workflow suites). |
| `tests/smoke/` | Post-deploy-critical checks; minimal path validation. |
| `tests/contract/` | API/OpenAPI and consumer-oriented contract checks. |
| `tests/performance/` | Load, latency budgets, or backend performance scenarios (complements frontend bundle/Lighthouse gates in CI). |

Shared configuration lives in `tests/conftest.py`. Integration-specific client and auth fixtures live in `tests/integration/conftest.py`.

---

## 3. Coverage targets

| Milestone | Line coverage (approx.) | Notes |
|-----------|-------------------------|--------|
| **Current (baseline)** | **48%** | Measured 2026-04-03; up from 38% historical baseline. Enforced via `pyproject.toml` and CI unit/integration cov gates. |
| **Q2 2026** | **50%** | Focus on high-risk domain services and auth paths. |
| **Q3 2026** | **60%** | Broaden route and infrastructure coverage; reduce “hot spot” modules. |
| **Q4 2026** | **70%** | Sustainable plateau with mutation and property tests on critical code. |

Local and PR workflows should use `coverage` / `pytest-cov` with `source = ["src"]` as configured in `pyproject.toml`.

---

## 4. Coverage progression plan — top 10 priority modules

The following modules are **prioritised for new tests** based on **compliance risk**, **security impact**, and **historical concentration of complexity** (many appear in type-safety remediation tracking). Re-run `coverage report --skip-covered` periodically to **replace** this list with data-driven ordering.

| Priority | Module | Rationale |
|----------|--------|-----------|
| P1 | `src.domain.services.auth_service` | Authentication and session safety are merge-critical. |
| P2 | `src.domain.services.workflow_service` | Core IMS process orchestration. |
| P3 | `src.services.workflow_engine` | Engine behaviour affects multi-step governance flows. |
| P4 | `src.domain.services.audit_service` | Audit evidence and ISO traceability. |
| P5 | `src.domain.services.risk_service` | Risk register integrity and scoring. |
| P6 | `src.api.routes.compliance` | Compliance surface area exposed to users and auditors. |
| P7 | `src.domain.services.xml_importer_service` | Data import boundaries and validation. |
| P8 | `src.domain.services.gdpr_service` | Privacy and data-subject operations. |
| P9 | `src.infrastructure.tasks.pams_sync_tasks` | Async integration; failure modes must be observable. |
| P10 | `src.api.routes.audits` | High-traffic audit execution APIs. |

**Plan:** For each module, add **unit tests** for branches and invariants, then **integration tests** for persistence and API contracts. Link tests to issues when coverage is deferred.

---

## 5. Test naming convention

All new tests MUST follow:

```text
test_{module}_{scenario}_{expected_outcome}
```

**Examples:**

- `test_auth_service_expired_token_rejects_with_401`
- `test_risk_service_closed_risk_cannot_transition_to_open`

Apply this to **function names** in `test_*.py` files. For class-based tests, keep the class name stable (`TestRiskService`) and use the pattern on each **test method**.

---

## 6. Test data strategy

| Mechanism | Location / usage |
|-----------|------------------|
| **Factories** | `tests/factories/core.py` — Factory Boy models for core domain entities; use `.build()` for in-memory and `.create()` when persisted. Timestamps and sequences are **deterministic** (fixed epoch, `factory.Sequence`) for reproducible assertions. |
| **Async helpers** | `tests/factories/async_helpers.py` (when using async DB sessions) — use alongside factories for integration tests. |
| **Golden / baseline datasets** | **E2E:** `docs/evidence/e2e_baseline.json` — pass-count baseline for CI regression gate. **OpenAPI:** `openapi-baseline.json` (when committed) for contract compatibility. **Evidence packs:** under `docs/evidence/` as required by governance scripts. |
| **Deterministic fixtures** | Prefer explicit values over random data; avoid non-seeded randomness in assertions. Use environment-driven config only via well-known test env vars (see `tests/conftest.py` `TestConfig`). |

**Rules:** No production data in tests. Do not bypass factory discipline for “quick” dicts unless the test is explicitly about raw payload shape.

---

## 7. CI integration

### 7.1 Workflow

Primary continuous integration is **`.github/workflows/ci.yml`** (workflow name: `CI`), triggered on `push` and `pull_request` to `main` and `develop`.

### 7.2 Jobs (25)

The `CI` workflow defines **25 jobs** (names as shown in GitHub Actions):

1. Code Quality  
2. Workflow Lint (actionlint)  
3. Smoke Gate Self-Test  
4. Configuration Drift Guard  
5. ADR-0002 Fail-Fast Proof  
6. Unit Tests  
7. Frontend Tests  
8. SBOM Generation  
9. Lockfile Freshness Check  
10. Integration Tests  
11. Security Scan  
12. Build Check  
13. CI Security Covenant (Stage 2.0)  
14. Smoke Tests (CRITICAL)  
15. End-to-End Tests  
16. UAT Tests (User Acceptance)  
17. API Path Drift Prevention  
18. Quality Trend Report  
19. OpenAPI Contract Stability  
20. Audit Acceptance Artifacts Gate  
21. Performance Budget (PR-04)  
22. API Contract Tests  
23. Dependency Review  
24. Secret Scanning (Gitleaks)  
25. All Checks Passed  

Deploy workflows (e.g. staging/production) are **separate** and depend on a green `CI` conclusion where configured.

### 7.3 Coverage gates

- **Unit Tests** job: `pytest tests/unit/` with `--cov=src`, XML/term reports, and an explicit **`--cov-fail-under`** (see `.github/workflows/ci.yml`; **keep this in sync** with `[tool.coverage.report] fail_under` in `pyproject.toml` when ratcheting).
- **Integration Tests** job: `pytest tests/integration/` with coverage reporting and its own **`--cov-fail-under`** threshold.
- **`[tool.coverage.report]`** in `pyproject.toml` sets the default **`fail_under`** for local `coverage` / `pytest-cov` runs when no CLI override is passed (**45%** as of D15).

### 7.4 JUnit XML artifacts

Python pytest jobs emit JUnit XML for trend and audit consumption, including:

- `junit-unit.xml` → artifact `junit-unit-tests`  
- `junit-integration.xml` → artifact `junit-integration-tests`  
- `junit-smoke.xml` → artifact `junit-smoke-tests`  
- `junit-e2e.xml` → artifact `junit-e2e-tests`  
- UAT: `junit-uat-stage1.xml`, `junit-uat-stage2.xml` → artifact `uat-test-results`  

Frontend tests use Vitest with coverage as configured in `frontend/`.

### 7.5 Other gates

- **Codecov** uploads from unit/integration jobs (`codecov/codecov-action`) with flags.  
- **Quarantine validation:** `scripts/validate_quarantine.py` in the integration job.  
- **E2E baseline gate:** compares pass counts against `docs/evidence/e2e_baseline.json`.

---

## 8. Flakiness policy

| Timebox | Action |
|---------|--------|
| **Within 24 hours** | **Quarantine** any test that flakes on `main` or blocks merges: document in **`docs/TEST_QUARANTINE_POLICY.md`**, add a tracked GitHub issue, and mark with `@pytest.mark.skip(reason="Quarantined - … see docs/TEST_QUARANTINE_POLICY.md")`. CI validates skips against that document. |
| **Within 1 sprint** | **Fix or remove** the root cause: stabilise async/DB/session usage, tighten fixtures, or delete obsolete scenarios. |

**Non-negotiable:** Undocumented skips fail CI. The merge gate remains strict for all non-quarantined tests in `tests/integration/` per the policy.

---

## 9. Mutation testing plan (Python)

| Item | Decision |
|------|----------|
| **Tool** | **mutmut** for Python sources under `src/`. |
| **Scope (phase 1)** | Critical packages: `src.domain.services`, selected `src.api.routes`, and auth/workflow helpers. |
| **Target** | **≥ 70% mutation score** on included modules (incremental: 40% → 55% → 70% by quarter). |
| **Execution** | Run locally and optionally as a scheduled (non-blocking) workflow; do not block every PR until the score is stable. |
| **Killed vs survived** | Survived mutants must yield new tests or explicit `# pragma: no cover` with justification (rare). |

---

## 10. Property-based testing plan (Hypothesis)

| Item | Decision |
|------|----------|
| **Tool** | **hypothesis** for Python. |
| **Focus** | Boundary and edge cases on **critical services**: validation parsers, state machines (e.g. workflow transitions), scoring/risk calculations, date/window logic, and redaction/anonymisation. |
| **Style** | Prefer `@given` strategies colocated with unit tests; keep examples minimal and use `example()` for regressions. |
| **Determinism** | Use `settings(max_examples=…, derandomize=True)` (or CI env profile) for stable CI runs. |
| **Integration** | Use property tests sparingly in integration tests (slower); favour pure functions and service methods in unit tests. |

---

## 11. Ownership and review

- **Engineering** owns unit and integration coverage for features they ship.  
- **QA / governance** owns UAT scenario catalogues and baseline updates (`e2e_baseline.json`) with engineering review.  
- **This document** should be reviewed when coverage gates change or when CI jobs are added/removed.

**Document version:** 1.0 (D15)  
**Last updated:** 2026-03-21
