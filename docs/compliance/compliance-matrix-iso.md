# ISO Compliance Matrix — QGP

**Platform:** Quality Governance Platform (QGP)  
**Version:** 1.0  
**Standards:** ISO 9001:2015, ISO 45001:2018, ISO 14001:2015

This matrix maps major QGP capabilities to standard clauses and lists **evidence artifact paths** in this repository. It is a **living document**; clause wording is abbreviated — refer to the published standards for authoritative text.

---

## 1. ISO 9001:2015 — Quality management

| Clause | Summary | QGP feature / module | Primary evidence (repo paths) |
| --- | --- | --- | --- |
| **4.1** | Context of the organisation | Standards library, compliance dashboards, document/policy libraries | `src/api/routes/compliance.py`, `src/domain/services/governance_service.py`, `docs/evidence/` |
| **4.2** | Interested parties | Complaints, notifications, policy acknowledgments | `src/api/routes/complaints.py`, `src/api/routes/policy_acknowledgment.py` |
| **4.3** | Scope of QMS | IMS description in app metadata / OpenAPI | `src/main.py`, `openapi-baseline.json` (if present) |
| **4.4** | QMS and processes | Workflow engine, CAPA, actions | `src/services/workflow_engine.py`, `src/api/routes/actions.py`, `src/api/routes/capa.py` |
| **5.1–5.3** | Leadership, policy, roles | Policy library, RBAC/ABAC, admin routes | `src/api/routes/policy_*.py`, `src/domain/models/permissions.py`, `src/domain/services/abac_service.py` |
| **6.1–6.3** | Planning, risks, resources | Risk register, audits, competence | `src/api/routes/risk_register.py`, `src/api/routes/audits.py`, `src/api/routes/auditor_competence.py` |
| **7.1–7.5** | Support (resources, competence, awareness, documented information) | Document control, training/competence hooks, attachments | `src/api/routes/document_control.py`, `src/api/routes/auditor_competence.py` |
| **8.1** | Operational planning and control | Incident / complaint / audit lifecycles | `src/api/routes/incidents.py`, `src/api/routes/complaints.py`, `src/api/routes/audits.py` |
| **8.2** | Requirements for products and services | Contract / requirement traceability via documents & compliance links | `src/api/routes/document_control.py`, `src/api/routes/compliance.py` |
| **8.3** | Design and development of products and services | **Partial** — QGP document control module provides version-controlled document lifecycle; formal PLM/ALM design controls are out of scope as QGP is a governance/compliance platform, not a product design tool | See §5 |
| **8.4** | Control of externally provided processes | Supplier / UVDB-style integrations (where enabled) | `src/api/routes/uvdb.py` |
| **8.5** | Production and service provision | Operational checklists, vehicle checks, workflows | `src/api/routes/vehicle_checklists.py`, `src/services/workflow_engine.py` |
| **8.6** | Release of products and services | Approvals / signatures (where configured) | `src/api/routes/signatures.py` |
| **8.7** | Control of nonconforming outputs | Incidents, CAPA, complaints, investigations | `src/api/routes/incidents.py`, `src/api/routes/capa.py`, `src/api/routes/investigation_templates.py` |
| **9.1** | Monitoring, measurement, analysis | Analytics, KPIs, dashboards | `src/api/routes/` (analytics-related modules), `frontend/` dashboards |
| **9.2** | Internal audit | Audit templates, runs, findings | `src/api/routes/audit_templates.py`, `src/api/routes/audits.py` |
| **9.3** | Management review | Executive / IMS summaries (via reporting) | `src/domain/services/ims_dashboard_service.py`, reporting routes |
| **10.1–10.3** | Improvement, nonconformity, continual improvement | CAPA, RCA, near misses, trend analytics | `src/api/routes/capa.py`, `src/api/routes/rca_tools.py`, `src/api/routes/near_miss.py` |

---

## 2. ISO 45001:2018 — Occupational health and safety

