"""Employee Self-Service Portal API routes.

Thin controller layer — all business logic lives in PortalService.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.domain.services.portal_service import PortalService

router = APIRouter(tags=["Employee Portal"])


# ============================================================================
# Schemas
# ============================================================================


class QuickReportCreate(BaseModel):
    report_type: str = Field(..., description="Type: 'incident', 'complaint', 'rta', or 'near_miss'")
    title: str = Field(..., min_length=5, max_length=200, description="Brief title")
    description: str = Field(..., min_length=10, description="What happened?")
    location: Optional[str] = Field(None, max_length=200, description="Where did it occur?")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")
    reporter_name: Optional[str] = Field(None, max_length=100)
    reporter_email: Optional[EmailStr] = None
    reporter_phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    is_anonymous: bool = Field(default=False, description="Submit anonymously")
    attachment_ids: Optional[list[str]] = None


class QuickReportResponse(BaseModel):
    success: bool
    reference_number: str
    tracking_code: str
    message: str
    estimated_response: str
    qr_code_url: Optional[str] = None


class ReportStatusResponse(BaseModel):
    reference_number: str
    report_type: str
    title: str
    status: str
    status_label: str
    submitted_at: datetime
    updated_at: datetime
    priority: str
    timeline: list[dict]
    next_steps: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None


class PortalStatsResponse(BaseModel):
    total_reports_today: int
    average_resolution_days: float
    reports_resolved_this_week: int
    anonymous_reports_percentage: float


class MyReportSummary(BaseModel):
    reference_number: str
    report_type: str
    title: str
    status: str
    status_label: str
    submitted_at: datetime
    updated_at: datetime


class MyReportsResponse(BaseModel):
    items: list[MyReportSummary]
    total: int
    page: int
    page_size: int


class QRCodeResponse(BaseModel):
    reference_number: str
    tracking_url: str
    qr_data: str


class ReportTypeItem(BaseModel):
    id: str
    label: str
    description: str
    icon: str
    color: str


class SeverityLevelItem(BaseModel):
    id: str
    label: str
    description: str
    color: str


class ReportTypesResponse(BaseModel):
    report_types: list[ReportTypeItem]
    severity_levels: list[SeverityLevelItem]


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/reports/", response_model=QuickReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_quick_report(
    report: QuickReportCreate,
    db: DbSession,
):
    """Submit a quick report (incident, complaint, RTA, or near miss)."""
    service = PortalService(db)
    try:
        return await service.submit_report(report)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


@router.get("/reports/{reference_number}/", response_model=ReportStatusResponse)
async def track_report(
    reference_number: str,
    db: DbSession,
    tracking_code: Optional[str] = Query(None, description="Required for anonymous reports"),
):
    """Track a report's status by reference number."""
    service = PortalService(db)
    try:
        return await service.track_report(reference_number)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ErrorCode.VALIDATION_ERROR)


@router.get("/stats/", response_model=PortalStatsResponse)
async def get_portal_stats(db: DbSession):
    """Get portal statistics for transparency."""
    service = PortalService(db)
    return await service.get_stats()


@router.get("/qr/{reference_number}/", response_model=QRCodeResponse)
async def generate_qr_code(reference_number: str):
    """Generate QR code data for a report."""
    tracking_url = f"https://purple-water-03205fa03.6.azurestaticapps.net/portal/track/{reference_number}"
    return {
        "reference_number": reference_number,
        "tracking_url": tracking_url,
        "qr_data": tracking_url,
    }


@router.get("/report-types/", response_model=ReportTypesResponse)
async def get_report_types():
    """Get available report types for the quick report form."""
    return {
        "report_types": [
            {
                "id": "incident",
                "label": "Safety Incident",
                "description": "Report a safety issue, near-miss, or workplace incident",
                "icon": "🚨",
                "color": "#ef4444",
            },
            {
                "id": "complaint",
                "label": "Complaint",
                "description": "Submit a complaint about service, quality, or conduct",
                "icon": "📝",
                "color": "#f59e0b",
            },
        ],
        "severity_levels": [
            {"id": "low", "label": "Low", "description": "Minor issue, no immediate action needed", "color": "#22c55e"},
            {"id": "medium", "label": "Medium", "description": "Moderate issue, attention needed", "color": "#eab308"},
            {"id": "high", "label": "High", "description": "Serious issue, prompt action required", "color": "#f97316"},
            {
                "id": "critical",
                "label": "Critical",
                "description": "Urgent! Immediate action required",
                "color": "#ef4444",
            },
        ],
    }


# =============================================================================
# Authenticated Portal Endpoints (My Reports)
# =============================================================================


@router.get("/my-reports/", response_model=MyReportsResponse)
async def get_my_reports(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> MyReportsResponse:
    """Get all reports submitted by the current authenticated user."""
    service = PortalService(db)
    result = await service.get_my_reports(current_user.email, page=page, page_size=page_size)
    return MyReportsResponse(
        items=[MyReportSummary(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )
