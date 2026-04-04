# Data Protection Impact Assessment (DPIA) — Template

**Platform:** Quality Governance Platform (QGP)  
**Document type:** DPIA template (UK GDPR / EU GDPR accountability)  
**Version:** 1.0  
**Review:** Annual (see Review Schedule)

---

## 1. Summary

This DPIA assesses personal data processing within QGP for **incident management, immutable audit trail, vehicle checks, driver profiles, and road traffic incidents (RTAs)**. It documents data categories, legal bases, retention, technical and organisational measures, data subject rights, residual risks, and review cadence.

---

## 2. Processing activity

| Field | Description |
| --- | --- |
| **Name of processing** | QGP operational safety, compliance, and governance processing |
| **Purposes** | Workplace safety; regulatory and contractual compliance; fleet and driver assurance; investigation and learning from incidents; auditability |
| **Scope** | Incident management; audit trail; vehicle checks; driver profiles; RTAs; related workflows (e.g. complaints, near misses where configured) |
| **Data subjects** | Employees, contractors, drivers, witnesses, and other individuals described in incident and vehicle records |
| **Controllers / processors** | As defined in the organisation’s ROPA and DPA schedule (QGP may be operated as controller or processor depending on deployment) |

---

## 3. Data categories

| Category | Examples processed in QGP |
| --- | --- |
| **Employee PII** | Name, work email |
| **Driver details** | Identity and role-related attributes linked to driver profiles |
| **Vehicle registrations** | Registration identifiers and checklist / inspection data |
| **Incident descriptions** | Free text and structured incident metadata |
| **Witness statements** | Narrative statements and linked metadata |
| **Photos** | Images attached to incidents, checks, or investigations |

Special category data may appear in free text or images. Where that occurs, processing must be justified under Article 9 GDPR (e.g. occupational health, legal claims, or explicit consent) and recorded in the ROPA.

---

## 4. Legal basis

| Basis | Application (examples) |
| --- | --- |
| **Legitimate interests (Art. 6(1)(f))** | Workplace safety, prevention of harm, fleet risk management, security of the service — balanced against data subject rights |
| **Legal obligation (Art. 6(1)(c))** | Health & safety reporting, statutory retention, and similar mandatory duties (as applicable to the controller) |
| **Consent (Art. 6(1)(a))** | Where used for optional processing (e.g. certain notifications or non-essential analytics); must be withdrawable |

Document the specific basis per tenant workflow in the Record of Processing Activities (ROPA).

---

## 5. Data retention

| Record class | Retention period | Notes |
| --- | --- | --- |
| **Incidents** | **7 years** | Aligns with common limitation periods for workplace / liability records (confirm against jurisdictional advice) |
| **Audit logs** | **7 years** | Model default `AuditLogEntry.retention_days = 2555` (~7 years); subject to automated retention job evolution |
| **RTAs** | **6 years** | Motor / RTA-related records (confirm against motor insurance and local rules) |
| **Complaints** | **3 years** | Customer / employee complaint records unless a longer period is mandated |

Retention is enforced through policy, configuration, and scheduled retention tasks. See `docs/privacy/data-retention-policy.md`.

---

## 6. Technical and organisational safeguards

| Measure | Description |
| --- | --- |
| **Encryption at rest** | **Fernet** (symmetric) for designated application-layer payloads and secrets where enabled; **Azure** platform encryption for database and blob storage (deployment-dependent) |
| **Encryption in transit** | **TLS** for client/API traffic; HTTPS termination at the edge |
| **Pseudonymisation on erasure** | GDPR erasure flow pseudonymises PII (peppered hashing and redaction patterns) while preserving integrity where legally required |
| **Access control** | **RBAC** with role hierarchy and **ABAC** policy evaluation for fine-grained permissions |
| **Audit logging** | Immutable-style **audit log entries** with hash chain and export records for compliance evidence |

---

## 7. Data subject rights

| Right | QGP mechanism |
| --- | --- |
| **Access** | `GET /api/v1/gdpr/data-export` — JSON export of personal data for the authenticated subject (supports `dry_run`) |
| **Erasure** | `POST /api/v1/gdpr/erasure-request` — pseudonymisation / erasure workflow (`dry_run`, `confirm` flags as implemented) |
| **Portability** | **JSON export** from the access export (Art. 20 — further formats by agreement) |
| **Status** | `GET /api/v1/gdpr/me/data-erasure/status` — erasure / pseudonymisation status |

> **Implementation note:** The FastAPI router in `src/api/routes/gdpr.py` currently exposes **`/api/v1/gdpr/me/data-export`** and **`/api/v1/gdpr/me/data-erasure`** (plus `…/me/data-erasure/status`). Align public DPIA wording with either stable aliases at the gateway or add route aliases so the catalogue paths above match production URLs exactly.

---

## 8. Risk assessment matrix

| # | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| 1 | **Unauthorised access** to incident or driver data via compromised credentials | Medium | High | Azure AD / JWT auth, RBAC+ABAC, rate limiting, session controls, security headers, monitoring |
| 2 | **Excessive collection** or retention of personal data beyond purpose | Medium | Medium | Retention schedule, `retention_days` on audit entries, periodic ROPA/DPIA review, data minimisation in forms |
| 3 | **Integrity / repudiation** — tampering with audit or incident history | Low | High | Hash-chained audit log, verification records, restricted admin roles, export file hashes |
| 4 | **Disclosure in transit** (eavesdropping, MITM) | Low | High | TLS, HSTS, strict transport configuration at reverse proxy |
| 5 | **Erasure / portability errors** (wrong subject, partial export) | Low | Medium | Authenticated “me” endpoints, dry-run modes, confirmation flags, structured export tests |

*Likelihood and impact are qualitative (Low / Medium / High) and should be rescored after incidents or architecture changes.*

---

## 9. Review schedule

- **Annual DPIA review** (minimum), or sooner if:
  - New high-risk processing is introduced
  - A data breach or near-miss affects this processing
  - Material change to vendors, hosting region, or AI/automation touching personal data

**Next review date:** 2026-10-03  
**Owner:** _[Name / role]_  
**Approver:** _[DPO / privacy lead]_

---

## 10. Sign-off

| Role | Name | Signature / date |
| --- | --- | --- |
| Process owner | | |
| Security | | |
| DPO / Privacy | | |
