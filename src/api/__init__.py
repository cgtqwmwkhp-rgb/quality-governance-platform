"""API module - FastAPI routes and endpoints."""

from fastapi import APIRouter

from src.api.routes import (
    actions,
    ai_intelligence,
    analytics,
    audit_trail,
    auditor_competence,
    audits,
    auth,
    capa,
    complaints,
    compliance,
    compliance_automation,
    copilot,
    cross_standard_mappings,
    dlq_admin,
    document_control,
    documents,
    employee_portal,
    evidence_assets,
    executive_dashboard,
    form_config,
    gdpr,
    global_search,
    health,
    ims_dashboard,
    incidents,
    investigation_templates,
    investigations,
    iso27001,
    kri,
    near_miss,
    notifications,
    planet_mark,
    policies,
    policy_acknowledgment,
    rca_tools,
    realtime,
    risk_register,
    risks,
    rtas,
    signatures,
    slo,
    standards,
    telemetry,
    tenants,
    testing,
    users,
    uvdb,
    workflow,
    workflows,
)

router = APIRouter()

# Include all route modules
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(standards.router, prefix="/standards", tags=["Standards Library"])
router.include_router(audits.router, prefix="/audits", tags=["Audits & Inspections"])
router.include_router(risks.router, prefix="/risks", tags=["Risk Register"])
router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
router.include_router(actions.router, prefix="/actions", tags=["Actions"])
router.include_router(rtas.router, prefix="/rtas", tags=["Road Traffic Collisions"])
router.include_router(
    investigation_templates.router,
    prefix="/investigation-templates",
    tags=["Investigations"],
)
router.include_router(investigations.router, prefix="/investigations", tags=["Investigations"])
router.include_router(capa.router, prefix="/capa", tags=["CAPA"])
router.include_router(complaints.router, prefix="/complaints", tags=["Complaints"])
router.include_router(policies.router, prefix="/policies", tags=["Policy Library"])
router.include_router(documents.router, prefix="/documents", tags=["Document Library"])
router.include_router(employee_portal.router, prefix="/portal", tags=["Employee Portal"])
router.include_router(compliance.router, prefix="/compliance", tags=["ISO Compliance & Evidence"])
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
router.include_router(realtime.router, prefix="/realtime", tags=["Real-Time & WebSocket"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & Reporting"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflow Automation"])
router.include_router(
    compliance_automation.router,
    prefix="/compliance-automation",
    tags=["Compliance Automation"],
)
# Enterprise Risk Register & AI Intelligence (Tier 1 & 2)
router.include_router(risk_register.router, prefix="/risk-register", tags=["Enterprise Risk Register"])
router.include_router(ai_intelligence.router, prefix="/ai", tags=["AI Intelligence"])
router.include_router(
    document_control.router,
    prefix="/document-control",
    tags=["Document Control System"],
)
# ISO 27001 Information Security Management System
router.include_router(iso27001.router, prefix="/iso27001", tags=["ISO 27001 ISMS"])
# UVDB Achilles Verify B2 Audit Protocol
router.include_router(uvdb.router, prefix="/uvdb", tags=["UVDB Achilles Verify"])
# Planet Mark Carbon Management
router.include_router(planet_mark.router, prefix="/planet-mark", tags=["Planet Mark Carbon"])
# IMS (Integrated Management System) Dashboard
router.include_router(ims_dashboard.router, tags=["IMS Dashboard"])
# Cross-Standard ISO Mappings
router.include_router(
    cross_standard_mappings.router,
    prefix="/cross-standard-mappings",
    tags=["Cross-Standard Mappings"],
)
# AI Copilot (Tier 2)
router.include_router(copilot.router, prefix="/copilot", tags=["AI Copilot"])
# Digital Signatures (Tier 2)
router.include_router(signatures.router, prefix="/signatures", tags=["Digital Signatures"])
# Multi-tenancy (Tier 1)
router.include_router(tenants.router, prefix="/tenants", tags=["Multi-Tenancy"])
# Immutable Audit Trail (Tier 1)
router.include_router(audit_trail.router, prefix="/audit-trail", tags=["Audit Trail"])
# GDPR Compliance (Right of Access & Right to Erasure)
router.include_router(gdpr.router, tags=["GDPR"])
# Admin Form Builder & Configuration
router.include_router(form_config.router, prefix="/admin/config", tags=["Admin Configuration"])
# Near Misses
router.include_router(near_miss.router, prefix="/near-misses", tags=["Near Misses"])
# Evidence Assets (Shared Attachments Module)
router.include_router(evidence_assets.router, prefix="/evidence-assets", tags=["Evidence Assets"])
# Workflow Engine (SLA, Escalation, Automation)
router.include_router(workflow.router, tags=["Workflow Engine"])
# Key Risk Indicators & SIF Classification
router.include_router(kri.router, tags=["Key Risk Indicators"])
# Policy Acknowledgments & Document Read Tracking
router.include_router(policy_acknowledgment.router, tags=["Policy Acknowledgments"])
# Executive Dashboard
router.include_router(executive_dashboard.router, tags=["Executive Dashboard"])
# RCA Tools (5-Whys, Fishbone, CAPA)
router.include_router(rca_tools.router, tags=["RCA Tools"])
# Auditor Competence Management
router.include_router(auditor_competence.router, tags=["Auditor Competence"])
# Global Search
router.include_router(global_search.router, prefix="/search", tags=["Global Search"])
# CI Testing Endpoints (Staging Only)
router.include_router(testing.router, prefix="/testing", tags=["Testing (Staging Only)"])
# Telemetry (EXP-001 and future experiments)
router.include_router(telemetry.router, tags=["Telemetry"])
# SLO/SLI Observability
router.include_router(slo.router, tags=["SLO Metrics"])
# Health sub-routes (circuit breakers)
router.include_router(health.router, tags=["Health"])
# DLQ Admin
router.include_router(dlq_admin.router, tags=["Admin"])

__all__ = ["router"]
