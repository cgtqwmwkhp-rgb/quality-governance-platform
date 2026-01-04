# Stage 2.0: Feature Delivery Covenants

**Date:** 2026-01-04

**Author:** Manus AI

## 1. Overview

As we enter Stage 2.0, the focus shifts to accelerating feature delivery. However, this must not come at the cost of the governance and quality standards established in Stage 1. These covenants are non-negotiable rules that all contributors must adhere to during feature development.

## 2. Covenants

### 2.1. No Gate Relaxations

All CI gates are mandatory and must pass. There will be no `continue-on-error` or similar configurations that would weaken the integrity of the CI pipeline.

### 2.2. Migrations for All Schema Changes

Any and all changes to database schemas or models must be accompanied by an Alembic migration. Direct changes to the database are strictly forbidden.

### 2.3. Postgres Integration Tests for DB-Facing Changes

Any code that interacts with the database must be covered by a Postgres-backed integration test. This ensures that the code is not only syntactically correct but also functionally correct in a realistic database environment.

### 2.4. Deterministic Outputs

All outputs, especially from API endpoints, must be deterministic. This means stable ordering of lists and explicit reason codes for errors. This is crucial for auditability and for preventing non-obvious regressions.

### 2.5. Evidence-Led Delivery

All pull requests must include a detailed description with the following information:

- A list of all files touched (added, modified, or deleted)
- Evidence of testing (unit, integration, and security)
- A note on whether a migration is included (and if so, the Alembic revision)
- A risk and rollback plan
