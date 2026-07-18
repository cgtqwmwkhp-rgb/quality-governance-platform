"""AI Template Intelligence API routes.

Provides Gemini-powered endpoints for:
- Document-to-template conversion (OCR + structured extraction)
- Web search enrichment for manufacturer recommendations
- Compliance-to-assessment template conversion
- Assessor guidance generation
- Gap analysis for existing templates
- Builder multi-scheme standard-link suggest + confirm persist (MAP-01..04)
"""

from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import AliasChoices, BaseModel, Field

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services.builder_standard_link_service import (
    DEFAULT_LIBRARY_VERSION,
    builder_standard_link_service,
)
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

    template: dict = Field(..., description="Compliance template to convert to assessment")


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


class PromptTemplateRequest(BaseModel):
    """Request for freeform prompt-to-template generation."""

    prompt: str = Field(..., min_length=5, max_length=4000)


class SuggestQuestionInput(BaseModel):
    """One builder question snapshot for Assist Map suggest."""

    question_id: str = Field(..., min_length=1, max_length=64)
    question_text: str = Field(..., min_length=1, max_length=2000)
    description: Optional[str] = Field(None, max_length=2000)


class SuggestStandardLinksRequest(BaseModel):
    """Batch suggest multi-scheme mappings for template questions."""

    questions: list[SuggestQuestionInput] = Field(..., min_length=1, max_length=200)
    schemes: list[str] = Field(
        default_factory=lambda: ["ISO", "Planet Mark", "UVDB"],
        max_length=8,
    )
    library_version: str = Field(DEFAULT_LIBRARY_VERSION, max_length=64)


class StandardLinkPayload(BaseModel):
    """Client-proposed or previously suggested standard link."""

    model_config = {"populate_by_name": True}

    id: Optional[str] = Field(None, max_length=64)
    scheme: str = Field(..., min_length=1, max_length=40)
    ref_id: str = Field(
        ...,
        min_length=1,
        max_length=80,
        validation_alias=AliasChoices("refId", "ref_id"),
    )
    label: Optional[str] = Field(None, max_length=300)
    confidence: Optional[float] = Field(None, ge=0, le=100)
    status: Optional[str] = Field(None, max_length=32)
    source_fingerprint: Optional[str] = Field(
        None,
        max_length=200,
        validation_alias=AliasChoices("sourceFingerprint", "source_fingerprint"),
    )
    library_version: Optional[str] = Field(
        None,
        max_length=64,
        validation_alias=AliasChoices("libraryVersion", "library_version"),
    )
    rationale: Optional[str] = Field(None, max_length=2000)


class DecideStandardLinkRequest(BaseModel):
    """Accept / edit / reject a suggested mapping (MAP-04 confirm loop)."""

    decision: Literal["accept", "edit", "reject"]
    link: StandardLinkPayload
    edited_ref_id: Optional[str] = Field(None, max_length=80)
    edited_label: Optional[str] = Field(None, max_length=300)
    rationale: Optional[str] = Field(None, max_length=2000)


# ============ Endpoints ============


@router.post("/from-document")
async def from_document(
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
    file: UploadFile = File(..., description="PDF or image document to convert to template"),
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


@router.post("/generate-template")
async def generate_template(
    request: PromptTemplateRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> list[dict]:
    """Generate template sections from a freeform prompt."""
    service = GeminiAIService()
    try:
        return await service.prompt_to_template(request.prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI template generation unavailable: {exc}",
        ) from exc


@router.post("/web-enrich")
async def web_enrich(
    request: WebEnrichRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
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
    user: Annotated[User, Depends(require_permission("audit:create"))],
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
    user: Annotated[User, Depends(require_permission("audit:create"))],
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
    user: Annotated[User, Depends(require_permission("audit:create"))],
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


@router.post("/suggest-standard-links")
async def suggest_standard_links(
    request: SuggestStandardLinksRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """AI Assist Map: suggest ISO / Planet Mark / UVDB links for builder questions."""
    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    suggestions = await builder_standard_link_service.suggest_for_questions(
        db,
        questions=[q.model_dump() for q in request.questions],
        schemes=request.schemes,
        tenant_id=tenant_id,
        library_version=request.library_version,
    )
    return {
        "library_version": request.library_version,
        "assist_map_live": True,
        "suggestions": suggestions,
        "count": len(suggestions),
    }


@router.post("/questions/{question_id}/standard-links/decide")
async def decide_standard_link(
    question_id: int,
    request: DecideStandardLinkRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:update"))],
) -> dict[str, Any]:
    """Persist Accept / Edit / Reject for a builder standard-link suggestion."""
    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    if request.decision == "reject":
        rationale = (request.rationale or "").strip()
        if len(rationale) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reject requires a rationale (min 3 characters)",
            )
    try:
        result = await builder_standard_link_service.decide_link(
            db,
            question_id=question_id,
            tenant_id=tenant_id,
            user=user,
            decision=request.decision,
            link={
                **request.link.model_dump(),
                "refId": request.link.ref_id,
                "sourceFingerprint": request.link.source_fingerprint,
                "libraryVersion": request.link.library_version,
            },
            edited_ref_id=request.edited_ref_id,
            edited_label=request.edited_label,
            rationale=request.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    await db.commit()
    return result


@router.get("/templates/{template_id}/standards-coverage")
async def template_standards_coverage(
    template_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:read"))],
) -> dict[str, Any]:
    """Template Stats coverage from accepted multi-scheme standard links."""
    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    try:
        return await builder_standard_link_service.template_coverage(
            db,
            template_id=template_id,
            tenant_id=tenant_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
