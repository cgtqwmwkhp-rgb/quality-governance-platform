# Investigations Tool Contracts v1.0

**Status:** APPROVED  
**Date:** 2026-01-26  
**Author:** Principal Engineer (Cursor.ai)  
**Stage:** Stage 1 - Contracts (Locked Before Build)

---

## 1. Template Contract v2.1

Replicates Plantexpand Incident Investigation Report Template v2.0 with conditional addenda for Complaint and RTA.

### 1.1 Section Structure

| Section | ID | Title | Level Gating | Required |
|---------|-----|-------|--------------|----------|
| 1 | `section_1_details` | Incident/Event Details | LOW, MEDIUM, HIGH | Yes |
| 2 | `section_2_immediate_actions` | Immediate Actions Taken | LOW, MEDIUM, HIGH | Yes |
| 3 | `section_3_investigation_findings` | Investigation Findings | LOW, MEDIUM, HIGH | Yes |
| 4 | `section_4_root_cause` | Root Cause Analysis (5-Whys) | MEDIUM, HIGH | MEDIUM+ |
| 5 | `section_5_corrective_actions` | Corrective Actions (CAPA) | HIGH | HIGH only |
| 6 | `section_6_fishbone` | Fishbone Diagram | HIGH | HIGH only |
| Sign-off | `section_signoff` | Sign-off & Approval | LOW, MEDIUM, HIGH | Yes |

### 1.2 Level Gating Rules

```json
{
  "LOW": ["section_1_details", "section_2_immediate_actions", "section_3_investigation_findings", "section_signoff"],
  "MEDIUM": ["section_1_details", "section_2_immediate_actions", "section_3_investigation_findings", "section_4_root_cause", "section_signoff"],
  "HIGH": ["section_1_details", "section_2_immediate_actions", "section_3_investigation_findings", "section_4_root_cause", "section_5_corrective_actions", "section_6_fishbone", "section_signoff"]
}
```

### 1.3 Section 1: Incident/Event Details

| Field ID | Label | Type | Required | Prefill Source |
|----------|-------|------|----------|----------------|
| `reference_number` | Reference Number | readonly_text | Yes | source.reference_number |
| `source_type` | Record Type | enum | Yes | source_type |
| `incident_date` | Date of Incident | datetime | Yes | source.event_date OR source.collision_date OR source.received_date |
| `location` | Location | text | Yes | source.location |
| `location_coordinates` | GPS Coordinates | coordinates | No | source.location_coordinates |
| `description` | Description of Event | textarea | Yes | source.description |
| `severity` | Severity Level | enum | Yes | source.severity OR source.potential_severity OR source.priority |
| `persons_involved` | Persons Involved | text | No | source.persons_involved OR source.complainant_name OR source.driver_name |
| `witnesses` | Witnesses | text | No | source.witness_names OR source.witnesses |
| `immediate_harm` | Immediate Harm/Damage | textarea | No | source.potential_consequences OR source.company_vehicle_damage |
| `evidence_refs` | Evidence References | evidence_gallery | No | linked evidence_assets |

### 1.4 Section 2: Immediate Actions Taken

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `actions_taken` | Actions Taken Immediately | textarea | Yes |
| `first_responder` | First Responder | text | No |
| `emergency_services` | Emergency Services Called | boolean | No |
| `area_secured` | Area Secured | boolean | No |
| `evidence_preserved` | Evidence Preserved | boolean | No |

### 1.5 Section 3: Investigation Findings

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `what_happened` | What Happened | textarea | Yes |
| `why_happened` | Why Did It Happen | textarea | Yes |
| `contributing_factors` | Contributing Factors | checklist | No |
| `management_factors` | Management/System Factors | textarea | No |
| `human_factors` | Human Factors | textarea | No |
| `environmental_factors` | Environmental Factors | textarea | No |

### 1.6 Section 4: Root Cause Analysis (5-Whys)

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `why_1` | Why 1 | textarea | Yes |
| `why_2` | Why 2 | textarea | Yes |
| `why_3` | Why 3 | textarea | No |
| `why_4` | Why 4 | textarea | No |
| `why_5` | Why 5 | textarea | No |
| `root_cause_statement` | Root Cause Statement | textarea | Yes |

