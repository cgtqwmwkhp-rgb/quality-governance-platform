# User Personas & Journey Maps

**Last Updated**: 2026-03-07
**Review Cycle**: Quarterly

---

## Personas

### P1: Field Reporter (Incident Reporter)
- **Role**: Field worker, site supervisor, driver, operative
- **Goals**: Report incidents/near-misses quickly from mobile; track what happened to their report; comply with site safety requirements
- **Frustrations**: Complex forms that take too long; not knowing if their report was received; having to re-enter information they already provided
- **Tech Comfort**: Low-Medium — uses mobile phone daily but not a power user
- **Access Pattern**: Portal (anonymous/SSO) via mobile browser; occasional desktop
- **Key Modules**: Employee Portal (incident/near-miss/complaint/RTA forms), report tracking

### P2: Quality Auditor
- **Role**: Internal auditor, quality manager, compliance officer
- **Goals**: Plan and execute audits efficiently; capture findings with evidence; generate CAPA from non-conformances; produce audit reports for management review
- **Frustrations**: Template setup is time-consuming; offline auditing on-site; keeping track of finding status across multiple audits
- **Tech Comfort**: Medium — comfortable with business applications and spreadsheets
- **Access Pattern**: Desktop primary; tablet for on-site audits; needs offline capability
- **Key Modules**: Audit Templates, Audit Runs, Findings, CAPA, Standards Library, Compliance

### P3: Risk Manager
- **Role**: Enterprise risk manager, HSEQ director, operations manager
- **Goals**: Maintain enterprise risk register; monitor key risk indicators; produce risk reports for board; ensure controls are effective; identify emerging risks
- **Frustrations**: Risk data scattered across spreadsheets; no real-time visibility of risk posture; manual calculation of residual risk scores
- **Tech Comfort**: Medium-High — uses dashboards, analytics, and BI tools
- **Access Pattern**: Desktop; executive dashboard; scheduled reports
- **Key Modules**: Enterprise Risk Register, KRI Dashboard, Bow-Tie Analysis, Risk Heatmap, Analytics

### P4: System Administrator
- **Role**: IT admin, platform administrator, HSEQ system owner
- **Goals**: Configure the platform for their organisation; manage users and roles; set up forms and workflows; ensure data integrity and audit compliance
- **Frustrations**: Changes requiring developer involvement; understanding impact of configuration changes; managing user permissions across modules
- **Tech Comfort**: High — comfortable with admin interfaces, APIs, and configuration
- **Access Pattern**: Desktop; admin panel; occasional API access
- **Key Modules**: User Management, Form Builder, System Settings, Lookup Tables, Tenancy, Audit Trail

### P5: Executive / Board Member
- **Role**: CEO, COO, board member, HSEQ director
- **Goals**: Understand compliance posture at a glance; see trend data for incidents, risks, audit findings; make decisions on resource allocation; demonstrate governance to external auditors
- **Frustrations**: Too much detail; data not actionable; reports that don't tell a story
- **Tech Comfort**: Low-Medium — wants clear dashboards, not complex interfaces
- **Access Pattern**: Desktop/tablet; dashboard-only; weekly/monthly frequency
- **Key Modules**: Executive Dashboard, Analytics, Compliance Reports, Management Review

---

## Journey Maps

### Journey 1: Incident Reporting (P1 — Field Reporter)

```
TRIGGER: Workplace incident occurs on site
     │
     ▼
[1. ACCESS PORTAL]                          ← Mobile browser, no login required
     │ Pain: Finding the correct URL
     │ Opportunity: QR codes on site; bookmark/PWA
     ▼
[2. SELECT REPORT TYPE]                     ← Incident / Near Miss / Complaint / RTA
     │ Pain: Not sure which category to choose
     │ Opportunity: Plain language descriptions; "not sure" option with triage
     ▼
[3. FILL INCIDENT FORM]                    ← Date, location, description, severity
     │ Pain: Form too long on mobile; losing progress
     │ Opportunity: Auto-save; progressive disclosure; GPS auto-fill location
     ▼
[4. ATTACH EVIDENCE]                       ← Photos from phone camera
     │ Pain: Photo quality; file size limits
     │ Opportunity: In-app camera; compression; multiple file upload
     ▼
[5. SUBMIT REPORT]                         ← Confirmation screen
     │ Pain: "Did it actually submit?"
     │ Opportunity: Clear success message with reference number; email/SMS confirmation
     ▼
[6. RECEIVE REFERENCE NUMBER]              ← INC-2026-0042
     │
     ▼
[7. TRACK STATUS]                          ← Portal status page
     │ Pain: No visibility after submission
     │ Opportunity: Status updates via push/email; timeline view
     ▼
[8. NOTIFIED OF RESOLUTION]               ← Email notification
     │ Opportunity: Feedback request; "was this resolved satisfactorily?"
```

