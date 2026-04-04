# Privacy Program Overview (D07)

**Platform:** Quality Governance Platform (QGP)
**Version:** 1.0
**Effective:** 2026-04-04 | **Review:** 2026-10-04
**Related:** [`data-classification.md`](data-classification.md), [`data-retention-policy.md`](data-retention-policy.md), [`dpia-incidents.md`](dpia-incidents.md), [`dpia-template.md`](dpia-template.md)

---

## 1. Purpose

Single-source overview of the Quality Governance Platform's privacy program covering GDPR compliance, data protection, and privacy-by-design implementation. This document maps regulatory requirements to concrete platform controls and provides evidence pointers for audit and certification.

---

## 2. Regulatory Framework

| Regulation | Jurisdiction | Relevance |
|------------|-------------|-----------|
| **GDPR** (EU 2016/679) | EU / EEA | Primary — all processing of personal data |
| **UK Data Protection Act 2018** | United Kingdom | UK GDPR equivalent; applies to UK tenants |

### Key GDPR Articles

| Article | Topic | QGP Implementation |
|---------|-------|---------------------|
| Art. 5 | Principles of processing | Data minimisation, purpose limitation, accuracy enforced by domain model validation |
| Art. 6 | Lawful basis | Legitimate interest (safety reporting), contract (employee data), legal obligation (RIDDOR) |
| Art. 13–14 | Transparency | Privacy notices; data export in human-readable JSON |
| Art. 15 | Right of access | `GDPRService.export_user_data()` |
| Art. 17 | Right to erasure | `GDPRService.request_erasure()` via `PseudonymizationService` |
| Art. 18 | Right to restriction | `GDPRService.restrict_processing()` |
| Art. 20 | Right to portability | JSON export from `export_user_data()` |
| Art. 25 | Privacy by design | `DataClassification` enum in model layer; classification-aware handling |
| Art. 32 | Security of processing | TLS 1.2+, field-level Fernet encryption, tenant isolation, audit trail |
| Art. 33–34 | Breach notification | Incident response runbook with 72-hour supervisory authority notification |
| Art. 35 | DPIA | Completed for incident/complaint modules ([DPIA-001](dpia-incidents.md)) |

---

## 3. Privacy-by-Design Implementation

| Principle | Implementation | Evidence |
|-----------|---------------|----------|
| **Data classification at model layer** | `DataClassification` class (C1–C4) in `src/domain/models/base.py`; every model declares `__data_classification__` | [`data-classification.md`](data-classification.md) |
| **DPIA process** | Formal DPIA completed before processing special-category data | [`dpia-incidents.md`](dpia-incidents.md), [`dpia-template.md`](dpia-template.md) |
| **Data retention with automated enforcement** | Per-entity retention schedule; `AuditLogEntry.retention_days` (default 2555 ≈ 7 years); Celery purge job | [`data-retention-policy.md`](data-retention-policy.md) |
| **Pseudonymization** | SHA-256 HMAC one-way hashing of PII fields (`email`, `first_name`, `last_name`, `phone`) via `PseudonymizationService` | `src/domain/services/pseudonymization_service.py` |
| **Encryption** | Azure managed encryption at rest; field-level Fernet for C4 data; TLS 1.2+ in transit | Infrastructure config |
| **Tenant isolation** | `tenant_id` filter on every query; row-level security for C4 | Domain model base classes |
| **PII-filtered logging** | Structured logger strips C3/C4 fields before output | Logging configuration |
| **Audit trail** | Immutable hash-chain `AuditLogEntry` records for all mutations | `src/domain/models/audit_log.py` |

---

## 4. Data Subject Rights

| GDPR Right | Article | Implementation | Service Method | Evidence |
|------------|---------|----------------|---------------|----------|
| **Right of access** | Art. 15 | Full user data export in machine-readable JSON | `GDPRService.export_user_data(user_id, tenant_id)` | Returns profile, incidents, complaints, actions, audit log |
| **Right to erasure** | Art. 17 | Pseudonymization of PII fields + clearing of metadata; supports `dry_run` mode | `GDPRService.request_erasure(user_id, tenant_id, reason)` | PII hashed via `PseudonymizationService`; `job_title`, `department` cleared |
| **Right to restrict processing** | Art. 18 | Per-record processing restriction flag | `GDPRService.restrict_processing(user_id, record_type, record_id)` | Prevents further processing of specified records |
| **Right to portability** | Art. 20 | JSON export of all personal data | `GDPRService.export_user_data()` | Same as access; portable JSON format |
| **Right to rectification** | Art. 16 | Standard CRUD update endpoints | User profile / record update APIs | Validated at domain layer |

---

## 5. Data Classification Framework

The platform implements a four-tier data classification system declared at the model layer:

```python
class DataClassification:
    C1_PUBLIC     = "C1_PUBLIC"       # No special handling required
    C2_INTERNAL   = "C2_INTERNAL"     # Internal use only
    C3_CONFIDENTIAL = "C3_CONFIDENTIAL"  # Authorised users; encrypted at rest
    C4_RESTRICTED = "C4_RESTRICTED"   # PII/special-category; encrypted, pseudonymised, audit-logged
```

