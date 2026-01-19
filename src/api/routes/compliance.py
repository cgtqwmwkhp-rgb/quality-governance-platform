"""
ISO Compliance Evidence API Routes

Provides endpoints for:
- Auto-tagging content with ISO clauses
- Managing evidence links
- Generating compliance reports
- Gap analysis
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.domain.services.iso_compliance_service import (
    iso_compliance_service,
    ISOStandard,
    EvidenceLink
)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class AutoTagRequest(BaseModel):
    content: str
    min_confidence: float = 30.0
    use_ai: bool = False


class AutoTagResponse(BaseModel):
    clause_id: str
    clause_number: str
    title: str
    standard: str
    confidence: float
    linked_by: str


class ClauseResponse(BaseModel):
    id: str
    standard: str
    clause_number: str
    title: str
    description: str
    keywords: List[str]
    parent_clause: Optional[str]
    level: int


class EvidenceLinkRequest(BaseModel):
    entity_type: str  # 'document', 'audit', 'incident', 'policy', 'action', 'risk'
    entity_id: str
    clause_ids: List[str]
    linked_by: str = "manual"
    confidence: Optional[float] = None


class ComplianceSummary(BaseModel):
    total_clauses: int
    full_coverage: int
    partial_coverage: int
    gaps: int
    coverage_percentage: float


class GapClause(BaseModel):
    clause_id: str
    clause_number: str
    title: str
    standard: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/clauses", response_model=List[ClauseResponse])
async def list_clauses(
    standard: Optional[str] = Query(None, description="Filter by ISO standard (iso9001, iso14001, iso45001)"),
    level: Optional[int] = Query(None, description="Filter by clause level (1=main, 2=sub)"),
    search: Optional[str] = Query(None, description="Search by keyword or clause number")
):
    """List all ISO clauses with optional filtering."""
    
    # Convert string to enum if provided
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid standard: {standard}")
    
    if search:
        clauses = iso_compliance_service.search_clauses(search)
    else:
        clauses = iso_compliance_service.get_all_clauses(std_enum)
    
    if level:
        clauses = [c for c in clauses if c.level == level]
    
    return [
        ClauseResponse(
            id=c.id,
            standard=c.standard.value,
            clause_number=c.clause_number,
            title=c.title,
            description=c.description,
            keywords=c.keywords,
            parent_clause=c.parent_clause,
            level=c.level
        )
        for c in clauses
    ]


@router.get("/clauses/{clause_id}", response_model=ClauseResponse)
async def get_clause(clause_id: str):
    """Get a specific ISO clause by ID."""
    clause = iso_compliance_service.get_clause(clause_id)
    if not clause:
        raise HTTPException(status_code=404, detail=f"Clause not found: {clause_id}")
    
    return ClauseResponse(
        id=clause.id,
        standard=clause.standard.value,
        clause_number=clause.clause_number,
        title=clause.title,
        description=clause.description,
        keywords=clause.keywords,
        parent_clause=clause.parent_clause,
        level=clause.level
    )


@router.post("/auto-tag", response_model=List[AutoTagResponse])
async def auto_tag_content(request: AutoTagRequest):
    """
    Automatically detect ISO clauses that relate to the given content.
    
    Uses keyword matching and pattern recognition. Optionally can use AI
    for enhanced tagging when use_ai=True.
    """
    min_conf = request.min_confidence / 100.0  # Convert percentage to decimal
    
    if request.use_ai:
        # AI-enhanced tagging (async)
        results = await iso_compliance_service.ai_enhanced_tagging(request.content)
    else:
        # Keyword-based tagging (sync)
        results = iso_compliance_service.auto_tag_content(request.content, min_conf)
    
    return [
        AutoTagResponse(**result)
        for result in results
    ]


@router.post("/evidence/link")
async def link_evidence(request: EvidenceLinkRequest):
    """
    Link an entity (document, audit, incident, etc.) to ISO clauses.
    
    This creates the evidence mapping that shows which items satisfy
    which ISO requirements.
    """
    # Validate clause IDs exist
    for clause_id in request.clause_ids:
        if not iso_compliance_service.get_clause(clause_id):
            raise HTTPException(status_code=400, detail=f"Invalid clause ID: {clause_id}")
    
    # In production, this would save to database
    # For now, return success response
    links_created = []
    for clause_id in request.clause_ids:
        links_created.append({
            "entity_type": request.entity_type,
            "entity_id": request.entity_id,
            "clause_id": clause_id,
            "linked_by": request.linked_by,
            "confidence": request.confidence,
            "created_at": datetime.utcnow().isoformat()
        })
    
    return {
        "status": "success",
        "message": f"Created {len(links_created)} evidence link(s)",
        "links": links_created
    }


@router.get("/coverage")
async def get_compliance_coverage(
    standard: Optional[str] = Query(None, description="Filter by ISO standard")
):
    """
    Get compliance coverage statistics showing how many clauses
    have evidence linked to them.
    """
    # In production, this would fetch evidence links from database
    # For demo, using mock data
    mock_links = [
        EvidenceLink("l1", "policy", "1", "9001-5.2", "manual"),
        EvidenceLink("l2", "document", "2", "9001-7.5", "manual"),
        EvidenceLink("l3", "document", "3", "9001-7.5", "auto", 0.85),
        EvidenceLink("l4", "audit", "4", "9001-9.2", "auto", 0.92),
        EvidenceLink("l5", "incident", "5", "45001-10.2", "auto", 0.88),
        EvidenceLink("l6", "training", "6", "45001-7.2", "auto", 0.95),
        EvidenceLink("l7", "document", "7", "14001-8.2", "manual"),
    ]
    
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid standard: {standard}")
    
    return iso_compliance_service.calculate_compliance_coverage(mock_links, std_enum)


@router.get("/gaps")
async def get_compliance_gaps(
    standard: Optional[str] = Query(None, description="Filter by ISO standard")
):
    """
    Get list of ISO clauses that have no evidence linked to them.
    These represent compliance gaps that need attention.
    """
    # In production, fetch from database
    mock_links = [
        EvidenceLink("l1", "policy", "1", "9001-5.2", "manual"),
        EvidenceLink("l2", "document", "2", "9001-7.5", "manual"),
    ]
    
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid standard: {standard}")
    
    coverage = iso_compliance_service.calculate_compliance_coverage(mock_links, std_enum)
    
    return {
        "total_gaps": coverage["gaps"],
        "gap_clauses": coverage["gap_clauses"]
    }


@router.get("/report")
async def generate_compliance_report(
    standard: Optional[str] = Query(None, description="Filter by ISO standard"),
    include_evidence: bool = Query(True, description="Include evidence details in report")
):
    """
    Generate a comprehensive compliance report suitable for certification audits.
    
    Shows all clauses with their linked evidence and coverage status.
    """
    # In production, fetch from database
    mock_links = [
        EvidenceLink("l1", "policy", "1", "9001-5.2", "manual"),
        EvidenceLink("l2", "document", "2", "9001-7.5", "manual"),
        EvidenceLink("l3", "document", "3", "9001-7.5", "auto", 0.85),
        EvidenceLink("l4", "audit", "4", "9001-9.2", "auto", 0.92),
        EvidenceLink("l5", "incident", "5", "45001-10.2", "auto", 0.88),
        EvidenceLink("l6", "training", "6", "45001-7.2", "auto", 0.95),
        EvidenceLink("l7", "document", "7", "14001-8.2", "manual"),
    ]
    
    std_enum = None
    if standard:
        try:
            std_enum = ISOStandard(standard)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid standard: {standard}")
    
    return iso_compliance_service.generate_audit_report(
        mock_links,
        std_enum,
        include_evidence
    )


@router.get("/standards")
async def list_standards():
    """List all supported ISO standards."""
    return [
        {
            "id": "iso9001",
            "code": "ISO 9001:2015",
            "name": "Quality Management System",
            "description": "Requirements for a quality management system",
            "clause_count": len([c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_9001) if c.level == 2])
        },
        {
            "id": "iso14001",
            "code": "ISO 14001:2015",
            "name": "Environmental Management System",
            "description": "Requirements for an environmental management system",
            "clause_count": len([c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_14001) if c.level == 2])
        },
        {
            "id": "iso45001",
            "code": "ISO 45001:2018",
            "name": "Occupational Health and Safety Management System",
            "description": "Requirements for an OH&S management system",
            "clause_count": len([c for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_45001) if c.level == 2])
        }
    ]
