# GDPR Compliance Documentation (D07)

**Owner**: Platform Engineering / Data Protection
**Last Updated**: 2026-04-03
**Review Cycle**: Annually and on material changes

---

## 1. Data Processing Inventory

| Data Category | Examples | Lawful Basis | Retention | Storage |
|---------------|----------|-------------|-----------|---------|
| User accounts | Email, name, role | Legitimate interest (platform access) | Account lifetime + 90 days | PostgreSQL |
| Incident reports | Description, location, severity | Legal obligation (H&S reporting) | 7 years | PostgreSQL |
| Audit findings | Finding text, evidence references | Legitimate interest (quality governance) | 7 years | PostgreSQL |
| CAPA actions | Action description, assignee | Legitimate interest (corrective action tracking) | 7 years | PostgreSQL |
| Risk register | Risk description, scores | Legitimate interest (enterprise risk management) | 7 years | PostgreSQL |
| Complaints | Complainant details, narrative | Legal obligation (regulatory compliance) | 7 years | PostgreSQL |
| Evidence assets | PDF documents, images | Legitimate interest (audit evidence) | Per retention policy | Azure Blob Storage |
| Authentication logs | Login times, IP addresses | Legitimate interest (security monitoring) | 90 days | Structured logs |
| Request logs | API paths, tenant_id, user_id | Legitimate interest (operational monitoring) | 90 days | Azure Log Analytics |

---

## 2. Data Subject Rights

| Right | Implementation | Status |
|-------|---------------|--------|
| Right of access (Art. 15) | User profile page shows personal data; admin export available | Implemented |
| Right to rectification (Art. 16) | Profile editing; admin can update user records | Implemented |
| Right to erasure (Art. 17) | Soft-delete of user account; anonymization of linked records | Partial — hard delete not yet automated |
| Right to restriction (Art. 18) | Account deactivation prevents login and data processing | Implemented |
| Right to portability (Art. 20) | JSON export of user-owned data via API | Planned |
| Right to object (Art. 21) | Contact platform admin to object to processing | Manual process |

---

## 3. Data Protection Impact Assessment (DPIA) Summary

| Factor | Assessment |
|--------|------------|
| **Nature of processing** | Multi-tenant SaaS platform processing workplace safety, quality, and compliance data |
| **Scope** | Organizational users (employees) within tenant organizations |
| **Context** | Professional/employment context; no special category data unless disclosed in free-text fields |
| **Purpose** | Quality governance, incident management, audit tracking, regulatory compliance |
| **Risk to individuals** | Low-Medium — primarily professional data; free-text fields could contain sensitive details |
| **Mitigations** | Role-based access, tenant isolation, encryption at rest and in transit, audit logging, retention limits |

### DPIA Conclusion

The processing is necessary for legitimate business purposes. Risks are mitigated through technical and organizational measures. No high residual risk requiring supervisory authority consultation.

---

## 4. Technical Measures

| Measure | Implementation | Evidence |
|---------|---------------|----------|
| Encryption at rest | Azure-managed encryption for PostgreSQL and Blob Storage | Azure platform default |
| Encryption in transit | TLS 1.2+ enforced on all endpoints | `staticwebapp.config.json`, App Service HTTPS enforcement |
| Access control | JWT-based authentication, role-based authorization | `src/api/middleware/auth.py` |
| Tenant isolation | Row-level `tenant_id` filtering on all queries | `src/api/dependencies.py` |
| Audit logging | Structured request logs with user_id and tenant_id | `src/infrastructure/middleware/request_logger.py` |
| Password security | bcrypt hashing with salt | `src/infrastructure/auth/` |
| Secret management | Azure Key Vault for production secrets | `scripts/infra/` |

---

## 5. Data Retention Schedule

| Data Type | Active Retention | Archive | Deletion |
|-----------|-----------------|---------|----------|
| User accounts | Account lifetime | 90 days post-deactivation | Anonymized |
| Incident records | 7 years from creation | N/A | Soft-deleted |
| Audit records | 7 years from audit date | N/A | Soft-deleted |
| Evidence assets | Per audit record retention | Move to Cool tier after 90 days | Delete with parent record |
| Authentication logs | 90 days | N/A | Auto-purged |
| Request logs | 90 days | N/A | Auto-purged by Azure Log Analytics |

See also: [`docs/evidence/retention-automation-evidence.md`](../evidence/retention-automation-evidence.md)

---

## 6. Breach Notification Process

| Step | Timeframe | Action |
|------|-----------|--------|
| 1. Detection | Immediate | Security incident logged; on-call notified |
| 2. Assessment | Within 4 hours | Determine if personal data affected; assess severity |
| 3. Containment | Within 8 hours | Isolate affected systems; preserve forensic evidence |
| 4. ICO notification | Within 72 hours | Notify Information Commissioner's Office if threshold met |
| 5. Data subject notification | Without undue delay | Notify affected individuals if high risk to rights/freedoms |
| 6. Post-incident review | Within 14 days | Root cause analysis; preventive measures documented |

---

## 7. International Transfers

The platform is hosted entirely within Azure UK South region. No personal data is transferred outside the UK/EEA. If future requirements necessitate international transfers, appropriate safeguards (Standard Contractual Clauses or adequacy decisions) will be implemented before any transfer occurs.

---

## Related Documents

- [`docs/evidence/retention-automation-evidence.md`](../evidence/retention-automation-evidence.md) — retention policy evidence
- [`docs/security/security-baseline.md`](../security/security-baseline.md) — security controls
- [`docs/adr/ADR-0009-csrf-not-required.md`](../adr/ADR-0009-csrf-not-required.md) — CSRF decision
