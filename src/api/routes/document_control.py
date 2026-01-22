"""
Advanced Document Control API Routes

Provides endpoints for:
- Document CRUD with version control
- Approval workflows
- Distribution management
- Obsolete document handling
- Access tracking
"""

from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.domain.models.document_control import (
    ControlledDocument,
    ControlledControlledDocumentVersion,
    DocumentAccessLog,
    DocumentApprovalAction,
    DocumentApprovalInstance,
    DocumentApprovalWorkflow,
    DocumentDistribution,
    DocumentTrainingLink,
    ObsoleteDocumentRecord,
)
from src.infrastructure.database import get_db

router = APIRouter()


# ============ Pydantic Schemas ============


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = None
    document_type: str = Field(..., description="policy, procedure, work_instruction, etc.")
    category: str = Field(...)
    subcategory: Optional[str] = None
    department: Optional[str] = None
    author_name: Optional[str] = None
    owner_name: Optional[str] = None
    review_frequency_months: int = Field(default=12, ge=1, le=60)
    relevant_standards: Optional[list[str]] = None
    relevant_clauses: Optional[list[str]] = None
    access_level: str = Field(default="internal")
    is_confidential: bool = False
    training_required: bool = False


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    department: Optional[str] = None
    owner_name: Optional[str] = None
    review_frequency_months: Optional[int] = None
    relevant_standards: Optional[list[str]] = None
    relevant_clauses: Optional[list[str]] = None
    access_level: Optional[str] = None
    is_confidential: Optional[bool] = None
    training_required: Optional[bool] = None


class VersionCreate(BaseModel):
    change_summary: str = Field(..., min_length=10, max_length=2000)
    change_reason: Optional[str] = None
    change_type: str = Field(default="revision", description="new, revision, amendment")
    is_major_version: bool = False


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = None
    applicable_document_types: list[str] = Field(...)
    applicable_categories: Optional[list[str]] = None
    applicable_departments: Optional[list[str]] = None
    workflow_steps: list[dict] = Field(...)
    allow_parallel_approval: bool = False
    require_all_approvals: bool = True
    auto_escalate_after_days: Optional[int] = None


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., description="approved, rejected, returned, delegated")
    comments: Optional[str] = None
    conditions: Optional[str] = None
    delegated_to: Optional[int] = None


class DistributionCreate(BaseModel):
    recipient_type: str = Field(..., description="user, department, role, external")
    recipient_id: Optional[int] = None
    recipient_name: str = Field(...)
    recipient_email: Optional[str] = None
    distribution_type: str = Field(default="controlled")
    copy_number: Optional[str] = None
    acknowledgment_required: bool = True


class ObsoleteRequest(BaseModel):
    obsolete_reason: str = Field(..., min_length=10)
    superseded_by_id: Optional[int] = None


# ============ Document CRUD Endpoints ============


