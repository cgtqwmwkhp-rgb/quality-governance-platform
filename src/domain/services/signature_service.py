"""
Digital Signature Service

Provides DocuSign-level e-signature capabilities with:
- Signature request management
- Multi-party workflows
- Legal compliance
- Audit trail
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.digital_signature import (
    Signature,
    SignatureAuditLog,
    SignatureRequest,
    SignatureRequestSigner,
    SignatureTemplate,
)


class SignatureService:
    """
    Digital signature management service.
    """

    LEGAL_STATEMENT = (
        "By signing this document electronically, I agree that my electronic signature "
        "is the legal equivalent of my manual signature. I consent to the use of electronic "
        "signatures, and I understand that I am legally bound by this agreement."
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Signature Requests
    # =========================================================================

    async def create_request(
        self,
        tenant_id: int,
        title: str,
        initiated_by_id: int,
        document_type: str,
        document_id: Optional[str] = None,
        description: Optional[str] = None,
        document_content: Optional[bytes] = None,
        document_filename: Optional[str] = None,
        document_mime_type: Optional[str] = None,
        workflow_type: str = "sequential",
        require_all: bool = True,
        expires_in_days: int = 30,
        reminder_frequency: int = 3,
        signers: Optional[list[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> SignatureRequest:
        """Create a new signature request."""
        reference = f"SIG-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

        document_hash = None
        if document_content:
            document_hash = hashlib.sha256(document_content).hexdigest()

        request = SignatureRequest(
            tenant_id=tenant_id,
            reference_number=reference,
            title=title,
            description=description,
            document_type=document_type,
            document_id=document_id,
            document_content=document_content,
            document_filename=document_filename,
            document_mime_type=document_mime_type,
            document_hash=document_hash,
            workflow_type=workflow_type,
            require_all=require_all,
            initiated_by_id=initiated_by_id,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            reminder_frequency=reminder_frequency,
            request_metadata=metadata or {},
        )

        self.db.add(request)
        await self.db.flush()

        if signers:
            for i, signer_data in enumerate(signers):
                signer = SignatureRequestSigner(
                    request_id=request.id,
                    user_id=signer_data.get("user_id"),
                    email=signer_data["email"],
                    name=signer_data["name"],
                    signer_role=signer_data.get("role", "signer"),
                    order=signer_data.get("order", i + 1),
                    access_token=secrets.token_urlsafe(32),
                    token_expires_at=request.expires_at,
                )
                self.db.add(signer)

        await self._log_action(
            tenant_id=tenant_id,
            request_id=request.id,
            action="created",
            actor_type="user",
            actor_id=initiated_by_id,
        )

        await self.db.commit()
        await self.db.refresh(request)

        return request

    async def get_request(self, request_id: int) -> Optional[SignatureRequest]:
        """Get a signature request by ID."""
        result = await self.db.execute(select(SignatureRequest).where(SignatureRequest.id == request_id))
        return result.scalar_one_or_none()

    async def get_request_by_reference(self, reference: str) -> Optional[SignatureRequest]:
        """Get a signature request by reference number."""
        result = await self.db.execute(select(SignatureRequest).where(SignatureRequest.reference_number == reference))
        return result.scalar_one_or_none()

    async def send_request(self, request_id: int) -> SignatureRequest:
        """Send a signature request to signers."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status not in ["draft"]:
            raise ValueError(f"Request is already {request.status}")

        request.status = "pending"

        await self._log_action(
            tenant_id=request.tenant_id,
            request_id=request.id,
            action="sent",
            actor_type="system",
        )

        await self.db.commit()
        await self.db.refresh(request)

        return request

    async def void_request(
        self,
        request_id: int,
        voided_by_id: int,
        reason: Optional[str] = None,
    ) -> SignatureRequest:
        """Void a signature request."""
        request = await self.get_request(request_id)
        if not request:
            raise ValueError(f"Request {request_id} not found")

        if request.status in ["completed", "expired"]:
            raise ValueError(f"Cannot void a {request.status} request")

        request.status = "voided"

        await self._log_action(
            tenant_id=request.tenant_id,
            request_id=request.id,
            action="voided",
            actor_type="user",
            actor_id=voided_by_id,
            details={"reason": reason},
        )

        await self.db.commit()
        await self.db.refresh(request)

        return request

    # =========================================================================
    # Signing
    # =========================================================================

    async def get_signer_by_token(self, token: str) -> Optional[SignatureRequestSigner]:
        """Get a signer by their access token."""
        result = await self.db.execute(
            select(SignatureRequestSigner).where(
                SignatureRequestSigner.access_token == token,
                SignatureRequestSigner.token_expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def record_view(
        self,
        signer_id: int,
        ip_address: str,
        user_agent: str,
    ) -> SignatureRequestSigner:
        """Record that a signer viewed the document."""
        result = await self.db.execute(select(SignatureRequestSigner).where(SignatureRequestSigner.id == signer_id))
        signer = result.scalar_one_or_none()
        if not signer:
            raise ValueError(f"Signer {signer_id} not found")

        now = datetime.utcnow()

        if not signer.first_viewed_at:
            signer.first_viewed_at = now
        signer.last_viewed_at = now

        if signer.status == "pending":
            signer.status = "viewed"

        signer.ip_address = ip_address
        signer.user_agent = user_agent

        await self._log_action(
            tenant_id=signer.request.tenant_id,
            request_id=signer.request_id,
            action="viewed",
            actor_type="signer",
            actor_email=signer.email,
            actor_name=signer.name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.db.commit()
        await self.db.refresh(signer)

        return signer

    async def sign(
        self,
        signer_id: int,
        signature_type: str,
        signature_data: str,
        ip_address: str,
        user_agent: str,
        auth_method: str = "email",
        geo_location: Optional[str] = None,
    ) -> Signature:
        """Apply a signature."""
        result = await self.db.execute(select(SignatureRequestSigner).where(SignatureRequestSigner.id == signer_id))
        signer = result.scalar_one_or_none()
        if not signer:
            raise ValueError(f"Signer {signer_id} not found")

        request = signer.request

        if signer.status == "signed":
            raise ValueError("Already signed")
        if signer.status == "declined":
            raise ValueError("Signer declined")
        if request.status not in ["pending", "in_progress"]:
            raise ValueError(f"Request is {request.status}")

        if request.workflow_type == "sequential":
            result = await self.db.execute(
                select(func.count())
                .select_from(SignatureRequestSigner)
                .where(
                    SignatureRequestSigner.request_id == request.id,
                    SignatureRequestSigner.order < signer.order,
                    SignatureRequestSigner.status != "signed",
                    SignatureRequestSigner.signer_role != "cc",
                )
            )
            pending_before = result.scalar_one()
            if pending_before > 0:
                raise ValueError("Waiting for previous signers")

        now = datetime.utcnow()

        signer.status = "signed"
        signer.signed_at = now
        signer.signature_type = signature_type
        signer.signature_data = signature_data
        signer.ip_address = ip_address
        signer.user_agent = user_agent
        signer.geo_location = geo_location
        signer.auth_method = auth_method

        signature_hash = hashlib.sha256(
            f"{signature_data}{request.document_hash}{now.isoformat()}".encode()
        ).hexdigest()

        signature = Signature(
            tenant_id=request.tenant_id,
            request_id=request.id,
            signer_id=signer.id,
            document_type=request.document_type,
            document_id=request.document_id or str(request.id),
            document_hash=request.document_hash or "",
            signer_user_id=signer.user_id,
            signer_name=signer.name,
            signer_email=signer.email,
            signature_type=signature_type,
            signature_image=signature_data if signature_type == "drawn" else None,
            signature_text=signature_data if signature_type == "typed" else None,
            legal_statement=self.LEGAL_STATEMENT,
            ip_address=ip_address,
            user_agent=user_agent,
            geo_location=geo_location,
            auth_method=auth_method,
            auth_timestamp=now,
            signature_hash=signature_hash,
        )
        self.db.add(signature)

        await self._log_action(
            tenant_id=request.tenant_id,
            request_id=request.id,
            action="signed",
            actor_type="signer",
            actor_email=signer.email,
            actor_name=signer.name,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"signature_type": signature_type},
        )

        request.status = "in_progress"

        await self._check_completion(request)

        await self.db.commit()
        await self.db.refresh(signature)

        return signature

    async def decline(
        self,
        signer_id: int,
        reason: str,
        ip_address: str,
        user_agent: str,
    ) -> SignatureRequestSigner:
        """Decline to sign."""
        result = await self.db.execute(select(SignatureRequestSigner).where(SignatureRequestSigner.id == signer_id))
        signer = result.scalar_one_or_none()
        if not signer:
            raise ValueError(f"Signer {signer_id} not found")

        request = signer.request

        if signer.status in ["signed", "declined"]:
            raise ValueError(f"Already {signer.status}")

        now = datetime.utcnow()

        signer.status = "declined"
        signer.declined_at = now
        signer.decline_reason = reason
        signer.ip_address = ip_address
        signer.user_agent = user_agent

        if request.require_all:
            request.status = "declined"

        await self._log_action(
            tenant_id=request.tenant_id,
            request_id=request.id,
            action="declined",
            actor_type="signer",
            actor_email=signer.email,
            actor_name=signer.name,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"reason": reason},
        )

        await self.db.commit()
        await self.db.refresh(signer)

        return signer

    async def _check_completion(self, request: SignatureRequest) -> bool:
        """Check if all required signatures are complete."""
        result = await self.db.execute(
            select(SignatureRequestSigner).where(
                SignatureRequestSigner.request_id == request.id,
                SignatureRequestSigner.signer_role.in_(["signer", "approver"]),
            )
        )
        required_signers = result.scalars().all()

        signed_count = sum(1 for s in required_signers if s.status == "signed")

        if request.require_all:
            complete = signed_count == len(required_signers)
        else:
            complete = signed_count >= 1

        if complete:
            request.status = "completed"
            request.completed_at = datetime.utcnow()

            await self._log_action(
                tenant_id=request.tenant_id,
                request_id=request.id,
                action="completed",
                actor_type="system",
            )

            return True

        return False

    # =========================================================================
    # Templates
    # =========================================================================

    async def create_template(
        self,
        tenant_id: int,
        name: str,
        created_by_id: int,
        description: Optional[str] = None,
        document_template: Optional[bytes] = None,
        document_filename: Optional[str] = None,
        signer_roles: Optional[list] = None,
        signature_fields: Optional[list] = None,
        workflow_type: str = "sequential",
        expiry_days: int = 30,
        reminder_days: int = 3,
    ) -> SignatureTemplate:
        """Create a reusable signature template."""
        template = SignatureTemplate(
            tenant_id=tenant_id,
            name=name,
            description=description,
            document_template=document_template,
            document_filename=document_filename,
            signer_roles=signer_roles or [],
            signature_fields=signature_fields or [],
            workflow_type=workflow_type,
            expiry_days=expiry_days,
            reminder_days=reminder_days,
            created_by_id=created_by_id,
        )

        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)

        return template

    async def create_from_template(
        self,
        template_id: int,
        initiated_by_id: int,
        signers: list[dict],
        title: Optional[str] = None,
        document_content: Optional[bytes] = None,
        metadata: Optional[dict] = None,
    ) -> SignatureRequest:
        """Create a signature request from a template."""
        result = await self.db.execute(select(SignatureTemplate).where(SignatureTemplate.id == template_id))
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError(f"Template {template_id} not found")

        return await self.create_request(
            tenant_id=template.tenant_id,
            title=title or f"{template.name} - {datetime.now().strftime('%Y-%m-%d')}",
            initiated_by_id=initiated_by_id,
            document_type="template",
            document_content=document_content or template.document_template,
            document_filename=template.document_filename,
            workflow_type=template.workflow_type,
            expires_in_days=template.expiry_days,
            reminder_frequency=template.reminder_days,
            signers=signers,
            metadata=metadata,
        )

    # =========================================================================
    # Queries
    # =========================================================================

    async def get_pending_requests(
        self,
        tenant_id: int,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
    ) -> list[SignatureRequest]:
        """Get pending signature requests for a user."""
        stmt = select(SignatureRequest).where(
            SignatureRequest.tenant_id == tenant_id,
            SignatureRequest.status.in_(["pending", "in_progress"]),
        )

        if user_id or email:
            stmt = stmt.join(SignatureRequestSigner).where(
                or_(
                    SignatureRequestSigner.user_id == user_id,
                    SignatureRequestSigner.email == email,
                ),
                SignatureRequestSigner.status.in_(["pending", "viewed"]),
            )

        stmt = stmt.order_by(SignatureRequest.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_completed_requests(
        self,
        tenant_id: int,
        limit: int = 50,
    ) -> list[SignatureRequest]:
        """Get completed signature requests."""
        result = await self.db.execute(
            select(SignatureRequest)
            .where(
                SignatureRequest.tenant_id == tenant_id,
                SignatureRequest.status == "completed",
            )
            .order_by(SignatureRequest.completed_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_audit_log(self, request_id: int) -> list[SignatureAuditLog]:
        """Get audit log for a signature request."""
        result = await self.db.execute(
            select(SignatureAuditLog)
            .where(SignatureAuditLog.request_id == request_id)
            .order_by(SignatureAuditLog.created_at)
        )
        return result.scalars().all()

    # =========================================================================
    # Reminders
    # =========================================================================

    async def send_reminders(self, tenant_id: int) -> int:
        """Send reminders for pending signatures. Returns count sent."""
        now = datetime.utcnow()
        reminder_count = 0

        result = await self.db.execute(
            select(SignatureRequest).where(
                SignatureRequest.tenant_id == tenant_id,
                SignatureRequest.status.in_(["pending", "in_progress"]),
                SignatureRequest.expires_at > now,
                SignatureRequest.reminder_frequency > 0,
            )
        )
        requests = result.scalars().all()

        for request in requests:
            if request.last_reminder_at:
                days_since = (now - request.last_reminder_at).days
                if days_since < request.reminder_frequency:
                    continue
            else:
                days_since_created = (now - request.created_at).days
                if days_since_created < 1:
                    continue

            pending_signers = [s for s in request.signers if s.status in ["pending", "viewed"]]

            if pending_signers:
                request.last_reminder_at = now

                await self._log_action(
                    tenant_id=tenant_id,
                    request_id=request.id,
                    action="reminded",
                    actor_type="system",
                    details={"signers": [s.email for s in pending_signers]},
                )

                reminder_count += len(pending_signers)

        await self.db.commit()
        return reminder_count

    async def expire_old_requests(self, tenant_id: int) -> int:
        """Expire requests past their deadline. Returns count expired."""
        now = datetime.utcnow()

        result = await self.db.execute(
            select(SignatureRequest).where(
                SignatureRequest.tenant_id == tenant_id,
                SignatureRequest.status.in_(["pending", "in_progress"]),
                SignatureRequest.expires_at < now,
            )
        )
        expired = result.scalars().all()

        for request in expired:
            request.status = "expired"

            await self._log_action(
                tenant_id=tenant_id,
                request_id=request.id,
                action="expired",
                actor_type="system",
            )

        await self.db.commit()
        return len(expired)

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _log_action(
        self,
        tenant_id: int,
        request_id: int,
        action: str,
        actor_type: str,
        actor_id: Optional[int] = None,
        actor_email: Optional[str] = None,
        actor_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> SignatureAuditLog:
        """Log a signature-related action."""
        log = SignatureAuditLog(
            tenant_id=tenant_id,
            request_id=request_id,
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)
        return log
