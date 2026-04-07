# OpenAPI Route Group Audit

**Status**: Current  
**Date**: 2026-04-07  
**Source**: `src/api/__init__.py` — 66 `include_router` call sites  
**Base path**: All routes are prefixed with `/api/v1` via the top-level app mount  
**Assessed by**: World-Class Scorecard 2026-04-07 (EG-01 remediation)

---

## Summary

| Metric | Value |
|--------|-------|
| Total `include_router` registrations | 66 |
| Named route groups (distinct tags) | 56 |
| Routes with explicit prefix | 51 |
| Routes without prefix (tag-only) | 5 |
| Staging-only routes | 1 (`/testing`) |
| Auth model | Azure AD (Bearer JWT) via `src/api/dependencies/tenant.py` |
| API versioning ADR | ADR-0011 (`docs/adr/ADR-0011-api-versioning-strategy.md`) |

---

## Route Group Inventory

### Core Platform

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Authentication | `/auth` | `src/api/routes/auth.py` | Partial (login endpoints public) |
| Users | `/users` | `src/api/routes/users.py` | Yes |
| Multi-Tenancy | `/tenants` | `src/api/routes/tenants.py` | Yes (admin) |
| Feature Flags | `/feature-flags` | `src/api/routes/feature_flags.py` | Yes (admin) |
| Admin Configuration | `/admin/config` | `src/api/routes/form_config.py` | Yes (admin) |

### Quality & Compliance

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Audits & Inspections | `/audits` | `src/api/routes/audits.py` | Yes |
| Audit Template Builder | `/audit-templates` | `src/api/routes/audit_templates.py` | Yes |
| Audit Trail | `/audit-trail` | `src/api/routes/audit_trail.py` | Yes |
| Auditor Competence | *(no prefix)* | `src/api/routes/auditor_competence.py` | Yes |
| XML Template Import | `/xml-import` | `src/api/routes/xml_import.py` | Yes |
| Standards Library | `/standards` | `src/api/routes/standards.py` | Yes |
| ISO Compliance & Evidence | `/compliance` | `src/api/routes/compliance.py` | Yes |
| ISO 27001 ISMS | `/iso27001` | `src/api/routes/iso27001.py` | Yes |
| Compliance Automation | `/compliance-automation` | `src/api/routes/compliance_automation.py` | Yes |
| Cross-Standard Mappings | `/cross-standard-mappings` | `src/api/routes/cross_standard_mappings.py` | Yes |
| IMS Dashboard | *(no prefix)* | `src/api/routes/ims_dashboard.py` | Yes |
| Assessments | `/assessments` | `src/api/routes/assessments.py` | Yes |

### Risk & Incident Management

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Risk Register | `/risks` | `src/api/routes/risks.py` | Yes |
| Enterprise Risk Register | `/risk-register` | `src/api/routes/risk_register.py` | Yes |
| Key Risk Indicators | *(no prefix)* | `src/api/routes/kri.py` | Yes |
| Incidents | `/incidents` | `src/api/routes/incidents.py` | Yes |
| Near Misses | `/near-misses` | `src/api/routes/near_miss.py` | Yes |
| Complaints | `/complaints` | `src/api/routes/complaints.py` | Yes |
| Investigations | `/investigations` | `src/api/routes/investigations.py` | Yes |
| Investigation Templates | `/investigation-templates` | `src/api/routes/investigation_templates.py` | Yes |
| Road Traffic Collisions | `/rtas` | `src/api/routes/rtas.py` | Yes |
| CAPA | `/capa` | `src/api/routes/capa.py` | Yes |
| RCA Tools | *(no prefix)* | `src/api/routes/rca_tools.py` | Yes |
| Actions | `/actions` | `src/api/routes/actions.py` | Yes |

### Governance & Policy

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Policy Library | `/policies` | `src/api/routes/policies.py` | Yes |
| Policy Acknowledgments | *(no prefix)* | `src/api/routes/policy_acknowledgment.py` | Yes |
| Governance Framework | `/governance` | `src/api/routes/governance.py` | Yes |
| Document Library | `/documents` | `src/api/routes/documents.py` | Yes |
| Document Control System | `/document-control` | `src/api/routes/document_control.py` | Yes |
| Digital Signatures | `/signatures` | `src/api/routes/signatures.py` | Yes |
| Evidence Assets | `/evidence-assets` | `src/api/routes/evidence_assets.py` | Yes |

### Workforce & Operational

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Employee Portal | `/portal` | `src/api/routes/employee_portal.py` | Partial (anonymous submission supported) |
| Inductions | `/inductions` | `src/api/routes/inductions.py` | Yes |
| Engineers | `/engineers` | `src/api/routes/engineers.py` | Yes |
| Asset Registry | `/assets` | `src/api/routes/assets.py` | Yes |
| UVDB Achilles Verify | `/uvdb` | `src/api/routes/uvdb.py` | Yes |
| Workforce Analytics | `/wdp-analytics` | `src/api/routes/wdp_analytics.py` | Yes |

