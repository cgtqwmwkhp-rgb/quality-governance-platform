# Product clarity and user journeys (D01)

This document captures persona-level acceptance criteria, critical user journeys (CUJs), a feature completeness view by persona, and how feedback feeds the roadmap.

## Persona-based acceptance criteria

Each criterion is a testable outcome the platform must satisfy for that persona.

### Safety Manager

1. Can log, triage, and close incidents with a clear status model, audit trail, and tenant-safe visibility.
2. Can see overdue actions and high-severity open items on dashboards without exporting to spreadsheets.
3. Can link incidents to investigations, actions, and (where configured) standards or controls.
4. Receives or can subscribe to notifications for assignments, due dates, and escalations relevant to their sites.
5. Can produce evidence packs (exports/reports) suitable for regulator or customer review within defined retention rules.

### Quality Auditor

1. Can build or consume audit templates, run audits (including mobile-friendly execution where enabled), and record responses with evidence.
2. Findings are traceable to questions, runs, and corrective actions with consistent reference numbers.
3. Can complete an audit run and see scoring / pass-fail outcomes aligned to template rules.
4. Can filter and report audit history by template, site, date range, and outcome.
5. Permissions prevent cross-tenant data access and enforce segregation between draft and published templates where configured.

### Driver (field / operational)

1. Can complete vehicle checks, RTA-related workflows, or assigned field forms with minimal steps and clear validation errors.
2. Works on common mobile viewports with usable touch targets and offline-tolerant flows where the product supports them.
3. Can attach photos or files where the workflow allows, with visible upload progress and retry-safe behaviour.
4. Sees only the data and actions permitted by role and contract/site scope.
5. Receives confirmation of submission (reference, next steps) without exposing internal admin-only metadata.

### Compliance Officer

1. Can map activities to standards / controls and view compliance evidence across modules in one place where integrated.
2. Can demonstrate control effectiveness with traceable records (policies acknowledged, audits completed, actions closed).
3. Can monitor overdue compliance tasks, CAPAs, and audit actions with exportable audit trails.
4. Can administer or coordinate document/policy lifecycles with version and visibility rules respected.
5. Can trust that authentication, authorization, and tenant isolation enforce regulatory expectations for access control.

### Executive

1. Sees a concise IMS / governance dashboard: risk posture, incident trends, audit and complaint throughput, and open critical actions.
2. Can drill from summary tiles to filtered lists without needing deep module expertise.
3. Dashboards load within agreed performance targets under normal operating conditions.
4. Data reflects the same canonical records as operational users (no shadow reporting spreadsheets required for basics).
5. Can identify cross-site or cross-contract patterns when permissions and data model allow aggregation.

## Critical user journeys (CUJs)

| # | Journey | Entry point | Steps (summary) | Expected outcome | Success metric |
|---|---------|-------------|-----------------|------------------|----------------|
| 1 | Report workplace incident | Incidents list or “New incident” | Capture details → validate → submit → receive reference | Incident stored with reference, visible to authorized users | Create success rate; time-to-submit p95 |
| 2 | Investigate and close incident | Incident detail | Assign → update status → add actions/evidence → close with reason | Closed incident with complete trail | % closed within target SLA; reopen rate |
| 3 | Plan and execute audit | Audits / template library | Select template → create run → answer questions → complete run | Completed run with score and findings as configured | Run completion rate; findings per run |
| 4 | Raise and close CAPA | Actions / CAPA | Create CAPA → transition states → verify → close | Closed CAPA linked to source where applicable | CAPA cycle time; overdue CAPA count |
| 5 | Handle customer complaint | Complaints | Intake → acknowledge → investigate → resolve → close | Closed complaint with communications trail | Time-to-acknowledge; reopen rate |
| 6 | Register and treat risk | Risks / risk register | Create/update risk → assess → treatments → review dates | Risk record reflects current residual score and ownership | Overdue reviews; risks outside appetite |
| 7 | RTA / fleet event | RTAs or driver portal | Capture collision details → supporting evidence → submit | RTA record created with correct permissions | Submission success; data completeness |
| 8 | Vehicle safety check | Vehicle checklists | Open checklist → complete items → sign/submit | Checklist stored; defects flagged if configured | Completion rate; defect follow-up rate |
| 9 | Policy acknowledgement | Policies / employee portal | View policy → acknowledge → record stored | Acknowledgement auditable per user/version | Acknowledgement coverage % |
| 10 | Executive review | IMS / analytics dashboards | Open dashboard → filter period/site → drill to detail | Accurate aggregates with drill-through | Dashboard engagement; error rate on aggregates |

## Feature completeness matrix

Status legend: **Complete** (shipped and used in primary flows), **Partial** (exists but gaps for persona), **Planned** (on roadmap or not yet persona-ready).

| Feature area | Safety Manager | Quality Auditor | Driver | Compliance Officer | Executive |
|--------------|----------------|-----------------|--------|-------------------|-----------|
| Incidents & investigations | Complete | Partial | Partial | Complete | Partial |
| Audits & inspections | Partial | Complete | Partial | Complete | Partial |
| Risk register / KRIs | Complete | Partial | Planned | Complete | Complete |
| CAPA / actions | Complete | Complete | Planned | Complete | Partial |
| Complaints | Partial | Planned | Planned | Complete | Partial |
| Documents & policies | Partial | Partial | Planned | Complete | Partial |
| Standards / compliance mapping | Partial | Complete | Planned | Complete | Partial |
| RTAs & fleet / vehicle checks | Complete | Planned | Complete | Partial | Partial |
| Workforce / competency (where enabled) | Partial | Partial | Partial | Partial | Partial |
| Notifications | Complete | Complete | Partial | Complete | Partial |
| Reporting & exports | Partial | Partial | Planned | Complete | Complete |
| Admin / forms / contracts | Partial | Partial | Planned | Partial | Planned |

## User feedback loop

1. **Capture**: Structured feedback via support tickets, customer success interviews, in-app feedback (where enabled), and telemetry summaries (non-PII) for friction points.
2. **Triage**: Product and engineering review weekly; classify as defect, usability, regulatory, or enhancement; link to module and severity.
3. **Prioritize**: Score against risk, regulatory exposure, customer commitments, and strategic themes (IMS unification, mobile, automation).
4. **Commit**: Approved items become roadmap themes and versioned milestones; ADRs updated when architectural impact.
5. **Verify**: Acceptance against persona criteria and CUJs; regression checks on permissions, audit trail, and exports.
6. **Communicate**: Release notes and customer-facing summaries for material behaviour or compliance-relevant changes.
