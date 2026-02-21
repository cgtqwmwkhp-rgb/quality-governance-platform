"""Document control domain service.

Extracts business logic from document_control routes into a testable service class.
Covers document CRUD, versioning, approval workflows, distribution, and obsolete handling.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.document_control import (
    ControlledDocument,
    ControlledDocumentVersion,
    DocumentAccessLog,
    DocumentApprovalAction,
    DocumentApprovalInstance,
    DocumentApprovalWorkflow,
    DocumentDistribution,
    ObsoleteDocumentRecord,
)
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class DocumentControlService:
    """Handles controlled-document lifecycle: CRUD, versioning, approval, distribution."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Document CRUD
    # ------------------------------------------------------------------

    async def list_documents(
        self,
        *,
        tenant_id: int | None,
        params: PaginationParams,
        document_type: Optional[str] = None,
        category: Optional[str] = None,
        department: Optional[str] = None,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict[str, Any]:
        stmt = select(ControlledDocument).where(
            ControlledDocument.is_current == True,  # noqa: E712
            ControlledDocument.tenant_id == tenant_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        )

        if document_type:
            stmt = stmt.where(ControlledDocument.document_type == document_type)
        if category:
            stmt = stmt.where(ControlledDocument.category == category)
        if department:
            stmt = stmt.where(ControlledDocument.department == department)
        if status_filter:
            stmt = stmt.where(ControlledDocument.status == status_filter)
        if search:
            stmt = stmt.where(
                ControlledDocument.title.ilike(f"%{search}%") | ControlledDocument.document_number.ilike(f"%{search}%")
            )

        stmt = stmt.order_by(ControlledDocument.updated_at.desc())
        result = await paginate(self.db, stmt, params)

        return {
            "items": [
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
                    "is_overdue": (d.next_review_date < datetime.now(timezone.utc) if d.next_review_date else False),
                }
                for d in result.items
            ],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "pages": result.pages,
        }

    async def create_document(
        self,
        document_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Create a new controlled document with initial version.

        Returns:
            Dict with id, document_number and message.
        """
        data = document_data.model_dump()
        count_result = await self.db.execute(select(func.count()).select_from(ControlledDocument))
        count = count_result.scalar_one()
        type_prefix = data["document_type"][:3].upper()
        document_number = f"{type_prefix}-{(count + 1):05d}"

        document = ControlledDocument(
            document_number=document_number,
            current_version="0.1",
            major_version=0,
            minor_version=1,
            status="draft",
            **data,
        )

        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        version = ControlledDocumentVersion(
            document_id=document.id,
            version_number="0.1",
            major_version=0,
            minor_version=1,
            change_summary="Initial document creation",
            change_type="new",
            status="draft",
            created_by_name=data.get("author_name"),
        )
        self.db.add(version)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)
        track_metric("document_control.documents_created", 1)

        return {
            "id": document.id,
            "document_number": document_number,
            "message": "Document created successfully",
        }

    async def get_document(self, document_id: int, *, tenant_id: int | None) -> dict[str, Any]:
        """Fetch detailed document information including versions and distributions.

        Records an access-log entry and increments view_count.

        Raises:
            LookupError: If the document is not found.
        """
        document = await self._get_document_or_raise(document_id, tenant_id)

        versions_result = await self.db.execute(
            select(ControlledDocumentVersion)
            .where(ControlledDocumentVersion.document_id == document_id)
            .order_by(ControlledDocumentVersion.created_at.desc())
        )
        versions = versions_result.scalars().all()

        distributions_result = await self.db.execute(
            select(DocumentDistribution).where(DocumentDistribution.document_id == document_id)
        )
        distributions = distributions_result.scalars().all()

        log = DocumentAccessLog(document_id=document_id, user_name="Current User", action="view")
        self.db.add(log)
        document.view_count += 1
        await self.db.commit()

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

    async def update_document(
        self,
        document_id: int,
        document_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Update document metadata.

        Raises:
            LookupError: If the document is not found.
        """
        document = await self._get_document_or_raise(document_id, tenant_id)
        apply_updates(document, document_data)
        await self.db.commit()
        await self.db.refresh(document)
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {"message": "Document updated successfully", "id": document.id}

    # ------------------------------------------------------------------
    # Version control
    # ------------------------------------------------------------------

    async def create_version(
        self,
        document_id: int,
        version_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Create a new version of the document.

        Raises:
            LookupError: If the document is not found.
        """
        document = await self._get_document_or_raise(document_id, tenant_id)
        data = version_data.model_dump()

        if data.get("is_major_version"):
            new_major = document.major_version + 1
            new_minor = 0
        else:
            new_major = document.major_version
            new_minor = document.minor_version + 1

        new_version_number = f"{new_major}.{new_minor}"

        document.current_version = new_version_number
        document.major_version = new_major
        document.minor_version = new_minor
        document.status = "under_revision"
        document.updated_at = datetime.now(timezone.utc)

        version = ControlledDocumentVersion(
            document_id=document_id,
            version_number=new_version_number,
            major_version=new_major,
            minor_version=new_minor,
            change_summary=data["change_summary"],
            change_reason=data.get("change_reason"),
            change_type=data.get("change_type", "revision"),
            status="draft",
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {
            "id": version.id,
            "version_number": new_version_number,
            "message": f"Version {new_version_number} created",
        }

    async def get_version_diff(
        self,
        document_id: int,
        version_id: int,
        *,
        compare_to: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get diff information for a document version.

        Raises:
            LookupError: If the version is not found.
        """
        result = await self.db.execute(
            select(ControlledDocumentVersion).where(
                ControlledDocumentVersion.id == version_id,
                ControlledDocumentVersion.document_id == document_id,
            )
        )
        version = result.scalar_one_or_none()
        if not version:
            raise LookupError(f"Version {version_id} not found for document {document_id}")

        response: dict[str, Any] = {
            "version": {
                "id": version.id,
                "version_number": version.version_number,
                "change_summary": version.change_summary,
                "sections_changed": version.sections_changed,
            },
            "diff": version.diff_from_previous,
        }

        if compare_to:
            compare_result = await self.db.execute(
                select(ControlledDocumentVersion).where(
                    ControlledDocumentVersion.id == compare_to,
                    ControlledDocumentVersion.document_id == document_id,
                )
            )
            compare_version = compare_result.scalar_one_or_none()
            if compare_version:
                response["compare_to"] = {
                    "id": compare_version.id,
                    "version_number": compare_version.version_number,
                }

        return response

    # ------------------------------------------------------------------
    # Approval workflows
    # ------------------------------------------------------------------

    async def list_workflows(self, *, tenant_id: int | None) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(DocumentApprovalWorkflow).where(
                DocumentApprovalWorkflow.is_active == True,  # noqa: E712
                DocumentApprovalWorkflow.tenant_id == tenant_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        workflows = result.scalars().all()

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

    async def create_workflow(
        self,
        workflow_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        workflow = DocumentApprovalWorkflow(**workflow_data.model_dump())
        self.db.add(workflow)
        await self.db.commit()
        await self.db.refresh(workflow)
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {"id": workflow.id, "message": "Workflow created successfully"}

    async def submit_for_approval(
        self,
        document_id: int,
        workflow_id: int,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Submit a document for approval via a specific workflow.

        Raises:
            LookupError: If document or workflow is not found.
        """
        document = await self._get_document_or_raise(document_id, tenant_id)
        workflow = await self._get_workflow_or_raise(workflow_id, tenant_id)

        instance = DocumentApprovalInstance(
            document_id=document_id,
            workflow_id=workflow_id,
            current_step=1,
            status="pending",
        )

        if workflow.auto_escalate_after_days:
            instance.due_date = datetime.now(timezone.utc) + timedelta(days=workflow.auto_escalate_after_days)

        document.status = "pending_approval"

        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {
            "instance_id": instance.id,
            "message": "Document submitted for approval",
            "current_step": 1,
            "due_date": instance.due_date.isoformat() if instance.due_date else None,
        }

    async def take_approval_action(
        self,
        instance_id: int,
        action_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Record an approval action (approved / rejected / returned / delegated).

        Raises:
            LookupError: If the approval instance is not found.
        """
        instance = await self._get_approval_instance_or_raise(instance_id, tenant_id)
        data = action_data.model_dump()

        action = DocumentApprovalAction(
            instance_id=instance_id,
            workflow_step=instance.current_step,
            approver_id=1,
            approver_name="Current User",
            action=data["action"],
            comments=data.get("comments"),
            conditions=data.get("conditions"),
            delegated_to=data.get("delegated_to"),
        )
        self.db.add(action)

        wf_result = await self.db.execute(
            select(DocumentApprovalWorkflow).where(DocumentApprovalWorkflow.id == instance.workflow_id)
        )
        workflow = wf_result.scalar_one_or_none()

        doc_result = await self.db.execute(
            select(ControlledDocument).where(ControlledDocument.id == instance.document_id)
        )
        document = doc_result.scalar_one_or_none()

        if data["action"] == "approved":
            workflow_steps = workflow.workflow_steps if workflow else []
            if instance.current_step >= len(workflow_steps):
                instance.status = "approved"
                instance.completed_date = datetime.now(timezone.utc)
                instance.final_decision = "approved"
                if document:
                    document.status = "approved"
                    document.approved_date = datetime.now(timezone.utc)
                    document.effective_date = datetime.now(timezone.utc)
                    review_months: int = getattr(document, "review_frequency_months", 12) or 12
                    document.next_review_date = datetime.now(timezone.utc) + timedelta(days=review_months * 30)
            else:
                instance.current_step += 1

        elif data["action"] == "rejected":
            instance.status = "rejected"
            instance.completed_date = datetime.now(timezone.utc)
            instance.final_decision = "rejected"
            instance.final_comments = data.get("comments")
            if document:
                document.status = "draft"

        elif data["action"] == "returned":
            if document:
                document.status = "draft"

        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {
            "message": f"Action '{data['action']}' recorded",
            "instance_status": instance.status,
            "current_step": instance.current_step,
        }

    # ------------------------------------------------------------------
    # Distribution
    # ------------------------------------------------------------------

    async def distribute_document(
        self,
        document_id: int,
        distribution_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Distribute a document to a recipient.

        Raises:
            LookupError: If the document is not found.
        """
        await self._get_document_or_raise(document_id, tenant_id)

        dist = DocumentDistribution(
            document_id=document_id,
            notified_date=datetime.now(timezone.utc),
            **distribution_data.model_dump(),
        )
        self.db.add(dist)
        await self.db.commit()
        await self.db.refresh(dist)
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        recipient_name = distribution_data.model_dump().get("recipient_name", "recipient")
        return {
            "id": dist.id,
            "message": f"Document distributed to {recipient_name}",
            "copy_number": dist.copy_number,
        }

    async def acknowledge_distribution(
        self,
        document_id: int,
        distribution_id: int,
    ) -> dict[str, Any]:
        """Acknowledge receipt of a distributed document.

        Raises:
            LookupError: If the distribution is not found.
        """
        result = await self.db.execute(
            select(DocumentDistribution).where(
                DocumentDistribution.id == distribution_id,
                DocumentDistribution.document_id == document_id,
            )
        )
        dist = result.scalar_one_or_none()
        if not dist:
            raise LookupError(f"Distribution {distribution_id} not found for document {document_id}")

        dist.acknowledged = True
        dist.acknowledged_date = datetime.now(timezone.utc)
        await self.db.commit()

        return {"message": "Acknowledgment recorded"}

    # ------------------------------------------------------------------
    # Obsolete handling
    # ------------------------------------------------------------------

    async def mark_obsolete(
        self,
        document_id: int,
        obsolete_data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Mark a document as obsolete and create a retention record.

        Raises:
            LookupError: If the document is not found.
        """
        document = await self._get_document_or_raise(document_id, tenant_id)
        data = obsolete_data.model_dump()

        document.status = "obsolete"
        document.is_current = False
        document.obsolete_date = datetime.now(timezone.utc)
        document.obsolete_reason = data["obsolete_reason"]
        document.superseded_by = data.get("superseded_by_id")

        record = ObsoleteDocumentRecord(
            document_id=document_id,
            obsolete_date=datetime.now(timezone.utc),
            obsolete_reason=data["obsolete_reason"],
            superseded_by_id=data.get("superseded_by_id"),
            retention_required=True,
            retention_end_date=datetime.now(timezone.utc)
            + timedelta(days=int(getattr(document, "retention_period_years", 7) or 7) * 365),
        )
        self.db.add(record)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "document_control")
        track_metric("document.mutation", 1)

        return {
            "message": "Document marked as obsolete",
            "retention_end_date": record.retention_end_date.isoformat() if record.retention_end_date else None,
        }

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    async def get_summary(self, *, tenant_id: int | None) -> dict[str, Any]:
        tenant_filter = ControlledDocument.tenant_id == tenant_id  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

        total_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(ControlledDocument.is_current == True, tenant_filter)  # noqa: E712
        )
        total = total_result.scalar_one()

        active_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(
                ControlledDocument.status == "active",
                ControlledDocument.is_current == True,  # noqa: E712
                tenant_filter,
            )
        )
        active = active_result.scalar_one()

        draft_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(
                ControlledDocument.status == "draft",
                ControlledDocument.is_current == True,  # noqa: E712
                tenant_filter,
            )
        )
        draft = draft_result.scalar_one()

        pending_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(
                ControlledDocument.status == "pending_approval",
                ControlledDocument.is_current == True,  # noqa: E712
                tenant_filter,
            )
        )
        pending_approval = pending_result.scalar_one()

        overdue_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(
                ControlledDocument.next_review_date < datetime.now(timezone.utc),
                ControlledDocument.status == "active",
                ControlledDocument.is_current == True,  # noqa: E712
                tenant_filter,
            )
        )
        overdue_review = overdue_result.scalar_one()

        obsolete_result = await self.db.execute(
            select(func.count())
            .select_from(ControlledDocument)
            .where(
                ControlledDocument.status == "obsolete",
                tenant_filter,
            )
        )
        obsolete = obsolete_result.scalar_one()

        pending_ack_result = await self.db.execute(
            select(func.count())
            .select_from(DocumentDistribution)
            .where(
                DocumentDistribution.acknowledged == False,  # noqa: E712
                DocumentDistribution.acknowledgment_required == True,  # noqa: E712
            )
        )
        pending_ack = pending_ack_result.scalar_one()

        by_type_result = await self.db.execute(
            select(ControlledDocument.document_type, func.count(ControlledDocument.id))
            .where(ControlledDocument.is_current == True, tenant_filter)  # noqa: E712
            .group_by(ControlledDocument.document_type)
        )
        by_type = by_type_result.all()

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

    # ------------------------------------------------------------------
    # Access logs
    # ------------------------------------------------------------------

    async def get_access_log(self, document_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(DocumentAccessLog)
            .where(DocumentAccessLog.document_id == document_id)
            .order_by(DocumentAccessLog.timestamp.desc())
            .limit(limit)
        )
        logs = result.scalars().all()

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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_document_or_raise(self, document_id: int, tenant_id: int | None) -> ControlledDocument:
        result = await self.db.execute(
            select(ControlledDocument).where(
                ControlledDocument.id == document_id,
                ControlledDocument.tenant_id == tenant_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise LookupError(f"Document with ID {document_id} not found")
        return document

    async def _get_workflow_or_raise(self, workflow_id: int, tenant_id: int | None) -> DocumentApprovalWorkflow:
        result = await self.db.execute(
            select(DocumentApprovalWorkflow).where(
                DocumentApprovalWorkflow.id == workflow_id,
                DocumentApprovalWorkflow.tenant_id == tenant_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise LookupError(f"Workflow with ID {workflow_id} not found")
        return workflow

    async def _get_approval_instance_or_raise(
        self, instance_id: int, tenant_id: int | None
    ) -> DocumentApprovalInstance:
        result = await self.db.execute(
            select(DocumentApprovalInstance).where(
                DocumentApprovalInstance.id == instance_id,
                DocumentApprovalInstance.tenant_id == tenant_id,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            )
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise LookupError(f"Approval instance with ID {instance_id} not found")
        return instance