**Source:** `src/domain/models/base.py` — `DataClassification` class and `get_model_classification()` helper.

### Classification by Model

| Classification | Models | Handling |
|---------------|--------|----------|
| **C4 Restricted** | `Incident`, `RTA` | Health/injury data; field-level Fernet encryption, audit-logged access, pseudonymised on erasure |
| **C3 Confidential** | `User`, `Complaint`, `NearMiss`, `IncidentAction`, `Tenant`, `InformationAsset` | PII; encrypted at rest, role-based access, PII-filtered logging |
| **C2 Internal** | `Risk`, `AuditRun`, `AuditFinding`, `AuditTemplate`, `Policy`, `Document`, `Notification`, `WorkflowTemplate`, `EmissionSource` | Internal business data; standard access controls |
| **C1 Public** | `Standard` | ISO clause reference data; no special handling |

Full classification matrix with handling requirements: [`data-classification.md`](data-classification.md)

---

## 6. Retention & Erasure

### Retention Schedule (Summary)

| Entity | Retention | Legal Basis |
|--------|-----------|-------------|
| Incidents | 7 years | Legitimate interest (safety); legal/liability preservation |
| Audit log entries | 7 years (2555 days) | Legal obligation / legitimate interest |
| RTAs | 6 years | Road traffic / insurance / regulatory |
| Complaints | 3 years | Contract / consumer obligations |
| Employee accounts | Life of employment + statutory window | Contract / legal obligation |
| Tokens / sessions | Hours–days | Security |

### Automated Enforcement

- `AuditLogEntry.retention_days` field (default 2555) enables per-entry and per-tenant policy overrides
- Celery-based retention purge job executes scheduled deletion
- GDPR erasure via `PseudonymizationService` for right-to-be-forgotten requests

Full policy: [`data-retention-policy.md`](data-retention-policy.md)

---

## 7. DPIA Register

| Ref | Scope | Date | Status | Next Review |
|-----|-------|------|--------|-------------|
| DPIA-001 | Incident Reporting, Complaint Management, Near Miss, RTA | 2026-03-07 | Complete | 2026-09-07 |

DPIAs are required before any new processing of C4 (restricted) data. The DPIA template is at [`dpia-template.md`](dpia-template.md).

Full DPIA for incident/complaint modules: [`dpia-incidents.md`](dpia-incidents.md)

---

## 8. Privacy Controls Matrix

| Control | Implementation | Automated | Evidence |
|---------|---------------|-----------|----------|
| Data classification | `DataClassification` enum on every model | Yes (CI validation planned Q2 2026) | `src/domain/models/base.py` |
| Encryption at rest | Azure managed + Fernet field-level for C4 | Yes | Infrastructure config |
| Encryption in transit | TLS 1.2+ enforced | Yes | Azure App Service config |
| Access control | JWT + role-based; named-individual access for C4 | Yes | Auth middleware |
| Tenant isolation | `tenant_id` filter on all queries | Yes | Base query classes |
| PII-filtered logging | Structured logger strips C3/C4 fields | Yes | Logger configuration |
| Audit trail | Immutable hash-chain `AuditLogEntry` | Yes | `src/domain/models/audit_log.py` |
| Pseudonymization | SHA-256 HMAC with secret pepper | Yes | `src/domain/services/pseudonymization_service.py` |
| Data export (SAR) | `GDPRService.export_user_data()` | Yes | `src/domain/services/gdpr_service.py` |
| Erasure | `GDPRService.request_erasure()` | Yes | `src/domain/services/gdpr_service.py` |
| Processing restriction | `GDPRService.restrict_processing()` | Yes | `src/domain/services/gdpr_service.py` |
| Retention enforcement | Celery purge job + `retention_days` | Yes | `src/infrastructure/tasks/celery_app.py` |
| DPIA | Documented assessment before C4 processing | Manual | `docs/privacy/dpia-incidents.md` |
| Breach notification | Incident response runbook | Manual | `docs/runbooks/incident-response.md` |

---

## 9. Related Documents

| Document | Path |
|----------|------|
| Data Classification Policy | [`docs/privacy/data-classification.md`](data-classification.md) |
| Data Retention Policy | [`docs/privacy/data-retention-policy.md`](data-retention-policy.md) |
| DPIA — Incidents & Complaints | [`docs/privacy/dpia-incidents.md`](dpia-incidents.md) |
| DPIA Template | [`docs/privacy/dpia-template.md`](dpia-template.md) |
| GDPR Service | [`src/domain/services/gdpr_service.py`](../../src/domain/services/gdpr_service.py) |
| Pseudonymization Service | [`src/domain/services/pseudonymization_service.py`](../../src/domain/services/pseudonymization_service.py) |
| DataClassification Enum | [`src/domain/models/base.py`](../../src/domain/models/base.py) |
| Incident Response Runbook | [`docs/runbooks/incident-response.md`](../runbooks/incident-response.md) |
