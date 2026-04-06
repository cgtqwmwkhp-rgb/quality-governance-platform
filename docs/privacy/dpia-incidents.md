# Data Protection Impact Assessment (DPIA)

## Incident & Complaint Management Modules

| Field | Value |
|-------|-------|
| **Assessment Date** | 2026-03-07 |
| **Assessor** | Quality Governance Team |
| **Modules in Scope** | Incident Reporting, Complaint Management, Near Miss, RTA |
| **DPIA Reference** | DPIA-001 |
| **Review Due** | 2026-09-07 (6 months) |

---

## 1. Data Inventory

### 1.1 Personal Data Collected

| Data Element | Category | Source | Storage Location | Retention |
|-------------|----------|--------|-----------------|-----------|
| Reporter name | Identity | User input / JWT | `incidents.reported_by_name` | Duration of employment + 7 years |
| Reporter email | Contact | User input / JWT | `incidents.reporter_email` | Same as above |
| Reporter phone | Contact | User input | `incidents.reporter_phone` | Same as above |
| Injured person name | Identity / Health | User input | `incidents.injured_person_name` | RIDDOR: 3 years minimum |
| Injury description | Health (Special Category) | User input | `incidents.injury_description` | RIDDOR: 3 years minimum |
| Witness names | Identity | User input | `incidents.witness_names` (JSON) | Same as incident |
| Complainant name | Identity | User input / Email | `complaints.complainant_name` | Contract period + 6 years |
| Complainant email | Contact | User input / Email | `complaints.complainant_email` | Same as above |
| Complainant phone | Contact | User input | `complaints.complainant_phone` | Same as above |
| Assigned investigator | Identity | System assignment | `*.assigned_to_id` (FK to users) | Same as parent record |
| GPS coordinates | Location | Mobile input | `incidents.latitude`, `incidents.longitude` | Same as incident |
| Photographs | Visual (may contain faces) | Mobile upload | Azure Blob Storage | Same as incident |

### 1.2 Special Category Data

| Element | Legal Basis | Additional Safeguards |
|---------|-------------|----------------------|
| Injury description | Art. 9(2)(b) — Employment obligation (H&S) | Field-level encryption (Fernet/AES-128-CBC), access restricted to investigators + H&S managers |
| Medical treatment details | Art. 9(2)(b) | Same encryption, audit trail on access |
| RIDDOR classification | Art. 9(2)(b) + Legal obligation | Immutable audit trail, retention enforced |

---

## 2. Processing Purpose & Legal Basis

| Purpose | Legal Basis (GDPR Art. 6) | Special Category Basis (Art. 9) |
|---------|--------------------------|--------------------------------|
| Record workplace incidents | Art. 6(1)(c) — Legal obligation (H&S at Work Act 1974, RIDDOR 2013) | Art. 9(2)(b) — Employment |
| Investigate root causes | Art. 6(1)(f) — Legitimate interest (preventing future incidents) | Art. 9(2)(b) |
| Track corrective actions | Art. 6(1)(c) — Legal obligation + Art. 6(1)(f) — Legitimate interest | N/A |
| Handle customer complaints | Art. 6(1)(b) — Contract performance + Art. 6(1)(f) — Legitimate interest | N/A |
| Generate regulatory reports | Art. 6(1)(c) — Legal obligation (RIDDOR, HSE) | Art. 9(2)(b) |
| Calculate risk scores | Art. 6(1)(f) — Legitimate interest | N/A (aggregated) |

---

## 3. Data Flow

```
Reporter (field/portal) → FastAPI endpoint → Validation → PostgreSQL
                                                ↓
                                          Fernet encryption (PII fields)
                                                ↓
                                          Audit trail (immutable hash-chain)
                                                ↓
                                   Azure Blob Storage (attachments)

Access: JWT-authenticated users → tenant_id filter → role check → data
```

### 3.1 Data Sharing

| Recipient | Data Shared | Purpose | Safeguard |
|-----------|------------|---------|-----------|
| HSE (via RIDDOR) | Incident details | Legal obligation | Manual export, data minimised |
| Insurance providers | Incident + RTA summaries | Contract | Data minimised, no health data unless required |
| Tenant administrators | All tenant data | Platform operation | Tenant isolation enforced |
| AI services (Copilot) | De-identified summaries | Analysis | PII stripped before processing |

---

## 4. Risk Assessment

| Risk | Likelihood | Impact | Inherent Risk | Mitigation | Residual Risk |
|------|-----------|--------|---------------|------------|---------------|
| Cross-tenant data leakage | Low | Critical | High | Tenant_id filtering on all queries (enforced Week 1-2), superuser bypass only | Low |
| Unauthorized access to health data | Low | High | Medium | JWT auth on all endpoints, role-based access, field encryption | Low |
| PII in logs | Medium | Medium | Medium | PII filter in structured logger, log sampling | Low |
| Data breach via SQL injection | Very Low | Critical | Medium | SQLAlchemy parameterised queries, input validation (Pydantic) | Very Low |
| Excessive data retention | Medium | Medium | Medium | Retention policy defined but not automated | Medium |
| Unencrypted data at rest | Low | High | Medium | Field-level Fernet encryption for PII, Azure disk encryption | Low |
| Data loss | Very Low | High | Low | Azure managed backups, point-in-time recovery | Very Low |

---

## 5. Rights of Data Subjects

| Right | Implementation Status | Mechanism |
|-------|----------------------|-----------|
| Access (Art. 15) | Partial | API supports record retrieval; no self-service portal for data subjects yet |
| Rectification (Art. 16) | Implemented | PATCH endpoints with audit trail |
| Erasure (Art. 17) | Partial | Soft-delete implemented; hard-delete not available for RIDDOR-reportable incidents (legal retention override) |
| Restriction (Art. 18) | Implemented | `processing_restricted` column + `GDPRService.restrict_processing()` (src/domain/services/gdpr_service.py) |
| Portability (Art. 20) | Partial | JSON export available via API but no self-service portal |
| Object (Art. 21) | N/A | Processing based on legal obligation, not consent |

### 5.1 Gaps & Remediation

| Gap | Priority | Remediation | Target |
|-----|----------|-------------|--------|
| No self-service data access portal | P2 | Build DSAR endpoint `/api/v1/privacy/my-data` | Q3 2026 |
| No automated retention enforcement | P2 | Celery task to flag records past retention | Q3 2026 |
| ~~No restriction-of-processing flag~~ | ~~P3~~ | ~~Resolved: `processing_restricted` column added via Alembic migration; `GDPRService.restrict_processing()` enforces Art. 18~~ | Done |

---

## 6. Consultation

| Stakeholder | Consulted | Outcome |
|------------|-----------|---------|
| Data Protection Officer | Reviewed (internal — 2026-04-03) | DPIA to be reviewed |
| Information Security | Reviewed (internal — 2026-04-03) | Encryption controls to be verified |
| HR / H&S Manager | Reviewed (internal — 2026-04-03) | Retention periods to be confirmed |
| Legal | Reviewed (internal — 2026-04-03) | RIDDOR retention obligations to be confirmed |

---

## 7. Decision

- [x] Processing may proceed with additional mitigations (listed above)
- [ ] Processing must not proceed until risks are addressed
- [ ] ICO consultation required (Art. 36)

**Signed**: Platform Engineering Lead **Date**: 2026-04-04

**DPO Review**: Reviewed — internal compliance team **Date**: 2026-04-04
