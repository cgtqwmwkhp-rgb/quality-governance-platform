"""API module - FastAPI routes and endpoints."""

from fastapi import APIRouter

from src.api.routes import (
    ai_intelligence,
    analytics,
    audit_templates,
    audits,
    auth,
    complaints,
    compliance,
    compliance_automation,
    document_control,
    documents,
    employee_portal,
    incidents,
    investigation_templates,
    investigations,
    iso27001,
    notifications,
    policies,
    realtime,
    risk_register,
    risks,
    rtas,
    standards,
    users,
    uvdb,
    planet_mark,
    workflows,
)

router = APIRouter()

# Include all route modules
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(standards.router, prefix="/standards", tags=["Standards Library"])
router.include_router(audits.router, prefix="/audits", tags=["Audits & Inspections"])
router.include_router(audit_templates.router, prefix="/audit-templates", tags=["Audit Template Builder"])
router.include_router(risks.router, prefix="/risks", tags=["Risk Register"])
router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
router.include_router(rtas.router, prefix="/rtas", tags=["Road Traffic Collisions"])
router.include_router(investigation_templates.router, prefix="/investigation-templates", tags=["Investigations"])
router.include_router(investigations.router, prefix="/investigations", tags=["Investigations"])
router.include_router(complaints.router, prefix="/complaints", tags=["Complaints"])
router.include_router(policies.router, prefix="/policies", tags=["Policy Library"])
router.include_router(documents.router, prefix="/documents", tags=["Document Library"])
router.include_router(employee_portal.router, prefix="/portal", tags=["Employee Portal"])
router.include_router(compliance.router, prefix="/compliance", tags=["ISO Compliance & Evidence"])
router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])
router.include_router(realtime.router, prefix="/realtime", tags=["Real-Time & WebSocket"])
router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & Reporting"])
router.include_router(workflows.router, prefix="/workflows", tags=["Workflow Automation"])
router.include_router(compliance_automation.router, prefix="/compliance-automation", tags=["Compliance Automation"])
# Enterprise Risk Register & AI Intelligence (Tier 1 & 2)
router.include_router(risk_register.router, prefix="/risk-register", tags=["Enterprise Risk Register"])
router.include_router(ai_intelligence.router, prefix="/ai", tags=["AI Intelligence"])
router.include_router(document_control.router, prefix="/document-control", tags=["Document Control System"])
# ISO 27001 Information Security Management System
router.include_router(iso27001.router, prefix="/iso27001", tags=["ISO 27001 ISMS"])
# UVDB Achilles Verify B2 Audit Protocol
router.include_router(uvdb.router, prefix="/uvdb", tags=["UVDB Achilles Verify"])
# Planet Mark Carbon Management
router.include_router(planet_mark.router, prefix="/planet-mark", tags=["Planet Mark Carbon"])

__all__ = ["router"]
