# Policy Library Module Documentation

## Overview
The Policy Library module provides a governed, version-controlled repository for organizational policies, standards, and procedures. It is the first feature module to be delivered under the **Stage 2.1 Governed Feature Delivery** pattern, demonstrating the required schema discipline, API integrity, and full test coverage enforced by the CI pipeline.

## Data Model (Policy)
The module utilizes the existing `Policy` domain model, which is backed by the `policies` table in the database.

| Field Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `int` | Primary Key | Unique identifier for the policy. |
| `reference_number` | `str` | Required, Unique | System-generated reference number (e.g., POL-2026-0001). |
| `title` | `str` | Required, Max 300 chars | The official title of the policy. |
| `description` | `str` | Optional | A brief summary of the policy's purpose. |
| `document_type` | `Enum` | Required | Type of document (e.g., `POLICY`, `STANDARD`, `PROCEDURE`). |
| `status` | `Enum` | Required | Current lifecycle status (`DRAFT`, `ACTIVE`, `ARCHIVED`). |
| `created_at` | `datetime` | Auto-generated | Timestamp of creation. |
| `updated_at` | `datetime` | Auto-updated | Timestamp of last modification. |

## API Endpoints

The Policy Library exposes a minimal set of CRUD (Create, Read, Update, Delete) endpoints, ensuring data integrity and deterministic behavior.

| Method | Endpoint | Description | Governance Note |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/policies` | Creates a new policy document. | Auto-generates `reference_number`. |
| `GET` | `/api/v1/policies/{policy_id}` | Retrieves a single policy by its ID. | Returns 404 if not found. |
| `GET` | `/api/v1/policies` | Lists all policies. | **Deterministic Ordering:** Sorted by `created_at DESC` then `id ASC`. Supports pagination. |
| `PUT` | `/api/v1/policies/{policy_id}` | Updates an existing policy. | Supports partial updates. |
| `DELETE` | `/api/v1/policies/{policy_id}` | Deletes a policy document. | **Hard Delete:** The record is permanently removed from the database. |

## Governance and Quality Gates

This module was delivered under the strict Stage 2.1 covenants, ensuring audit-readiness:

1.  **Schema Discipline**: The existing `policies` table schema was used, and the migration check confirmed no drift.
2.  **Deterministic Ordering**: The `/api/v1/policies` endpoint explicitly enforces ordering by `created_at DESC, id ASC`, which is verified by integration tests.
3.  **Full Test Coverage**:
    *   **Unit Tests (15)**: Cover all Pydantic schema validation rules (e.g., title length, required fields, enum values).
    *   **Integration Tests (10)**: Cover the full CRUD lifecycle against a real Postgres instance in CI, including deterministic ordering and pagination.
4.  **CI Enforcement**: All changes passed the full suite of CI gates:
    *   Code Quality (Black, Isort, Mypy, Flake8)
    *   Security Scan (Bandit)
    *   CI Security Covenant (Stage 2.0)
    *   Unit and Integration Tests

## Rollout Notes

This module is a non-breaking addition to the API. No database migration is required for existing installations as the table was part of the initial schema.

### Dependencies
- No new external dependencies introduced.
- Relies on existing `Policy` model and database connection.

### Verification Steps
1.  Run `alembic check` to confirm no pending migrations.
2.  Run `pytest tests/integration/test_policy_api.py` to verify full CRUD functionality.
3.  Verify CI status for PR #9 is green across all checks.
