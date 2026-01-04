# Complaints Module

## Overview
The Complaints module provides a governed API for managing external complaints received by the organization. It ensures a structured, auditable process for tracking complaints from reception to resolution.

## Key Features
- **Governed Delivery:** Implemented with full schema discipline, deterministic ordering, and audit logging.
- **Deterministic Ordering:** All list endpoints are ordered by `received_date DESC` (newest first) and `id ASC` (stable tie-breaker).
- **Auditability:** All creation and status changes are recorded as `AuditEvent` records via the `AuditService`.
- **Reference Numbering:** Complaints are automatically assigned a unique, sequential reference number (`COMP-YYYY-NNNN`).

## API Endpoints

| Method | Path | Description | Deterministic Ordering | Audit Logging |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/complaints` | Creates a new complaint record. | N/A | `complaint.created` |
| `GET` | `/api/v1/complaints/{id}` | Retrieves a single complaint by ID. | N/A | No |
| `GET` | `/api/v1/complaints` | Lists all complaints with pagination. | `received_date DESC`, `id ASC` | No |
| `PATCH` | `/api/v1/complaints/{id}` | Updates complaint details (e.g., status, resolution). | N/A | `complaint.updated` |

## Data Model (Complaint)

The module utilizes the existing `Complaint` model, which includes comprehensive fields for tracking complainant details, investigation, resolution, and linkage to other governance elements.

| Field | Type | Description | Notes |
| :--- | :--- | :--- | :--- |
| `id` | `int` | Primary key. | Auto-incrementing. |
| `reference_number` | `str` | Unique identifier. | Auto-generated (`COMP-YYYY-NNNN`). |
| `title` | `str` | Summary of the complaint. | Max 300 chars. |
| `description` | `str` | Detailed description of the complaint. | Required. |
| `status` | `Enum` | Current status (e.g., RECEIVED, RESOLVED). | Default: RECEIVED. |
| `received_date` | `datetime` | Date the complaint was received. | Required for ordering. |
| `complainant_name` | `str` | Name of the person making the complaint. | Required. |

## Rollout Notes

1.  **Dependencies:** No new external dependencies. Requires the `AuditService` implemented in Stage 2.3.
2.  **Migration:** No new schema migration is required as the `complaints` table already exists in the initial schema.
3.  **Testing:** All unit and integration tests passed locally, verifying CRUD, validation, deterministic ordering, and audit integration.
4.  **Audit Events:** Verify that `complaint.created` and `complaint.updated` events are correctly logged in the `audit_events` table upon API calls.