### 1.7 Section 5: Corrective Actions (CAPA)

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `corrective_actions` | Corrective Actions | action_list | Yes |
| `preventive_actions` | Preventive Actions | action_list | No |
| `verification_method` | Verification Method | text | Yes |
| `target_completion` | Target Completion Date | date | Yes |
| `responsible_person` | Responsible Person | user_select | Yes |

### 1.8 Section 6: Fishbone Diagram (HIGH only)

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `fishbone_data` | Fishbone Diagram Data | fishbone | Yes |
| `fishbone_summary` | Fishbone Summary | textarea | Yes |

Fishbone Categories:
- People
- Methods
- Materials
- Machinery/Equipment
- Environment
- Measurement

### 1.9 Section Sign-off

| Field ID | Label | Type | Required |
|----------|-------|------|----------|
| `investigator_name` | Investigator Name | user_select | Yes |
| `investigator_sign_date` | Investigator Sign Date | datetime | Yes |
| `reviewer_name` | Reviewer Name | user_select | Yes |
| `reviewer_sign_date` | Reviewer Sign Date | datetime | No |
| `approver_name` | Approver Name | user_select | MEDIUM+ |
| `approver_sign_date` | Approver Sign Date | datetime | No |
| `approval_status` | Approval Status | enum | Yes |

