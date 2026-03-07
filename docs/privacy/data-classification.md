# Data Classification Policy

> Quality Governance Platform — Version 1.0
>
> Effective: 2026-03-07 | Review: 2026-09-07

## 1. Classification Levels

| Level | Label | Description | Examples |
|-------|-------|-------------|----------|
| **C4** | **Restricted** | Highly sensitive data whose disclosure would cause severe harm. Requires encryption at rest and in transit, strict access control, and audit logging. | Health/injury data, RIDDOR reports, passwords, encryption keys, API secrets |
| **C3** | **Confidential** | Business-sensitive data with legal or contractual protection requirements. | Employee PII (names, emails, phones), complainant details, investigation findings, audit scores |
| **C2** | **Internal** | Data intended for internal use. Low risk if disclosed but not for public consumption. | Risk scores, workflow configurations, audit templates, form definitions, tenant settings |
| **C1** | **Public** | Data safe for public access. No special handling required. | ISO clause reference numbers, published policies (if flagged public), API schema, health check status |

---

## 2. Handling Requirements

| Control | C1 Public | C2 Internal | C3 Confidential | C4 Restricted |
|---------|-----------|-------------|------------------|---------------|
| **Encryption at rest** | Optional | Platform default (Azure) | Required (Azure + Fernet) | Required (field-level Fernet) |
| **Encryption in transit** | HTTPS | HTTPS | HTTPS + TLS 1.2+ | HTTPS + TLS 1.2+ |
| **Authentication** | None | JWT required | JWT + role check | JWT + role check + audit log |
| **Tenant isolation** | N/A | tenant_id filter | tenant_id filter | tenant_id filter + row-level check |
| **Logging** | Standard | Standard | PII-filtered structured logs | PII-filtered + access audit trail |
| **Backup** | Standard | Standard | Encrypted backup | Encrypted backup + verified restore |
| **Retention** | Indefinite | Per data type | Per DPIA | Per legal requirement (min 3yr for RIDDOR) |
| **Deletion** | Immediate | Soft delete | Soft delete + 30-day archive | Legal hold check → approved hard delete |
| **Sharing** | Unrestricted | Authenticated users | Need-to-know (role-based) | Named individuals only |

---

## 3. Model-Level Classification

### 3.1 Backend Models

| Model | Module | Classification | Justification |
|-------|--------|---------------|---------------|
| `User` | `src/domain/models/user.py` | **C3** | Contains email, name, hashed password |
| `Incident` | `src/domain/models/incident.py` | **C4** | Contains health/injury data, witness names |
| `IncidentAction` | `src/domain/models/incident.py` | **C3** | Linked to identified individuals |
| `Complaint` | `src/domain/models/complaint.py` | **C3** | Contains complainant PII |
| `RTA` | `src/domain/models/rta.py` | **C4** | Contains vehicle/driver details, injury data |
| `NearMiss` | `src/domain/models/near_miss.py` | **C3** | Contains reporter identity |
| `Risk` | `src/domain/models/risk.py` | **C2** | Business data, no PII |
| `AuditRun` | `src/domain/models/audit.py` | **C2** | Assessment data, no PII (assessor linked by FK) |
| `AuditFinding` | `src/domain/models/audit.py` | **C2** | Finding descriptions, no direct PII |
| `AuditTemplate` | `src/domain/models/audit.py` | **C2** | Template definitions |
| `Policy` | `src/domain/models/policy.py` | **C2** | Document metadata |
| `Document` | `src/domain/models/document.py` | **C2** | Document metadata (content in blob storage) |
| `Standard` | `src/domain/models/standard.py` | **C1** | ISO clause reference data |
| `Notification` | `src/domain/models/notification.py` | **C2** | Notification metadata |
| `WorkflowTemplate` | `src/domain/models/workflow.py` | **C2** | Workflow definitions |
| `Tenant` | `src/domain/models/tenant.py` | **C3** | Organisation details, billing |
| `InformationAsset` | `src/domain/models/iso27001.py` | **C3** | Asset inventory with risk ratings |
| `EmissionSource` | `src/domain/models/planet_mark.py` | **C2** | Environmental data |

### 3.2 External Storage

| Store | Classification | Controls |
|-------|---------------|----------|
| PostgreSQL | **C4** (contains restricted data) | Azure managed encryption, network isolation, backup encryption |
| Azure Blob Storage | **C3** (attachments may contain PII) | Azure Storage Service Encryption, SAS token access, container-level ACL |
| Redis | **C2** (cache, no PII persisted) | In-memory only, TTL expiry, network isolation |
| Application logs | **C2** (PII filtered) | PII filter in structured logger, 90-day retention |
| Audit trail | **C3** (contains user IDs + actions) | Immutable hash-chain, encrypted backup |

---

## 4. Classification Tagging (Implementation)

All SQLAlchemy models should declare their classification using the `__data_classification__` class attribute:

```python
class Incident(Base, TimestampMixin, AuditTrailMixin):
    __tablename__ = "incidents"
    __data_classification__ = "C4"  # Restricted — contains health data
```

A CI validation script (`scripts/validate_data_classification.py`) should verify:
1. Every model in `src/domain/models/` declares `__data_classification__`
2. No C4 model is logged without PII filtering
3. No C4 field is returned in list endpoints without explicit opt-in

**Status**: Classification attribute not yet implemented in code. Target: Q2 2026.

---

## 5. Responsibilities

| Role | Responsibility |
|------|---------------|
| **Data Owner** (module lead) | Assign classification to new models; review annually |
| **Developer** | Apply handling controls per classification level; never log C3/C4 data |
| **DPO** | Review classifications; approve C4 processing; conduct DPIAs |
| **Security Lead** | Verify encryption and access controls match classification |
| **DevOps** | Ensure infrastructure controls match classification requirements |

---

## 6. Review Schedule

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Full classification review | Every 6 months | Data Owner + DPO |
| New model classification | At PR review | Developer + Reviewer |
| DPIA trigger assessment | When adding C4 data | DPO |
| Control verification | Quarterly | Security Lead |
