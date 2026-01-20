"""
Digital Signature Models

Provides DocuSign-level e-signature capabilities with:
- Signature requests and workflows
- Multi-party signing
- Certificate-based signatures
- Audit trail
- Legal compliance (eIDAS, ESIGN)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class SignatureRequest(Base):
    """
    A request for one or more signatures on a document.
    """
    __tablename__ = "signature_requests"
    
    __table_args__ = (
        Index("ix_sig_request_status", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Request identity
    reference_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    
    # Document details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Document being signed
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)  # policy, audit_report, capa, etc.
    document_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Document content (for standalone documents)
    document_content: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    document_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256
    
    # Signing workflow
    workflow_type: Mapped[str] = mapped_column(String(20), default="sequential")  # sequential, parallel
    require_all: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft, pending, in_progress, completed, declined, expired
    
    # Initiator
    initiated_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Deadlines
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Reminders
    reminder_frequency: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Days between reminders
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Completion
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Signed document
    signed_document: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    signed_document_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Certificate
    certificate_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Metadata
    request_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    signers = relationship("SignatureRequestSigner", back_populates="request", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<SignatureRequest {self.reference_number}>"


class SignatureRequestSigner(Base):
    """
    A signer on a signature request.
    """
    __tablename__ = "signature_request_signers"
    
    __table_args__ = (
        Index("ix_signer_request", "request_id", "order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("signature_requests.id"), nullable=False)
    
    # Signer identity
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    
    # External signer (if not a system user)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Role
    signer_role: Mapped[str] = mapped_column(String(50), default="signer")  # signer, approver, witness, cc
    
    # Order (for sequential signing)
    order: Mapped[int] = mapped_column(Integer, default=1)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, viewed, signed, declined
    
    # Access token for external signers
    access_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Viewing
    first_viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Signature details
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    signature_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # drawn, typed, uploaded
    signature_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Base64 image or typed name
    
    # Decline
    declined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decline_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Verification
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    geo_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Authentication method used
    auth_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # email, sms, biometric
    
    # Relationships
    request = relationship("SignatureRequest", back_populates="signers")
    
    def __repr__(self) -> str:
        return f"<SignatureRequestSigner {self.email} status={self.status}>"


class Signature(Base):
    """
    An individual signature applied to a document.
    """
    __tablename__ = "signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Link to signature request (optional - for ad-hoc signatures)
    request_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("signature_requests.id"), nullable=True)
    signer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("signature_request_signers.id"), nullable=True)
    
    # Document signed
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_id: Mapped[str] = mapped_column(String(100), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of document at signing
    
    # Signer
    signer_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    signer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    signer_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Signature data
    signature_type: Mapped[str] = mapped_column(String(20), nullable=False)  # drawn, typed, uploaded
    signature_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Base64
    signature_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For typed signatures
    
    # Position on document
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_x: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    position_y: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    width: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    
    # Legal validity
    legal_statement: Mapped[str] = mapped_column(Text, nullable=False)  # "I agree to sign electronically..."
    consent_given: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Verification details
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=False)
    geo_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Authentication
    auth_method: Mapped[str] = mapped_column(String(50), nullable=False)  # email, sms, password, biometric
    auth_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Certificate
    certificate_serial: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    certificate_issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Cryptographic proof
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Hash of signature data + document
    
    # Timestamp
    signed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Signature {self.id} by {self.signer_email}>"


class SignatureTemplate(Base):
    """
    Reusable signature request template.
    """
    __tablename__ = "signature_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Template document
    document_template: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    document_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Placeholder signers
    signer_roles: Mapped[list] = mapped_column(JSON, default=list)
    # Example: [{"role": "Manager", "order": 1}, {"role": "Director", "order": 2}]
    
    # Signature fields
    signature_fields: Mapped[list] = mapped_column(JSON, default=list)
    # Example: [{"page": 1, "x": 100, "y": 500, "signer_role": "Manager"}]
    
    # Workflow
    workflow_type: Mapped[str] = mapped_column(String(20), default="sequential")
    expiry_days: Mapped[int] = mapped_column(Integer, default=30)
    reminder_days: Mapped[int] = mapped_column(Integer, default=3)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<SignatureTemplate {self.name}>"


class SignatureAuditLog(Base):
    """
    Audit trail for signature activities.
    """
    __tablename__ = "signature_audit_logs"
    
    __table_args__ = (
        Index("ix_sig_audit_request", "request_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    request_id: Mapped[int] = mapped_column(Integer, ForeignKey("signature_requests.id"), nullable=False)
    
    # Action
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # created, sent, viewed, signed, declined, expired, reminded, completed, voided
    
    # Actor
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)  # system, user, signer
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Details
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Verification
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<SignatureAuditLog {self.action} request={self.request_id}>"