**Critical Moments**: Steps 3 (form completion) and 5 (submission confidence) are highest drop-off risk.
**Metrics to Track**: Form start-to-submit time; abandonment rate at each step; mobile vs desktop ratio.

---

### Journey 2: Audit Lifecycle (P2 — Quality Auditor)

```
TRIGGER: Scheduled audit due or management request
     │
     ▼
[1. SELECT/CREATE TEMPLATE]                ← From template library
     │ Pain: Finding the right template; customising for specific audit
     │ Opportunity: Template search; clone and modify; AI-suggested questions
     ▼
[2. CONFIGURE AUDIT RUN]                   ← Assign auditor, date, scope, auditee
     │ Pain: Scheduling conflicts; scope definition
     │ Opportunity: Calendar integration; scope wizard; auto-assign based on competence
     ▼
[3. EXECUTE AUDIT (ON-SITE)]              ← Go through questions, capture responses
     │ Pain: Offline environments; slow loading; switching between sections
     │ Opportunity: Offline mode with sync; section navigation; evidence photo capture
     ▼
[4. RECORD FINDINGS]                       ← Non-conformances, observations, good practices
     │ Pain: Describing findings clearly; linking to correct ISO clause
     │ Opportunity: Auto-tag ISO clauses; finding templates; severity guidance
     ▼
[5. COMPLETE AUDIT]                        ← Score calculation; summary generation
     │ Pain: Manual score calculation; forgetting to complete sections
     │ Opportunity: Auto-score; completeness check; section progress indicator
     ▼
[6. RAISE CAPA FROM FINDINGS]             ← Corrective/preventive actions
     │ Pain: CAPA creation is separate from finding context
     │ Opportunity: One-click CAPA from finding; pre-populated description
     ▼
[7. GENERATE AUDIT REPORT]                ← PDF/HTML report for management
     │ Pain: Report formatting; missing context
     │ Opportunity: Auto-generated report with findings, evidence, scores; export options
     ▼
[8. TRACK CAPA TO CLOSURE]               ← Monitor actions through to verification
     │ Pain: CAPA tracking across multiple audits; overdue reminders
     │ Opportunity: CAPA dashboard; automated reminders; effectiveness review prompts
```

**Critical Moments**: Step 3 (on-site execution) and Step 6 (finding-to-CAPA flow).
**Metrics to Track**: Audit completion time; CAPA closure rate; average time from finding to CAPA closure.

---

### Journey 3: Risk Assessment (P3 — Risk Manager)

```
TRIGGER: New risk identified or periodic risk review
     │
     ▼
[1. IDENTIFY RISK]                         ← Create new risk entry
     │ Pain: Categorisation uncertainty; duplicate risks
     │ Opportunity: AI-suggested categories; duplicate detection; risk library
     ▼
[2. ASSESS INHERENT RISK]                  ← Likelihood x Impact (5x5 matrix)
     │ Pain: Subjective scoring; inconsistent criteria
     │ Opportunity: Scoring guidance with examples; calibration workshops reference
     ▼
[3. DEFINE CONTROLS]                       ← Existing controls that mitigate the risk
     │ Pain: Control effectiveness is hard to quantify
     │ Opportunity: Control effectiveness ratings; link to audit evidence; control testing schedule
     ▼
[4. ASSESS RESIDUAL RISK]                  ← Post-control risk score
     │ Pain: Forgetting to re-assess after control changes
     │ Opportunity: Auto-prompt for reassessment; trend visualisation
     ▼
[5. SET RISK APPETITE]                     ← Compare residual to acceptable threshold
     │ Pain: Risk appetite not defined or not accessible
     │ Opportunity: Visual threshold on heatmap; appetite statement per category
     ▼
[6. MONITOR KRIs]                          ← Key Risk Indicators with RAG thresholds
     │ Pain: Manual data collection; stale indicators
     │ Opportunity: Automated KRI feeds; traffic-light dashboard; alert on threshold breach
     ▼
[7. REPORT TO BOARD]                       ← Risk heatmap, trends, top 10 risks
     │ Pain: Creating board-ready reports is manual
     │ Opportunity: One-click executive report; trend analysis; bow-tie visualisation
     ▼
[8. REVIEW & UPDATE CYCLE]                ← Quarterly/annual risk review
     │ Opportunity: Review scheduler; assessment history comparison; effectiveness tracking
```

**Critical Moments**: Step 2 (assessment consistency) and Step 6 (KRI monitoring).
**Metrics to Track**: Risk register completeness; KRI breach frequency; time from risk identification to control implementation.

---

### Journey 4: System Configuration (P4 — Administrator)