@router.get("/", response_model=dict)
async def list_documents(
    document_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List controlled documents with filtering"""
    query = db.query(ControlledDocument).filter(ControlledDocument.is_current == True)

    if document_type:
        query = query.filter(ControlledDocument.document_type == document_type)
    if category:
        query = query.filter(ControlledDocument.category == category)
    if department:
        query = query.filter(ControlledDocument.department == department)
    if status:
        query = query.filter(ControlledDocument.status == status)
    if search:
        query = query.filter(
            ControlledDocument.title.ilike(f"%{search}%") | ControlledDocument.document_number.ilike(f"%{search}%")
        )

    total = query.count()
    documents = query.order_by(ControlledDocument.updated_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "documents": [
            {
                "id": d.id,
                "document_number": d.document_number,
                "title": d.title,
                "document_type": d.document_type,
                "category": d.category,
                "current_version": d.current_version,
                "status": d.status,
                "department": d.department,
                "owner_name": d.owner_name,
                "effective_date": d.effective_date.isoformat() if d.effective_date else None,
                "next_review_date": d.next_review_date.isoformat() if d.next_review_date else None,
                "is_overdue": (d.next_review_date < datetime.utcnow() if d.next_review_date else False),
            }
            for d in documents
        ],
    }


@router.post("/", response_model=dict, status_code=201)
async def create_document(
    document_data: DocumentCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new controlled document"""
    # Generate document number
    count = db.query(ControlledDocument).count()
    type_prefix = document_data.document_type[:3].upper()
    document_number = f"{type_prefix}-{(count + 1):05d}"

    document = ControlledDocument(
        document_number=document_number,
        current_version="0.1",
        major_version=0,
        minor_version=1,
        status="draft",
        **document_data.model_dump(),
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # Create initial version record
    version = ControlledDocumentVersion(
        document_id=document.id,
        version_number="0.1",
        major_version=0,
        minor_version=1,
        change_summary="Initial document creation",
        change_type="new",
        status="draft",
        created_by_name=document_data.author_name,
    )
    db.add(version)
    db.commit()

    return {
        "id": document.id,
        "document_number": document_number,
        "message": "Document created successfully",
    }


@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed document information"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get version history
    versions = (
        db.query(ControlledDocumentVersion)
        .filter(ControlledDocumentVersion.document_id == document_id)
        .order_by(ControlledDocumentVersion.created_at.desc())
        .all()
    )

    # Get distributions
    distributions = db.query(DocumentDistribution).filter(DocumentDistribution.document_id == document_id).all()

    # Log access
    log = DocumentAccessLog(
        document_id=document_id,
        user_name="Current User",  # Would come from auth
        action="view",
    )
    db.add(log)
    document.view_count += 1
    db.commit()

    return {
        "id": document.id,
        "document_number": document.document_number,
        "title": document.title,
        "description": document.description,
        "document_type": document.document_type,
        "category": document.category,
        "subcategory": document.subcategory,
        "current_version": document.current_version,
        "status": document.status,
        "department": document.department,
        "author_name": document.author_name,
        "owner_name": document.owner_name,
        "approver_name": document.approver_name,
        "approved_date": document.approved_date.isoformat() if document.approved_date else None,
        "effective_date": document.effective_date.isoformat() if document.effective_date else None,
        "expiry_date": document.expiry_date.isoformat() if document.expiry_date else None,
        "review_frequency_months": document.review_frequency_months,
        "next_review_date": document.next_review_date.isoformat() if document.next_review_date else None,
        "last_review_date": document.last_review_date.isoformat() if document.last_review_date else None,
        "file_name": document.file_name,
        "file_path": document.file_path,
        "file_size": document.file_size,
        "file_type": document.file_type,
        "relevant_standards": document.relevant_standards,
        "relevant_clauses": document.relevant_clauses,
        "access_level": document.access_level,
        "is_confidential": document.is_confidential,
        "training_required": document.training_required,
        "view_count": document.view_count,
        "download_count": document.download_count,
        "versions": [
            {
                "id": v.id,
                "version_number": v.version_number,
                "change_summary": v.change_summary,
                "change_type": v.change_type,
                "status": v.status,
                "created_by_name": v.created_by_name,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "approved_by_name": v.approved_by_name,
                "approved_date": v.approved_date.isoformat() if v.approved_date else None,
            }
            for v in versions
        ],
        "distributions": [
            {
                "id": d.id,
                "recipient_name": d.recipient_name,
                "recipient_type": d.recipient_type,
                "distribution_type": d.distribution_type,
                "copy_number": d.copy_number,
                "acknowledged": d.acknowledged,
                "acknowledged_date": d.acknowledged_date.isoformat() if d.acknowledged_date else None,
            }
            for d in distributions
        ],
    }


@router.put("/{document_id}", response_model=dict)
async def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update document metadata"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    update_data = document_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(document, key, value)

    document.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(document)

    return {"message": "Document updated successfully", "id": document.id}


# ============ Version Control Endpoints ============


@router.post("/{document_id}/versions", response_model=dict, status_code=201)
async def create_new_version(
    document_id: int,
    version_data: VersionCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a new version of the document"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Calculate new version number
    if version_data.is_major_version:
        new_major = document.major_version + 1
        new_minor = 0
    else:
        new_major = document.major_version
        new_minor = document.minor_version + 1

    new_version_number = f"{new_major}.{new_minor}"

    # Update document
    document.current_version = new_version_number
    document.major_version = new_major
    document.minor_version = new_minor
    document.status = "under_revision"
    document.updated_at = datetime.utcnow()

    # Create version record
    version = ControlledDocumentVersion(
        document_id=document_id,
        version_number=new_version_number,
        major_version=new_major,
        minor_version=new_minor,
        change_summary=version_data.change_summary,
        change_reason=version_data.change_reason,
        change_type=version_data.change_type,
        status="draft",
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    return {
        "id": version.id,
        "version_number": new_version_number,
        "message": f"Version {new_version_number} created",
    }


@router.get("/{document_id}/versions/{version_id}/diff", response_model=dict)
async def get_version_diff(
    document_id: int,
    version_id: int,
    compare_to: Optional[int] = Query(None, description="Version ID to compare with"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get diff between versions"""
    version = (
        db.query(ControlledDocumentVersion)
        .filter(ControlledDocumentVersion.id == version_id, ControlledDocumentVersion.document_id == document_id)
        .first()
    )

    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    result = {
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "change_summary": version.change_summary,
            "sections_changed": version.sections_changed,
        },
        "diff": version.diff_from_previous,
    }

    if compare_to:
        compare_version = (
            db.query(ControlledDocumentVersion)
            .filter(ControlledDocumentVersion.id == compare_to, ControlledDocumentVersion.document_id == document_id)
            .first()
        )
        if compare_version:
            result["compare_to"] = {
                "id": compare_version.id,
                "version_number": compare_version.version_number,
            }

    return result


# ============ Approval Workflow Endpoints ============


@router.get("/workflows", response_model=list)
async def list_workflows(
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List approval workflows"""
    workflows = db.query(DocumentApprovalWorkflow).filter(DocumentApprovalWorkflow.is_active == True).all()

    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "applicable_document_types": w.applicable_document_types,
            "workflow_steps": w.workflow_steps,
            "allow_parallel_approval": w.allow_parallel_approval,
        }
        for w in workflows
    ]


@router.post("/workflows", response_model=dict, status_code=201)
async def create_workflow(
    workflow_data: WorkflowCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create approval workflow"""
    workflow = DocumentApprovalWorkflow(**workflow_data.model_dump())
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    return {"id": workflow.id, "message": "Workflow created successfully"}


@router.post("/{document_id}/submit-for-approval", response_model=dict)
async def submit_for_approval(
    document_id: int,
    workflow_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit document for approval"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    workflow = db.query(DocumentApprovalWorkflow).filter(DocumentApprovalWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # Create approval instance
    instance = DocumentApprovalInstance(
        document_id=document_id,
        workflow_id=workflow_id,
        current_step=1,
        status="pending",
    )

    # Set due date based on workflow
    if workflow.auto_escalate_after_days:
        instance.due_date = datetime.utcnow() + timedelta(days=workflow.auto_escalate_after_days)

    document.status = "pending_approval"

    db.add(instance)
    db.commit()
    db.refresh(instance)

    return {
        "instance_id": instance.id,
        "message": "Document submitted for approval",
        "current_step": 1,
        "due_date": instance.due_date.isoformat() if instance.due_date else None,
    }


@router.post("/approvals/{instance_id}/action", response_model=dict)
async def take_approval_action(
    instance_id: int,
    action_request: ApprovalActionRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Take action on an approval request"""
    instance = db.query(DocumentApprovalInstance).filter(DocumentApprovalInstance.id == instance_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Approval instance not found")

    # Record the action
    action = DocumentApprovalAction(
        instance_id=instance_id,
        workflow_step=instance.current_step,
        approver_id=1,  # Would come from auth
        approver_name="Current User",  # Would come from auth
        action=action_request.action,
        comments=action_request.comments,
        conditions=action_request.conditions,
        delegated_to=action_request.delegated_to,
    )
    db.add(action)

    # Get workflow to determine next steps
    workflow = db.query(DocumentApprovalWorkflow).filter(DocumentApprovalWorkflow.id == instance.workflow_id).first()

    document = db.query(ControlledDocument).filter(ControlledDocument.id == instance.document_id).first()

    if action_request.action == "approved":
        # Check if this was the last step
        if instance.current_step >= len(workflow.workflow_steps):
            instance.status = "approved"
            instance.completed_date = datetime.utcnow()
            instance.final_decision = "approved"
            if document:
                document.status = "approved"
                document.approved_date = datetime.utcnow()
                document.effective_date = datetime.utcnow()
                document.next_review_date = datetime.utcnow() + timedelta(days=document.review_frequency_months * 30)
        else:
            instance.current_step += 1

    elif action_request.action == "rejected":
        instance.status = "rejected"
        instance.completed_date = datetime.utcnow()
        instance.final_decision = "rejected"
        instance.final_comments = action_request.comments
        if document:
            document.status = "draft"

    elif action_request.action == "returned":
        if document:
            document.status = "draft"

    db.commit()

    return {
        "message": f"Action '{action_request.action}' recorded",
        "instance_status": instance.status,
        "current_step": instance.current_step,
    }


# ============ Distribution Endpoints ============


@router.post("/{document_id}/distribute", response_model=dict, status_code=201)
async def distribute_document(
    document_id: int,
    distribution: DistributionCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Distribute document to recipients"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    dist = DocumentDistribution(
        document_id=document_id,
        notified_date=datetime.utcnow(),
        **distribution.model_dump(),
    )
    db.add(dist)
    db.commit()
    db.refresh(dist)

    # TODO: Send notification email

    return {
        "id": dist.id,
        "message": f"Document distributed to {distribution.recipient_name}",
        "copy_number": dist.copy_number,
    }


@router.post("/{document_id}/distributions/{distribution_id}/acknowledge", response_model=dict)
async def acknowledge_distribution(
    document_id: int,
    distribution_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Acknowledge receipt of document"""
    dist = (
        db.query(DocumentDistribution)
        .filter(DocumentDistribution.id == distribution_id, DocumentDistribution.document_id == document_id)
        .first()
    )

    if not dist:
        raise HTTPException(status_code=404, detail="Distribution not found")

    dist.acknowledged = True
    dist.acknowledged_date = datetime.utcnow()
    db.commit()

    return {"message": "Acknowledgment recorded"}


# ============ Obsolete Document Handling ============


@router.post("/{document_id}/obsolete", response_model=dict)
async def mark_document_obsolete(
    document_id: int,
    obsolete_data: ObsoleteRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mark document as obsolete"""
    document = db.query(ControlledDocument).filter(ControlledDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update document
    document.status = "obsolete"
    document.is_current = False
    document.obsolete_date = datetime.utcnow()
    document.obsolete_reason = obsolete_data.obsolete_reason
    document.superseded_by = obsolete_data.superseded_by_id

    # Create obsolete record
    record = ObsoleteDocumentRecord(
        document_id=document_id,
        obsolete_date=datetime.utcnow(),
        obsolete_reason=obsolete_data.obsolete_reason,
        superseded_by_id=obsolete_data.superseded_by_id,
        retention_required=True,
        retention_end_date=datetime.utcnow() + timedelta(days=document.retention_period_years * 365),
    )
    db.add(record)
    db.commit()

    return {
        "message": "Document marked as obsolete",
        "retention_end_date": record.retention_end_date.isoformat() if record.retention_end_date else None,
    }


# ============ Access Logs ============


@router.get("/{document_id}/access-log", response_model=list)
async def get_access_log(
    document_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get document access log"""
    logs = (
        db.query(DocumentAccessLog)
        .filter(DocumentAccessLog.document_id == document_id)
        .order_by(DocumentAccessLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "user_name": log.user_name,
            "action": log.action,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "ip_address": log.ip_address,
        }
        for log in logs
    ]


# ============ Summary Statistics ============


@router.get("/summary", response_model=dict)
async def get_document_summary(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get document control summary statistics"""
    total = db.query(ControlledDocument).filter(ControlledDocument.is_current == True).count()
    active = (
        db.query(ControlledDocument)
        .filter(ControlledDocument.status == "active", ControlledDocument.is_current == True)
        .count()
    )
    draft = (
        db.query(ControlledDocument)
        .filter(ControlledDocument.status == "draft", ControlledDocument.is_current == True)
        .count()
    )
    pending_approval = (
        db.query(ControlledDocument)
        .filter(ControlledDocument.status == "pending_approval", ControlledDocument.is_current == True)
        .count()
    )
    overdue_review = (
        db.query(ControlledDocument)
        .filter(
            ControlledDocument.next_review_date < datetime.utcnow(),
            ControlledDocument.status == "active",
            ControlledDocument.is_current == True,
        )
        .count()
    )
    obsolete = db.query(ControlledDocument).filter(ControlledDocument.status == "obsolete").count()

    # Pending acknowledgments
    pending_ack = (
        db.query(DocumentDistribution)
        .filter(DocumentDistribution.acknowledged == False, DocumentDistribution.acknowledgment_required == True)
        .count()
    )

    # By type
    by_type = (
        db.query(ControlledDocument.document_type, db.func.count(ControlledDocument.id))
        .filter(ControlledDocument.is_current == True)
        .group_by(ControlledDocument.document_type)
        .all()
    )

    return {
        "total_documents": total,
        "active": active,
        "draft": draft,
        "pending_approval": pending_approval,
        "overdue_review": overdue_review,
        "obsolete": obsolete,
        "pending_acknowledgments": pending_ack,
        "by_type": {dtype: count for dtype, count in by_type},
    }
