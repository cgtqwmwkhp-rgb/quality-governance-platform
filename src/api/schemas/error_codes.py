"""API-layer re-export of domain error codes.

Single source of truth: ``src.domain.error_codes.ErrorCode``.
This module re-exports for convenient access from API routes without
violating import boundaries (API routes import from ``api.schemas``,
which in turn imports from ``domain``).
"""

from src.domain.error_codes import ErrorCode

__all__ = ["ErrorCode"]
