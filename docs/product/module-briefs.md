# Product Module Briefs

**Last Updated**: 2026-04-04
**Review Cycle**: Quarterly
**Owner**: Product

---

## Purpose

This document captures per-module product definitions for every major capability in the Quality Governance Platform (QGP). Each brief anchors a module to the business problem it solves, the personas it serves, the API surface it exposes, and the domain entities it owns. It is the single source of truth for product scope, module boundaries, and cross-module dependencies, and should be referenced during sprint planning, architecture reviews, and stakeholder conversations.

---

## Persona Quick Reference

| ID | Persona | Role Archetype |
|----|---------|---------------|
| P1 | Field Reporter | Field worker, site supervisor, driver, operative |
| P2 | Quality Auditor | Internal auditor, quality manager, compliance officer |
| P3 | Risk Manager | Enterprise risk manager, HSEQ director, operations manager |
| P4 | System Administrator | IT admin, platform administrator, HSEQ system owner |
| P5 | Executive / Board Member | CEO, COO, board member, HSEQ director |

Full persona definitions: [`docs/user-journeys/personas-and-journeys.md`](../user-journeys/personas-and-journeys.md)

---

## Module Inventory

### 1. Incident Management

- **Domain**: Health, Safety & Environment (HSE)
- **Problem**: Field workers need a fast, reliable way to report workplace incidents; managers need to triage, investigate, and close them with full traceability.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As a field reporter, I can submit an incident with severity, location, and evidence photos so the event is captured before details are forgotten.
  - As a quality manager, I can triage incoming incidents, assign severity, and escalate RIDDOR-reportable events.
  - As a manager, I can track an incident through its lifecycle (Open → Under Investigation → Closed) and attach running-sheet entries.
  - As an auditor, I can generate CAPA directly from an incident finding.
  - As an executive, I can view incident trends and severity distributions on the dashboard.
