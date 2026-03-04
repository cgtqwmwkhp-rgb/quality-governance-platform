# Compliance Matrix

This document maps the Quality Governance Platform's features and controls to compliance requirements across ISO 9001, ISO 45001, ISO 14001, and GDPR.

---

## ISO 9001:2015 — Quality Management Systems

| Clause | Requirement | Platform Feature |
|--------|-------------|------------------|
| **4.1** | Understanding the organization and its context | Standards Library; Risk Register for context analysis; IMS Dashboard for organizational overview |
| **6.1** | Actions to address risks and opportunities | Risk Register; Risk scoring; KRI (Key Risk Indicators); Risk trend analytics |
| **7.1.6** | Organizational knowledge | Policy & Document Library; Document control; Controlled documents and SOPs |
| **8.2.1** | Customer communication | Complaints module; Email ingestion; Complaint handling workflow |
| **9.2** | Internal audit | Audit & Inspection module; Audit templates; Audit execution; Audit findings tracking |
| **10.2** | Nonconformity and corrective action | Incident Reporting; Investigation Service; Corrective action workflows; Action tracking |

---

## ISO 45001:2018 — Occupational Health & Safety Management

| Clause | Requirement | Platform Feature |
|--------|-------------|------------------|
| **6.1.2** | Hazard identification and risk assessment | Risk Register; Incident Reporting; Near Miss module; Risk scoring and assessment |
| **8.1** | Operational planning and control | Incident workflows; RTA (Road Traffic Accident) management; Action assignment and escalation |
| **8.2** | Emergency preparedness and response | Incident capture; Workflow engine for escalation; Notification system |
| **9.2** | Internal audit | Audit & Inspection; Auditor competence; Audit templates and execution |
| **10.2** | Incident, nonconformity and corrective action | Incident Reporting; Investigation Service; RCA tools; Corrective action tracking |
| **7.2** | Competence | Auditor Competence Service; Certification tracking; Training records; CPD hours |

---

## ISO 14001:2015 — Environmental Management Systems

| Clause | Requirement | Platform Feature |
|--------|-------------|------------------|
| **4.1** | Context of the organisation | Standards Library; Risk Register; PlanetMark/UVDB integration for environmental aspects |
| **6.1** | Actions to address risks and opportunities | Risk Register; Environmental risk assessment; KRI dashboard |
| **7.2** | Competence | Auditor Competence Service; Training and certification management |
| **8.1** | Operational planning and control | Document control; Policy library; Workflow engine for process control |
| **9.1** | Monitoring, measurement and evaluation | Analytics; Executive dashboard; KRI calculations; Compliance automation |
| **10.2** | Nonconformity and corrective action | Incident Reporting; Complaints; Investigation Service; Corrective action workflows |

---

## GDPR — General Data Protection Regulation

| Article | Requirement | Platform Feature |
|---------|-------------|------------------|
| **Art. 5** | Principles (lawfulness, purpose limitation, minimisation, accuracy, storage limitation, integrity) | Retention policies (`retention_config.py`); Pseudonymization service; Audit log integrity (hash chain) |
| **Art. 15** | Right of access | GDPR Service `export_user_data`; Data export endpoint; User data portability |
| **Art. 17** | Right to erasure | GDPR Service `request_erasure`; Data erasure endpoint; Pseudonymization on erasure |
| **Art. 20** | Data portability | GDPR export; JSON export of user data; Audit log export for compliance reporting |
| **Art. 25** | Data protection by design and default | Pseudonymization; Retention policies; RBAC; Security headers; Rate limiting |
| **Art. 32** | Security of processing | Azure AD authentication; Security scan pipeline (Bandit, Semgrep, Trivy); Audit trail; Encryption at rest |

---

## Summary

| Standard | Mappings | Key Platform Capabilities |
|----------|----------|---------------------------|
| ISO 9001 | 6 | Standards Library, Risk Register, Complaints, Audits, Incidents, Document control |
| ISO 45001 | 6 | Incidents, Near Miss, RTA, Risk Register, Auditor competence, Investigations |
| ISO 14001 | 6 | Risk Register, PlanetMark, Document control, Analytics, Incidents, Complaints |
| GDPR | 6 | GDPR Service, Retention policies, Pseudonymization, Audit log, Security pipeline |

---

*Last updated: March 2025*
