# ADR-0001: Disciplined Database Migrations and CI-Enforced Quality Gates

**Date**: 2026-01-04

**Status**: Accepted

## Context

The Quality Governance Platform lacked a formal release governance process. Key gaps identified were:

1.  **No Migration History**: Although Alembic was configured, no migration scripts were present in the repository. This means schema changes were not being tracked, versioned, or applied deterministically, creating a high risk of environment drift and deployment failures.
2.  **No CI Pipeline**: There was no automated process to validate code quality, run tests, or check for regressions before merging code. This allows bugs, style violations, and breaking changes to enter the main branch unchecked.
3.  **In-Memory Testing**: Existing tests used an in-memory SQLite database, which does not accurately represent the production PostgreSQL environment. This can hide database-specific issues (e.g., data type mismatches, constraint violations).

To build an audit-ready, enterprise-grade system, we must enforce discipline and automation around schema evolution and code integration.

## Decision

We will implement a strict, automated release governance strategy based on two core pillars: **Alembic Migrations** for database schema management and a **Comprehensive CI Pipeline** for quality assurance.

### 1. Alembic Migration Workflow

- **Mandatory Migrations**: Every change to a SQLAlchemy model that affects the database schema **MUST** be accompanied by an Alembic migration script. Manual changes to the database schema are strictly forbidden.
- **Autogeneration**: Developers should use `alembic revision --autogenerate` to create baseline migration scripts. These scripts should be reviewed for correctness before being committed.
- **Golden Path**: The CI pipeline and deployment runbooks will use `alembic upgrade head` to apply migrations, ensuring a consistent and repeatable process.
- **Initial Schema**: An initial migration script has been generated from the existing models to establish a baseline schema history.

### 2. CI Pipeline Quality Gates

A GitHub Actions workflow (`.github/workflows/ci.yml`) will be triggered on every push and pull request to the `main` and `develop` branches. It will run the following jobs in parallel:

- **`code-quality`**: Checks for adherence to coding standards.
    - **Formatting (Black)**: Enforces a consistent code style.
    - **Import Sorting (isort)**: Organizes imports for readability.
    - **Linting (Flake8)**: Catches common programming errors and style issues.
    - **Type Checking (MyPy)**: Statically analyzes type hints to prevent type-related bugs.
- **`unit-tests`**: Runs fast, isolated unit tests that do not require external services (like a database).
- **`integration-tests`**: Runs tests against a real, ephemeral PostgreSQL database spun up as a service container. This job will:
    1.  Start a Postgres container.
    2.  Apply all Alembic migrations (`alembic upgrade head`) to the test database.
    3.  Run the integration test suite (`tests/integration/`).
- **`security-scan`**: Performs basic security analysis.
    - **Dependency Vulnerability Scan (pip-audit)**: Scans for known vulnerabilities in installed packages using the official PyPA tool. This replaced Safety due to compatibility issues with the project's dependency resolver.
    - **Static Analysis (Bandit)**: Scans for common security issues in the codebase (e.g., hardcoded secrets, insecure function usage).

Only if all checks pass can code be merged.

## Consequences

### Positive

- **Stability & Reliability**: Automated checks prevent regressions and ensure that the `main` branch is always in a deployable state.
- **Auditability**: All schema changes are version-controlled and auditable through Alembic migration scripts.
- **Developer Velocity**: Developers get fast feedback on their changes, reducing the time spent on manual testing and debugging environment-specific issues.
- **Confidence in Deployments**: Deployments become a deterministic, low-risk process by ensuring migrations are applied consistently across all environments.

### Negative

- **Slower Initial Setup**: There is an upfront time investment in creating and configuring the CI pipeline and test harnesses.
- **CI Overhead**: Builds will take longer to complete due to the comprehensive nature of the checks. This is a necessary trade-off for quality and stability.

## Implementation Evidence

- **Alembic Migration**: The initial migration is located at `alembic/versions/20260104_103754_bdb09892867a_initial_schema_all_modules.py`.
- **CI Workflow**: The pipeline is defined in `.github/workflows/ci.yml`.
- **Integration Tests**: DB-backed tests are located in `tests/integration/` and use fixtures defined in `tests/conftest.py` to connect to a test database.
