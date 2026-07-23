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
from src.domain.services.builder_standard_link_service import DEFAULT_LIBRARY_VERSION, builder_standard_link_service
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
AI_TEMPLATE_UNAVAILABLE_DETAIL = "AI template generation is currently unavailable. Please try again later."


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


class CaseRefInput(BaseModel):
    type: str = Field(..., min_length=1, max_length=40)
    id: int = Field(..., ge=1)


class BuilderBriefRequest(BaseModel):
    """Intent + scope for Audit Builder brief gather."""

    purpose: str = Field("freeform", max_length=40)
    scopes: list[str] = Field(default_factory=list, max_length=12)
    case_refs: list[CaseRefInput] = Field(default_factory=list, max_length=20)
    asset_hint: str = Field("", max_length=200)
    standards: list[str] = Field(default_factory=list, max_length=12)
    freeform_notes: str = Field("", max_length=2000)
    upload_summaries: list[str] = Field(default_factory=list, max_length=10)
    include_research: bool = False
    include_workforce: bool = False


class BuilderQaRequest(BaseModel):
    brief: dict[str, Any] = Field(..., description="BuilderBrief from gather-brief")
    answers: dict[str, str] = Field(default_factory=dict)


class SimilarTemplatesRequest(BaseModel):
    brief: dict[str, Any]
    limit: int = Field(5, ge=1, le=15)


class GenerateFromBriefRequest(BaseModel):
    brief: dict[str, Any]
    similar_gate_action: Literal["build_new", "use_existing", "clone_reference"] = "build_new"
    similar_template_id: Optional[int] = Field(None, ge=1)
    similar_gate_reason: str = Field("", max_length=500)


class ResearchRequest(BaseModel):
    query: Optional[str] = Field(None, max_length=2000)
    brief: Optional[dict[str, Any]] = None


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
        # Upstream SDK/provider errors can contain operational details. Keep the
        # user-facing response actionable without exposing those internals.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_TEMPLATE_UNAVAILABLE_DETAIL,
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


