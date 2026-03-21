# Quality Governance Platform — Product Roadmap

**Owner**: Product & Platform Engineering
**Last Updated**: 2026-03-20
**Review Cycle**: Monthly (SLT review)

---

## Vision

A single-pane governance platform for Plantexpand that unifies safety incidents,
vehicle management, quality audits, risk registers, compliance tracking, and
operational governance — enabling data-driven decisions and regulatory readiness.

---

## Current State (v1.0 / v2.0 Frontend)

### Delivered Capabilities

| Module | Status | User Journey |
|--------|--------|-------------|
| Incident Management | Live | P1 Field Reporter → P2 Quality Auditor |
| Complaint Management | Live | P1 Field Reporter → P2 Quality Auditor |
| RTA (Road Traffic Collision) | Live | P1 → P2 (tabbed detail: vehicles, drivers, witnesses, photos, running sheet) |
| Near Miss Reporting | Live | P1 Field Reporter |
| Risk Register | Live | P3 Risk Manager |
| Audit Templates & Runs | Live | P2 Quality Auditor |
| Compliance Standards | Live | P3 Risk Manager |
| CAPA (Corrective Actions) | Live | P2 Quality Auditor |
| Policy Management | Live | P3 Risk Manager |
| Vehicle Checklists (PAMS) | Live | P1 Field Reporter → fleet integration |
| Driver Profiles & Acknowledgements | Live | P1 → allocation sign-off |
| Employee Portal | Live | P1 Field Reporter (mobile) |
| GDPR (Export / Erasure) | Live | P4 System Admin |
| AI Copilot | Live (beta) | P2 / P3 (PII-stripped summaries) |
| Audit Trail | Live | P4 System Admin → P5 Executive |
| Evidence Assets | Live | All personas (photo/document upload) |

### Key Personas (from `docs/user-journeys/personas-and-journeys.md`)

- **P1** Field Reporter — mobile-first incident/near-miss/RTA reporting
- **P2** Quality Auditor — audit execution, findings, CAPA
- **P3** Risk Manager — risk register, compliance, policy oversight
- **P4** System Admin — user management, config, GDPR
- **P5** Executive / Board — dashboards, KPIs, governance assurance

---

## Roadmap (Prioritised by User Journey Impact)

### Q2 2026 — Operational Excellence

| # | Feature | Persona | Journey | Priority |
|---|---------|---------|---------|----------|
| R01 | Executive Dashboard with KPI tiles | P5 | Board reporting | High |
| R02 | Automated retention policies (GDPR Art. 5) | P4 | Data lifecycle | High |
| R03 | Multi-locale support (Welsh, Polish) | P1 | Accessibility | Medium |
| R04 | Storybook component library | P4 (dev) | UX consistency | Medium |
| R05 | Load test baseline (Locust CI gate) | P4 (dev) | Reliability | Medium |

### Q3 2026 — Intelligence & Integration

| # | Feature | Persona | Journey | Priority |
|---|---------|---------|---------|----------|
| R06 | Trend analysis (incidents by category/site/month) | P3, P5 | Data-driven risk | High |
| R07 | Email notifications (incident assignment, overdue actions) | P2 | Workflow efficiency | High |
| R08 | PAMS two-way sync (write-back defect status) | P1 | Fleet governance | Medium |
| R09 | Mobile PWA offline support | P1 | Field reliability | Medium |
| R10 | External pentest + remediation | P4 | Security assurance | Medium |

### Q4 2026 — Scale & Compliance

| # | Feature | Persona | Journey | Priority |
|---|---------|---------|---------|----------|
| R11 | Multi-tenant onboarding wizard | P4 | Scale | High |
| R12 | Scheduled audit recurrence | P2 | Audit efficiency | High |
| R13 | ISO 27001 evidence auto-mapping | P3 | Compliance readiness | Medium |
| R14 | Canary/blue-green deployment | P4 (dev) | Release safety | Medium |
| R15 | Cost attribution per tenant | P5 | FinOps | Low |

### 2027 H1 — World-Class

| # | Feature | Persona | Journey | Priority |
|---|---------|---------|---------|----------|
| R16 | SLO alerting integration (PagerDuty/Teams) | P4 | Operational resilience | High |
| R17 | DSAR self-service portal | P4 | GDPR maturity | Medium |
| R18 | Accessibility audit (external WCAG 2.2 AA) | All | Inclusivity | Medium |
| R19 | Federated identity (SAML/OIDC beyond Azure AD) | P4 | Enterprise scale | Low |
| R20 | API v2 (GraphQL layer) | P4 (dev) | Developer experience | Low |

---

## Mapping to Scorecard Gaps

| Roadmap Item | Scorecard Gap | Dimension |
|-------------|---------------|-----------|
| R01 | Product clarity (no exec dashboard) | D01 |
| R02 | Privacy (retention not automated) | D07 |
| R03 | I18n (single locale) | D27 |
| R04 | UX (no Storybook) | D02 |
| R05 | Performance (no load test CI) | D04 |
| R06 | Analytics (limited feature instrumentation) | D28 |
| R10 | Security (no external pentest) | D06 |
| R14 | CD (no canary/blue-green) | D18 |
| R15 | Cost (no per-tenant attribution) | D26 |
| R16 | Runbooks (no alerting integration) | D23 |
| R17 | Privacy (DSAR self-service) | D07 |
| R18 | Accessibility (external audit) | D03 |
