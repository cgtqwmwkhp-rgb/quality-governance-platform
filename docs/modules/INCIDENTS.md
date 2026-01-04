# Incidents Module

## Overview
The Incidents module provides a minimal API for reporting, tracking, and updating incidents within the Quality Governance Platform. It is designed with a focus on data integrity, deterministic ordering, and full auditability, adhering to all Stage 2 governance covenants.

## Data Model
The module utilizes the existing `Incident` model, which is mapped to the `incidents` table in the database.

| Field | Type | Description | Constraints |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary key. | Auto-generated |
| `reference_number` | `String` | Unique identifier (e.g., INC-YYYY-NNNN). | Auto-generated on creation |
| `title` | `String` | Brief summary of the incident. | Required, Max 300 chars |
| `description` | `Text` | Detailed description of the incident. | Optional |
| `incident_type` | `Enum` | Type of incident (e.g., QUALITY, SAFETY, SECURITY). | Default: OTHER |
| `severity` | `Enum` | Impact level (e.g., CRITICAL, HIGH, MEDIUM, LOW). | Default: MEDIUM |
| `status` | `Enum` | Current state (e.g., REPORTED, IN_PROGRESS, CLOSED). | Default: REPORTED |
| `incident_date` | `Timestamp` | Date/time the incident occurred. | Required |
| `reported_date` | `Timestamp` | Date/time the incident was reported. | Auto-generated on creation |
| `created_at` | `Timestamp` | Record creation timestamp. | Auto-generated |
| `updated_at` | `Timestamp` | Record last update timestamp. | Auto-updated |

## API Endpoints

The API provides the following endpoints:

| Method | Path | Description | Determinism |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/incidents` | Creates a new incident record. | N/A |
| `GET` | `/api/v1/incidents/{id}` | Retrieves a single incident by its ID. | N/A |
| `GET` | `/api/v1/incidents` | Lists all incidents with pagination. | **Yes**: Ordered by `reported_date DESC`, then `id ASC`. |
| `PATCH` | `/api/v1/incidents/{id}` | Partially updates an incident record (e.g., status change). | N/A |

## Governance Compliance

This module adheres to the following Stage 2 covenants:

1.  **Schema Discipline**: The `incidents` table is included in the initial Alembic migration and `alembic check` is clean.
2.  **Deterministic Ordering**: The list endpoint is explicitly ordered by `reported_date DESC, id ASC` to ensure stable, reproducible results across all environments.
3.  **Full Test Coverage**: The module has 9 unit tests for validation and 5 integration tests covering the full CRUD flow against a live Postgres database.
4.  **Auditability**: All CI checks, including security and governance gates, passed successfully, and JUnit XML reports are generated as audit artifacts.

## Policy Alignment (Phase 0)

The delete semantics for the Policy Library module were aligned in this stage:

*   **Policy Library Delete Semantics**: The `DELETE /api/v1/policies/{id}` endpoint performs a **Hard Delete**. This was verified by an updated integration test to ensure the resource is permanently removed from the database.