Approval Status Enum:
- `PENDING_INVESTIGATION`
- `PENDING_REVIEW`
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`

### 1.10 Conditional Addenda

#### 1.10.1 Complaint Addendum (source_type = complaint)

| Field ID | Label | Type | Prefill Source |
|----------|-------|------|----------------|
| `complaint_type` | Complaint Type | enum | source.complaint_type |
| `complainant_company` | Complainant Company | text | source.complainant_company |
| `related_reference` | Related Order/Invoice | text | source.related_reference |
| `customer_satisfaction` | Customer Satisfied | boolean | source.customer_satisfied |
| `compensation_offered` | Compensation Offered | text | source.compensation_offered |

#### 1.10.2 RTA Addendum (source_type = road_traffic_collision)

| Field ID | Label | Type | Prefill Source |
|----------|-------|------|----------------|
| `collision_date` | Collision Date | datetime | source.collision_date |
| `collision_time` | Collision Time | time | source.collision_time |
| `road_name` | Road Name | text | source.road_name |
| `postcode` | Postcode | text | source.postcode |
| `weather_conditions` | Weather Conditions | text | source.weather_conditions |
| `road_conditions` | Road Conditions | text | source.road_conditions |
| `company_vehicle_reg` | Company Vehicle Registration | text | source.company_vehicle_registration |
| `company_vehicle_damage` | Company Vehicle Damage | textarea | source.company_vehicle_damage |
| `driver_injured` | Driver Injured | boolean | source.driver_injured |
| `driver_injury_details` | Driver Injury Details | textarea | source.driver_injury_details |
| `third_parties` | Third Parties Involved | json | source.third_parties |
| `police_attended` | Police Attended | boolean | source.police_attended |
| `police_reference` | Police Reference | text | source.police_reference |
| `insurance_notified` | Insurance Notified | boolean | source.insurance_notified |
| `insurance_reference` | Insurance Reference | text | source.insurance_reference |
| `fault_determination` | Fault Determination | enum | source.fault_determination |
| `cctv_available` | CCTV Available | boolean | source.cctv_available |
| `dashcam_available` | Dashcam Available | boolean | source.dashcam_footage_available |

---

## 2. EvidenceAsset Contract v1

### 2.1 Asset Type Enum

| Value | Description | Render Hint |
|-------|-------------|-------------|
| `photo` | Photograph/Image | thumbnail |
| `video` | Video file | embed |
| `pdf` | PDF document | link |
| `document` | Word/Excel document | link |
| `map_pin` | GPS location / map marker | map |
| `diagram` | Diagram/schematic | thumbnail |
| `chart` | Chart/graph | embed |
| `cctv_ref` | CCTV footage reference (not file) | link |
| `dashcam_ref` | Dashcam footage reference (not file) | link |
| `audio` | Audio recording | audio_player |
| `signature` | Digital signature image | thumbnail |
| `other` | Other file type | link |

### 2.2 Metadata Schema

```json
{
  "id": "integer",
  "storage_key": "string (unique)",
  "original_filename": "string (nullable)",
  "content_type": "string (MIME type)",
  "file_size_bytes": "integer (nullable)",
  "checksum_sha256": "string (nullable)",
  "asset_type": "enum (EvidenceAssetType)",
  "source_module": "enum (EvidenceSourceModule)",
  "source_id": "integer",
  "linked_investigation_id": "integer (nullable)",
  "title": "string (nullable)",
  "description": "string (nullable)",
  "captured_at": "datetime (nullable)",
  "captured_by_role": "string (nullable)",
  "latitude": "float (nullable, -90 to 90)",
  "longitude": "float (nullable, -180 to 180)",
  "location_description": "string (nullable)",
  "render_hint": "string (nullable)",
  "thumbnail_storage_key": "string (nullable)",
  "metadata_json": "json (nullable)",
  "visibility": "enum (EvidenceVisibility)",
  "contains_pii": "boolean (default: false)",
  "redaction_required": "boolean (default: false)",
  "retention_policy": "enum (EvidenceRetentionPolicy)",
  "retention_expires_at": "datetime (nullable)",
  "created_at": "datetime",
  "updated_at": "datetime",
  "created_by_id": "integer (nullable)",
  "deleted_at": "datetime (nullable)",
  "deleted_by_id": "integer (nullable)"
}
```

### 2.3 Visibility Enum (Customer Pack Rules)

| Value | Internal Pack | External Pack | Notes |
|-------|---------------|---------------|-------|
| `internal_only` | ❌ EXCLUDE | ❌ EXCLUDE | Never in any customer pack |
| `internal_customer` | ✅ INCLUDE | ❌ EXCLUDE | Internal packs only |
| `external_allowed` | ✅ INCLUDE | ✅ INCLUDE (may redact) | Both packs, may need redaction |
| `public` | ✅ INCLUDE | ✅ INCLUDE | Safe for all audiences |

### 2.4 Retention Policy Enum

| Value | Retention Period | Notes |
|-------|-----------------|-------|
| `standard` | 7 years | Standard record retention |
| `legal_hold` | Indefinite | Under legal hold, do not delete |
| `extended` | 10+ years | Extended retention for serious incidents |
| `temporary` | 90 days | Short-term unless promoted |

### 2.5 Permissions

| Action | Required Permission |
|--------|---------------------|
| Upload | `evidence:upload` + source module write access |
| View | `evidence:read` + source module read access |
| Update metadata | `evidence:update` + source module write access |
| Delete (soft) | `evidence:delete` + source module admin access |
| Link to investigation | `investigation:edit` |

---

## 3. Mapping Contract v1 (Deterministic)

### 3.1 Source Type to InvestigationDraft Mapping

#### 3.1.1 Near Miss Mapping

| Source Field | Target Field | Transform | Fallback |
|--------------|--------------|-----------|----------|
| `reference_number` | `section_1.reference_number` | direct | MISSING_EVIDENCE |
| `event_date` | `section_1.incident_date` | direct | MISSING_EVIDENCE |
| `location` | `section_1.location` | direct | MISSING_EVIDENCE |
| `location_coordinates` | `section_1.location_coordinates` | direct | null |
| `description` | `section_1.description` | direct | MISSING_EVIDENCE |
| `potential_severity` | `section_1.severity` | map_severity | NOT_APPLICABLE |
| `persons_involved` | `section_1.persons_involved` | direct | null |
| `witness_names` | `section_1.witnesses` | direct | null |
| `potential_consequences` | `section_1.immediate_harm` | direct | null |
| `preventive_action_suggested` | `section_2.actions_taken` | direct | null |
| `attachments` | evidence_assets | migrate_attachments | EMPTY_ARRAY |

#### 3.1.2 Complaint Mapping

| Source Field | Target Field | Transform | Fallback |
|--------------|--------------|-----------|----------|
| `reference_number` | `section_1.reference_number` | direct | MISSING_EVIDENCE |
| `received_date` | `section_1.incident_date` | direct | MISSING_EVIDENCE |
| `title` | `section_1.description` | prepend_title | direct |
| `description` | `section_1.description` | direct | MISSING_EVIDENCE |
| `priority` | `section_1.severity` | map_priority | NOT_APPLICABLE |
| `complainant_name` | `section_1.persons_involved` | direct | null |
| `complaint_type` | `addendum_complaint.complaint_type` | direct | null |
| `complainant_company` | `addendum_complaint.complainant_company` | direct | null |
| `related_reference` | `addendum_complaint.related_reference` | direct | null |
| `customer_satisfied` | `addendum_complaint.customer_satisfaction` | direct | null |
| `compensation_offered` | `addendum_complaint.compensation_offered` | direct | null |

#### 3.1.3 RTA Mapping

| Source Field | Target Field | Transform | Fallback |
|--------------|--------------|-----------|----------|
| `reference_number` | `section_1.reference_number` | direct | MISSING_EVIDENCE |
| `collision_date` | `section_1.incident_date` | direct | MISSING_EVIDENCE |
| `location` | `section_1.location` | direct | MISSING_EVIDENCE |
| `description` | `section_1.description` | direct | MISSING_EVIDENCE |
| `severity` | `section_1.severity` | map_rta_severity | NOT_APPLICABLE |
| `driver_name` | `section_1.persons_involved` | direct | null |
| `witnesses` | `section_1.witnesses` | direct | null |
| `company_vehicle_damage` | `section_1.immediate_harm` | direct | null |
| Full RTA record | `addendum_rta.*` | map_rta_addendum | null per field |

### 3.2 Reason Codes

| Code | Description |
|------|-------------|
| `SOURCE_MISSING_FIELD` | Field does not exist in source record |
| `TYPE_MISMATCH` | Field type incompatible, cannot map |
| `NOT_APPLICABLE` | Field not relevant for this source type |
| `EMPTY_VALUE` | Field exists but has no value |
| `REDACTED_PII` | Field contained PII and was redacted |
| `MAPPING_ERROR` | Unexpected error during mapping |

### 3.3 Severity Mapping Tables

#### 3.3.1 Near Miss Severity Mapping

| Source Value | Target Value |
|--------------|--------------|
| `low` | `LOW` |
| `medium` | `MEDIUM` |
| `high` | `HIGH` |
| `critical` | `HIGH` |

#### 3.3.2 RTA Severity Mapping

| Source Value | Target Value |
|--------------|--------------|
| `near_miss` | `LOW` |
| `damage_only` | `MEDIUM` |
| `minor_injury` | `MEDIUM` |
| `serious_injury` | `HIGH` |
| `fatal` | `HIGH` |

#### 3.3.3 Complaint Priority Mapping

| Source Value | Target Value |
|--------------|--------------|
| `LOW` | `LOW` |
| `MEDIUM` | `MEDIUM` |
| `HIGH` | `HIGH` |
| `CRITICAL` | `HIGH` |

### 3.4 Source Snapshot Contract

```json
{
  "source_type": "string (enum)",
  "source_id": "integer",
  "source_reference_number": "string",
  "source_schema_version": "string (e.g., '1.0')",
  "snapshot_taken_at": "datetime (ISO 8601)",
  "snapshot_taken_by_id": "integer",
  "snapshot_data": "json (immutable copy of source record, PII redacted)",
  "mapping_log": [
    {
      "source_field": "string",
      "target_field": "string",
      "transform": "string",
      "result": "string (SUCCESS | FALLBACK | ERROR)",
      "reason_code": "string (nullable)"
    }
  ]
}
```

---

## 4. Customer Pack Redaction Rules v1

### 4.1 Base Rules (ALL Packs)

| Content Type | Rule |
|--------------|------|
| Internal comments | ❌ ALWAYS EXCLUDE |
| Revision history | ❌ ALWAYS EXCLUDE |
| Audit trail (created_by, updated_by) | ❌ ALWAYS EXCLUDE |
| Draft versions | ❌ ALWAYS EXCLUDE |
| System metadata (IDs, timestamps) | ❌ ALWAYS EXCLUDE |

### 4.2 INTERNAL_CUSTOMER Pack Rules

| Content Type | Rule |
|--------------|------|
| Identities (names, emails) | ✅ INCLUDE (as-is) |
| Evidence assets (visibility: internal_customer) | ✅ INCLUDE |
| Evidence assets (visibility: external_allowed) | ✅ INCLUDE |
| Evidence assets (visibility: internal_only) | ❌ EXCLUDE |
| PII-flagged assets | ✅ INCLUDE (with warning banner) |
| Investigation findings | ✅ INCLUDE |
| Root cause analysis | ✅ INCLUDE |
| Corrective actions | ✅ INCLUDE (assigned_to visible) |

### 4.3 EXTERNAL_CUSTOMER Pack Rules

| Content Type | Rule |
|--------------|------|
| Identities (names, emails) | 🔒 REDACT by default |
| Identities (with explicit consent) | ✅ INCLUDE |
| Evidence assets (visibility: external_allowed) | ✅ INCLUDE |
| Evidence assets (visibility: public) | ✅ INCLUDE |
| Evidence assets (visibility: internal_customer) | ❌ EXCLUDE |
| Evidence assets (visibility: internal_only) | ❌ EXCLUDE |
| Evidence assets (redaction_required: true) | 🔒 REDACT or EXCLUDE |
| PII-flagged assets | 🔒 REDACT or EXCLUDE |
| Investigation findings | ✅ INCLUDE (sanitized) |
| Root cause analysis | ✅ INCLUDE (no individual names) |
| Corrective actions | ✅ INCLUDE (anonymized owner) |

### 4.4 Evidence Asset Handling in Packs

| Visibility | Contains PII | Redaction Required | Internal Pack | External Pack |
|------------|-------------|-------------------|---------------|---------------|
| internal_only | any | any | ❌ | ❌ |
| internal_customer | false | false | ✅ | ❌ |
| internal_customer | true | false | ✅ (warning) | ❌ |
| internal_customer | any | true | ✅ (warning) | ❌ |
| external_allowed | false | false | ✅ | ✅ |
| external_allowed | true | false | ✅ (warning) | ✅ (redact) |
| external_allowed | any | true | ✅ | 🔒 (redact) |
| public | false | false | ✅ | ✅ |
| public | true | any | ✅ (warning) | ✅ (flag error) |

### 4.5 Identity Redaction Transforms

| Field Type | Redaction Method |
|------------|------------------|
| Full name | Replace with role (e.g., "Driver", "Investigator") |
| Email | Remove entirely or replace with "[email redacted]" |
| Phone | Remove entirely or replace with "[phone redacted]" |
| Address | Remove or anonymize to region level |
| Vehicle registration | Partial mask (e.g., "AB12 ***") |
| Employee ID | Remove entirely |

### 4.6 Pack Generation Output Schema

```json
{
  "pack_id": "uuid",
  "pack_type": "enum (INTERNAL_CUSTOMER | EXTERNAL_CUSTOMER)",
  "investigation_id": "integer",
  "investigation_reference": "string",
  "generated_at": "datetime",
  "generated_by_id": "integer",
  "expires_at": "datetime (optional)",
  "content": {
    "sections": [
      {
        "section_id": "string",
        "title": "string",
        "fields": [
          {
            "field_id": "string",
            "label": "string",
            "value": "any (redacted as needed)",
            "redacted": "boolean"
          }
        ]
      }
    ],
    "evidence_assets": [
      {
        "asset_id": "integer",
        "title": "string",
        "asset_type": "string",
        "thumbnail_url": "string (optional)",
        "download_url": "string (optional, signed)",
        "included": "boolean",
        "exclusion_reason": "string (optional)"
      }
    ],
    "addenda": {
      "complaint": {},
      "rta": {}
    }
  },
  "redaction_log": [
    {
      "field_path": "string",
      "redaction_type": "string",
      "original_type": "string"
    }
  ],
  "checksum": "string (SHA-256 of content)"
}
```

---

## 5. Contract Versioning

| Contract | Version | Status |
|----------|---------|--------|
| Template Contract | v2.1 | LOCKED |
| EvidenceAsset Contract | v1 | LOCKED |
| Mapping Contract | v1 | LOCKED |
| Customer Pack Redaction Rules | v1 | LOCKED |

---

## 6. Change Control

Any changes to these contracts require:
1. Written justification with impact assessment
2. Review by Principal Engineer
3. Update to contract version number
4. Migration plan for existing data
5. Test coverage for new/changed rules