### Fleet & Transport

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Vehicle Checklists | `/vehicle-checklists` | `src/api/routes/vehicle_checklists.py` | Yes |
| Vehicle Checklist Analytics | `/vehicle-checklists/analytics` | `src/api/routes/vehicle_checklist_analytics.py` | Yes |
| Vehicles | `/vehicles` | `src/api/routes/vehicles.py` | Yes |
| Drivers | `/drivers` | `src/api/routes/drivers.py` | Yes |

### External Integrations & Imports

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| External Audit Imports | `/external-audit-imports` | `src/api/routes/external_audit_imports.py` | Yes |
| External Audit Records | `/external-audit-records` | `src/api/routes/external_audit_records.py` | Yes |
| XML Template Import | `/xml-import` | `src/api/routes/xml_import.py` | Yes |

### AI & Intelligence

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| AI Intelligence | `/ai` | `src/api/routes/ai_intelligence.py` | Yes |
| AI Copilot | `/copilot` | `src/api/routes/copilot.py` | Yes |
| AI Template Intelligence | `/ai-templates` | `src/api/routes/ai_templates.py` | Yes |

### Sustainability

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Planet Mark Carbon | `/planet-mark` | `src/api/routes/planet_mark.py` | Yes |

### Platform Infrastructure

| Tag | Prefix | Module | Auth Required |
|-----|--------|--------|---------------|
| Health | `/health` | `src/api/routes/health.py` | No |
| SLO Metrics | `/slo` | `src/api/routes/slo.py` | Yes |
| Telemetry | *(no prefix)* | `src/api/routes/telemetry.py` | Yes |
| Real-Time & WebSocket | `/realtime` | `src/api/routes/realtime.py` | Yes |
| Notifications | `/notifications` | `src/api/routes/notifications.py` | Yes |
| Push Notifications | `/notifications/push` | `src/api/routes/push_notifications.py` | Yes |
| Workflow Automation | `/workflows` | `src/api/routes/workflows.py` | Yes |
| Workflow Engine | *(no prefix)* | `src/api/routes/workflow.py` | Yes |
| Executive Dashboard | *(no prefix)* | `src/api/routes/executive_dashboard.py` | Yes |
| Analytics & Reporting | `/analytics` | `src/api/routes/analytics.py` | Yes |
| Global Search | `/search` | `src/api/routes/global_search.py` | Yes |
| DLQ Admin | *(no prefix)* | `src/api/routes/dlq_admin.py` | Yes (admin) |
| GDPR | *(no prefix)* | `src/api/routes/gdpr.py` | Yes |
| Auditor Competence | *(no prefix)* | `src/api/routes/auditor_competence.py` | Yes |

### Staging Only

| Tag | Prefix | Module | Auth Required | Guard |
|-----|--------|--------|---------------|-------|
| Testing (Staging Only) | `/testing` | `src/api/routes/testing.py` | Yes | `ENVIRONMENT != "production"` guard in `__init__.py` |

---

## Auth Model

All protected routes depend on:

- **Dependency**: `src/api/dependencies/tenant.py` — injects `TenantContext` from JWT
- **Token validation**: `src/core/azure_auth.py` / `src/core/azure_ad.py` — validates Azure AD Bearer tokens
- **ABAC**: `src/domain/services/abac_service.py` — attribute-based access control layered on top of JWT identity

Routes without authentication gates:
- `GET /api/v1/health/...` — public health/readiness probes
- `POST /api/v1/portal/...` — employee portal supports anonymous submission (confirmed `source_type='portal'` added in PR #491)

---

## OpenAPI Schema Location

The live interactive schema is served at:
- **Staging**: `https://<staging-app>.azurewebsites.net/docs` (Swagger UI)
- **Production**: `https://<prod-app>.azurewebsites.net/docs` (Swagger UI)
- **JSON schema**: `<base>/openapi.json`

> Note: The `/docs` and `/openapi.json` endpoints are exposed by FastAPI automatically from the registered routers. This audit document provides the human-readable inventory; the machine-readable source of truth is the live `/openapi.json` endpoint.

---

## Known Gaps & Follow-On Actions

| Gap | Detail | Owner |
|-----|--------|-------|
| Response schema audit | Auth requirements above marked "Yes" are inferred from dependency injection patterns, not individually verified per endpoint | Platform Team |
| Error model consistency | Not all routes have been verified for consistent `4xx`/`5xx` response shapes per ADR-0011 | Platform Team |
| Pagination audit | Not all list endpoints verified for cursor/offset pagination conformance | Platform Team |

---

## Change History

| Date | Change | Author |
|------|--------|--------|
| 2026-04-07 | Initial audit created (EG-01 remediation) | Automated assessment |