@router.post("/gather-brief")
async def gather_builder_brief(
    request: BuilderBriefRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Gather platform + optional research context into a BuilderBrief."""
    from src.domain.services.audit_builder_orchestrator import AuditBuilderOrchestrator
    from src.domain.services.library_horizon_adapter import research_with_perplexity

    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    orch = AuditBuilderOrchestrator(db)
    research_findings: list[dict[str, Any]] = []
    if request.include_research:
        q_parts = [
            request.purpose,
            request.asset_hint,
            " ".join(request.standards),
            request.freeform_notes[:400],
        ]
        query = " ".join(p for p in q_parts if p).strip() or "UK H&S audit best practice"
        for finding in research_with_perplexity(query):
            research_findings.append(
                {
                    "title": finding.title,
                    "summary": finding.summary,
                    "source_url": finding.source_url,
                    "provider": finding.provider,
                }
            )
    workforce: list[str] = []
    if request.include_workforce or request.purpose == "technical_assessment":
        workforce = await orch.workforce_signals(tenant_id, request.asset_hint)
    brief = await orch.gather_brief(
        tenant_id=tenant_id,
        purpose=request.purpose,
        scopes=request.scopes,
        case_refs=[c.model_dump() for c in request.case_refs],
        asset_hint=request.asset_hint,
        standards=request.standards,
        freeform_notes=request.freeform_notes,
        upload_summaries=request.upload_summaries,
        research_findings=research_findings,
        workforce_signals=workforce,
    )
    return brief


@router.post("/apply-qa")
async def apply_builder_qa(
    request: BuilderQaRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Apply clarifying Q&A answers onto a BuilderBrief."""
    from src.domain.services.audit_builder_orchestrator import AuditBuilderOrchestrator

    _ = require_tenant_id(getattr(user, "tenant_id", None))
    orch = AuditBuilderOrchestrator(db)
    return orch.apply_qa_answers(request.brief, request.answers)


@router.post("/similar-templates")
async def similar_templates(
    request: SimilarTemplatesRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Score existing templates against the brief (anti-duplication gate)."""
    from src.domain.services.audit_builder_orchestrator import AuditBuilderOrchestrator

    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    orch = AuditBuilderOrchestrator(db)
    matches = await orch.find_similar_templates(tenant_id=tenant_id, brief=request.brief, limit=request.limit)
    return {"matches": matches, "count": len(matches)}


@router.post("/research")
async def research_for_builder(
    request: ResearchRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Live Perplexity research for the Audit Builder — fail-closed to empty."""
    from src.domain.services.library_horizon_adapter import research_with_perplexity

    _ = require_tenant_id(getattr(user, "tenant_id", None))
    _ = db
    query = (request.query or "").strip()
    if not query and request.brief:
        brief = request.brief
        query = " ".join(
            [
                str(brief.get("purpose") or ""),
                str(brief.get("asset_hint") or ""),
                " ".join(brief.get("standards") or []),
                str(brief.get("freeform_notes") or "")[:400],
            ]
        ).strip()
    if not query:
        return {"findings": [], "available": False, "reason": "empty_query"}
    findings = research_with_perplexity(query)
    return {
        "findings": [
            {
                "title": f.title,
                "summary": f.summary,
                "source_url": f.source_url,
                "provider": f.provider,
            }
            for f in findings
        ],
        "available": bool(findings),
        "reason": None if findings else "research_unavailable",
    }


@router.post("/generate-from-brief")
async def generate_from_brief(
    request: GenerateFromBriefRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Generate template sections from a refined BuilderBrief after similar-gate."""
    from src.domain.services.audit_builder_orchestrator import AuditBuilderOrchestrator

    tenant_id = require_tenant_id(getattr(user, "tenant_id", None))
    if request.similar_gate_action == "use_existing":
        if not request.similar_template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="similar_template_id required when using an existing template",
            )
        return {
            "action": "use_existing",
            "template_id": request.similar_template_id,
            "sections": [],
            "builder_meta": {
                "brief_id": (request.brief or {}).get("brief_id"),
                "source_case_refs": (request.brief or {}).get("case_refs") or [],
                "similar_gate_action": request.similar_gate_action,
                "similar_gate_reason": request.similar_gate_reason[:500],
                "tenant_id": tenant_id,
            },
        }

    orch = AuditBuilderOrchestrator(db)
    prompt = orch.compose_generation_prompt(request.brief)
    service = GeminiAIService()
    try:
        sections = await service.prompt_to_template(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=AI_TEMPLATE_UNAVAILABLE_DETAIL,
        ) from exc

    # Optional post-generate Assist Map suggestions (Wave 3) — fail-closed
    suggestions: list[dict[str, Any]] = []
    try:
        questions = []
        for sec in sections or []:
            for q in sec.get("questions") or []:
                qid = str(q.get("id") or "")
                text = str(q.get("text") or "")
                if qid and text:
                    questions.append({"question_id": qid, "question_text": text[:2000]})
        if questions:
            schemes = ["ISO", "Planet Mark", "UVDB"]
            for s in request.brief.get("standards") or []:
                if "Planet" in s and "Planet Mark" not in schemes:
                    schemes.append("Planet Mark")
            suggestions = await builder_standard_link_service.suggest_for_questions(
                db,
                questions=questions[:80],
                schemes=schemes,
                tenant_id=tenant_id,
            )
    except Exception:  # noqa: BLE001 — fail-closed
        suggestions = []

    return {
        "action": request.similar_gate_action,
        "sections": sections,
        "standard_suggestions": suggestions,
        "builder_meta": {
            "brief_id": (request.brief or {}).get("brief_id"),
            "source_case_refs": (request.brief or {}).get("case_refs") or [],
            "similar_gate_action": request.similar_gate_action,
            "similar_gate_reason": request.similar_gate_reason[:500],
            "similar_template_id": request.similar_template_id,
            "research_available": bool((request.brief or {}).get("research_findings")),
        },
    }
