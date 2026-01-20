"""
Immutable Audit Trail Models

Provides blockchain-style immutable audit logging with:
- Cryptographic hash chain
- Tamper detection
- Complete change history
- Compliance-grade audit trail
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class AuditLogEntry(Base):
    """
    Immutable audit log entry with blockchain-style hash chain.
    
    Each entry contains:
    - What changed (entity, action, old/new values)
    - Who made the change
    - When it happened
    - Cryptographic hash linking to previous entry
    """
    __tablename__ = "audit_log_entries"
    
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_user", "user_id", "timestamp"),
        Index("ix_audit_log_tenant", "tenant_id", "timestamp"),
        Index("ix_audit_log_action", "action", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Multi-tenancy
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    
    # Entry sequence for hash chain
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Blockchain-style hash chain
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)  # SHA-256
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Link to previous entry
    
    # What changed
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # incident, audit, risk, etc.
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)  # ID of the entity
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Human-readable name
    
    # Action performed
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # create, update, delete, view, export, approve, etc.
    action_category: Mapped[str] = mapped_column(String(50), default="data")  # data, auth, admin, system
    
    # Change details
    old_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of field names that changed
    
    # Who made the change
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Denormalized for immutability
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 compatible
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Geolocation (optional)
    geo_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    geo_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Additional metadata
    entry_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Timestamp (UTC)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Compliance flags
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)  # PII or sensitive data
    retention_days: Mapped[int] = mapped_column(Integer, default=2555)  # 7 years default
    
    def __repr__(self) -> str:
        return f"<AuditLogEntry {self.id} {self.action} {self.entity_type}:{self.entity_id}>"
    
    @staticmethod
    def compute_hash(
        sequence: int,
        previous_hash: str,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: Optional[int],
        timestamp: datetime,
        old_values: Optional[dict],
        new_values: Optional[dict],
    ) -> str:
        """
        Compute SHA-256 hash for the audit entry.
        
        This creates an immutable chain where tampering with any entry
        would invalidate all subsequent hashes.
        """
        data = {
            "sequence": sequence,
            "previous_hash": previous_hash,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "action": action,
            "user_id": user_id,
            "timestamp": timestamp.isoformat(),
            "old_values": old_values,
            "new_values": new_values,
        }
        
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()


class AuditLogVerification(Base):
    """
    Periodic verification records for the audit chain.
    
    Stores verification checkpoints to detect tampering.
    """
    __tablename__ = "audit_log_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Verification range
    start_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    end_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Verification result
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    entries_verified: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_entries: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    
    # Merkle root (optional advanced verification)
    merkle_root: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Metadata
    verified_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    verification_method: Mapped[str] = mapped_column(String(50), default="hash_chain")
    
    # Timestamps
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<AuditLogVerification {self.id} valid={self.is_valid}>"


class AuditLogExport(Base):
    """
    Records of audit log exports for compliance.
    """
    __tablename__ = "audit_log_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False)
    
    # Export details
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)  # csv, json, pdf
    export_type: Mapped[str] = mapped_column(String(50), nullable=False)  # full, filtered, date_range
    
    # Filters applied
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    date_from: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    date_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Result
    entries_exported: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256 of export file
    
    # Metadata
    exported_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    exported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
