# Data Dictionary

Reference for all core database entities, their columns, types, and relationships.
Derived from SQLAlchemy models in `src/domain/models/`.

---

## Core Entities

### Tenants (`tenants`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| name | VARCHAR(255) | No | Organisation name |
| slug | VARCHAR(100) | No | Unique URL-safe identifier |
| domain | VARCHAR(255) | Yes | Custom domain for tenant |
| is_active | BOOLEAN | No | Tenant active status (default: true) |
| subscription_tier | VARCHAR(50) | No | free / standard / professional / enterprise |
| logo_url | VARCHAR(500) | Yes | Logo image URL |
| favicon_url | VARCHAR(500) | Yes | Favicon URL |
| primary_color | VARCHAR(7) | No | Hex colour (default: #3B82F6) |
| secondary_color | VARCHAR(7) | No | Hex colour (default: #10B981) |
| accent_color | VARCHAR(7) | No | Hex colour (default: #8B5CF6) |
| theme_mode | VARCHAR(20) | No | light / dark / system |
| custom_css | TEXT | Yes | Custom CSS overrides |
| admin_email | VARCHAR(255) | No | Primary admin email |
| support_email | VARCHAR(255) | Yes | Support contact email |
| phone | VARCHAR(50) | Yes | Phone number |
| address_line1 | VARCHAR(255) | Yes | Street address line 1 |
| address_line2 | VARCHAR(255) | Yes | Street address line 2 |
| city | VARCHAR(100) | Yes | City |
| state | VARCHAR(100) | Yes | State / region |
| postal_code | VARCHAR(20) | Yes | Postal code |
| country | VARCHAR(100) | No | Country (default: United Kingdom) |
| settings | JSON | No | Tenant-specific settings |
| features_enabled | JSON | No | Feature flags per tenant |
| max_users | INTEGER | No | User limit (default: 50) |
| max_storage_gb | INTEGER | No | Storage limit in GB (default: 10) |
| created_at | TIMESTAMP | No | Creation timestamp |
| updated_at | TIMESTAMP | No | Last update timestamp |
| trial_ends_at | TIMESTAMP | Yes | Trial period end date |

### Users (`users`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| email | VARCHAR(255) | No | Unique email address (indexed) |
| hashed_password | VARCHAR(255) | No | Bcrypt password hash |
| first_name | VARCHAR(100) | No | User's first name |
| last_name | VARCHAR(100) | No | User's last name |
| job_title | VARCHAR(100) | Yes | Job title |
| department | VARCHAR(100) | Yes | Department name |
| phone | VARCHAR(20) | Yes | Phone number |
| is_active | BOOLEAN | No | Account active status (default: true) |
| is_superuser | BOOLEAN | No | Superuser flag (default: false) |
| last_login | VARCHAR(50) | Yes | Last login timestamp (ISO string) |
| azure_oid | VARCHAR(36) | Yes | Azure AD Object ID for SSO (indexed) |
| tenant_id | INTEGER | Yes | FK to `tenants.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| deleted_at | TIMESTAMP(tz) | Yes | Soft-delete timestamp (mixin) |

### Roles (`roles`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| name | VARCHAR(50) | No | Unique role name (indexed) |
| description | TEXT | Yes | Role description |
| permissions | TEXT | Yes | JSON string of permission identifiers |
| is_system_role | BOOLEAN | No | System-managed role (default: false) |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |

### User–Role Association (`user_roles`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| user_id | INTEGER | No | PK, FK to `users.id` (CASCADE) |
| role_id | INTEGER | No | PK, FK to `roles.id` (CASCADE) |

---

## Incident Management

### Incidents (`incidents`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference (e.g., INC-2026-0001) |
| title | VARCHAR(300) | No | Incident title (indexed) |
| description | TEXT | No | Detailed description |
| incident_type | ENUM | No | injury / near_miss / hazard / property_damage / environmental / security / quality / other |
| severity | ENUM | No | critical / high / medium / low / negligible |
| status | ENUM | No | reported / under_investigation / pending_actions / actions_in_progress / pending_review / closed |
| incident_date | TIMESTAMP(tz) | No | When the incident occurred |
| reported_date | TIMESTAMP(tz) | No | When the incident was reported |
| location | VARCHAR(300) | Yes | Location of incident |
| department | VARCHAR(100) | Yes | Department |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| reporter_id | INTEGER | Yes | FK to `users.id` |
| reporter_email | VARCHAR(255) | Yes | Portal reporter's email (indexed) |
| reporter_name | VARCHAR(255) | Yes | Portal reporter's name |
| people_involved | TEXT | Yes | People involved (free text) |
| witnesses | TEXT | Yes | Witness details |
| immediate_actions | TEXT | Yes | Immediate response actions taken |
| first_aid_given | BOOLEAN | No | First aid administered (default: false) |
| emergency_services_called | BOOLEAN | No | Emergency services called (default: false) |
| investigator_id | INTEGER | Yes | FK to `users.id` |
| investigation_started_at | TIMESTAMP(tz) | Yes | Investigation start date |
| investigation_completed_at | TIMESTAMP(tz) | Yes | Investigation completion date |
| root_cause | TEXT | Yes | Root cause analysis |
| contributing_factors | TEXT | Yes | Contributing factors |
| is_riddor_reportable | BOOLEAN | Yes | RIDDOR reportable (UK) |
| riddor_classification | VARCHAR(100) | Yes | RIDDOR classification |
| riddor_rationale | TEXT | Yes | RIDDOR rationale |
| clause_ids | TEXT | Yes | Mapped standard clause IDs |
| linked_risk_ids | TEXT | Yes | Comma-separated risk IDs |
| source_type | VARCHAR(50) | No | manual / email / api (default: manual) |
| source_email_id | VARCHAR(200) | Yes | Source email message ID |
| source_form_id | VARCHAR(50) | Yes | Portal form ID for traceability |
| closed_at | TIMESTAMP(tz) | Yes | Closure timestamp |
| closed_by_id | INTEGER | Yes | FK to `users.id` |
| closure_notes | TEXT | Yes | Closure notes |
| is_sif | BOOLEAN | Yes | Serious Injury or Fatality (default: false) |
| is_psif | BOOLEAN | Yes | Potential SIF (default: false) |
| sif_classification | VARCHAR(50) | Yes | SIF / pSIF / Non-SIF |
| sif_assessment_date | TIMESTAMP(tz) | Yes | SIF assessment date |
| sif_assessed_by_id | INTEGER | Yes | FK to `users.id` |
| sif_rationale | TEXT | Yes | SIF classification rationale |
| life_altering_potential | BOOLEAN | Yes | Life-altering potential (default: false) |
| precursor_events | JSON | Yes | List of precursor indicators |
| control_failures | JSON | Yes | List of failed controls |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Incident Actions (`incident_actions`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference |
| incident_id | INTEGER | No | FK to `incidents.id` (CASCADE) |
| title | VARCHAR(300) | No | Action title |
| description | TEXT | No | Action description |
| action_type | VARCHAR(50) | No | corrective / preventive / improvement |
| priority | VARCHAR(20) | No | critical / high / medium / low |
| owner_id | INTEGER | Yes | FK to `users.id` |
| status | ENUM | No | open / in_progress / completed / verified / overdue / cancelled |
| due_date | TIMESTAMP(tz) | Yes | Target completion date |
| completed_at | TIMESTAMP(tz) | Yes | Actual completion date |
| verified_at | TIMESTAMP(tz) | Yes | Verification date |
| verified_by_id | INTEGER | Yes | FK to `users.id` |
| completion_notes | TEXT | Yes | Completion evidence |
| verification_notes | TEXT | Yes | Verification notes |
| effectiveness_review_date | TIMESTAMP(tz) | Yes | Effectiveness review date |
| effectiveness_notes | TEXT | Yes | Effectiveness assessment |
| is_effective | BOOLEAN | Yes | Whether action was effective |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

---

## Risk Management

### Risks (`risks`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference (e.g., RSK-2026-0001) |
| title | VARCHAR(300) | No | Risk title (indexed) |
| description | TEXT | No | Risk description |
| category | VARCHAR(100) | No | Risk category (default: operational) |
| subcategory | VARCHAR(100) | Yes | Risk subcategory |
| risk_source | VARCHAR(500) | Yes | Source of the risk |
| risk_event | VARCHAR(500) | Yes | Risk event description |
| risk_consequence | VARCHAR(500) | Yes | Consequence if risk materialises |
| likelihood | INTEGER | No | 1–5 scale (default: 3) |
| impact | INTEGER | No | 1–5 scale (default: 3) |
| risk_score | INTEGER | No | likelihood × impact (default: 9) |
| risk_level | VARCHAR(50) | No | Calculated level (default: medium) |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| owner_id | INTEGER | Yes | FK to `users.id` |
| department | VARCHAR(100) | Yes | Owning department |
| review_frequency_months | INTEGER | No | Review cycle in months (default: 12) |
| next_review_date | TIMESTAMP(tz) | Yes | Next scheduled review |
| clause_ids_json | JSON | Yes | Mapped standard clause IDs |
| control_ids_json | JSON | Yes | Mapped control IDs |
| linked_audit_ids_json | JSON | Yes | Linked audit IDs |
| linked_incident_ids_json | JSON | Yes | Linked incident IDs |
| linked_policy_ids_json | JSON | Yes | Linked policy IDs |
| treatment_strategy | VARCHAR(50) | No | mitigate / accept / transfer / avoid |
| treatment_plan | TEXT | Yes | Treatment plan details |
| treatment_due_date | TIMESTAMP(tz) | Yes | Treatment target date |
| status | ENUM | No | identified / assessing / treating / monitoring / closed |
| is_active | BOOLEAN | No | Active flag (default: true) |
| created_by_id | INTEGER | Yes | FK to `users.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Risk Controls (`risk_controls`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| risk_id | INTEGER | No | FK to `risks.id` (CASCADE) |
| title | VARCHAR(300) | No | Control title |
| description | TEXT | Yes | Control description |
| control_type | VARCHAR(50) | No | preventive / detective / corrective |
| implementation_status | VARCHAR(50) | No | planned / in_progress / implemented |
| effectiveness | VARCHAR(50) | Yes | Effectiveness rating |
| is_active | BOOLEAN | No | Active flag (default: true) |
| owner_id | INTEGER | Yes | FK to `users.id` |
| clause_ids_json | JSON | Yes | Mapped standard clause IDs |
| control_ids_json | JSON | Yes | Mapped control IDs |
| last_tested_date | TIMESTAMP(tz) | Yes | Last test date |
| next_test_date | TIMESTAMP(tz) | Yes | Next scheduled test |
| test_frequency_months | INTEGER | Yes | Test cycle in months |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Risk Assessments (`risk_assessments`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| risk_id | INTEGER | No | FK to `risks.id` (CASCADE) |
| assessment_date | TIMESTAMP(tz) | No | Date of assessment |
| assessment_type | VARCHAR(50) | No | periodic / ad_hoc / triggered |
| inherent_likelihood | INTEGER | No | Before controls (1–5) |
| inherent_impact | INTEGER | No | Before controls (1–5) |
| inherent_score | INTEGER | No | likelihood × impact |
| inherent_level | VARCHAR(50) | No | Calculated level |
| residual_likelihood | INTEGER | No | After controls (1–5) |
| residual_impact | INTEGER | No | After controls (1–5) |
| residual_score | INTEGER | No | likelihood × impact |
| residual_level | VARCHAR(50) | No | Calculated level |
| target_likelihood | INTEGER | Yes | Desired state (1–5) |
| target_impact | INTEGER | Yes | Desired state (1–5) |
| target_score | INTEGER | Yes | likelihood × impact |
| target_level | VARCHAR(50) | Yes | Calculated level |
| assessment_notes | TEXT | Yes | Assessor notes |
| control_effectiveness_notes | TEXT | Yes | Control effectiveness notes |
| assessed_by_id | INTEGER | Yes | FK to `users.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |

---

## Audit Management

### Audit Templates (`audit_templates`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference |
| name | VARCHAR(200) | No | Template name (indexed) |
| description | TEXT | Yes | Template description |
| category | VARCHAR(100) | Yes | Audit category |
| audit_type | VARCHAR(50) | No | inspection / internal / external / surveillance |
| frequency | VARCHAR(50) | Yes | Audit frequency |
| version | INTEGER | No | Template version (default: 1) |
| is_active | BOOLEAN | No | Active flag (default: true) |
| is_published | BOOLEAN | No | Published flag (default: false) |
| archived_at | TIMESTAMP(tz) | Yes | Archive date (indexed) |
| archived_by_id | INTEGER | Yes | FK to `users.id` |
| scoring_method | VARCHAR(50) | No | percentage / weighted / pass_fail |
| passing_score | FLOAT | Yes | Minimum passing score |
| allow_offline | BOOLEAN | No | Offline mode (default: false) |
| require_gps | BOOLEAN | No | GPS required (default: false) |
| require_signature | BOOLEAN | No | Signature required (default: false) |
| require_approval | BOOLEAN | No | Approval workflow (default: false) |
| auto_create_findings | BOOLEAN | No | Auto-create findings (default: true) |
| standard_ids_json | JSON | Yes | Mapped standard IDs |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| created_by_id | INTEGER | Yes | FK to `users.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Audit Runs (`audit_runs`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference |
| template_id | INTEGER | No | FK to `audit_templates.id` |
| template_version | INTEGER | No | Snapshot of template version |
| title | VARCHAR(300) | Yes | Run title |
| location | VARCHAR(200) | Yes | Audit location |
| location_details | VARCHAR(500) | Yes | Specific location details |
| notes | TEXT | Yes | General notes |
| latitude | FLOAT | Yes | GPS latitude |
| longitude | FLOAT | Yes | GPS longitude |
| status | ENUM | No | draft / scheduled / in_progress / pending_review / completed / cancelled |
| scheduled_date | TIMESTAMP(tz) | Yes | Scheduled date |
| due_date | TIMESTAMP(tz) | Yes | Due date |
| started_at | TIMESTAMP(tz) | Yes | Actual start |
| completed_at | TIMESTAMP(tz) | Yes | Actual completion |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| assigned_to_id | INTEGER | Yes | FK to `users.id` |
| created_by_id | INTEGER | Yes | FK to `users.id` |
| score | FLOAT | Yes | Achieved score |
| max_score | FLOAT | Yes | Maximum possible score |
| score_percentage | FLOAT | Yes | Score as percentage |
| passed | BOOLEAN | Yes | Pass/fail result |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Audit Findings (`audit_findings`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference |
| run_id | INTEGER | No | FK to `audit_runs.id` (CASCADE) |
| question_id | INTEGER | Yes | FK to `audit_questions.id` |
| title | VARCHAR(300) | No | Finding title |
| description | TEXT | No | Finding description |
| severity | VARCHAR(50) | No | critical / high / medium / low / observation |
| finding_type | VARCHAR(50) | No | nonconformity / observation / opportunity |
| status | ENUM | No | open / in_progress / pending_verification / closed / deferred |
| clause_ids_json | JSON | Yes | Mapped standard clause IDs |
| control_ids_json | JSON | Yes | Mapped control IDs |
| risk_ids_json | JSON | Yes | Linked risk IDs |
| corrective_action_required | BOOLEAN | No | CA required (default: true) |
| corrective_action_due_date | TIMESTAMP(tz) | Yes | CA due date |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| created_by_id | INTEGER | Yes | FK to `users.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

---

## Complaint Management

### Complaints (`complaints`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference (e.g., CMP-2026-0001) |
| external_ref | VARCHAR(100) | Yes | Idempotency key for ETL imports (unique) |
| title | VARCHAR(300) | No | Complaint title (indexed) |
| description | TEXT | No | Complaint description |
| complaint_type | ENUM | No | product / service / delivery / communication / billing / staff / environmental / safety / other |
| priority | ENUM | No | critical / high / medium / low |
| status | ENUM | No | received / acknowledged / under_investigation / pending_response / awaiting_customer / resolved / closed / escalated |
| received_date | TIMESTAMP(tz) | No | When complaint was received |
| acknowledged_date | TIMESTAMP(tz) | Yes | Acknowledgement date |
| target_resolution_date | TIMESTAMP(tz) | Yes | Target resolution date |
| resolved_date | TIMESTAMP(tz) | Yes | Actual resolution date |
| complainant_name | VARCHAR(200) | No | Complainant's name |
| complainant_email | VARCHAR(255) | Yes | Complainant's email |
| complainant_phone | VARCHAR(30) | Yes | Complainant's phone |
| complainant_company | VARCHAR(200) | Yes | Complainant's company |
| complainant_address | TEXT | Yes | Complainant's address |
| related_reference | VARCHAR(100) | Yes | Related order/invoice number |
| related_product_service | VARCHAR(200) | Yes | Related product or service |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| owner_id | INTEGER | Yes | FK to `users.id` |
| department | VARCHAR(100) | Yes | Assigned department |
| investigation_notes | TEXT | Yes | Investigation notes |
| root_cause | TEXT | Yes | Root cause analysis |
| resolution_summary | TEXT | Yes | Resolution summary |
| customer_satisfied | BOOLEAN | Yes | Customer satisfaction |
| compensation_offered | TEXT | Yes | Compensation details |
| clause_ids | TEXT | Yes | Mapped standard clause IDs |
| linked_risk_ids | TEXT | Yes | Comma-separated risk IDs |
| source_type | VARCHAR(50) | No | manual / email / api / phone |
| source_email_id | VARCHAR(200) | Yes | Source email message ID |
| original_email_subject | VARCHAR(500) | Yes | Original email subject |
| original_email_body | TEXT | Yes | Original email body |
| source_form_id | VARCHAR(50) | Yes | Portal form ID |
| closed_at | TIMESTAMP(tz) | Yes | Closure timestamp |
| closed_by_id | INTEGER | Yes | FK to `users.id` |
| closure_notes | TEXT | Yes | Closure notes |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

---

## Policy & Document Library

### Policies (`policies`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference (e.g., POL-2026-0001) |
| title | VARCHAR(300) | No | Policy title (indexed) |
| description | TEXT | Yes | Policy description |
| document_type | ENUM | No | policy / procedure / work_instruction / sop / form / template / guideline / manual / record / other |
| status | ENUM | No | draft / under_review / approved / published / superseded / retired |
| category | VARCHAR(100) | Yes | Policy category |
| department | VARCHAR(100) | Yes | Owning department |
| tags | TEXT | Yes | Comma-separated tags |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| owner_id | INTEGER | Yes | FK to `users.id` |
| approver_id | INTEGER | Yes | FK to `users.id` |
| review_frequency_months | INTEGER | No | Review cycle (default: 12) |
| next_review_date | TIMESTAMP(tz) | Yes | Next review date |
| clause_ids | TEXT | Yes | Mapped standard clause IDs |
| is_public | BOOLEAN | No | Public access (default: false) |
| restricted_to_roles | TEXT | Yes | Comma-separated role IDs |
| restricted_to_departments | TEXT | Yes | Comma-separated departments |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Policy Versions (`policy_versions`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| policy_id | INTEGER | No | FK to `policies.id` (CASCADE) |
| version_number | VARCHAR(20) | No | Version string (e.g., "1.0", "2.1") |
| version_notes | TEXT | Yes | Change summary |
| is_current | BOOLEAN | No | Current active version (default: false) |
| is_major_revision | BOOLEAN | No | Major revision flag (default: false) |
| content | TEXT | Yes | Rich text content |
| file_path | VARCHAR(500) | Yes | Path to uploaded file |
| file_name | VARCHAR(255) | Yes | Original file name |
| file_size | INTEGER | Yes | File size in bytes |
| file_type | VARCHAR(50) | Yes | MIME type |
| status | ENUM | No | draft / under_review / approved / published / superseded / retired |
| submitted_at | TIMESTAMP(tz) | Yes | Submission date |
| submitted_by_id | INTEGER | Yes | FK to `users.id` |
| reviewed_at | TIMESTAMP(tz) | Yes | Review date |
| reviewed_by_id | INTEGER | Yes | FK to `users.id` |
| approved_at | TIMESTAMP(tz) | Yes | Approval date |
| approved_by_id | INTEGER | Yes | FK to `users.id` |
| published_at | TIMESTAMP(tz) | Yes | Publish date |
| effective_date | TIMESTAMP(tz) | Yes | Effective start date |
| expiry_date | TIMESTAMP(tz) | Yes | Expiry date |
| supersedes_version_id | INTEGER | Yes | FK to `policy_versions.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| created_by_id | INTEGER | Yes | Audit trail: creator (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

### Documents (`documents`)

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Primary key |
| reference_number | VARCHAR(20) | No | Unique reference (e.g., DOC-2026-0001) |
| title | VARCHAR(500) | No | Document title (indexed) |
| description | TEXT | Yes | Document description |
| file_name | VARCHAR(500) | No | Original file name |
| file_type | ENUM | No | pdf / docx / doc / xlsx / xls / csv / md / txt / png / jpg / jpeg |
| file_size | INTEGER | No | File size in bytes |
| file_path | VARCHAR(1000) | No | Azure Blob storage path |
| mime_type | VARCHAR(100) | Yes | MIME type |
| document_type | ENUM | No | policy / procedure / sop / form / manual / guideline / faq / template / record / other |
| category | VARCHAR(100) | Yes | Document category |
| department | VARCHAR(100) | Yes | Department |
| sensitivity | ENUM | No | public / internal / confidential / restricted |
| status | ENUM | No | pending / processing / indexed / approved / rejected / archived / failed |
| version | VARCHAR(20) | No | Version string (default: "1.0") |
| is_active | BOOLEAN | No | Active flag (default: true) |
| is_latest | BOOLEAN | No | Latest version flag (default: true) |
| parent_document_id | INTEGER | Yes | FK to `documents.id` (self-referential) |
| ai_summary | TEXT | Yes | AI-generated summary |
| ai_tags | JSON | Yes | AI-extracted tags |
| ai_keywords | JSON | Yes | AI-extracted keywords |
| ai_topics | JSON | Yes | AI-extracted topics |
| ai_entities | JSON | Yes | AI-extracted entities |
| ai_confidence | FLOAT | Yes | AI confidence score (0–1) |
| ai_processed_at | TIMESTAMP(tz) | Yes | AI processing timestamp |
| page_count | INTEGER | Yes | Number of pages |
| word_count | INTEGER | Yes | Word count |
| has_images | BOOLEAN | No | Contains images (default: false) |
| has_tables | BOOLEAN | No | Contains tables (default: false) |
| indexed_at | TIMESTAMP(tz) | Yes | Vector index timestamp |
| chunk_count | INTEGER | Yes | Number of RAG chunks |
| effective_date | TIMESTAMP(tz) | Yes | Effective start date |
| review_date | TIMESTAMP(tz) | Yes | Review date |
| expiry_date | TIMESTAMP(tz) | Yes | Expiry date |
| is_public | BOOLEAN | No | Public access (default: false) |
| restricted_to_roles | JSON | Yes | Role-based access list |
| restricted_to_departments | JSON | Yes | Department-based access list |
| view_count | INTEGER | No | View count (default: 0) |
| download_count | INTEGER | No | Download count (default: 0) |
| citation_count | INTEGER | No | Citation count (default: 0) |
| linked_policy_id | INTEGER | Yes | FK to `policies.id` |
| linked_standard_id | INTEGER | Yes | FK to `standards.id` |
| tenant_id | INTEGER | Yes | FK to `tenants.id` (indexed) |
| created_by_id | INTEGER | Yes | FK to `users.id` |
| reviewed_by_id | INTEGER | Yes | FK to `users.id` |
| created_at | TIMESTAMP(tz) | No | Creation timestamp (mixin) |
| updated_at | TIMESTAMP(tz) | No | Last update timestamp (mixin) |
| updated_by_id | INTEGER | Yes | Audit trail: last updater (mixin) |

---

## Relationships

### Tenant Relationships
- **User** belongs to **Tenant** (many-to-one via `users.tenant_id`)
- **TenantUser** associates **User** ↔ **Tenant** (many-to-many with role)
- All domain entities (Incident, Risk, Audit, Complaint, Policy, Document) belong to **Tenant** via `tenant_id`

### User Relationships
- **User** has many **Roles** (many-to-many via `user_roles`)
- **User** owns/reports/investigates **Incidents**
- **User** owns **Risks**, **Complaints**, **Policies**
- **User** is assigned to **Audit Runs**

### Incident Relationships
- **Incident** has many **IncidentActions** (one-to-many, cascade delete)
- **Incident** reported by **User** (many-to-one via `reporter_id`)
- **Incident** investigated by **User** (many-to-one via `investigator_id`)

### Risk Relationships
- **Risk** has many **OperationalRiskControls** (one-to-many, cascade delete)
- **Risk** has many **RiskAssessments** (one-to-many, cascade delete)
- **Risk** owned by **User** (many-to-one via `owner_id`)
- **Risk** linked to **Audits**, **Incidents**, **Policies** (via JSON arrays)

### Audit Relationships
- **AuditTemplate** has many **AuditSections** (one-to-many, cascade delete)
- **AuditTemplate** has many **AuditQuestions** (one-to-many, cascade delete)
- **AuditTemplate** has many **AuditRuns** (one-to-many)
- **AuditRun** has many **AuditResponses** (one-to-many, cascade delete)
- **AuditRun** has many **AuditFindings** (one-to-many, cascade delete)

### Complaint Relationships
- **Complaint** has many **ComplaintActions** (one-to-many, cascade delete)
- **Complaint** owned by **User** (many-to-one via `owner_id`)

### Policy & Document Relationships
- **Policy** has many **PolicyVersions** (one-to-many, cascade delete)
- **Document** has many **DocumentChunks** (one-to-many, cascade delete)
- **Document** has many **DocumentAnnotations** (one-to-many, cascade delete)
- **Document** has many **DocumentVersions** (one-to-many, cascade delete)
- **Document** links to **Policy** (many-to-one via `linked_policy_id`)

---

## Common Mixins

All models inherit from common mixins defined in `src/domain/models/base.py`:

| Mixin | Columns Added | Description |
|-------|---------------|-------------|
| **TimestampMixin** | `created_at`, `updated_at` | Automatic timestamps with timezone |
| **ReferenceNumberMixin** | `reference_number` | Auto-generated unique reference (e.g., INC-2026-0001) |
| **SoftDeleteMixin** | `deleted_at` | Soft delete with `is_deleted` property |
| **AuditTrailMixin** | `created_by_id`, `updated_by_id` | Track which user created/modified the record |
| **OptimisticLockMixin** | `version` | Prevents concurrent update conflicts |
