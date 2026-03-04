"""Data retention configuration for GDPR compliance."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RetentionPolicy:
    entity: str
    retention_days: int
    soft_delete_first: bool = True
    requires_audit_log: bool = True


DEFAULT_RETENTION_POLICIES: Dict[str, RetentionPolicy] = {
    "incidents": RetentionPolicy(entity="incidents", retention_days=2555),  # 7 years
    "complaints": RetentionPolicy(entity="complaints", retention_days=2555),  # 7 years
    "near_misses": RetentionPolicy(entity="near_misses", retention_days=1825),  # 5 years
    "audit_runs": RetentionPolicy(entity="audit_runs", retention_days=2555),  # 7 years
    "audit_logs": RetentionPolicy(entity="audit_logs", retention_days=2555),  # 7 years
    "users_deleted": RetentionPolicy(entity="users", retention_days=365),  # 1 year post-deletion
    "session_logs": RetentionPolicy(entity="session_logs", retention_days=90),  # 90 days
}
