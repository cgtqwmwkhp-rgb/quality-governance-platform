"""
Audit Template API Routes - Enterprise-grade audit tool builder
Full CRUD for templates, sections, questions, and audit execution
"""

# sqlalchemy operators imported if needed for filtering
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db

# Note: Authentication handled by route-specific dependencies

router = APIRouter()


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================


class QuestionOptionSchema(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    value: str
    score: Optional[float] = 0
    isCorrect: Optional[bool] = False


class ConditionalLogicSchema(BaseModel):
    enabled: bool = False
    showWhen: Optional[str] = "equals"
    dependsOnQuestionId: Optional[str] = None
    value: Optional[str] = None


class QuestionCreateSchema(BaseModel):
    text: str
    description: Optional[str] = None
    guidance: Optional[str] = None
    question_type: str = "yes_no"
    required: bool = True
    weight: float = 1.0
    risk_level: Optional[str] = None
    failure_triggers_action: bool = False
    evidence_required: bool = False
    evidence_type: Optional[str] = None
    iso_clause: Optional[str] = None
    options: Optional[List[QuestionOptionSchema]] = None
    conditional_logic: Optional[ConditionalLogicSchema] = None
    tags: Optional[List[str]] = None
    order: int = 0


class QuestionResponseSchema(QuestionCreateSchema):
    id: str
    section_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SectionCreateSchema(BaseModel):
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    weight: float = 1.0
    order: int = 0
    questions: Optional[List[QuestionCreateSchema]] = None


class SectionResponseSchema(BaseModel):
    id: str
    template_id: str
    title: str
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    weight: float
    order: int
    questions: List[QuestionResponseSchema] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateCreateSchema(BaseModel):
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    status: str = "draft"
    category: str = "quality"
    subcategory: Optional[str] = None
    iso_standards: Optional[List[str]] = None
    scoring_method: str = "weighted"
    pass_threshold: float = 80.0
    estimated_duration: Optional[int] = 60
    tags: Optional[List[str]] = None
    is_locked: bool = False
    is_global: bool = False
    sections: Optional[List[SectionCreateSchema]] = None


class TemplateUpdateSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    iso_standards: Optional[List[str]] = None
    scoring_method: Optional[str] = None
    pass_threshold: Optional[float] = None
    estimated_duration: Optional[int] = None
    tags: Optional[List[str]] = None
    is_locked: Optional[bool] = None
    is_global: Optional[bool] = None


class TemplateResponseSchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str
    status: str
    category: str
    subcategory: Optional[str] = None
    iso_standards: Optional[List[str]] = None
    scoring_method: str
    pass_threshold: float
    estimated_duration: Optional[int] = None
    tags: Optional[List[str]] = None
    is_locked: bool
    is_global: bool
    created_by_id: Optional[str] = None
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    question_count: int = 0
    section_count: int = 0
    sections: List[SectionResponseSchema] = []

    class Config:
        from_attributes = True


class TemplateListSchema(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    version: str
    status: str
    category: str
    iso_standards: Optional[List[str]] = None
    question_count: int = 0
    section_count: int = 0
    pass_threshold: float
    estimated_duration: Optional[int] = None
    tags: Optional[List[str]] = None
    is_locked: bool
    is_global: bool
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    avg_score: Optional[float] = None

    class Config:
        from_attributes = True


class PaginatedTemplateResponse(BaseModel):
    items: List[TemplateListSchema]
    total: int
    page: int
    page_size: int
    total_pages: int


# Audit Execution Schemas
class AuditStartSchema(BaseModel):
    template_id: str
    location: Optional[str] = None
    asset_id: Optional[str] = None
    asset_name: Optional[str] = None
    scheduled_date: Optional[datetime] = None


class AuditResponseSubmitSchema(BaseModel):
    question_id: str
    response: Optional[dict] = None
    notes: Optional[str] = None
    photos: Optional[List[str]] = None
    signature: Optional[str] = None
    flagged: bool = False
    flagged_reason: Optional[str] = None


class AuditCompleteSchema(BaseModel):
    notes: Optional[str] = None


# ============================================================================
# TEMPLATE ENDPOINTS
# ============================================================================


@router.get("/", response_model=PaginatedTemplateResponse)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    iso_standard: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    """List all audit templates with filtering and pagination"""
    from typing import Any, Dict

    # Mock data for demonstration (in production, query from database)
    mock_templates: List[Dict[str, Any]] = [
        {
            "id": "1",
            "name": "ISO 9001:2015 Full Compliance Audit",
            "description": "Comprehensive audit template covering all clauses of ISO 9001:2015",
            "version": "3.2.0",
            "status": "published",
            "category": "quality",
            "iso_standards": ["iso9001"],
            "question_count": 156,
            "section_count": 10,
            "pass_threshold": 85,
            "estimated_duration": 180,
            "tags": ["ISO", "Quality", "Certification"],
            "is_locked": True,
            "is_global": True,
            "created_at": datetime(2025, 8, 15, 10, 0, 0),
            "updated_at": datetime(2026, 1, 10, 14, 30, 0),
            "usage_count": 487,
            "avg_score": 87.3,
        },
        {
            "id": "2",
            "name": "Vehicle Pre-Departure Inspection",
            "description": "Daily vehicle safety check for fleet vehicles",
            "version": "2.1.0",
            "status": "published",
            "category": "safety",
            "iso_standards": ["iso45001"],
            "question_count": 42,
            "section_count": 5,
            "pass_threshold": 100,
            "estimated_duration": 15,
            "tags": ["Vehicle", "Safety", "Daily"],
            "is_locked": False,
            "is_global": False,
            "created_at": datetime(2025, 6, 20, 9, 0, 0),
            "updated_at": datetime(2026, 1, 5, 11, 0, 0),
            "usage_count": 2341,
            "avg_score": 94.7,
        },
        {
            "id": "3",
            "name": "Site Environmental Compliance",
            "description": "Environmental impact assessment and compliance check",
            "version": "1.5.0",
            "status": "published",
            "category": "environment",
            "iso_standards": ["iso14001"],
            "question_count": 78,
            "section_count": 8,
            "pass_threshold": 80,
            "estimated_duration": 90,
            "tags": ["Environment", "Compliance", "Site"],
            "is_locked": False,
            "is_global": True,
            "created_at": datetime(2025, 9, 1, 8, 0, 0),
            "updated_at": datetime(2025, 12, 20, 16, 0, 0),
            "usage_count": 156,
            "avg_score": 82.1,
        },
        {
            "id": "4",
            "name": "Workplace Safety Walk-Through",
            "description": "Quick safety inspection for office and workshop environments",
            "version": "1.0.0",
            "status": "published",
            "category": "safety",
            "iso_standards": ["iso45001"],
            "question_count": 35,
            "section_count": 6,
            "pass_threshold": 75,
            "estimated_duration": 30,
            "tags": ["Safety", "Workplace", "Quick"],
            "is_locked": False,
            "is_global": False,
            "created_at": datetime(2025, 11, 10, 13, 0, 0),
            "updated_at": datetime(2026, 1, 8, 9, 0, 0),
            "usage_count": 892,
            "avg_score": 88.5,
        },
        {
            "id": "5",
            "name": "ISO 45001 Health & Safety Management",
            "description": "Full audit template for ISO 45001:2018",
            "version": "2.0.0",
            "status": "published",
            "category": "safety",
            "iso_standards": ["iso45001"],
            "question_count": 134,
            "section_count": 10,
            "pass_threshold": 85,
            "estimated_duration": 150,
            "tags": ["ISO", "Health", "Safety", "Certification"],
            "is_locked": True,
            "is_global": True,
            "created_at": datetime(2025, 7, 5, 10, 0, 0),
            "updated_at": datetime(2025, 12, 15, 14, 0, 0),
            "usage_count": 234,
            "avg_score": 79.8,
        },
    ]

    # Apply filters
    filtered = mock_templates
    if search:
        search_lower = search.lower()
        filtered = [
            t
            for t in filtered
            if search_lower in str(t["name"]).lower() or search_lower in str(t.get("description") or "").lower()
        ]
    if category and category != "all":
        filtered = [t for t in filtered if t["category"] == category]
    if status and status != "all":
        filtered = [t for t in filtered if t["status"] == status]
    if iso_standard:
        filtered = [t for t in filtered if iso_standard in list(t.get("iso_standards") or [])]

    # Sort
    reverse = sort_order == "desc"
    if sort_by == "name":
        filtered.sort(key=lambda x: str(x["name"]), reverse=reverse)
    elif sort_by == "usage":
        filtered.sort(key=lambda x: int(x.get("usage_count") or 0), reverse=reverse)
    elif sort_by == "score":
        filtered.sort(key=lambda x: float(x.get("avg_score") or 0), reverse=reverse)
    else:
        filtered.sort(key=lambda x: str(x["updated_at"]), reverse=reverse)

    # Paginate
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    return PaginatedTemplateResponse(
        items=[TemplateListSchema(**dict(t)) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post("/", response_model=TemplateResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_template(
    template: TemplateCreateSchema,
    db: Session = Depends(get_db),
):
    """Create a new audit template"""

    # In production, create in database
    # For now, return mock response
    template_id = str(uuid.uuid4())
    now = datetime.utcnow()

    sections = []
    if template.sections:
        for i, section in enumerate(template.sections):
            section_id = str(uuid.uuid4())
            questions = []
            if section.questions:
                for j, question in enumerate(section.questions):
                    questions.append(
                        QuestionResponseSchema(
                            id=str(uuid.uuid4()),
                            section_id=section_id,
                            text=question.text,
                            description=question.description,
                            guidance=question.guidance,
                            question_type=question.question_type,
                            required=question.required,
                            weight=question.weight,
                            risk_level=question.risk_level,
                            failure_triggers_action=question.failure_triggers_action,
                            evidence_required=question.evidence_required,
                            evidence_type=question.evidence_type,
                            iso_clause=question.iso_clause,
                            options=question.options,
                            conditional_logic=question.conditional_logic,
                            tags=question.tags,
                            order=j,
                            created_at=now,
                            updated_at=now,
                        )
                    )

            sections.append(
                SectionResponseSchema(
                    id=section_id,
                    template_id=template_id,
                    title=section.title,
                    description=section.description,
                    icon=section.icon,
                    color=section.color,
                    weight=section.weight,
                    order=i,
                    questions=questions,
                    created_at=now,
                    updated_at=now,
                )
            )

    return TemplateResponseSchema(
        id=template_id,
        name=template.name,
        description=template.description,
        version=template.version,
        status=template.status,
        category=template.category,
        subcategory=template.subcategory,
        iso_standards=template.iso_standards,
        scoring_method=template.scoring_method,
        pass_threshold=template.pass_threshold,
        estimated_duration=template.estimated_duration,
        tags=template.tags,
        is_locked=template.is_locked,
        is_global=template.is_global,
        created_at=now,
        updated_at=now,
        question_count=sum(len(s.questions) for s in sections),
        section_count=len(sections),
        sections=sections,
    )


@router.get("/{template_id}", response_model=TemplateResponseSchema)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific audit template by ID"""

    # Mock response for demonstration
    now = datetime.utcnow()

    # Vehicle Pre-Departure Inspection template
    sections = [
        SectionResponseSchema(
            id="sec-1",
            template_id=template_id,
            title="Exterior Checks",
            description="Visual inspection of vehicle exterior",
            icon="car",
            color="from-blue-500 to-cyan-500",
            weight=1.0,
            order=0,
            questions=[
                QuestionResponseSchema(
                    id="q-1-1",
                    section_id="sec-1",
                    text="Are all lights working correctly?",
                    description="Check headlights, indicators, brake lights, hazards",
                    guidance="Turn on ignition and test each light function",
                    question_type="pass_fail",
                    required=True,
                    weight=2.0,
                    risk_level="high",
                    evidence_required=True,
                    evidence_type="photo",
                    order=0,
                    created_at=now,
                    updated_at=now,
                ),
                QuestionResponseSchema(
                    id="q-1-2",
                    section_id="sec-1",
                    text="Are tyres in good condition with adequate tread depth?",
                    description="Minimum 1.6mm tread depth required",
                    guidance="Use tread depth gauge. Check for damage.",
                    question_type="pass_fail",
                    required=True,
                    weight=3.0,
                    risk_level="critical",
                    evidence_required=True,
                    evidence_type="photo",
                    order=1,
                    created_at=now,
                    updated_at=now,
                ),
            ],
            created_at=now,
            updated_at=now,
        ),
        SectionResponseSchema(
            id="sec-2",
            template_id=template_id,
            title="Interior Checks",
            description="Safety equipment and interior condition",
            icon="shield",
            color="from-purple-500 to-pink-500",
            weight=1.0,
            order=1,
            questions=[
                QuestionResponseSchema(
                    id="q-2-1",
                    section_id="sec-2",
                    text="Is the first aid kit present and fully stocked?",
                    question_type="pass_fail",
                    required=True,
                    weight=2.0,
                    risk_level="high",
                    evidence_required=True,
                    order=0,
                    created_at=now,
                    updated_at=now,
                ),
            ],
            created_at=now,
            updated_at=now,
        ),
    ]

    return TemplateResponseSchema(
        id=template_id,
        name="Vehicle Pre-Departure Inspection",
        description="Daily vehicle safety check for fleet vehicles",
        version="2.1.0",
        status="published",
        category="safety",
        iso_standards=["iso45001"],
        scoring_method="pass_fail",
        pass_threshold=100,
        estimated_duration=15,
        tags=["Vehicle", "Safety", "Daily"],
        is_locked=False,
        is_global=False,
        created_at=datetime(2025, 6, 20, 9, 0, 0),
        updated_at=now,
        question_count=3,
        section_count=2,
        sections=sections,
    )


@router.put("/{template_id}", response_model=TemplateResponseSchema)
async def update_template(
    template_id: str,
    updates: TemplateUpdateSchema,
    db: Session = Depends(get_db),
):
    """Update an existing audit template"""

    # Get existing template and apply updates
    existing = await get_template(template_id, db)

    # Apply updates
    update_data = updates.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    existing.updated_at = datetime.utcnow()

    return existing


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Delete an audit template"""

    # In production, delete from database
    return None


@router.post("/{template_id}/duplicate", response_model=TemplateResponseSchema)
async def duplicate_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Duplicate an existing template"""

    existing = await get_template(template_id, db)

    # Create copy with new ID
    new_template = TemplateResponseSchema(
        id=str(uuid.uuid4()),
        name=f"{existing.name} (Copy)",
        description=existing.description,
        version="1.0.0",
        status="draft",
        category=existing.category,
        subcategory=existing.subcategory,
        iso_standards=existing.iso_standards,
        scoring_method=existing.scoring_method,
        pass_threshold=existing.pass_threshold,
        estimated_duration=existing.estimated_duration,
        tags=existing.tags,
        is_locked=False,
        is_global=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        question_count=existing.question_count,
        section_count=existing.section_count,
        sections=existing.sections,
    )

    return new_template


@router.post("/{template_id}/publish", response_model=TemplateResponseSchema)
async def publish_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Publish a template (change status from draft to published)"""

    existing = await get_template(template_id, db)
    existing.status = "published"
    existing.published_at = datetime.utcnow()
    existing.updated_at = datetime.utcnow()

    return existing


@router.post("/{template_id}/archive", response_model=TemplateResponseSchema)
async def archive_template(
    template_id: str,
    db: Session = Depends(get_db),
):
    """Archive a template"""

    existing = await get_template(template_id, db)
    existing.status = "archived"
    existing.updated_at = datetime.utcnow()

    return existing


# ============================================================================
# SECTION ENDPOINTS
# ============================================================================


@router.post("/{template_id}/sections", response_model=SectionResponseSchema, status_code=status.HTTP_201_CREATED)
async def add_section(
    template_id: str,
    section: SectionCreateSchema,
    db: Session = Depends(get_db),
):
    """Add a new section to a template"""

    section_id = str(uuid.uuid4())
    now = datetime.utcnow()

    questions = []
    if section.questions:
        for i, q in enumerate(section.questions):
            questions.append(
                QuestionResponseSchema(
                    id=str(uuid.uuid4()),
                    section_id=section_id,
                    text=q.text,
                    description=q.description,
                    question_type=q.question_type,
                    required=q.required,
                    weight=q.weight,
                    order=i,
                    created_at=now,
                    updated_at=now,
                )
            )

    return SectionResponseSchema(
        id=section_id,
        template_id=template_id,
        title=section.title,
        description=section.description,
        icon=section.icon,
        color=section.color,
        weight=section.weight,
        order=section.order,
        questions=questions,
        created_at=now,
        updated_at=now,
    )


@router.put("/{template_id}/sections/{section_id}", response_model=SectionResponseSchema)
async def update_section(
    template_id: str,
    section_id: str,
    section: SectionCreateSchema,
    db: Session = Depends(get_db),
):
    """Update a section"""

    now = datetime.utcnow()

    return SectionResponseSchema(
        id=section_id,
        template_id=template_id,
        title=section.title,
        description=section.description,
        icon=section.icon,
        color=section.color,
        weight=section.weight,
        order=section.order,
        questions=[],
        created_at=now,
        updated_at=now,
    )


@router.delete("/{template_id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    template_id: str,
    section_id: str,
    db: Session = Depends(get_db),
):
    """Delete a section from a template"""
    return None


# ============================================================================
# QUESTION ENDPOINTS
# ============================================================================


@router.post(
    "/{template_id}/sections/{section_id}/questions",
    response_model=QuestionResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def add_question(
    template_id: str,
    section_id: str,
    question: QuestionCreateSchema,
    db: Session = Depends(get_db),
):
    """Add a new question to a section"""

    now = datetime.utcnow()

    return QuestionResponseSchema(
        id=str(uuid.uuid4()),
        section_id=section_id,
        text=question.text,
        description=question.description,
        guidance=question.guidance,
        question_type=question.question_type,
        required=question.required,
        weight=question.weight,
        risk_level=question.risk_level,
        failure_triggers_action=question.failure_triggers_action,
        evidence_required=question.evidence_required,
        evidence_type=question.evidence_type,
        iso_clause=question.iso_clause,
        options=question.options,
        conditional_logic=question.conditional_logic,
        tags=question.tags,
        order=question.order,
        created_at=now,
        updated_at=now,
    )


@router.delete("/{template_id}/sections/{section_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    template_id: str,
    section_id: str,
    question_id: str,
    db: Session = Depends(get_db),
):
    """Delete a question from a section"""
    return None


# ============================================================================
# AUDIT EXECUTION ENDPOINTS
# ============================================================================


@router.post("/{template_id}/start")
async def start_audit(
    template_id: str,
    audit_data: AuditStartSchema,
    db: Session = Depends(get_db),
):
    """Start a new audit run from a template"""

    audit_id = str(uuid.uuid4())
    ref_number = f"AUD-{datetime.utcnow().strftime('%Y%m%d')}-{audit_id[:4].upper()}"

    return {
        "id": audit_id,
        "reference_number": ref_number,
        "template_id": template_id,
        "status": "in_progress",
        "location": audit_data.location,
        "asset_id": audit_data.asset_id,
        "asset_name": audit_data.asset_name,
        "started_at": datetime.utcnow(),
        "created_at": datetime.utcnow(),
    }


@router.post("/runs/{audit_id}/responses")
async def submit_response(
    audit_id: str,
    response: AuditResponseSubmitSchema,
    db: Session = Depends(get_db),
):
    """Submit a response to a question during audit execution"""

    return {
        "id": str(uuid.uuid4()),
        "audit_run_id": audit_id,
        "question_id": response.question_id,
        "response": response.response,
        "notes": response.notes,
        "photos": response.photos,
        "signature": response.signature,
        "flagged": response.flagged,
        "answered_at": datetime.utcnow(),
    }


@router.post("/runs/{audit_id}/complete")
async def complete_audit(
    audit_id: str,
    completion: AuditCompleteSchema,
    db: Session = Depends(get_db),
):
    """Complete an audit run and calculate final score"""

    return {
        "id": audit_id,
        "status": "completed",
        "completed_at": datetime.utcnow(),
        "score_percentage": 92.5,  # Mock score
        "total_questions": 15,
        "answered_questions": 15,
        "passed_questions": 14,
        "failed_questions": 1,
        "notes": completion.notes,
    }


# ============================================================================
# PRE-BUILT TEMPLATES
# ============================================================================


@router.get("/prebuilt/list")
async def list_prebuilt_templates():
    """List available pre-built enterprise templates"""

    return {
        "templates": [
            {
                "id": "prebuilt-iso9001",
                "name": "ISO 9001:2015 Complete Audit",
                "description": "Full compliance audit for ISO 9001 Quality Management System",
                "category": "quality",
                "iso_standards": ["iso9001"],
                "question_count": 156,
                "section_count": 10,
                "estimated_duration": 180,
            },
            {
                "id": "prebuilt-iso14001",
                "name": "ISO 14001:2015 Environmental Audit",
                "description": "Environmental management system compliance audit",
                "category": "environment",
                "iso_standards": ["iso14001"],
                "question_count": 98,
                "section_count": 8,
                "estimated_duration": 120,
            },
            {
                "id": "prebuilt-iso45001",
                "name": "ISO 45001:2018 Health & Safety Audit",
                "description": "Occupational health and safety management audit",
                "category": "safety",
                "iso_standards": ["iso45001"],
                "question_count": 134,
                "section_count": 10,
                "estimated_duration": 150,
            },
            {
                "id": "prebuilt-vehicle",
                "name": "Vehicle Pre-Departure Inspection",
                "description": "Daily vehicle safety check checklist",
                "category": "safety",
                "iso_standards": ["iso45001"],
                "question_count": 42,
                "section_count": 5,
                "estimated_duration": 15,
            },
            {
                "id": "prebuilt-5s",
                "name": "5S Workplace Audit",
                "description": "Sort, Set in order, Shine, Standardize, Sustain",
                "category": "operational",
                "iso_standards": [],
                "question_count": 50,
                "section_count": 5,
                "estimated_duration": 45,
            },
            {
                "id": "prebuilt-supplier",
                "name": "Supplier Quality Assessment",
                "description": "New supplier qualification and evaluation",
                "category": "quality",
                "iso_standards": ["iso9001"],
                "question_count": 52,
                "section_count": 7,
                "estimated_duration": 60,
            },
        ]
    }


@router.post("/prebuilt/{prebuilt_id}/install", response_model=TemplateResponseSchema)
async def install_prebuilt_template(
    prebuilt_id: str,
    db: Session = Depends(get_db),
):
    """Install a pre-built template to user's library"""

    # In production, copy the pre-built template to user's templates
    now = datetime.utcnow()

    return TemplateResponseSchema(
        id=str(uuid.uuid4()),
        name="Vehicle Pre-Departure Inspection",
        description="Daily vehicle safety check for fleet vehicles",
        version="1.0.0",
        status="draft",
        category="safety",
        iso_standards=["iso45001"],
        scoring_method="pass_fail",
        pass_threshold=100,
        estimated_duration=15,
        tags=["Vehicle", "Safety", "Daily"],
        is_locked=False,
        is_global=False,
        created_at=now,
        updated_at=now,
        question_count=42,
        section_count=5,
        sections=[],
    )