```
TRIGGER: New module deployment, organisational change, or user request
     │
     ▼
[1. ACCESS ADMIN PANEL]                    ← Protected by RequireRole
     │ Pain: Finding the right setting
     │ Opportunity: Admin search; recently changed settings; change impact preview
     ▼
[2. MANAGE USERS & ROLES]                  ← Create users, assign roles, manage permissions
     │ Pain: Understanding permission impact; bulk user operations
     │ Opportunity: Role preview ("what can this role do?"); bulk import; Azure AD sync
     ▼
[3. CONFIGURE FORMS]                       ← Form Builder for incident/complaint/RTA forms
     │ Pain: Complex conditional logic; preview vs live differences
     │ Opportunity: Visual form builder; live preview; version comparison
     ▼
[4. SET UP LOOKUP TABLES]                  ← Departments, locations, categories, severity levels
     │ Pain: Cascading impacts of changes; missing values
     │ Opportunity: Impact analysis ("used by N records"); import/export
     ▼
[5. CONFIGURE WORKFLOWS]                   ← Approval chains, escalation rules, SLA timers
     │ Pain: Complex routing logic; testing workflows
     │ Opportunity: Visual workflow builder; test mode; audit log of workflow changes
     ▼
[6. MANAGE TENANCY]                        ← Branding, features, user limits (if multi-tenant)
     │ Pain: Understanding tenant isolation boundaries
     │ Opportunity: Tenant health dashboard; feature flag management; usage analytics
     ▼
[7. REVIEW AUDIT TRAIL]                    ← Who changed what, when
     │ Pain: Finding specific changes in large audit trail
     │ Opportunity: Filter by user/entity/date; export; hash-chain verification
     ▼
[8. MONITOR SYSTEM HEALTH]                ← Health checks, error rates, performance
     │ Opportunity: Admin dashboard; system status page; scheduled maintenance calendar
```

**Critical Moments**: Step 3 (form configuration) and Step 5 (workflow setup).
**Metrics to Track**: Time to onboard new user; admin task completion rate; configuration error rate.

---

### Journey 5: Executive Oversight (P5 — Executive / Board Member)

```
TRIGGER: Board meeting preparation, management review, external audit
     │
     ▼
[1. OPEN EXECUTIVE DASHBOARD]              ← Landing page with KPIs
     │ Pain: Dashboard doesn't show what I need; too much data
     │ Opportunity: Personalised dashboard; role-based default views
     ▼
[2. REVIEW COMPLIANCE POSTURE]             ← ISO gap analysis, coverage percentage
     │ Pain: Not sure what the numbers mean in practical terms
     │ Opportunity: RAG summary; natural language insights; trend vs target
     ▼
[3. REVIEW INCIDENT TRENDS]               ← Incident count, severity distribution, RIDDOR stats
     │ Pain: Can't compare across periods; no context
     │ Opportunity: Period comparison (vs last quarter); industry benchmarks; AI commentary
     ▼
[4. REVIEW RISK POSTURE]                   ← Top 10 risks, heatmap, risk appetite alignment
     │ Pain: Static snapshot; no sense of trajectory
     │ Opportunity: Risk movement arrows; forecast; treatment effectiveness scores
     ▼
[5. REVIEW AUDIT RESULTS]                  ← Audit scores, finding trends, CAPA status
     │ Pain: Audit scores not comparable across templates
     │ Opportunity: Normalised scoring; maturity trends; overdue CAPA highlighting
     ▼
[6. GENERATE BOARD REPORT]                 ← One-click report generation
     │ Pain: Report doesn't match board template/expectations
     │ Opportunity: Customisable report templates; branded PDF export; executive summary
     ▼
[7. APPROVE/DELEGATE ACTIONS]             ← Sign off on management review items
     │ Pain: Context switching to approve/delegate
     │ Opportunity: In-dashboard action buttons; delegation with notes
```

**Critical Moments**: Step 1 (first impression) and Step 6 (board report generation).
**Metrics to Track**: Dashboard time-on-page; report generation frequency; action approval latency.

---

## Priority Matrix (Journey Step × Improvement Impact)

| Priority | Journey | Step | Improvement | Impact |
|----------|---------|------|-------------|--------|
| 1 | J1 (Incident) | 3 | Progressive disclosure + auto-save on mobile | HIGH — reduces abandonment |
| 2 | J2 (Audit) | 3 | Offline mode for on-site execution | HIGH — unblocks field auditors |
| 3 | J1 (Incident) | 5 | Clear confirmation with reference number | HIGH — builds trust |
| 4 | J3 (Risk) | 6 | KRI traffic-light dashboard | HIGH — enables proactive risk management |
| 5 | J5 (Executive) | 1 | Role-based default dashboard | MEDIUM — executive adoption |
| 6 | J2 (Audit) | 6 | One-click CAPA from finding | MEDIUM — reduces friction |
| 7 | J4 (Admin) | 3 | Visual form builder with preview | MEDIUM — admin efficiency |
| 8 | J5 (Executive) | 6 | One-click board report | MEDIUM — executive satisfaction |
| 9 | J3 (Risk) | 2 | Scoring guidance with examples | MEDIUM — assessment consistency |
| 10 | J1 (Incident) | 7 | Status updates via push/email | MEDIUM — reporter engagement |
