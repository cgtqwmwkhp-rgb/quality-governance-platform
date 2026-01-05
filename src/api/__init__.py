"""API module - FastAPI routes and endpoints."""

from fastapi import APIRouter

from src.api.routes import (
    audits,
    auth,
    complaints,
    incidents,
    investigation_templates,
    investigations,
    policies,
    risks,
    rta,
    standards,
    users,
)

router = APIRouter()

# Include all route modules
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(users.router, prefix="/users", tags=["Users"])
router.include_router(standards.router, prefix="/standards", tags=["Standards Library"])
router.include_router(audits.router, prefix="/audits", tags=["Audits & Inspections"])
router.include_router(risks.router, prefix="/risks", tags=["Risk Register"])
router.include_router(incidents.router, prefix="/incidents", tags=["Incidents"])
router.include_router(rta.router, prefix="/rta", tags=["Road Traffic Collisions"])
router.include_router(investigation_templates.router, prefix="/investigation-templates", tags=["Investigations"])
router.include_router(investigations.router, prefix="/investigations", tags=["Investigations"])
router.include_router(complaints.router, prefix="/complaints", tags=["Complaints"])
router.include_router(policies.router, prefix="/policies", tags=["Policy Library"])

__all__ = ["router"]