- **Success Metrics**: Mean time from occurrence to report; form abandonment rate; RIDDOR reporting compliance rate; incident closure cycle time.
- **Journey Reference**: Journey 1 — Incident Reporting (P1)
- **API Surface**: `src/api/routes/incidents.py` — CRUD endpoints (`POST /`, `GET /`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`), running sheet (`POST /{id}/running-sheet`, `DELETE /{id}/running-sheet/{entry_id}`), actions and status transitions.
- **Data Entities**: `Incident`, `IncidentAction`, `IncidentRunningSheetEntry` (`src/domain/models/incident.py`); enums `IncidentSeverity`, `IncidentStatus`, `IncidentType`, `ActionStatus`.
- **Dependencies**: Evidence Assets, Actions, CAPA, Notifications, Audit Trail, Employee Portal, Reference Numbers.
- **Status**: Active

---

### 2. Near-Miss Reporting

- **Domain**: Health, Safety & Environment (HSE)
- **Problem**: Near-miss events are precursors to serious incidents but go unreported because capture is too cumbersome; the platform must lower the friction of reporting to build a proactive safety culture.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor)
- **Key User Stories**:
  - As a field worker, I can report a near-miss from my phone in under two minutes.
  - As a safety manager, I can review near-miss reports, identify patterns, and link them to risk register entries.
  - As a manager, I can add running-sheet entries to track follow-up on a near-miss.
  - As an analyst, I can see near-miss trends alongside incident data to identify emerging hazards.
- **Success Metrics**: Near-miss to incident reporting ratio (target ≥ 10:1); time to submit; reporting volume trend.
- **Journey Reference**: Journey 1 — Incident Reporting (P1), step 2 variant
- **API Surface**: `src/api/routes/near_miss.py` — CRUD endpoints, running sheet management, status transitions.
- **Data Entities**: `NearMiss`, `NearMissRunningSheetEntry` (`src/domain/models/near_miss.py`).
- **Dependencies**: Evidence Assets, Employee Portal, Notifications, Audit Trail, Reference Numbers.
- **Status**: Active

---

### 3. Road Traffic Collisions (RTAs)

- **Domain**: Fleet Safety & Compliance
- **Problem**: Transport operators must capture, investigate, and report road traffic collisions with regulatory accuracy; manual paper-based processes cause delays and data loss.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As a driver, I can report an RTA from the portal with vehicle details, location, and third-party information.
  - As a fleet manager, I can triage RTAs, assign investigators, and track actions to closure.
  - As an analyst, I can run AI-powered RTA analysis to identify contributing factors.
  - As a compliance officer, I can generate regulatory reports from RTA data.
  - As a manager, I can attach running-sheet entries and evidence to an RTA record.
- **Success Metrics**: RTA reporting latency; action closure rate; repeat collision rate per vehicle/driver.
- **Journey Reference**: Journey 1 — Incident Reporting (P1), RTA variant
- **API Surface**: `src/api/routes/rtas.py` — CRUD endpoints, actions (`POST /{id}/actions`), running sheet, status transitions.
- **Data Entities**: `RoadTrafficCollision`, `RTAAction` (`src/domain/models/rta.py`); `RTAAnalysis` (`src/domain/models/rta_analysis.py`).
- **Dependencies**: Evidence Assets, Employee Portal, Driver Profiles, Vehicle Registry, Notifications, Audit Trail.
- **Status**: Active

---

### 4. Complaints Management

- **Domain**: Customer Quality & Service
- **Problem**: Customer and stakeholder complaints must be captured, triaged, investigated, and resolved within SLA; siloed tracking in spreadsheets causes missed deadlines and lost context.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor)
- **Key User Stories**:
  - As a customer-facing employee, I can log a complaint with category, priority, and complainant details.
  - As a complaint handler, I can triage, assign, and track a complaint through resolution.
  - As a quality manager, I can generate CAPA from complaint trends.
  - As a manager, I can view running-sheet updates and maintain an evidence-backed audit trail.
  - As an executive, I can see complaint volumes, response SLA compliance, and trend data.
- **Success Metrics**: SLA adherence (%); complaint resolution cycle time; repeat complaint rate; customer satisfaction score.
- **Journey Reference**: Journey 1 — Incident Reporting (P1), complaint variant
- **API Surface**: `src/api/routes/complaints.py` — CRUD endpoints, running sheet, status transitions, actions.
- **Data Entities**: `Complaint`, `ComplaintAction`, `ComplaintRunningSheetEntry` (`src/domain/models/complaint.py`); enums `ComplaintPriority`, `ComplaintStatus`, `ComplaintType`.
- **Dependencies**: Evidence Assets, CAPA, Employee Portal, Notifications, Audit Trail.
- **Status**: Active

---

### 5. CAPA (Corrective & Preventive Actions)

- **Domain**: Quality Management
- **Problem**: Non-conformances identified during audits, incidents, or complaints require structured corrective and preventive actions with tracked ownership, deadlines, and effectiveness verification; without a system, CAPAs slip and root causes recur.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As an auditor, I can raise a CAPA directly from an audit finding with pre-populated context.
  - As a quality manager, I can assign CAPA owners, set due dates, and define verification criteria.
  - As a CAPA owner, I can update progress, attach evidence, and submit for verification.
  - As a manager, I can view CAPA statistics (open, overdue, closed) and filter by source, type, or priority.
  - As an analyst, I can track CAPA effectiveness over time to ensure root causes are eliminated.
- **Success Metrics**: CAPA closure rate; mean time to closure; overdue CAPA count; effectiveness review completion rate.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), steps 6–8
- **API Surface**: `src/api/routes/capa.py` — CRUD (`POST /`, `GET /`, `GET /{id}`, `PATCH /{id}`), stats endpoint, filtered listing by source/type/status/priority. Permission-gated via `require_permission`.
- **Data Entities**: `CAPAAction` (`src/domain/models/capa.py`); enums `CAPAPriority`, `CAPASource`, `CAPAStatus`, `CAPAType`.
- **Dependencies**: Audits, Incidents, Complaints, Investigations, Actions, Notifications, Audit Trail.
- **Status**: Active

---

### 6. Audits & Inspections

- **Domain**: Quality Governance & Compliance
- **Problem**: Planning, executing, and reporting on audits involves templates, on-site data capture, scoring, findings, and CAPA generation — a multi-step process that breaks down when done on paper or disconnected spreadsheets.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As an auditor, I can select a template, configure an audit run, and execute it section-by-section with question-level responses.
  - As an on-site auditor, I can execute audits on mobile/tablet with offline capability.
  - As a quality manager, I can record findings (non-conformances, observations, good practices) with severity classification.
  - As a manager, I can view auto-calculated audit scores and generate PDF/HTML audit reports.
  - As an admin, I can create and version audit templates with sections, questions, and scoring criteria.
- **Success Metrics**: Audit completion time; finding-to-CAPA conversion rate; audit programme coverage; template reuse rate.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2)
- **API Surface**: `src/api/routes/audits.py` — Audit runs CRUD, sections, questions, responses, findings; `src/api/routes/audit_templates.py` — Template CRUD, versioning, archiving; scoring and statistics endpoints.
- **Data Entities**: `AuditRun`, `AuditTemplate`, `AuditSection`, `AuditQuestion`, `AuditResponse`, `AuditFinding` (`src/domain/models/audit.py`, `src/domain/models/audit_template.py`).
- **Dependencies**: CAPA, Evidence Assets, Standards Library, Compliance Evidence, Digital Signatures, Audit Trail, Notifications.
- **Status**: Active

---

### 7. Investigations

- **Domain**: Root Cause Analysis & Quality
- **Problem**: Complex incidents, complaints, and audit findings require structured multi-step investigations with evidence gathering, timeline reconstruction, root cause analysis, and customer pack generation; ad-hoc investigation processes produce inconsistent quality.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As an investigator, I can create an investigation from any source record (incident, complaint, RTA, audit finding).
  - As a lead investigator, I can build an investigation timeline, attach evidence, and add comments.
  - As a quality manager, I can use RCA tools (5-Whys, Fishbone) to identify root causes.
  - As a manager, I can generate customer packs and closure validation reports.
  - As an analyst, I can filter investigations by status, source type, and assigned investigator.
- **Success Metrics**: Investigation cycle time; root cause identification rate; customer pack generation time; closure validation pass rate.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), investigation branch
- **API Surface**: `src/api/routes/investigations.py` — CRUD, timeline, comments, evidence, customer packs, closure validation, source record linking; `src/api/routes/investigation_templates.py` — Investigation template management; `src/api/routes/rca_tools.py` — Root cause analysis tool endpoints.
- **Data Entities**: `InvestigationRun`, `InvestigationAction`, `InvestigationComment`, `InvestigationTimeline` (`src/domain/models/investigation.py`); `RCATools` (`src/domain/models/rca_tools.py`).
- **Dependencies**: Incidents, Complaints, RTAs, Audits, Evidence Assets, Actions, CAPA, Notifications.
- **Status**: Active

---

### 8. Risk Management (Operational)

- **Domain**: Operational Risk
- **Problem**: Operational risks tracked in isolated spreadsheets lack version history, scoring consistency, and real-time visibility; managers cannot see the risk posture across the organisation.
- **Primary Persona(s)**: P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a risk manager, I can create, score (likelihood × impact), and categorise risks with a 5×5 matrix.
  - As a risk owner, I can define controls, assess residual risk, and track risk status transitions (Open → Mitigating → Accepted → Closed).
  - As a manager, I can view the risk matrix heatmap to understand risk distribution.
  - As an analyst, I can view risk statistics and trend data.
  - As an executive, I can see top risks and their treatment status at a glance.
- **Success Metrics**: Risk register completeness; control effectiveness score; risk review cadence adherence.
- **Journey Reference**: Journey 3 — Risk Assessment (P3), steps 1–5
- **API Surface**: `src/api/routes/risks.py` — CRUD, assessments, controls, risk matrix, statistics, status transitions with defined state machine (`RISK_TRANSITIONS`).
- **Data Entities**: `Risk`, `RiskAssessment`, `OperationalRiskControl` (`src/domain/models/risk.py`); enum `RiskStatus`.
- **Dependencies**: KRI, Actions, Audit Trail, Notifications.
- **Status**: Active

---

### 9. Enterprise Risk Register

- **Domain**: Enterprise Risk & Governance
- **Problem**: Board-level risk oversight requires an enterprise-wide register with bow-tie analysis, heat maps, KRI linkage, and trend reporting — capabilities beyond operational risk tracking.
- **Primary Persona(s)**: P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a risk manager, I can create enterprise-level risks with inherent and residual scoring, control mapping, and KRI linkage.
  - As a risk analyst, I can build bow-tie diagrams linking threats, controls, and consequences.
  - As an executive, I can view the enterprise risk heat map with risk appetite overlays.
  - As a board member, I can review top-10 risk reports with trend arrows and treatment effectiveness.
  - As a risk manager, I can link enterprise KRIs to risks for automated threshold monitoring.
- **Success Metrics**: Enterprise risk coverage; bow-tie analysis completion rate; board report generation frequency.
- **Journey Reference**: Journey 3 — Risk Assessment (P3), steps 5–8
- **API Surface**: `src/api/routes/risk_register.py` — Enterprise risk CRUD, scoring, heat maps, bow-tie analysis, KRI management, trend endpoints.
- **Data Entities**: `EnterpriseRisk`, `EnterpriseRiskControl`, `BowTieElement`, `EnterpriseKeyRiskIndicator` (`src/domain/models/risk_register.py`).
- **Dependencies**: KRI, Operational Risk, Analytics, Executive Dashboard.
- **Status**: Active

---

### 10. KRI (Key Risk Indicators)

- **Domain**: Risk Intelligence
- **Problem**: Risk managers need automated, threshold-driven indicators to detect emerging risks before they materialise; manual KRI collection is slow and KRI data goes stale.
- **Primary Persona(s)**: P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a risk manager, I can define KRIs with RAG thresholds (red/amber/green) and measurement frequency.
  - As a risk analyst, I can record KRI measurements and view trend charts.
  - As a manager, I can receive alerts when KRI thresholds are breached.
  - As an executive, I can view the KRI traffic-light dashboard for a real-time risk pulse.
  - As a risk manager, I can track risk score history and trend direction.
- **Success Metrics**: KRI data freshness; threshold breach detection latency; KRI dashboard engagement.
- **Journey Reference**: Journey 3 — Risk Assessment (P3), step 6
- **API Surface**: `src/api/routes/kri.py` — KRI CRUD, measurements, alerts, dashboard, risk score history, trend analysis.
- **Data Entities**: `KRI`, `KRIMeasurement`, `KRIAlert` (`src/domain/models/kri.py`).
- **Dependencies**: Enterprise Risk Register, Operational Risk, Notifications, Analytics.
- **Status**: Active

---

### 11. Actions Management

- **Domain**: Cross-Module Task Tracking
- **Problem**: Actions arising from incidents, audits, complaints, investigations, and assessments are tracked in different places; a unified actions view prevents items falling through the cracks.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager), P4 (System Administrator)
- **Key User Stories**:
  - As a manager, I can view all open actions across every module in a single unified list.
  - As an action owner, I can update status, add notes, and mark actions complete.
  - As a quality manager, I can filter actions by source type (incident, audit, complaint, investigation, CAPA, assessment, induction).
  - As a supervisor, I can see overdue actions and escalate as needed.
  - As an analyst, I can track action closure rates and mean time to close.
- **Success Metrics**: Overdue action count; mean time to action closure; action completion rate by module.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), step 8; Journey 4 — System Configuration (P4)
- **API Surface**: `src/api/routes/actions.py` — Unified CRUD across `IncidentAction`, `ComplaintAction`, `RTAAction`, `InvestigationAction`, `CAPAAction`, `AssessmentRun`, `InductionRun`; bulk status updates.
- **Data Entities**: `IncidentAction`, `ComplaintAction`, `RTAAction`, `InvestigationAction`, `CAPAAction` (sourced from respective module models).
- **Dependencies**: Incidents, Complaints, RTAs, Investigations, CAPA, Audits, Assessments, Inductions.
- **Status**: Active

---

### 12. Standards Library

- **Domain**: Compliance & Governance
- **Problem**: Organisations must track compliance against multiple standards (ISO 9001, 14001, 45001, 27001, etc.) but standard clauses, controls, and cross-mappings are hard to navigate and maintain.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can create and maintain standards with hierarchical clauses and controls.
  - As an auditor, I can browse the standards library and link audit questions to specific clauses.
  - As a compliance officer, I can view compliance scores per standard.
  - As a manager, I can view cross-standard mappings to identify shared controls.
- **Success Metrics**: Standards library coverage; clause-to-evidence link completeness; compliance score trend.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), step 4
- **API Surface**: `src/api/routes/standards.py` — Standard CRUD, clause CRUD, control CRUD, compliance scoring; `src/api/routes/cross_standard_mappings.py` — Cross-standard mapping endpoints.
- **Data Entities**: `Standard`, `Clause`, `Control` (`src/domain/models/standard.py`).
- **Dependencies**: Compliance Evidence, Audits, ISO 27001.
- **Status**: Active

---

### 13. Compliance Evidence & ISO Mapping

- **Domain**: Compliance Assurance
- **Problem**: Demonstrating compliance to external auditors requires linking evidence (documents, audit findings, controls) to specific standard clauses; manual evidence mapping is labour-intensive and error-prone.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a compliance officer, I can auto-tag content with ISO clauses using AI-powered matching.
  - As an auditor, I can create and manage evidence links between platform records and standard clauses.
  - As a manager, I can run gap analysis to identify clauses with insufficient evidence coverage.
  - As an executive, I can view compliance scores and gap analysis reports for board reviews.
- **Success Metrics**: Evidence coverage percentage per standard; gap analysis closure rate; auto-tag accuracy.
- **Journey Reference**: Journey 5 — Executive Oversight (P5), step 2
- **API Surface**: `src/api/routes/compliance.py` — Auto-tagging, evidence link management, compliance reports, gap analysis, coverage summaries.
- **Data Entities**: `ComplianceEvidenceLink` (`src/domain/models/compliance_evidence.py`); `IMSRequirement` (`src/domain/models/ims_unification.py`).
- **Dependencies**: Standards Library, Audits, Evidence Assets, Documents, IMS Dashboard.
- **Status**: Active

---

### 14. Compliance Automation

- **Domain**: Regulatory Intelligence
- **Problem**: Regulatory changes, certificate expiries, and compliance deadlines are easy to miss without automated monitoring; reactive compliance creates risk.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As a compliance officer, I can monitor regulatory changes relevant to my industry and region.
  - As a quality manager, I can track certificate expiry dates and receive proactive alerts.
  - As an auditor, I can manage the scheduled audit programme and ensure coverage.
  - As a manager, I can view compliance scoring and RIDDOR automation status.
  - As an admin, I can configure gap analysis rules and compliance thresholds.
- **Success Metrics**: Regulatory change detection latency; certificate expiry miss rate; compliance score improvement over time.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2); Journey 5 — Executive Oversight (P5)
- **API Surface**: `src/api/routes/compliance_automation.py` — Regulatory monitoring, gap analysis, certificate tracking, scheduled audits, compliance scoring, RIDDOR automation.
- **Data Entities**: `ComplianceAutomation` (`src/domain/models/compliance_automation.py`).
- **Dependencies**: Standards Library, Audits, Notifications, Compliance Evidence.
- **Status**: Active

---

### 15. Document Management

- **Domain**: Information Management
- **Problem**: Quality-critical documents (procedures, policies, evidence files) are scattered across file shares and email; the platform must provide centralised storage with AI-powered search, version control, and access tracking.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As a user, I can upload documents with metadata, tags, and category classification.
  - As a quality manager, I can perform semantic search across the document library using AI.
  - As an auditor, I can annotate documents and link them to audit findings.
  - As an admin, I can manage document versions and track access history.
  - As a compliance officer, I can link documents to standard clauses as compliance evidence.
- **Success Metrics**: Document retrieval time; search relevance score; document version accuracy.
- **Journey Reference**: Journey 4 — System Configuration (P4)
- **API Surface**: `src/api/routes/documents.py` — Upload, CRUD, AI analysis, semantic search, annotations, version control, access tracking, chunk-level retrieval.
- **Data Entities**: `Document`, `DocumentAnnotation`, `DocumentChunk`, `DocumentSearchLog` (`src/domain/models/document.py`); enums `DocumentStatus`, `DocumentType`, `FileType`.
- **Dependencies**: Evidence Assets, Compliance Evidence, AI Intelligence.
- **Status**: Active

---

### 16. Document Control

- **Domain**: Quality Management Systems
- **Problem**: Controlled documents (SOPs, work instructions, policies) require formal approval workflows, distribution tracking, and obsolescence management to meet ISO requirements; informal document management fails external audits.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As a document author, I can create controlled documents with version control and submit for approval.
  - As an approver, I can review, approve, or reject document versions with comments.
  - As a document controller, I can manage distribution lists and track document access.
  - As an admin, I can obsolete documents and manage the controlled document register.
  - As an auditor, I can verify that controlled documents are current and properly approved.
- **Success Metrics**: Document approval cycle time; overdue review count; distribution acknowledgement rate.
- **Journey Reference**: Journey 4 — System Configuration (P4)
- **API Surface**: `src/api/routes/document_control.py` — Controlled document CRUD, version management, approval workflows, distribution management, obsolescence, access logging.
- **Data Entities**: `ControlledDocument`, `ControlledDocumentVersion`, `DocumentAccessLog`, `DocumentApprovalAction` (`src/domain/models/document_control.py`).
- **Dependencies**: Digital Signatures, Notifications, Audit Trail, Workflows.
- **Status**: Active

---

### 17. Evidence Assets

- **Domain**: Cross-Module Evidence Management
- **Problem**: Photos, files, and documents attached as evidence to incidents, audits, investigations, and other records need centralised, tamper-evident storage with hash verification and cross-module linking.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor)
- **Key User Stories**:
  - As a field reporter, I can upload photos and files as evidence when reporting an incident.
  - As an investigator, I can link evidence assets across multiple related records.
  - As a quality manager, I can view all evidence associated with a record in one place.
  - As an auditor, I can verify evidence integrity via SHA-256 hash verification.
  - As a compliance officer, I can soft-delete evidence with full audit trail.
- **Success Metrics**: Upload success rate; evidence completeness per record; hash verification pass rate.
- **Journey Reference**: Journey 1 — Incident Reporting (P1), step 4
- **API Surface**: `src/api/routes/evidence_assets.py` — Upload (`POST /`), listing by source (`GET /`), investigation linking, soft delete with audit trail; SHA-256 hash on upload.
- **Data Entities**: `EvidenceAsset` (`src/domain/models/evidence_asset.py`).
- **Dependencies**: Incidents, Audits, Investigations, Complaints, RTAs, Document Management.
- **Status**: Active

---

### 18. Employee Portal

- **Domain**: Self-Service & Mobile Access
- **Problem**: Frontline workers need a simplified, mobile-first interface to report incidents, near-misses, complaints, and RTAs without needing a full platform login; existing processes require paper forms or desktop access.
- **Primary Persona(s)**: P1 (Field Reporter)
- **Key User Stories**:
  - As a field worker, I can access the portal via QR code and submit a report without a full account.
  - As a reporter, I can choose the correct form type (incident, near-miss, complaint, RTA) from plain-language descriptions.
  - As a reporter, I can track the status of my submission using a reference number.
  - As a portal user, I can authenticate via SSO for a streamlined experience.
  - As a manager, I can view and triage reports submitted through the portal.
- **Success Metrics**: Portal submission rate; form completion rate; mobile vs desktop ratio; time-to-submit.
- **Journey Reference**: Journey 1 — Incident Reporting (P1), all steps
- **API Surface**: `src/api/routes/employee_portal.py` — Anonymous/SSO submission endpoints, report tracking by reference number, QR code generation, form type selection. Frontend: `PortalIncidentForm`, `PortalRTAForm`, `PortalNearMissForm`, `PortalDynamicForm`, `PortalTrack`, `PortalHelp`.
- **Data Entities**: Shares entities with Incidents, Near Misses, Complaints, RTAs. Portal auth context: `PortalAuthContext` (`frontend/src/contexts/PortalAuthContext.tsx`).
- **Dependencies**: Incidents, Near Misses, Complaints, RTAs, Form Configuration, Reference Numbers.
- **Status**: Active

---

### 19. Workflows & Approvals

- **Domain**: Business Process Automation
- **Problem**: Approval chains, escalation rules, and SLA-driven routing are configured ad hoc; the platform needs a generic workflow engine to automate multi-step business processes across all modules.
- **Primary Persona(s)**: P4 (System Administrator), P2 (Quality Auditor), P5 (Executive)
- **Key User Stories**:
  - As an admin, I can create workflow templates with steps, conditions, and approval requirements.
  - As a workflow participant, I can view my pending approvals and take action (approve, reject, delegate).
  - As a manager, I can configure delegation rules and escalation timers.
  - As a process owner, I can monitor workflow instances and identify bottlenecks.
  - As an admin, I can perform bulk workflow actions for efficiency.
- **Success Metrics**: Workflow completion rate; mean approval latency; escalation frequency; SLA adherence.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 5
- **API Surface**: `src/api/routes/workflows.py` and `src/api/routes/workflow.py` — Template management, instance operations, approval management, delegation configuration, bulk actions.
- **Data Entities**: `Workflow`, `WorkflowRules` (`src/domain/models/workflow.py`, `src/domain/models/workflow_rules.py`).
- **Dependencies**: Document Control, CAPA, Notifications, User Management.
- **Status**: Active

---

### 20. Digital Signatures

- **Domain**: Legal & Compliance
- **Problem**: Quality records, audit reports, and controlled documents require verifiable digital signatures for regulatory compliance; wet-ink processes are slow and hard to audit.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator), P5 (Executive)
- **Key User Stories**:
  - As a document owner, I can request digital signatures from one or more signatories.
  - As a signatory, I can review and digitally sign documents with a legally binding e-signature.
  - As an admin, I can track signature status and send reminders for pending signatures.
  - As an auditor, I can verify signature authenticity and view the signature chain.
- **Success Metrics**: Signature completion rate; mean time to sign; verification success rate.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), report signing
- **API Surface**: `src/api/routes/signatures.py` — Signature request creation, signing, verification, status tracking, reminders (DocuSign-level e-signature capabilities).
- **Data Entities**: `DigitalSignature` (`src/domain/models/digital_signature.py`).
- **Dependencies**: Document Control, Audits, Workflows, Notifications, User Management.
- **Status**: Active

---

### 21. Notifications & Alerts

- **Domain**: Platform Infrastructure
- **Problem**: Users miss critical events (overdue actions, KRI breaches, new assignments) because there is no unified notification system; the platform must deliver timely, context-rich notifications across channels.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor), P3 (Risk Manager), P4 (System Administrator), P5 (Executive)
- **Key User Stories**:
  - As a user, I can view my notifications in a centralised inbox with read/unread status.
  - As a manager, I can receive alerts when actions are overdue or KRI thresholds breach.
  - As an admin, I can configure notification preferences and channel routing (in-app, email, push).
  - As a user, I can search for mentionable users to tag in comments and trigger notifications.
  - As a user, I can manage notification settings per category and priority.
- **Success Metrics**: Notification delivery latency; read rate; alert-to-action conversion rate.
- **Journey Reference**: All journeys — notifications are cross-cutting
- **API Surface**: `src/api/routes/notifications.py` — List, mark read, preferences, mention search; `src/api/routes/push_notifications.py` — Push notification subscription/delivery; admin settings: `frontend/src/pages/admin/NotificationSettings.tsx`.
- **Data Entities**: `Notification` (`src/domain/models/notification.py`); enums `NotificationType`, `NotificationPriority`.
- **Dependencies**: All modules (event producers), Email Service, SMS Service, WebSocket (real-time).
- **Status**: Active

---

### 22. User Management & Authentication

- **Domain**: Identity & Access Management
- **Problem**: Multi-tenant organisations need role-based access control, secure authentication, and user lifecycle management; without it, data leakage across tenants and unauthorised access are risks.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can create users, assign roles, and manage permissions with RBAC and ABAC.
  - As an admin, I can manage roles with granular permission sets.
  - As a user, I can log in with username/password or SSO and receive JWT tokens.
  - As a user, I can reset my password via email-based flow.
  - As an admin, I can bulk import users and sync with Azure AD.
- **Success Metrics**: User onboarding time; authentication failure rate; permission misconfiguration incidents.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 2
- **API Surface**: `src/api/routes/users.py` — User CRUD, role management, permission assignment; `src/api/routes/auth.py` — Login, token refresh, password reset, password change; ABAC via `src/domain/services/abac_service.py`.
- **Data Entities**: `User`, `Role` (`src/domain/models/user.py`); `Permissions` (`src/domain/models/permissions.py`); `TokenBlacklist` (`src/domain/models/token_blacklist.py`).
- **Dependencies**: Tenant Management, Feature Flags, Audit Trail.
- **Status**: Active

---

### 23. Tenant Management

- **Domain**: Platform Infrastructure (Multi-Tenancy)
- **Problem**: SaaS deployment requires strict data isolation between customer organisations with per-tenant branding, feature configuration, and usage limits.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As a super-admin, I can create and manage tenants with branding and configuration.
  - As a tenant admin, I can configure tenant-specific branding (logo, colours, name).
  - As a user, I can switch between tenants if I have multi-tenant access.
  - As an admin, I can view tenant health metrics and user counts.
- **Success Metrics**: Tenant provisioning time; data isolation validation pass rate; tenant churn rate.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 6
- **API Surface**: `src/api/routes/tenants.py` — Tenant CRUD, user-tenant associations, branding configuration, tenant switching.
- **Data Entities**: `Tenant` (`src/domain/models/tenant.py`).
- **Dependencies**: User Management, Feature Flags.
- **Status**: Active

---

### 24. Feature Flags

- **Domain**: Platform Infrastructure (Release Management)
- **Problem**: Progressive feature rollout, A/B testing, and tenant-specific feature enablement require a feature flag system that decouples deployment from release.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can create, enable, and disable feature flags with per-tenant targeting.
  - As a developer, I can evaluate feature flags at runtime to gate functionality.
  - As a product manager, I can roll out features progressively to specific tenants or user cohorts.
  - As an admin, I can view all flags and their current state across tenants.
- **Success Metrics**: Flag evaluation latency; feature adoption rate post-rollout; rollback time.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 6
- **API Surface**: `src/api/routes/feature_flags.py` — CRUD, evaluate endpoint, filtered listing; frontend: `useFeatureFlag` hook (`frontend/src/hooks/useFeatureFlag.ts`).
- **Data Entities**: `FeatureFlag` (`src/domain/models/feature_flag.py`).
- **Dependencies**: Tenant Management, User Management.
- **Status**: Active

---

### 25. Analytics & Reporting

- **Domain**: Business Intelligence
- **Problem**: Stakeholders across the organisation need data-driven insights — from operational dashboards to board-level reports — but data is trapped in module silos.
- **Primary Persona(s)**: P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a manager, I can view pre-built dashboards with trend analysis and forecasting.
  - As an executive, I can access the executive dashboard with KPIs, health scoring, and vehicle governance summary.
  - As a power user, I can build custom dashboards with drag-and-drop widget configuration.
  - As a manager, I can generate reports with cost calculations, ROI tracking, and benchmarking.
  - As a user, I can export data in multiple formats via the Export Center.
- **Success Metrics**: Dashboard engagement frequency; report generation volume; data-to-insight latency.
- **Journey Reference**: Journey 5 — Executive Oversight (P5), all steps
- **API Surface**: `src/api/routes/analytics.py` — Dashboard CRUD, widget data, trends, forecasting, benchmarks, cost/ROI; `src/api/routes/executive_dashboard.py` — Executive KPI dashboard, vehicle governance summary; `src/api/routes/wdp_analytics.py` — Workforce analytics.
- **Data Entities**: `Analytics` (`src/domain/models/analytics.py`).
- **Dependencies**: All data-producing modules, Telemetry.
- **Status**: Active

---

### 26. Telemetry & Observability

- **Domain**: Platform Infrastructure
- **Problem**: Product and engineering teams need anonymised usage telemetry to understand feature adoption, identify friction points, and make data-driven decisions without compromising user privacy.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As a product manager, I can view anonymised page-view and feature-usage data.
  - As an engineer, I can analyse experiment events (e.g., EXP-001) with bounded dimensions.
  - As a privacy officer, I can verify that no PII is collected — all dimensions are from an allowlist.
  - As an admin, I can view client-side Web Vitals and error tracking data.
- **Success Metrics**: Telemetry coverage; event delivery reliability; experiment analysis turnaround time.
- **Journey Reference**: Cross-cutting — embedded in all journeys
- **API Surface**: `src/api/routes/telemetry.py` — Event ingestion with schema validation, dimension allowlist enforcement; frontend: `frontend/src/services/telemetry.ts`, `frontend/src/lib/webVitals.ts`, `frontend/src/services/errorTracker.ts`.
- **Data Entities**: Telemetry events (structured log records, not persistent models).
- **Dependencies**: Azure Monitor (`src/infrastructure/monitoring/azure_monitor.py`).
- **Status**: Active

---

### 27. Audit Trail

- **Domain**: Governance & Compliance
- **Problem**: Regulatory audits require immutable, tamper-evident records of every data change; without a hash-chained audit trail, organisations cannot prove data integrity.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator), P5 (Executive)
- **Key User Stories**:
  - As an auditor, I can view a chronological audit trail filtered by user, entity, or date range.
  - As a compliance officer, I can verify chain integrity to prove no records have been tampered with.
  - As an admin, I can export audit logs for external compliance submissions.
  - As an analyst, I can view audit trail statistics and anomaly patterns.
- **Success Metrics**: Chain integrity verification pass rate; audit log query performance; completeness of event capture.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 7
- **API Surface**: `src/api/routes/audit_trail.py` — Log viewing, chain verification, export, statistics.
- **Data Entities**: `AuditLog` (`src/domain/models/audit_log.py`).
- **Dependencies**: All modules (event producers).
- **Status**: Active

---

### 28. ISO 27001 Information Security

- **Domain**: Information Security Management
- **Problem**: Organisations pursuing or maintaining ISO 27001:2022 certification need to manage information assets, Annex A controls, Statement of Applicability, security risks, security incidents, access controls, business continuity plans, and supplier assessments in an integrated system.
- **Primary Persona(s)**: P3 (Risk Manager), P4 (System Administrator)
- **Key User Stories**:
  - As a security manager, I can maintain an information asset register with classification and ownership.
  - As a compliance officer, I can manage the Statement of Applicability (SoA) for all 93 Annex A controls.
  - As a risk manager, I can assess information security risks and link them to Annex A controls.
  - As an admin, I can track security incidents, access control records, and supplier assessments.
  - As a manager, I can manage business continuity plans with test schedules and results.
- **Success Metrics**: SoA completion rate; information asset coverage; security incident response time; BCP test pass rate.
- **Journey Reference**: Journey 3 — Risk Assessment (P3), information security variant
- **API Surface**: `src/api/routes/iso27001.py` — Information asset management, Annex A controls, SoA, security risks, security incidents, access control, business continuity plans, supplier assessments.
- **Data Entities**: `InformationAsset`, `AnnexAControl`, `StatementOfApplicability`, `InformationSecurityRisk`, `SecurityIncident`, `AccessControlRecord`, `BusinessContinuityPlan`, `SupplierAssessment` (`src/domain/models/iso27001.py`).
- **Dependencies**: Standards Library, Risk Management, Compliance Evidence, Audit Trail.
- **Status**: Active

---

### 29. GDPR & Privacy

- **Domain**: Data Privacy & Compliance
- **Problem**: GDPR Articles 15–17 require the ability to export, pseudonymise, and erase personal data on request; manual compliance is error-prone and legally risky.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As a data subject, I can request an export of all my personal data (Right of Access, Art. 15).
  - As a privacy officer, I can pseudonymise personal data for analytics while preserving utility.
  - As a data subject, I can request erasure of my personal data (Right to Erasure, Art. 17).
  - As an admin, I can preview data exports with a dry-run mode before generating final packages.
- **Success Metrics**: Data Subject Access Request (DSAR) response time; erasure completeness; pseudonymisation coverage.
- **Journey Reference**: N/A (regulatory requirement, cross-cutting)
- **API Surface**: `src/api/routes/gdpr.py` — Data export (`GET /me/data-export`), pseudonymisation, erasure; dry-run mode support.
- **Data Entities**: Uses entities from all modules; service layer: `GDPRService` (`src/domain/services/gdpr_service.py`), `PseudonymizationService` (`src/domain/services/pseudonymization_service.py`).
- **Dependencies**: User Management, all data-owning modules.
- **Status**: Active

---

### 30. Planet Mark / Sustainability

- **Domain**: Environmental Sustainability
- **Problem**: Organisations seeking Planet Mark certification need to track carbon footprints across Scope 1, 2, and 3 emissions, manage improvement actions, and demonstrate year-on-year reduction with data quality scoring.
- **Primary Persona(s)**: P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a sustainability manager, I can record multi-year carbon footprint data across all 15 GHG Protocol Scope 3 categories.
  - As a data owner, I can score data quality (0–16 scale) with auto-calculation.
  - As a sustainability lead, I can define SMART improvement actions and track progress.
  - As a manager, I can manage the Planet Mark certification lifecycle.
  - As a compliance officer, I can view ISO 14001 cross-mapping for environmental management alignment.
- **Success Metrics**: Year-on-year carbon reduction percentage; data quality score improvement; certification renewal rate.
- **Journey Reference**: N/A (sustainability-specific)
- **API Surface**: `src/api/routes/planet_mark.py` — Multi-year footprint tracking, Scope 1/2/3 management, data quality scoring, improvement actions, certification lifecycle, ISO 14001 cross-mapping.
- **Data Entities**: `PlanetMark` (`src/domain/models/planet_mark.py`).
- **Dependencies**: Standards Library, Compliance Evidence, Analytics.
- **Status**: Active

---

### 31. Vehicle Checklists & Fleet Governance

- **Domain**: Fleet Operations & Safety
- **Problem**: Daily vehicle checks captured in the external PAMS system need governance oversight — defect tracking, CAPA generation, and compliance reporting — within the QGP platform.
- **Primary Persona(s)**: P1 (Field Reporter), P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As a fleet manager, I can view van checklist data synced from the PAMS system.
  - As a supervisor, I can create and track defect records from failed checklist items.
  - As a quality manager, I can generate CAPA from recurring vehicle defects via the vehicle CAPA pipeline.
  - As an analyst, I can view checklist analytics and defect trend data.
  - As a manager, I can view the vehicle registry and defect status per vehicle.
- **Success Metrics**: Checklist completion rate; defect resolution time; PAMS sync reliability; repeat defect rate.
- **Journey Reference**: Journey 5 — Executive Oversight (P5), vehicle governance
- **API Surface**: `src/api/routes/vehicle_checklists.py` — Checklist listing (PAMS read-only), defect CRUD, defect actions; `src/api/routes/vehicle_checklist_analytics.py` — Analytics endpoints; `src/api/routes/vehicles.py` — Vehicle registry.
- **Data Entities**: `PAMSVanChecklistCache`, `PAMSSyncLog` (`src/domain/models/pams_cache.py`); `VehicleDefect` (`src/domain/models/vehicle_defect.py`); `VehicleRegistry` (`src/domain/models/vehicle_registry.py`).
- **Dependencies**: CAPA (via vehicle CAPA pipeline), Evidence Assets, Analytics, PAMS external database.
- **Status**: Active

---

### 32. UVDB / Achilles Audits

- **Domain**: Supply Chain Compliance
- **Problem**: Utilities and infrastructure organisations must demonstrate compliance through UVDB Achilles Verify B2 audit protocols with section-level scoring, KPI tracking, and ISO cross-mapping; manual preparation is time-consuming and error-prone.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As a UVDB auditor, I can manage UVDB audit runs with the Verify B2 protocol structure.
  - As a quality manager, I can track section-level responses and auto-calculated scores.
  - As a manager, I can monitor Section 15 KPI metrics for continuous improvement.
  - As a compliance officer, I can view ISO cross-mappings for UVDB questions.
  - As a customer, I can view customer-facing audit results.
- **Success Metrics**: UVDB audit score; section completion rate; KPI trend improvement; audit preparation time.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), UVDB variant
- **API Surface**: `src/api/routes/uvdb.py` — UVDB audit management, section/question management, responses and scoring, KPI tracking, ISO cross-mapping; `src/api/routes/external_audit_records.py` — External audit record management; `src/api/routes/external_audit_imports.py` — XML import of external audit data.
- **Data Entities**: `UVDBAchilles` (`src/domain/models/uvdb_achilles.py`); `ExternalAuditRecord` (`src/domain/models/external_audit_record.py`); `ExternalAuditImport` (`src/domain/models/external_audit_import.py`).
- **Dependencies**: Audits, Standards Library, Compliance Evidence, XML Importer.
- **Status**: Active

---

### 33. AI Intelligence & Copilot

- **Domain**: Artificial Intelligence
- **Problem**: QHSE professionals spend excessive time on manual analysis — classifying findings, generating audit questions, matching evidence, identifying trends, and performing root cause analysis; AI can automate and augment these tasks.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As an auditor, I can use AI to auto-generate audit questions from standard clauses and templates.
  - As an investigator, I can use AI-powered root cause analysis and anomaly detection.
  - As a quality manager, I can receive AI-driven recommendations and predictive analytics.
  - As an auditor, I can auto-classify findings and match evidence to clauses.
  - As a user, I can interact with an AI copilot via conversational chat and WebSocket for real-time assistance.
- **Success Metrics**: AI recommendation acceptance rate; prediction accuracy; time saved per AI-assisted task; copilot engagement rate.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), AI-augmented steps
- **API Surface**: `src/api/routes/ai_intelligence.py` — Predictive analytics, root cause analysis, anomaly detection, recommendations, audit AI assistant; `src/api/routes/copilot.py` — Conversational AI assistant with WebSocket support; `src/api/routes/ai_templates.py` — AI-powered template generation.
- **Data Entities**: `AICopilot` (`src/domain/models/ai_copilot.py`); services: `AuditQuestionGenerator`, `AuditReportGenerator`, `AuditTrendAnalyzer`, `EvidenceMatcher`, `FindingClassifier` (`src/domain/services/ai_audit_service.py`); `GeminiAIService`, `MistralAnalysisService`, multi-model consensus (`src/domain/services/ai_consensus_service.py`).
- **Dependencies**: Audits, Investigations, Documents, Risk Management, Standards Library.
- **Status**: Active

---

### 34. Workforce Development (Engineers, Assessments, Training)

- **Domain**: Workforce Competency & Training
- **Problem**: Organisations must track engineer competencies, conduct periodic assessments, deliver induction/training programmes, and maintain skills matrices to meet regulatory requirements and ensure workforce readiness.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can create and manage engineer profiles with qualifications, certifications, and competency records.
  - As a supervisor, I can create and execute competency assessments with question-level scoring.
  - As a training manager, I can create and deliver induction/training programmes with tracked completion.
  - As a manager, I can view the skills matrix and competency dashboard for gap analysis.
  - As an engineer, I can view my profile, upcoming assessments, and training schedule on the workforce calendar.
- **Success Metrics**: Assessment completion rate; competency coverage percentage; training programme completion rate; skills gap closure rate.
- **Journey Reference**: Journey 4 — System Configuration (P4), workforce variant
- **API Surface**: `src/api/routes/engineers.py` — Engineer CRUD, competency records, skills matrix; `src/api/routes/assessments.py` — Assessment run CRUD, responses, scoring; `src/api/routes/inductions.py` — Induction/training run CRUD, responses, scoring; `src/api/routes/wdp_analytics.py` — Workforce analytics. Frontend: `workforce/Engineers`, `workforce/Assessments`, `workforce/Training`, `workforce/CompetencyDashboard`, `workforce/Calendar`.
- **Data Entities**: `Engineer` (`src/domain/models/engineer.py`); `AssessmentRun` (`src/domain/models/assessment.py`); `InductionRun` (`src/domain/models/induction.py`); `AuditorCompetence` (`src/domain/models/auditor_competence.py`).
- **Dependencies**: User Management, Actions, Notifications, Digital Signatures.
- **Status**: Active

---

### 35. Form Configuration & Builder

- **Domain**: Platform Configuration
- **Problem**: Administrators need to create and customise data-capture forms (incident, complaint, RTA, near-miss) without developer involvement; rigid forms cannot adapt to changing regulatory or organisational requirements.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can create form templates with multi-step wizards, conditional logic, and field validation.
  - As an admin, I can configure field types, labels, help text, and display order.
  - As a manager, I can manage contracts linked to form configurations.
  - As an admin, I can preview forms before publishing and version form templates.
  - As a portal user, forms render dynamically based on the admin-defined configuration.
- **Success Metrics**: Form configuration time; form completion rate; form error rate; template reuse rate.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 3
- **API Surface**: `src/api/routes/form_config.py` — Form template CRUD, step management, field management, contract management, versioning. Frontend: `admin/FormBuilder`, `admin/FormsList`, `PortalDynamicForm`, `DynamicForm` component.
- **Data Entities**: `FormConfig` (`src/domain/models/form_config.py`).
- **Dependencies**: Employee Portal, Incidents, Complaints, Near Misses, RTAs.
- **Status**: Active

---

### 36. Policies

- **Domain**: Quality Management
- **Problem**: Organisational policies must be documented, versioned, distributed, and acknowledged by relevant staff; without a centralised policy library, compliance teams cannot verify policy awareness.
- **Primary Persona(s)**: P2 (Quality Auditor), P4 (System Administrator)
- **Key User Stories**:
  - As a policy owner, I can create, update, and version policies with metadata and categorisation.
  - As a compliance officer, I can distribute policies and track staff acknowledgement.
  - As a user, I can browse the policy library and acknowledge required policies.
  - As an admin, I can manage policy acknowledgement records and view compliance statistics.
- **Success Metrics**: Policy acknowledgement rate; time to acknowledge; policy review cadence adherence.
- **Journey Reference**: Journey 4 — System Configuration (P4)
- **API Surface**: `src/api/routes/policies.py` — Policy CRUD, versioning; `src/api/routes/policy_acknowledgment.py` — Acknowledgement tracking.
- **Data Entities**: `Policy` (`src/domain/models/policy.py`); `PolicyAcknowledgment` (`src/domain/models/policy_acknowledgment.py`).
- **Dependencies**: Document Control, Notifications, User Management, Audit Trail.
- **Status**: Active

---

### 37. IMS (Integrated Management System) Dashboard

- **Domain**: Multi-Standard Governance
- **Problem**: Organisations certified to multiple standards (ISO 9001, 14001, 45001, 27001) need a unified view of cross-standard compliance, shared controls, and overall management system health.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager), P5 (Executive)
- **Key User Stories**:
  - As a compliance officer, I can view overall IMS compliance percentage across all standards.
  - As a manager, I can identify shared controls and cross-standard synergies.
  - As an executive, I can see a single dashboard summarising the health of the entire management system.
  - As an auditor, I can drill into standard-specific compliance details from the IMS overview.
- **Success Metrics**: Overall IMS compliance score; cross-standard control reuse rate; dashboard engagement.
- **Journey Reference**: Journey 5 — Executive Oversight (P5), step 2
- **API Surface**: `src/api/routes/ims_dashboard.py` — IMS dashboard summary with overall compliance, per-standard breakdown, cross-standard mappings.
- **Data Entities**: `IMSRequirement` (`src/domain/models/ims_unification.py`); service: `IMSDashboardService` (`src/domain/services/ims_dashboard_service.py`).
- **Dependencies**: Standards Library, Compliance Evidence, Audits, Risk Management, ISO 27001.
- **Status**: Active

---

### 38. Global Search

- **Domain**: Platform Usability
- **Problem**: Users need to find records across all modules (incidents, audits, risks, documents, etc.) from a single search interface rather than navigating to each module individually.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager), P4 (System Administrator)
- **Key User Stories**:
  - As a user, I can search across all modules from a single search bar with type-ahead suggestions.
  - As a user, I can filter search results by record type, date range, and status.
  - As a user, I can view highlighted matches and navigate directly to the relevant record.
- **Success Metrics**: Search latency; results relevance score; search-to-navigation conversion rate.
- **Journey Reference**: Cross-cutting — improves all journeys
- **API Surface**: `src/api/routes/global_search.py` — Unified search endpoint with multi-module querying; service: `SearchService` (`src/domain/services/search_service.py`).
- **Data Entities**: Federated — queries across all module entities.
- **Dependencies**: All data-owning modules.
- **Status**: Active

---

### 39. Real-Time Collaboration

- **Domain**: Platform Infrastructure
- **Problem**: Multiple users editing the same record (e.g., investigation, audit) simultaneously can cause data conflicts; real-time presence and collaboration features prevent overwrites and improve teamwork.
- **Primary Persona(s)**: P2 (Quality Auditor), P3 (Risk Manager)
- **Key User Stories**:
  - As a user, I can see who else is viewing or editing the same record in real-time.
  - As a user, I can receive real-time updates when collaborators make changes.
  - As a user, I can use optimistic updates for instant UI feedback with background sync.
- **Success Metrics**: Concurrent editing conflict rate; collaboration session duration; real-time update delivery latency.
- **Journey Reference**: Journey 2 — Audit Lifecycle (P2), collaborative execution
- **API Surface**: `src/api/routes/realtime.py` — WebSocket endpoints; frontend: `useCollaboration` hook, `useWebSocket` hook, `useOptimisticUpdate` hook, `components/realtime/` module.
- **Data Entities**: `Collaboration` (`src/domain/models/collaboration.py`).
- **Dependencies**: WebSocket infrastructure, User Management.
- **Status**: Active

---

### 40. Governance & SLO Monitoring

- **Domain**: Platform Reliability & Governance
- **Problem**: The platform itself must meet governance and reliability standards — service-level objectives, dead-letter queue management, and operational health monitoring.
- **Primary Persona(s)**: P4 (System Administrator)
- **Key User Stories**:
  - As an admin, I can view SLO metrics and compliance status for platform services.
  - As an admin, I can review and retry failed background tasks from the dead-letter queue.
  - As an operations manager, I can view governance reports on system health and reliability.
  - As an admin, I can monitor system health checks and infrastructure status.
- **Success Metrics**: SLO compliance percentage; DLQ depth; mean time to recover failed tasks; system uptime.
- **Journey Reference**: Journey 4 — System Configuration (P4), step 8
- **API Surface**: `src/api/routes/slo.py` — SLO metrics and compliance; `src/api/routes/governance.py` — Governance reporting; `src/api/routes/dlq_admin.py` — Dead-letter queue admin; `src/api/routes/health.py` — Health checks.
- **Data Entities**: `FailedTask` (`src/domain/models/failed_task.py`); service: `GovernanceService` (`src/domain/services/governance_service.py`).
- **Dependencies**: All services, Infrastructure (Redis cache, database, background tasks).
- **Status**: Active

---

### 41. Driver & Asset Management

- **Domain**: Fleet Operations
- **Problem**: Transport and fleet organisations need to track driver profiles, LOLER equipment, and operational assets with compliance certification and maintenance schedules.
- **Primary Persona(s)**: P3 (Risk Manager), P4 (System Administrator)
- **Key User Stories**:
  - As a fleet manager, I can maintain driver profiles with licence details and compliance status.
  - As an admin, I can manage the asset register with maintenance and inspection schedules.
  - As a compliance officer, I can track LOLER equipment certification and inspection dates.
  - As a manager, I can view asset utilisation and maintenance compliance dashboards.
- **Success Metrics**: Asset register completeness; LOLER inspection compliance rate; driver licence expiry alert coverage.
- **Journey Reference**: Journey 4 — System Configuration (P4)
- **API Surface**: `src/api/routes/drivers.py` — Driver profile management; `src/api/routes/assets.py` — Asset CRUD and tracking.
- **Data Entities**: `DriverProfile` (`src/domain/models/driver_profile.py`); `Asset` (`src/domain/models/asset.py`); `LOLER` (`src/domain/models/loler.py`).
- **Dependencies**: Vehicle Checklists, User Management, Notifications.
- **Status**: Active

---

---

## Cross-Cutting Concerns

The following capabilities are not standalone modules but are shared across the platform:

| Concern | Implementation | Used By |
|---------|---------------|---------|
| Reference Numbers | `src/domain/services/reference_number.py` | Incidents, Near Misses, Complaints, RTAs, Policies |
| Pagination | `src/api/utils/pagination.py` | All list endpoints |
| Error Handling | `src/api/utils/errors.py`, `src/api/schemas/error_codes.py` | All routes |
| Tenant Isolation | `src/api/utils/tenant.py`, ABAC service | All data queries |
| Background Tasks | `src/infrastructure/tasks/` | Notifications, cleanup, sync |
| Caching | `src/infrastructure/cache/redis_cache.py` | Performance-critical paths |
| Email & SMS | `src/domain/services/email_service.py`, `sms_service.py` | Notifications, password reset |
| Offline Support | `frontend/src/services/offlineStorage.ts`, `syncService.ts` | Audit execution, portal forms |
| Internationalisation | `frontend/src/i18n/i18n.ts` | All frontend components |
| Accessibility | `frontend/src/test/axe-helper.ts`, `ui-a11y.test.tsx` | All UI components |
| Geolocation | `frontend/src/hooks/useGeolocation.ts` | Incident/near-miss forms |
| Voice-to-Text | `frontend/src/hooks/useVoiceToText.ts` | Form entry |
| Keyboard Shortcuts | `frontend/src/hooks/useKeyboardShortcuts.ts` | Power user navigation |

---

## Module Dependency Map (Simplified)

```
Employee Portal ──→ Incidents / Near Misses / Complaints / RTAs
                         │              │             │          │
                         ▼              ▼             ▼          ▼
                    Evidence Assets ◄──────────────────────────────
                         │
                         ▼
                  Investigations ──→ RCA Tools
                         │
                    ┌────┴────┐
                    ▼         ▼
                  CAPA ←── Audits ──→ Audit Templates
                    │         │
                    ▼         ▼
                 Actions   Findings ──→ Compliance Evidence
                                              │
                                              ▼
                                    Standards Library ──→ IMS Dashboard
                                              │
                                              ▼
                                    ISO 27001 / UVDB / Planet Mark

Risk Management ──→ Enterprise Risk Register ──→ KRI
       │
       ▼
 Analytics ──→ Executive Dashboard ──→ Report Generator

Workflows ──→ Document Control ──→ Digital Signatures
                    │
                    ▼
                 Policies

User Management ──→ Tenant Management ──→ Feature Flags
       │
       ▼
GDPR / Privacy

Form Config ──→ Portal Dynamic Forms

Notifications ──→ (all modules)
Audit Trail   ──→ (all modules)
Telemetry     ──→ (all modules)
Global Search ──→ (all modules)
```

---

## Revision History

| Date | Author | Change |
|------|--------|--------|
| 2026-04-04 | Product | Initial module inventory — 41 modules catalogued from codebase discovery |
