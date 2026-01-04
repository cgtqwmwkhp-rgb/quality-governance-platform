# Root Cause Analysis (RTA) Module

The Root Cause Analysis (RTA) module is designed to manage the investigation and corrective actions following an Incident. It is tightly coupled with the Incidents module, enforcing a one-to-many relationship where one Incident can have multiple associated RTAs.

## Key Features

*   **Incident Linkage:** Every RTA must be linked to an existing Incident.
*   **Deterministic Ordering:** All list endpoints are ordered deterministically by `created_at DESC` (newest first) and `id ASC` (stable tie-breaker).
*   **Audit Scaffolding:** Creation and update of RTA records trigger minimal `AuditEvent` logging, providing an auditable trail of changes.

## Data Model (`RootCauseAnalysis`)

| Field | Type | Description | Constraints |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Primary key. | Auto-generated |
| `incident_id` | UUID | Foreign key to the linked Incident. | Required, Valid Incident ID |
| `reference_number` | String | Unique identifier (e.g., RTA-YYYY-NNNN). | Auto-generated |
| `title` | String | Concise title for the analysis. | Required, Max 300 chars |
| `problem_statement` | Text | Detailed description of the problem being analyzed. | Required |
| `root_cause` | Text | The identified root cause. | Optional |
| `corrective_actions` | Text | Actions planned or taken to prevent recurrence. | Optional |
| `status` | Enum | Current state of the RTA. | DRAFT, IN\_REVIEW, APPROVED, CLOSED |
| `created_at` | Timestamp | Record creation time. | Auto-generated |
| `updated_at` | Timestamp | Record last update time. | Auto-updated |

## API Endpoints

| Method | Path | Description | Linkage |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/rtas` | Create a new RTA. | Requires `incident_id` |
| `GET` | `/api/v1/rtas/{id}` | Retrieve a specific RTA. | |
| `GET` | `/api/v1/rtas` | List all RTAs. | Deterministic ordering |
| `PATCH` | `/api/v1/rtas/{id}` | Update RTA details (e.g., status, root cause). | Partial update |
| `GET` | `/api/v1/incidents/{id}/rtas` | List RTAs linked to a specific Incident. | Deterministic ordering |

## Audit Events Scaffolding

The following actions now trigger an `AuditEvent` record:

| Resource | Action | Event Type |
| :--- | :--- | :--- |
| `Incident` | Create, Update | `incident.created`, `incident.updated` |
| `RTA` | Create, Update | `rta.created`, `rta.updated` |

This scaffolding ensures that a minimal, auditable trail is maintained for key governance actions.
