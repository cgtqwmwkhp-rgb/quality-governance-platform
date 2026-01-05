# Runtime Contract Baseline Map

## Purpose

This document maps the expected runtime behavior of the Quality Governance Platform's API endpoints to the canonical contracts defined in Stage 3.0. It serves as the baseline for Stage 3.1 runtime contract enforcement tests.

## Scope

This baseline covers the following modules:
- **Policies** (`/api/v1/policies`)
- **Incidents** (`/api/v1/incidents`)
- **Complaints** (`/api/v1/complaints`)
- **RTAs** (`/api/v1/rtas`)

## Contract Expectations by Module

### 1. Policies Module

#### Pagination Behavior
- **Endpoint:** `GET /api/v1/policies`
- **Parameters:** `page` (default: 1, min: 1), `page_size` (default: 50, min: 1, max: 100)
- **Response Fields:**
  - `items`: Array of policy objects
  - `total`: Total count of policies
  - `page`: Current page number
  - `page_size`: Items per page
  - `pages`: Total number of pages (calculated as `ceil(total / page_size)`)
- **Ordering:** `reference_number DESC, id ASC` (deterministic)
- **Tiebreaker:** `id ASC`

#### Error Envelope
- **404 Not Found:** `GET /api/v1/policies/{invalid_id}`
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"404"`
  - `message`: Human-readable error message
  - `details`: Additional context (e.g., `{"policy_id": 999}`)
  - `request_id`: Present and non-empty

#### Audit Events
- **Create:** `POST /api/v1/policies`
  - Event type: `policy.created`
  - Entity type: `policy`
  - Entity ID: Policy ID
  - Actor: `current_user.id`
  - Request ID: Present
- **Update:** `PUT /api/v1/policies/{policy_id}`
  - Event type: `policy.updated`
  - Entity type: `policy`
  - Entity ID: Policy ID
  - Actor: `current_user.id`
  - Request ID: Present
- **Delete:** `DELETE /api/v1/policies/{policy_id}`
  - Event type: `policy.deleted`
  - Entity type: `policy`
  - Entity ID: Policy ID
  - Actor: `current_user.id`
  - Request ID: Present

#### RBAC Expectation
- **Protected Endpoint:** `POST /api/v1/policies` (create)
- **Required Permission:** `policy:create`
- **403 Forbidden:** When user lacks permission
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"403"`

---

### 2. Incidents Module

#### Pagination Behavior
- **Endpoint:** `GET /api/v1/incidents`
- **Parameters:** `page` (default: 1, min: 1), `page_size` (default: 50, min: 1, max: 100)
- **Response Fields:**
  - `items`: Array of incident objects
  - `total`: Total count of incidents
  - `page`: Current page number
  - `page_size`: Items per page
  - `pages`: Total number of pages (calculated as `ceil(total / page_size)`)
- **Ordering:** `reported_date DESC, id ASC` (deterministic)
- **Tiebreaker:** `id ASC`

#### Error Envelope
- **404 Not Found:** `GET /api/v1/incidents/{invalid_id}`
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"404"`
  - `message`: Human-readable error message
  - `details`: Additional context (e.g., `{"incident_id": 999}`)
  - `request_id`: Present and non-empty

#### Audit Events
- **Create:** `POST /api/v1/incidents`
  - Event type: `incident.created`
  - Entity type: `incident`
  - Entity ID: Incident ID
  - Actor: `current_user.id`
  - Request ID: Present
- **Update:** `PUT /api/v1/incidents/{incident_id}`
  - Event type: `incident.updated`
  - Entity type: `incident`
  - Entity ID: Incident ID
  - Actor: `current_user.id`
  - Request ID: Present

#### RBAC Expectation
- **Protected Endpoint:** `POST /api/v1/incidents` (create)
- **Required Permission:** `incident:create`
- **403 Forbidden:** When user lacks permission
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"403"`

---

### 3. Complaints Module

#### Pagination Behavior
- **Endpoint:** `GET /api/v1/complaints/`
- **Parameters:** `page` (default: 1, min: 1), `page_size` (default: 20, min: 1, max: 100), `status_filter` (optional)
- **Response Fields:**
  - `items`: Array of complaint objects
  - `total`: Total count of complaints (filtered if `status_filter` is provided)
  - `page`: Current page number
  - `page_size`: Items per page
  - `pages`: Total number of pages (calculated as `ceil(total / page_size)`)
- **Ordering:** `received_date DESC, id ASC` (deterministic)
- **Tiebreaker:** `id ASC`

#### Error Envelope
- **404 Not Found:** `GET /api/v1/complaints/{invalid_id}`
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"404"`
  - `message`: Human-readable error message
  - `details`: Additional context (e.g., `{"complaint_id": 999}`)
  - `request_id`: Present and non-empty

#### Audit Events
- **Create:** `POST /api/v1/complaints/`
  - Event type: `complaint.created`
  - Entity type: `complaint`
  - Entity ID: Complaint ID
  - Actor: `current_user.id`
  - Request ID: Present
- **Update:** `PATCH /api/v1/complaints/{complaint_id}`
  - Event type: `complaint.updated`
  - Entity type: `complaint`
  - Entity ID: Complaint ID
  - Actor: `current_user.id`
  - Request ID: Present

#### RBAC Expectation
- **Protected Endpoint:** `POST /api/v1/complaints/` (create)
- **Required Permission:** `complaint:create`
- **403 Forbidden:** When user lacks permission
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"403"`

---

### 4. RTAs Module

#### Pagination Behavior
- **Endpoint:** `GET /api/v1/rtas/`
- **Parameters:** `page` (default: 1, min: 1), `page_size` (default: 10, min: 1, max: 100), `incident_id` (optional filter)
- **Response Fields:**
  - `items`: Array of RTA objects
  - `total`: Total count of RTAs (filtered if `incident_id` is provided)
  - `page`: Current page number
  - `page_size`: Items per page
  - `pages`: Total number of pages (calculated as `ceil(total / page_size)`)
- **Ordering:** `created_at DESC, id ASC` (deterministic)
- **Tiebreaker:** `id ASC`

#### Error Envelope
- **404 Not Found:** `GET /api/v1/rtas/{invalid_id}`
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"404"`
  - `message`: Human-readable error message
  - `details`: Additional context (e.g., `{"rta_id": 999}`)
  - `request_id`: Present and non-empty

#### Audit Events
- **Create:** `POST /api/v1/rtas/`
  - Event type: `rta.created`
  - Entity type: `rta`
  - Entity ID: RTA ID
  - Actor: `current_user.id`
  - Request ID: Present

#### RBAC Expectation
- **Protected Endpoint:** `POST /api/v1/rtas/` (create)
- **Required Permission:** `rta:create`
- **403 Forbidden:** When user lacks permission
  - Expected keys: `error_code`, `message`, `details`, `request_id`
  - `error_code`: `"403"`

---

## Notes

- All list endpoints must return the `pages` field calculated as `ceil(total / page_size)`.
- All error responses must include a `request_id` field for traceability.
- All audit events must include `request_id` for correlation with API requests.
- All protected endpoints must enforce RBAC and return canonical 403 errors when permission is denied.
- Ordering must be deterministic across all list endpoints to ensure consistent pagination behavior.
