# Information Architecture — Quality Governance Platform

> Last updated: 2026-03-07

## 1. Current Sitemap

The platform exposes **55 API route modules** under `/api/v1/`. They map to the following logical groups:

### Core Safety & Compliance

| Module | Prefix | Purpose |
|--------|--------|---------|
| incidents | /incidents | Workplace incident reporting & investigation |
| near_miss | /near-misses | Near-miss event tracking |
| complaints | /complaints | External complaint management |
| rtas | /rtas | Road traffic collision management |
| risks | /risks | Operational risk register |
| risk_register | /risk-register | Enterprise risk register (bow-tie, KRIs) |
| policies | /policies | Policy & document library |
| compliance | /compliance | ISO clause mapping & evidence linking |
| compliance_automation | /compliance-automation | Regulatory updates, certificates, RIDDOR |
| iso27001 | /iso27001 | ISO 27001 ISMS controls & SoA |
| capa | /capa | Corrective & preventive actions |

### Audits & Assessments

| Module | Prefix | Purpose |
|--------|--------|---------|
| audits | /audits | Audit templates, runs, findings, responses |
| audit_templates | /audit-templates | Template builder for audits |
| assessments | /assessments | Job competency assessments |
| investigations | /investigations | Root-cause investigation runs |
| investigation_templates | /investigation-templates | Investigation template structure |
| auditor_competence | — | Auditor skills tracking |
| standards | /standards | ISO standards library |

### Workforce Development

| Module | Prefix | Purpose |
|--------|--------|---------|
| engineers | /engineers | Engineer profiles & competencies |
| inductions | /inductions | Site induction tracking |
| wdp_analytics | /wdp-analytics | Workforce development analytics |

### Documents & Evidence

| Module | Prefix | Purpose |
|--------|--------|---------|
| documents | /documents | AI-powered document library |
| document_control | /document-control | Controlled document lifecycle |
| evidence_assets | /evidence-assets | Shared attachments (photos, files) |
| signatures | /signatures | Digital signature workflows |

### Intelligence & Analytics

| Module | Prefix | Purpose |
|--------|--------|---------|
| ai_intelligence | /ai | AI text analysis, predictions, anomalies |
| ai_templates | /ai-templates | AI-assisted template generation |
| copilot | /copilot | Conversational AI assistant |
| analytics | /analytics | KPIs, trends, dashboards, ROI |
| executive_dashboard | — | Executive health score overview |

### Platform

| Module | Prefix | Purpose |
|--------|--------|---------|
| auth | /auth | Login, token exchange, refresh |
| users | /users | User CRUD, roles, search |
| tenants | /tenants | Multi-tenancy management |
| notifications | /notifications | In-app notification centre |
| audit_trail | /audit-trail | Immutable audit log |
| actions | /actions | Unified action tracker |
| workflow | — | Workflow engine (SLA, escalation) |
| workflows | /workflows | Approval workflows & delegations |
| realtime | /realtime | WebSocket connections |
| telemetry | — | Frontend telemetry ingestion |
| form_config | /admin/config | Admin form builder & settings |
| governance | /governance | Governance framework |

### Specialist Modules

| Module | Prefix | Purpose |
|--------|--------|---------|
| planet_mark | /planet-mark | Carbon management & Planet Mark |
| uvdb | /uvdb | UVDB Achilles B2 audit protocol |
| xml_import | /xml-import | XML template batch import |
| employee_portal | /portal | Self-service employee portal |
| rca_tools | — | Root-cause analysis tools |
| kri | — | Key risk indicator dashboard |
| assets | /assets | Asset registry |

---

## 2. Navigation Hierarchy Recommendations

### Proposed Primary Navigation (7 groups)

```
Dashboard
  ├─ Executive Overview
  └─ My Tasks & Actions

Safety
  ├─ Incidents
  ├─ Near Misses
  ├─ Road Traffic Collisions
  ├─ Investigations
  └─ CAPA

Compliance
  ├─ Standards & Clauses
  ├─ Compliance Coverage
  ├─ Certificates & Renewals
  ├─ Regulatory Updates
  ├─ RIDDOR
  └─ Audit Schedule

Risk
  ├─ Operational Risk Register
  ├─ Enterprise Risk Register
  ├─ Key Risk Indicators
  └─ Risk Heatmap

Quality
  ├─ Audits & Inspections
  ├─ Complaints
  ├─ Policies & Documents
  ├─ Document Control
  └─ Evidence Assets

People
  ├─ Engineers
  ├─ Assessments
  ├─ Inductions
  ├─ Competency Matrix
  └─ Employee Portal

Settings
  ├─ Users & Roles
  ├─ Tenants
  ├─ Form Builder
  ├─ Notifications
  ├─ Audit Trail
  └─ Workflow Config
```

### Key IA Issues to Address

1. **Duplicate risk modules** — `/risks` (operational) and `/risk-register` (enterprise) should be unified under a single "Risk" section with tabs.
2. **Scattered audit-related routes** — `audits`, `audit-templates`, `audit_trail`, and `auditor_competence` should be co-located under "Audits & Inspections".
3. **Actions visibility** — The unified actions endpoint should surface as a "My Actions" widget on the dashboard, not hidden in a separate route.
4. **Deep nesting** — `compliance-automation` contains sub-features (RIDDOR, certificates, scheduled audits) that deserve top-level visibility within the Compliance group.
5. **Portal isolation** — The employee portal (`/portal`) serves a different persona and should have its own simplified navigation shell.

### Content Labelling Improvements

| Current Label | Suggested Label | Reason |
|---------------|----------------|--------|
| Near Misses | Near-Miss Reports | Clarity that these are reports, not events |
| RTAs | Road Traffic Collisions | Avoid jargon |
| CAPA | Corrective Actions | Plain language for non-quality users |
| WDP Analytics | Workforce Insights | User-friendly |
| KRI | Key Risk Indicators | Spell out on first encounter |

### Trademarks and programme names

Canonical product and third-party names (including **Planet Mark**) are listed in
[`glossary-trademarks.md`](./glossary-trademarks.md). Use that file as the SSOT for UI copy and docs.

---

## 3. Search & Discovery

- Global search (`/api/v1/search`) exists but is a single-field search. Consider faceted search by module, date range, status, and severity.
- No breadcrumb pattern is documented. Each page should display: `Section > Module > Record` breadcrumbs.
- Related records (e.g., incident → investigation → CAPA) should show cross-links in a "Related Items" sidebar.

---

## 4. Next Steps

1. Validate the proposed hierarchy with the 5 user personas (see `docs/user-journeys/personas-and-journeys.md`).
2. Build a clickable prototype of the new navigation structure.
3. Conduct a card-sort exercise with representative users.
4. Implement breadcrumbs and cross-linking as a frontend sprint.
