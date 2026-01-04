"""API routes package."""

from src.api.routes import audits, auth, complaints, incidents, policies, risks, rta, standards, users

__all__ = [
    "auth",
    "users",
    "standards",
    "audits",
    "risks",
    "incidents",
    "rta",
    "complaints",
    "policies",
]
