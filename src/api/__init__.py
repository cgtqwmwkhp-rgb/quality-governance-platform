"""API module - FastAPI routes and endpoints."""

from fastapi import APIRouter

from src.api.routes import (
    audit_templates,
    audits,
    auth,
    complaints,
    compliance,
    documents,
    employee_portal,
    incidents,
    investigation_templates,
    investigations,
    notifications,
    policies,
    realtime,
    risks,
    rtas,
    standards,
    users,
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

__all__ = ["router"]
