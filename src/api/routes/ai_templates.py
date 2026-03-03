"""AI Template Intelligence API routes.

Provides Gemini-powered endpoints for:
- Document-to-template conversion (OCR + structured extraction)
- Web search enrichment for manufacturer recommendations
- Compliance-to-assessment template conversion
- Assessor guidance generation
- Gap analysis for existing templates
"""

from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession
from src.domain.services.gemini_ai_service import GeminiAIService

router = APIRouter()

# Allowed content types for document upload (PDF, images for OCR)
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}
MAX_DOCUMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


# ============ Request/Response schemas ============


class WebEnrichRequest(BaseModel):
    """Request for web search enrichment."""

    asset_type: str = Field(..., min_length=1, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=200)


class ConvertToAssessmentRequest(BaseModel):
    """Request body containing template data to convert."""

    template: dict = Field(
        ..., description="Compliance template to convert to assessment"
    )


class AssessorGuidanceRequest(BaseModel):
    """Request for assessor guidance generation."""

    question_text: str = Field(..., min_length=1, max_length=2000)
    asset_type: Optional[str] = Field(None, max_length=200)


class GapAnalysisRequest(BaseModel):
    """Request for gap analysis of existing templates."""

    existing_templates: list[dict] = Field(
        ...,
        description="List of existing template summaries (name, sections)",
        min_length=1,
        max_length=50,
    )
    asset_type: str = Field(..., min_length=1, max_length=200)


# ============ Endpoints ============


@router.post("/from-document")
async def from_document(
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(
        ..., description="PDF or image document to convert to template"
    ),
    asset_type: Optional[str] = None,
) -> dict:
    """Upload a document and generate a structured audit template via Gemini.

    Supports PDF and images (JPEG, PNG, GIF, WebP). Uses OCR and structured
    extraction to produce sections and questions classified as essential or good-to-have.
    """
    # Validate content type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: PDF, JPEG, PNG, GIF, WebP. Got: {content_type}",
        )

    content = await file.read()
    if len(content) > MAX_DOCUMENT_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_DOCUMENT_SIZE_BYTES // (1024 * 1024)}MB",
        )

    service = GeminiAIService()
    return await service.document_to_template(
        file_content=content,
        filename=file.filename or "document",
        asset_type=asset_type,
    )


@router.post("/web-enrich")
async def web_enrich(
    request: WebEnrichRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Get web search recommendations for asset type and optional manufacturer.

    Uses Gemini with grounding to find manufacturer service intervals,
    UK regulatory requirements (LOLER, PUWER), and industry best practices.
    """
    service = GeminiAIService()
    return await service.web_search_enrichment(
        asset_type=request.asset_type,
        manufacturer=request.manufacturer,
    )


@router.post("/convert-to-assessment")
async def convert_to_assessment(
    request: ConvertToAssessmentRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Convert a compliance/inspection template into a competency assessment version.

    Transforms equipment condition checks into skill-based competency criteria.
    """
    service = GeminiAIService()
    return await service.template_to_assessment(template_data=request.template)


@router.post("/assessor-guidance")
async def assessor_guidance(
    request: AssessorGuidanceRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Generate detailed assessor guidance for a specific question/skill.

    Provides pass/fail indicators, common mistakes, and training tips.
    """
    service = GeminiAIService()
    return await service.generate_assessor_guidance(
        question_text=request.question_text,
        asset_type=request.asset_type,
    )


@router.post("/gap-analysis")
async def gap_analysis(
    request: GapAnalysisRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    """Analyse gaps between existing templates and industry standards for an asset type.

    Identifies missing inspection areas, regulatory gaps, and improvement opportunities.
    Uses web search for up-to-date regulatory and manufacturer requirements.
    """
    service = GeminiAIService()
    return await service.gap_analysis(
        existing_templates=request.existing_templates,
        asset_type=request.asset_type,
    )