| Clause | Summary | QGP feature / module | Primary evidence (repo paths) |
| --- | --- | --- | --- |
| **4.1–4.2** | Context, workers / interested parties | Portal workflows, complaints, notifications | `tests/uat/`, `src/api/routes/complaints.py`, `src/api/routes/notifications.py` |
| **5.1–5.4** | Leadership and worker participation | Policy acknowledgments, roles | `src/api/routes/policy_acknowledgment.py`, `src/domain/models/permissions.py` |
| **6.1.1–6.1.4** | OH&S risks, legal requirements, planning | Risk register, compliance mapping, incidents | `src/api/routes/risk_register.py`, `src/api/routes/compliance.py`, `src/api/routes/incidents.py` |
| **7.1–7.5** | Support (resources, competence, awareness, communication, documented information) | Documents, competence, push / in-app notifications | `src/api/routes/document_control.py`, `src/api/routes/auditor_competence.py`, `src/api/routes/push_notifications.py` |
| **8.1** | Operational planning and control | Safe systems of work via checklists and workflows | `src/api/routes/vehicle_checklists.py`, `src/services/workflow_engine.py` |
| **8.2** | Emergency preparedness | **Partial** — incident / RTA reporting supports response evidence | `src/api/routes/incidents.py`, RTA routes under `src/api/routes/` (e.g. collision modules), `tests/smoke/` |
| **9.1** | Performance evaluation | OH&S KPIs via analytics | Reporting / dashboard services |
| **9.2** | Internal audit | Audits & inspections | `src/api/routes/audits.py`, `src/api/routes/audit_templates.py` |
| **9.3** | Management review | IMS dashboard / governance summaries | `src/domain/services/ims_dashboard_service.py` |
| **10.1–10.3** | Incidents, nonconformity, continual improvement | Incidents, near misses, RTAs, CAPA, investigations | `src/api/routes/incidents.py`, `src/api/routes/near_miss.py`, `src/domain/services/rta_service.py`, `src/api/routes/capa.py`, `src/api/routes/investigation_templates.py` |

---

## 3. ISO 14001:2015 — Environmental management

| Clause | Summary | QGP feature / module | Primary evidence (repo paths) |
| --- | --- | --- | --- |
| **4.1–4.2** | Context, compliance obligations | Compliance automation, standards linkage | `src/api/routes/compliance.py`, `src/api/routes/compliance_automation.py` |
| **5.1–5.3** | Leadership, policy, roles | Policy library, ABAC | `src/api/routes/policy_*.py`, `src/domain/services/abac_service.py` |
| **6.1** | Risks and opportunities | Risk register, environmental aspects when modelled as risks | `src/api/routes/risk_register.py` |
| **7.1–7.5** | Support | Documented information, training hooks | `src/api/routes/document_control.py` |
| **8.1** | Operational planning and control | **PlanetMark / environmental programme** features | `src/api/routes/planet_mark.py`, `src/domain/services/planet_mark_service.py` |
| **8.2** | Emergency preparedness | Incident / spill-style events via incident module (config-dependent) | `src/api/routes/incidents.py` |
| **9.1** | Monitoring and measurement | Environmental KPIs if exposed via PlanetMark / analytics | `src/api/routes/planet_mark.py`, analytics routes |
| **9.2** | Internal audit | Audits module (EMS audits as templates) | `src/api/routes/audits.py` |
| **9.3** | Management review | Governance dashboards | `src/domain/services/ims_dashboard_service.py` |
| **10.1–10.2** | Nonconformity and corrective action | CAPA, complaints, incidents | `src/api/routes/capa.py`, `src/api/routes/complaints.py` |

---

## 4. Cross-cutting evidence artifacts

| Artifact | Path | Use |
| --- | --- | --- |
| CI quality & security gates | `.github/workflows/ci.yml` | Objective evidence of testing, SAST, dependency audit, secret scan |
| E2E / quality baseline | `docs/evidence/e2e_baseline.json` | Regression and baseline gate |
| Audit acceptance pack checklist | `scripts/governance/validate_audit_acceptance_pack.py` | Required governance documents |
| Runtime smoke / gates | `scripts/governance/runtime-smoke-gate.sh`, `tests/smoke/` | Operational verification |
| API contract stability | `scripts/check_openapi_compatibility.py`, `openapi-baseline.json` | Controlled API change |
| Security headers / TLS posture (app layer) | `src/main.py` (`SecurityHeadersMiddleware`) | Transport and browser security |
| Immutable audit model | `src/domain/models/audit_log.py`, `src/domain/services/audit_log_service.py` | Integrity and accountability |
| GDPR technical measures | `src/api/routes/gdpr.py`, `src/domain/services/gdpr_service.py` | Data subject rights |

---

## 5. Gap analysis and mitigation

| Gap | Standard area | Mitigation plan |
| --- | --- | --- |
| **ISO 9001 §8.3** (design & development) | Product / service design controls | Maintain design DMR in PLM or doc control *outside* QGP; link evidence URLs in QGP `document_control` / compliance records |
| **ISO 45001 §8.2** (emergency preparedness) | Full emergency response plans | Store plans and drill records as controlled documents; use notifications/workflows for escalation; optional integration with mass-notification tooling |
| **ISO 14001** aspects / compliance register depth | Environmental aspects inventory | Extend risk or compliance templates to tag environmental aspects; use `planet_mark` data model fields for KPIs |
| **On-site physical security** | All | QGP is software — physical controls evidenced via hosting provider & office security programmes |
| **Retention job implementation detail** | Records control | Implement explicit purge/archival in `cleanup_tasks.run_data_retention` with metrics and audit entries (see `docs/privacy/data-retention-policy.md`) |

---

## 6. Review

Review this matrix **annually** or when ISO certification scope changes.

**Last updated:** 2026-04-03
