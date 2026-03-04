"""API routes package."""

from src.api.routes import (
    audits,
    auth,
    complaints,
    feature_flags,
    incidents,
    near_miss,
    policies,
    risks,
    rtas,
    standards,
    users,
)

__all__ = [
    "auth",
    "users",
    "standards",
    "audits",
    "risks",
    "incidents",
    "rtas",
    "complaints",
    "policies",
    "near_miss",
    "feature_flags",
]
