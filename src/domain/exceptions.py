"""Domain exception hierarchy for structured error handling.

All business-logic errors inherit from DomainError. The API layer maps
these to HTTP status codes via registered exception handlers, ensuring
a consistent error envelope across the entire platform.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all domain-layer errors."""

    http_status: int = 500
    default_code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or {}


class NotFoundError(DomainError):
    http_status = 404
    default_code = "ENTITY_NOT_FOUND"


class ConflictError(DomainError):
    http_status = 409
    default_code = "DUPLICATE_ENTITY"


class ValidationError(DomainError):
    http_status = 422
    default_code = "VALIDATION_ERROR"


class AuthenticationError(DomainError):
    http_status = 401
    default_code = "AUTHENTICATION_REQUIRED"


class AuthorizationError(DomainError):
    http_status = 403
    default_code = "PERMISSION_DENIED"


class TenantAccessError(AuthorizationError):
    default_code = "TENANT_ACCESS_DENIED"


class StateTransitionError(DomainError):
    http_status = 409
    default_code = "INVALID_STATE_TRANSITION"


class RateLimitError(DomainError):
    http_status = 429
    default_code = "RATE_LIMIT_EXCEEDED"


class ExternalServiceError(DomainError):
    http_status = 502
    default_code = "EXTERNAL_SERVICE_ERROR"


class IdempotencyConflictError(ConflictError):
    default_code = "IDEMPOTENCY_CONFLICT"


class GDPRError(DomainError):
    http_status = 400
    default_code = "GDPR_ERROR"


class FileValidationError(ValidationError):
    default_code = "FILE_VALIDATION_ERROR"


class TokenError(AuthenticationError):
    default_code = "TOKEN_EXPIRED"


class TokenRevokedError(AuthenticationError):
    default_code = "TOKEN_REVOKED"


class BadRequestError(DomainError):
    http_status = 400
    default_code = "BAD_REQUEST"


class MeasurementUnavailableError(DomainError):
    """A figure could not be measured because a table it reads is absent.

    503 rather than 500: the request is well-formed and the code is not broken,
    the database simply does not currently carry what the answer is made of.

    Raised rather than returned. A list endpoint's empty payload is ``[]``, and
    every consumer of one defends with ``items ?? []``, so an "unmeasurable"
    value handed back in-band gets coerced to "nothing to show" by the very
    idiom that makes clients robust. An exception has no such coercion: the
    caller either reports it or the request fails, and neither outcome can be
    mistaken for a measurement of zero.
    """

    http_status = 503
    default_code = "MEASUREMENT_UNAVAILABLE"

    def __init__(self, message: str, missing_tables: list[str] | tuple[str, ...]) -> None:
        super().__init__(
            message,
            details={"missing_tables": list(missing_tables)},
        )
        self.missing_tables = tuple(missing_tables)
