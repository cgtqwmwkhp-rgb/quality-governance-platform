# Schema & Entity-Relationship Documentation

> Auto-generated from SQLAlchemy models in `src/domain/models/`.
> Last updated: 2026-04-04

---

## Table of Contents

1. [Base Mixins](#base-mixins)
2. [Entity Summary](#entity-summary)
3. [Entity Details](#entity-details)
4. [Relationship Diagram (Text ERD)](#relationship-diagram)

---

## Base Mixins

All domain models inherit from `Base` (SQLAlchemy `DeclarativeBase`). Most also
use one or more of these mixins, which add standard columns:

| Mixin | Columns Added | Notes |
|---|---|---|
| **TimestampMixin** | `created_at` (DateTime, indexed), `updated_at` (DateTime) | Timezone-aware, auto-set |
| **ReferenceNumberMixin** | `reference_number` (String(20), unique, indexed) | Format: `AUD-2026-0001` |
| **SoftDeleteMixin** | `deleted_at` (DateTime, nullable, indexed) | Adds `is_deleted` property |
| **AuditTrailMixin** | `created_by_id` (Int), `updated_by_id` (Int) | Nullable user references |
| **DataClassification** | `__data_classification__` class attr | C1-C4 tiers per DPIA policy |

---

## Entity Summary

### Core Platform (5)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 1 | Tenant | `tenants` | — | C2 (default) |
| 2 | TenantUser | `tenant_users` | — | C2 |
| 3 | User | `users` | Timestamp, SoftDelete | C2 |
| 4 | Role | `roles` | Timestamp | C2 |
| 5 | Notification | `notifications` | — | C2 |

### Safety & Incidents (4)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 6 | Incident | `incidents` | Timestamp, RefNumber, AuditTrail | **C4 Restricted** |
| 7 | IncidentAction | `incident_actions` | Timestamp, RefNumber, AuditTrail | C2 |
| 8 | NearMiss | `near_misses` | — (manual timestamps) | C4 Restricted |
| 9 | Complaint | `complaints` | Timestamp, RefNumber, AuditTrail | **C4 Restricted** |

### Audit & Compliance (4)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 10 | AuditTemplate | `audit_templates` | Timestamp, RefNumber, AuditTrail | C2 |
| 11 | AuditRun | `audit_runs` | Timestamp, RefNumber, AuditTrail | C2 |
| 12 | AuditFinding | `audit_findings` | Timestamp, RefNumber, AuditTrail | C2 |
| 13 | CAPAAction | `capa_actions` | — (manual timestamps) | C2 |

### Risk Management (2)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 14 | Risk | `risks` | Timestamp, RefNumber, AuditTrail | **C3 Confidential** |
| 15 | OperationalRiskControl | `risk_controls` | Timestamp, AuditTrail | C2 |

### Documents & Standards (3)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 16 | Document | `documents` | Timestamp, RefNumber, AuditTrail | C2 |
| 17 | Policy | `policies` | Timestamp, RefNumber, AuditTrail | C2 |
| 18 | Standard | `standards` | Timestamp | C2 |

### Investigation & Evidence (2)

| # | Entity | Table | Mixins | Data Classification |
|---|---|---|---|---|
| 19 | InvestigationRun | `investigation_runs` | Timestamp, RefNumber, AuditTrail | C2 |
| 20 | EvidenceAsset | `evidence_assets` | Timestamp, AuditTrail | C2 |

---

## Entity Details

### 1. Tenant

**Table:** `tenants`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| name | String(255) | NOT NULL |
| slug | String(100) | UNIQUE, NOT NULL, indexed |
| domain | String(255) | UNIQUE, nullable |
| is_active | Boolean | default `true` |
| subscription_tier | String(50) | default `standard` |
| admin_email | String(255) | NOT NULL |
| settings | JSON | Feature flags & config |
| max_users | Integer | default 50 |
| max_storage_gb | Integer | default 10 |
| created_at, updated_at | DateTime | Auto-managed |

**Relationships:** Has many `TenantUser`, referenced by nearly every domain entity via `tenant_id` FK.

---

### 2. TenantUser

**Table:** `tenant_users`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, NOT NULL |
| user_id | Integer | FK → `users.id`, NOT NULL |
| role | String(50) | default `user` (owner/admin/manager/user/viewer) |
| is_active | Boolean | default `true` |
| is_primary | Boolean | default `false` |
| custom_permissions | JSON | Override permissions |

---

### 3. User

**Table:** `users`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK, auto-increment |
| email | String(255) | UNIQUE, NOT NULL, indexed |
| hashed_password | String(255) | NOT NULL |
| first_name | String(100) | NOT NULL |
| last_name | String(100) | NOT NULL |
| job_title | String(100) | nullable |
| department | String(100) | nullable |
| is_active | Boolean | default `true` |
| is_superuser | Boolean | default `false` |
| azure_oid | String(36) | nullable, indexed (SSO) |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| deleted_at | DateTime | SoftDeleteMixin |

**Relationships:** Many-to-many with `Role` via `user_roles` junction table. Referenced by FKs across the entire schema (owner_id, reporter_id, assigned_to_id, etc.).

---

### 4. Role

**Table:** `roles`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK, auto-increment |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| name | String(50) | UNIQUE, NOT NULL, indexed |
| description | Text | nullable |
| permissions | Text | JSON string of permission codes |
| is_system_role | Boolean | default `false` |

**Junction table:** `user_roles` (user_id PK + role_id PK, both with CASCADE delete).

---

### 5. Notification

**Table:** `notifications`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| user_id | Integer | FK → `users.id`, NOT NULL, indexed |
| type | Enum(NotificationType) | NOT NULL, indexed |
| priority | Enum(NotificationPriority) | default `medium` |
| title | String(255) | NOT NULL |
| message | Text | NOT NULL |
| entity_type | String(50) | nullable (polymorphic) |
| entity_id | String(36) | nullable |
| sender_id | Integer | FK → `users.id`, nullable |
| is_read | Boolean | default `false`, indexed |
| created_at | DateTime | indexed |

---

### 6. Incident

**Table:** `incidents` · **Classification: C4 Restricted**

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed (RefNumberMixin) |
| title | String(300) | NOT NULL, indexed |
| description | Text | NOT NULL |
| incident_type | Enum(IncidentType) | CaseInsensitiveEnum |
| severity | Enum(IncidentSeverity) | CHECK constraint |
| status | Enum(IncidentStatus) | CHECK constraint, indexed |
| incident_date | DateTime(tz) | NOT NULL |
| location | String(300) | nullable |
| reporter_id | Integer | FK → `users.id` |
| investigator_id | Integer | FK → `users.id` |
| is_riddor_reportable | Boolean | nullable |
| is_sif / is_psif | Boolean | SIF classification fields |
| closed_by_id | Integer | FK → `users.id` |
| source_type | String(50) | default `manual` |
| processing_restricted | Boolean | GDPR Art. 18 |

**Indexes:** `(tenant_id, status)`, `(tenant_id, created_at)`.
**Check constraints:** severity, status, incident_type value lists.
**Relationships:** Has many `IncidentAction`.

---

### 7. IncidentAction

**Table:** `incident_actions`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| incident_id | Integer | FK → `incidents.id` CASCADE, indexed |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| title | String(300) | NOT NULL |
| description | Text | NOT NULL |
| action_type | String(50) | default `corrective` |
| priority | String(20) | default `medium` |
| owner_id | Integer | FK → `users.id` |
| status | Enum(ActionStatus) | CaseInsensitiveEnum |
| due_date | DateTime(tz) | nullable |
| verified_by_id | Integer | FK → `users.id` |

---

### 8. NearMiss

**Table:** `near_misses` · **Classification: C4 Restricted**

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| reference_number | String(50) | UNIQUE, indexed |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reporter_name | String(200) | NOT NULL |
| contract | String(100) | NOT NULL |
| location | Text | NOT NULL |
| event_date | DateTime(tz) | NOT NULL |
| description | Text | NOT NULL |
| status | String(50) | CHECK constraint, indexed |
| priority | String(20) | CHECK constraint |
| assigned_to_id | Integer | FK → `users.id` |
| processing_restricted | Boolean | GDPR Art. 18 |

**Check constraints:** status in (REPORTED, UNDER_REVIEW, ACTION_REQUIRED, IN_PROGRESS, CLOSED); priority in (LOW, MEDIUM, HIGH, CRITICAL).

---

### 9. Complaint

**Table:** `complaints` · **Classification: C4 Restricted**

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed (RefNumberMixin) |
| external_ref | String(100) | UNIQUE, indexed (idempotency) |
| title | String(300) | NOT NULL, indexed |
| description | Text | NOT NULL |
| complaint_type | Enum(ComplaintType) | CaseInsensitiveEnum |
| priority | Enum(ComplaintPriority) | CHECK constraint |
| status | Enum(ComplaintStatus) | CHECK constraint, indexed |
| received_date | DateTime(tz) | NOT NULL |
| complainant_name | String(200) | NOT NULL |
| complainant_email | String(255) | nullable |
| owner_id | Integer | FK → `users.id` |
| closed_by_id | Integer | FK → `users.id` |
| processing_restricted | Boolean | GDPR Art. 18 |

**Indexes:** `(tenant_id, status)`, `(tenant_id, created_at)`.
**Relationships:** Has many `ComplaintAction`.

---

### 10. AuditTemplate

**Table:** `audit_templates`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| name | String(200) | NOT NULL, indexed |
| external_id | String(36) | UNIQUE, indexed (UUID) |
| audit_type | String(50) | default `inspection` |
| version | Integer | default 1 |
| template_status | Enum(TemplateLifecycleStatus) | DRAFT→PUBLISHED flow |
| scoring_method | String(50) | default `percentage` |
| passing_score | Float | nullable |
| created_by_id | Integer | FK → `users.id` |

**Relationships:** Has many `AuditSection`, `AuditQuestion`, `AuditRun`, `TemplateVersion`.

---

### 11. AuditRun

**Table:** `audit_runs`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| template_id | Integer | FK → `audit_templates.id`, NOT NULL |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| title | String(300) | nullable |
| status | Enum(AuditStatus) | CaseInsensitiveEnum |
| scheduled_date | DateTime(tz) | nullable |
| assigned_to_id | Integer | FK → `users.id` |
| created_by_id | Integer | FK → `users.id` |
| score | Float | nullable |
| score_percentage | Float | nullable |
| passed | Boolean | nullable |

**Indexes:** `(tenant_id, status)`, `(tenant_id, created_at)`.
**Relationships:** Has many `AuditResponse`, `AuditFinding`. Belongs to `AuditTemplate`.

---

### 12. AuditFinding

**Table:** `audit_findings`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| run_id | Integer | FK → `audit_runs.id` CASCADE |
| question_id | Integer | FK → `audit_questions.id`, nullable |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| title | String(300) | NOT NULL |
| severity | String(50) | default `medium` |
| finding_type | String(50) | default `nonconformity` |
| status | Enum(FindingStatus) | indexed |
| corrective_action_required | Boolean | default `true` |
| created_by_id | Integer | FK → `users.id` |

---

### 13. CAPAAction

**Table:** `capa_actions`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(50) | UNIQUE, indexed |
| title | String(255) | NOT NULL |
| capa_type | Enum(CAPAType) | corrective / preventive |
| status | Enum(CAPAStatus) | indexed |
| priority | Enum(CAPAPriority) | default `medium` |
| source_type | Enum(CAPASource) | incident, audit_finding, complaint, etc. |
| source_id | Integer | nullable (polymorphic FK) |
| source_reference | String(100) | nullable, indexed (UUID refs) |
| assigned_to_id | Integer | FK → `users.id` |
| verified_by_id | Integer | FK → `users.id` |
| created_by_id | Integer | FK → `users.id`, NOT NULL |
| due_date | DateTime | nullable |
| iso_standard | String(50) | nullable |
| clause_reference | String(50) | nullable |

---

### 14. Risk

**Table:** `risks` · **Classification: C3 Confidential**

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| title | String(300) | NOT NULL, indexed |
| description | Text | NOT NULL |
| category | String(100) | default `operational` |
| likelihood | Integer | CHECK 1–5 |
| impact | Integer | CHECK 1–5 |
| risk_score | Integer | CHECK 1–25 |
| risk_level | String(50) | default `medium` |
| owner_id | Integer | FK → `users.id` |
| status | Enum(RiskStatus) | CaseInsensitiveEnum, indexed |
| treatment_strategy | String(50) | default `mitigate` |
| review_frequency_months | Integer | default 12 |

**Check constraints:** likelihood 1-5, impact 1-5, risk_score 1-25.
**Relationships:** Has many `OperationalRiskControl`, `RiskAssessment`.

---

### 15. OperationalRiskControl

**Table:** `risk_controls`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| risk_id | Integer | FK → `risks.id` CASCADE, indexed |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| title | String(300) | NOT NULL |
| control_type | String(50) | default `preventive` |
| implementation_status | String(50) | default `planned` |
| effectiveness | String(50) | nullable |
| owner_id | Integer | FK → `users.id` |

---

### 16. Document

**Table:** `documents`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| title | String(500) | NOT NULL, indexed |
| file_name | String(500) | NOT NULL |
| file_type | Enum(FileType) | NOT NULL |
| file_size | Integer | NOT NULL (bytes) |
| file_path | String(1000) | NOT NULL (blob storage) |
| document_type | Enum(DocumentType) | default `other` |
| sensitivity | Enum(SensitivityLevel) | default `internal` |
| status | Enum(DocumentStatus) | indexed |
| version | String(20) | default `1.0` |
| parent_document_id | Integer | FK → `documents.id` (self-ref) |
| linked_policy_id | Integer | FK → `policies.id` |
| linked_standard_id | Integer | FK → `standards.id` |
| created_by_id | Integer | FK → `users.id` |

**Relationships:** Has many `DocumentChunk`, `DocumentAnnotation`, `DocumentVersion`.

---

### 17. Policy

**Table:** `policies`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| title | String(300) | NOT NULL, indexed |
| document_type | Enum(DocumentType) | default `policy` |
| status | Enum(DocumentStatus) | indexed |
| category | String(100) | nullable |
| owner_id | Integer | FK → `users.id` |
| approver_id | Integer | FK → `users.id` |
| review_frequency_months | Integer | default 12 |

**Relationships:** Has many `PolicyVersion`.

---

### 18. Standard

**Table:** `standards`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| code | String(20) | UNIQUE, indexed (e.g. `ISO9001`) |
| name | String(200) | NOT NULL |
| full_name | String(500) | NOT NULL |
| version | String(20) | NOT NULL (e.g. `2015`) |
| is_active | Boolean | default `true` |

**Relationships:** Has many `Clause` → each has many `Control`.

---

### 19. InvestigationRun

**Table:** `investigation_runs`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| reference_number | String(20) | UNIQUE, indexed |
| template_id | Integer | FK → `investigation_templates.id`, indexed |
| assigned_entity_type | Enum(AssignedEntityType) | NOT NULL, indexed |
| assigned_entity_id | Integer | NOT NULL, indexed |
| status | Enum(InvestigationStatus) | indexed |
| level | Enum(InvestigationLevel) | LOW/MEDIUM/HIGH |
| title | String(255) | NOT NULL |
| data | JSON | Template response data |
| version | Integer | Optimistic locking |
| assigned_to_user_id | Integer | FK → `users.id` |
| reviewer_user_id | Integer | FK → `users.id` |
| approved_by_id | Integer | FK → `users.id` |

**Relationships:** Has many `InvestigationComment`, `InvestigationRevisionEvent`, `InvestigationCustomerPack`, `InvestigationAction`. Belongs to `InvestigationTemplate`.

---

### 20. EvidenceAsset

**Table:** `evidence_assets`

| Column | Type | Constraints |
|---|---|---|
| id | Integer | PK |
| tenant_id | Integer | FK → `tenants.id`, nullable, indexed |
| storage_key | String(500) | UNIQUE, NOT NULL, indexed |
| original_filename | String(255) | nullable |
| content_type | String(100) | NOT NULL (MIME) |
| file_size_bytes | Integer | nullable |
| checksum_sha256 | String(64) | nullable |
| asset_type | Enum(EvidenceAssetType) | NOT NULL |
| source_module | Enum(EvidenceSourceModule) | NOT NULL, indexed |
| source_id | String(36) | NOT NULL, indexed |
| linked_investigation_id | Integer | FK → `investigation_runs.id` |
| visibility | Enum(EvidenceVisibility) | default `internal_customer` |
| contains_pii | Boolean | default `false` |
| retention_policy | Enum(EvidenceRetentionPolicy) | default `standard` |

**Indexes:** `(source_module, source_id)`, `(asset_type)`, `(visibility)`.

---

## Supporting / Child Tables

These tables are children of the main entities above:

| Table | Parent FK | Purpose |
|---|---|---|
| `tenant_invitations` | `tenants.id` | Pending tenant join invitations |
| `user_roles` | `users.id`, `roles.id` | M:N junction (User ↔ Role) |
| `incident_actions` | `incidents.id` | Corrective actions from incidents |
| `incident_running_sheet_entries` | `incidents.id` | Timestamped log entries |
| `complaint_actions` | `complaints.id` | Follow-up actions from complaints |
| `complaint_running_sheet_entries` | `complaints.id` | Timestamped log entries |
| `near_miss_running_sheet_entries` | `near_misses.id` | Timestamped log entries |
| `risk_controls` | `risks.id` | Operational controls for risks |
| `risk_assessments` | `risks.id` | Assessment history (inherent/residual/target) |
| `audit_sections` | `audit_templates.id` | Grouped question sections |
| `audit_questions` | `audit_templates.id` | Template questions with scoring |
| `audit_responses` | `audit_runs.id` | Per-question answers |
| `audit_findings` | `audit_runs.id` | Non-conformities & observations |
| `template_versions` | `audit_templates.id` | Snapshot JSON for rollback |
| `policy_versions` | `policies.id` | Versioned policy content + approval flow |
| `clauses` | `standards.id` | Numbered clauses (self-referencing hierarchy) |
| `controls` | `clauses.id` | ISO controls within clauses |
| `document_chunks` | `documents.id` | RAG vector-search chunks |
| `document_annotations` | `documents.id` | User highlights & notes |
| `document_versions` | `documents.id` | File version history |
| `investigation_comments` | `investigation_runs.id` | Internal threaded comments |
| `investigation_revision_events` | `investigation_runs.id` | Audit trail of changes |
| `investigation_customer_packs` | `investigation_runs.id` | Redacted pack snapshots |
| `investigation_actions` | `investigation_runs.id` | Corrective/preventive actions |
| `audit_log_entries` | `tenants.id` | Immutable hash-chain audit log |
| `audit_log_verifications` | `tenants.id` | Periodic chain verification |
| `audit_log_exports` | `tenants.id` | Compliance export records |
| `workflow_templates` | `tenants.id` | Reusable workflow definitions |
| `workflow_instances` | `workflow_templates.id` | Running workflow instances |
| `workflow_steps` | `workflow_instances.id` | Step execution records |
| `approval_requests` | `workflow_steps.id` | Individual approval tasks |
| `escalation_rules` | `workflow_templates.id` | Auto-escalation config |
| `escalation_logs` | `workflow_instances.id` | Escalation event records |
| `mentions` | `users.id` | @mention tracking |
| `assignments` | `users.id` | Entity assignment tracking |
| `notification_preferences` | `users.id` | Per-user notification settings |
| `index_jobs` | `tenants.id` | Document indexing background jobs |

---

## Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MULTI-TENANCY CORE                               │
│                                                                         │
│  ┌──────────┐    1:N    ┌─────────────┐    N:1    ┌──────────┐         │
│  │  Tenant   │─────────▶│ TenantUser  │◀──────────│   User   │         │
│  │ (tenants) │          │(tenant_users)│           │ (users)  │         │
│  └────┬─────┘          └─────────────┘           └────┬─────┘         │
│       │                                                │               │
│       │  tenant_id FK on all domain tables              │  M:N          │
│       │                                                ▼               │
│       │                                          ┌──────────┐          │
│       │                                          │   Role   │          │
│       │                                          │ (roles)  │          │
│       │                                          └──────────┘          │
└───────┼─────────────────────────────────────────────────────────────────┘
        │
        │  (tenant_id FK present on nearly every table below)
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SAFETY & INCIDENTS                                │
│                                                                         │
│  ┌──────────────┐  1:N  ┌────────────────┐                             │
│  │   Incident   │──────▶│ IncidentAction │                             │
│  │ (incidents)  │       │(incident_actions│                             │
│  └──────┬───────┘       └────────────────┘                             │
│         │                                                               │
│         │ linked_risk_ids     ┌────────────┐  1:N  ┌─────────────────┐ │
│         │·····················│  Complaint  │─────▶│ ComplaintAction  │ │
│         │                    │(complaints) │      │(complaint_actions)│ │
│         │                    └─────────────┘      └─────────────────┘ │
│         │                                                               │
│         │                    ┌────────────┐                             │
│         │                    │  NearMiss  │                             │
│         │                    │(near_misses)│                             │
│         │                    └─────────────┘                             │
└─────────┼───────────────────────────────────────────────────────────────┘
          │
          │  source_type / source_id
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CAPA & INVESTIGATIONS                           │
│                                                                         │
│  ┌────────────┐           ┌─────────────────────┐                      │
│  │ CAPAAction │           │ InvestigationTemplate│                      │
│  │(capa_actions│           │(investigation_       │                      │
│  └────────────┘           │  templates)          │                      │
│   source_type points to:  └──────────┬──────────┘                      │
│   incident, audit_finding,           │  1:N                            │
│   complaint, risk, etc.              ▼                                  │
│                            ┌─────────────────┐  1:N  ┌──────────────┐  │
│                            │InvestigationRun │──────▶│Investigation │  │
│                            │(investigation_  │       │   Action     │  │
│                            │  runs)          │       └──────────────┘  │
│                            └────────┬────────┘                         │
│                                     │  1:N                             │
│                              ┌──────┴──────┐                           │
│                              ▼             ▼                           │
│                     ┌──────────────┐ ┌───────────────┐                 │
│                     │Investigation │ │Investigation  │                 │
│                     │  Comment     │ │ CustomerPack  │                 │
│                     └──────────────┘ └───────────────┘                 │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       RISK MANAGEMENT                                   │
│                                                                         │
│  ┌──────────┐  1:N  ┌──────────────────────┐                           │
│  │   Risk   │──────▶│OperationalRiskControl│                           │
│  │ (risks)  │       │  (risk_controls)     │                           │
│  └────┬─────┘       └──────────────────────┘                           │
│       │  1:N                                                            │
│       ▼                                                                 │
│  ┌────────────────┐                                                     │
│  │ RiskAssessment │  (inherent → residual → target scoring)            │
│  │(risk_assessments│                                                     │
│  └────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      AUDIT MANAGEMENT                                   │
│                                                                         │
│  ┌───────────────┐  1:N  ┌──────────────┐                              │
│  │ AuditTemplate │──────▶│  AuditSection │──┐                          │
│  │(audit_        │       │(audit_sections│  │ 1:N                      │
│  │  templates)   │       └──────────────┘  ▼                           │
│  └───────┬───────┘  1:N  ┌──────────────────┐                          │
│          │──────────────▶│  AuditQuestion   │                          │
│          │               │ (audit_questions) │                          │
│          │               └──────────────────┘                          │
│          │  1:N                                                         │
│          ▼                                                              │
│  ┌──────────────┐  1:N  ┌───────────────┐                              │
│  │   AuditRun   │──────▶│ AuditResponse │                              │
│  │ (audit_runs) │       │(audit_responses│                              │
│  └──────┬───────┘       └───────────────┘                              │
│         │  1:N                                                          │
│         ▼                                                               │
│  ┌───────────────┐                                                      │
│  │ AuditFinding  │                                                      │
│  │(audit_findings)│                                                      │
│  └───────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    DOCUMENTS & STANDARDS                                 │
│                                                                         │
│  ┌──────────┐  1:N  ┌───────────────┐                                  │
│  │ Standard │──────▶│    Clause     │ (self-referencing hierarchy)     │
│  │(standards)│       │  (clauses)   │──┐                               │
│  └──────────┘       └──────┬────────┘  │ parent_clause_id              │
│                            │ 1:N       │                                │
│                            ▼           │                                │
│                     ┌────────────┐     │                                │
│                     │  Control   │◀────┘                                │
│                     │ (controls) │                                      │
│                     └────────────┘                                      │
│                                                                         │
│  ┌──────────┐  1:N  ┌───────────────┐                                  │
│  │  Policy  │──────▶│ PolicyVersion │  (approval workflow)             │
│  │(policies)│       │(policy_versions│                                  │
│  └──────────┘       └───────────────┘                                  │
│                                                                         │
│  ┌──────────┐  1:N  ┌───────────────┐  1:N  ┌──────────────────┐      │
│  │ Document │──────▶│DocumentChunk  │       │DocumentAnnotation│      │
│  │(documents│       │(document_     │       │(document_        │      │
│  └────┬─────┘       │  chunks)     │       │  annotations)    │      │
│       │             └───────────────┘       └──────────────────┘      │
│       │  linked_policy_id ──▶ policies                                 │
│       │  linked_standard_id ──▶ standards                              │
│       │  parent_document_id ──▶ documents (self-ref)                   │
└───────┴─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       EVIDENCE & WORKFLOW                               │
│                                                                         │
│  ┌───────────────┐  source_module + source_id (polymorphic)            │
│  │ EvidenceAsset │  Links to: incident, complaint, near_miss,          │
│  │(evidence_     │           investigation, audit, assessment, etc.    │
│  │  assets)      │                                                      │
│  └───────────────┘                                                      │
│                                                                         │
│  ┌──────────────────┐ 1:N ┌──────────────────┐ 1:N ┌───────────────┐  │
│  │WorkflowTemplate  │────▶│WorkflowInstance  │────▶│ WorkflowStep  │  │
│  │(workflow_        │     │(workflow_        │     │(workflow_steps)│  │
│  │  templates)      │     │  instances)      │     └───────┬───────┘  │
│  └──────────────────┘     └──────────────────┘             │ 1:N      │
│                                                             ▼          │
│                                                    ┌────────────────┐  │
│                                                    │ApprovalRequest │  │
│                                                    │(approval_      │  │
│                                                    │  requests)     │  │
│                                                    └────────────────┘  │
│                                                                         │
│  ┌────────────────┐  Hash-chain immutable log                          │
│  │ AuditLogEntry  │  entry_hash → previous_hash (blockchain style)    │
│  │(audit_log_     │                                                     │
│  │  entries)      │                                                     │
│  └────────────────┘                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Cross-Entity Relationships

| From | To | Cardinality | Via |
|---|---|---|---|
| Tenant | All entities | 1:N | `tenant_id` FK on every table |
| User | Incident | 1:N | `reporter_id`, `investigator_id`, `closed_by_id` |
| User | Risk | 1:N | `owner_id` |
| User | AuditRun | 1:N | `assigned_to_id`, `created_by_id` |
| User | Complaint | 1:N | `owner_id`, `closed_by_id` |
| User | CAPAAction | 1:N | `assigned_to_id`, `verified_by_id`, `created_by_id` |
| User | Role | M:N | `user_roles` junction table |
| Incident | IncidentAction | 1:N | `incident_id` FK |
| Complaint | ComplaintAction | 1:N | `complaint_id` FK |
| Risk | RiskControl | 1:N | `risk_id` FK |
| Risk | RiskAssessment | 1:N | `risk_id` FK |
| AuditTemplate | AuditRun | 1:N | `template_id` FK |
| AuditTemplate | AuditSection | 1:N | `template_id` FK |
| AuditRun | AuditFinding | 1:N | `run_id` FK |
| AuditRun | AuditResponse | 1:N | `run_id` FK |
| Standard | Clause | 1:N | `standard_id` FK |
| Clause | Control | 1:N | `clause_id` FK |
| Clause | Clause | 1:N (self) | `parent_clause_id` FK |
| Document | DocumentChunk | 1:N | `document_id` FK |
| Document | Policy | N:1 | `linked_policy_id` FK |
| Document | Standard | N:1 | `linked_standard_id` FK |
| Document | Document | N:1 (self) | `parent_document_id` FK |
| Policy | PolicyVersion | 1:N | `policy_id` FK |
| InvestigationTemplate | InvestigationRun | 1:N | `template_id` FK |
| InvestigationRun | InvestigationAction | 1:N | `investigation_id` FK |
| EvidenceAsset | InvestigationRun | N:1 | `linked_investigation_id` FK |
| CAPAAction | (polymorphic) | N:1 | `source_type` + `source_id` |
| EvidenceAsset | (polymorphic) | N:1 | `source_module` + `source_id` |
| WorkflowTemplate | WorkflowInstance | 1:N | `template_id` FK |
| WorkflowInstance | WorkflowStep | 1:N | `instance_id` FK |
| WorkflowStep | ApprovalRequest | 1:N | `step_id` FK |
