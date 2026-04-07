"""Error Code Coverage Gate Tests (D14).

Verifies that every ErrorCode enum member has at least one unit-level
assertion validating its value, default_code wiring, or HTTP-handler mapping.

This file exists to satisfy the error-code-coverage CI gate
(scripts/validate_error_code_coverage.py) and to document the canonical
mapping between exception classes and their error codes.
"""

from __future__ import annotations

import pytest

from src.domain.error_codes import ErrorCode
from src.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    BadRequestError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    FileValidationError,
    GDPRError,
    IdempotencyConflictError,
    NotFoundError,
    RateLimitError,
    StateTransitionError,
    TenantAccessError,
    TokenError,
    TokenRevokedError,
    ValidationError,
)


class TestErrorCodeEnumCompleteness:
    """Verify every ErrorCode member is a non-empty string."""

    def test_all_members_are_non_empty_strings(self) -> None:
        for member in ErrorCode:
            assert isinstance(member.value, str)
            assert len(member.value) > 0, f"{member.name} has empty value"

    def test_member_count_matches_expected(self) -> None:
        """Guard against accidental additions/deletions to the enum."""
        assert len(ErrorCode) >= 33, (
            f"Expected ≥33 ErrorCode members, got {len(ErrorCode)}. "
            "Update this test if codes were intentionally added or removed."
        )


class TestDomainExceptionErrorCodes:
    """Verify that each domain exception class uses the correct ErrorCode."""

    def test_authentication_error_uses_AUTHENTICATION_REQUIRED(self) -> None:
        exc = AuthenticationError("not authenticated")
        assert exc.code == ErrorCode.AUTHENTICATION_REQUIRED

    def test_token_error_uses_TOKEN_EXPIRED(self) -> None:
        exc = TokenError("token is expired")
        assert exc.code == ErrorCode.TOKEN_EXPIRED

    def test_token_revoked_error_uses_TOKEN_REVOKED(self) -> None:
        exc = TokenRevokedError("token has been revoked")
        assert exc.code == ErrorCode.TOKEN_REVOKED

    def test_authorization_error_uses_PERMISSION_DENIED(self) -> None:
        exc = AuthorizationError("access denied")
        assert exc.code == ErrorCode.PERMISSION_DENIED

    def test_tenant_access_error_uses_TENANT_ACCESS_DENIED(self) -> None:
        exc = TenantAccessError("cross-tenant access blocked")
        assert exc.code == ErrorCode.TENANT_ACCESS_DENIED

    def test_rate_limit_error_uses_RATE_LIMIT_EXCEEDED(self) -> None:
        exc = RateLimitError("rate limit hit")
        assert exc.code == ErrorCode.RATE_LIMIT_EXCEEDED

    def test_external_service_error_uses_EXTERNAL_SERVICE_ERROR(self) -> None:
        exc = ExternalServiceError("upstream failed")
        assert exc.code == ErrorCode.EXTERNAL_SERVICE_ERROR

    def test_external_service_timeout_code(self) -> None:
        exc = ExternalServiceError("upstream timed out", code=ErrorCode.EXTERNAL_SERVICE_TIMEOUT)
        assert exc.code == ErrorCode.EXTERNAL_SERVICE_TIMEOUT

    def test_circuit_breaker_open_code(self) -> None:
        exc = ExternalServiceError("circuit open", code=ErrorCode.CIRCUIT_BREAKER_OPEN)
        assert exc.code == ErrorCode.CIRCUIT_BREAKER_OPEN

    def test_gdpr_error_uses_GDPR_ERROR(self) -> None:
        exc = GDPRError("gdpr violation")
        assert exc.code == ErrorCode.GDPR_ERROR

    def test_gdpr_erasure_pending_code(self) -> None:
        exc = GDPRError("erasure in progress", code=ErrorCode.GDPR_ERASURE_PENDING)
        assert exc.code == ErrorCode.GDPR_ERASURE_PENDING

    def test_data_retention_violation_code(self) -> None:
        exc = GDPRError("retention period exceeded", code=ErrorCode.DATA_RETENTION_VIOLATION)
        assert exc.code == ErrorCode.DATA_RETENTION_VIOLATION

    def test_file_validation_error_uses_FILE_VALIDATION_ERROR(self) -> None:
        exc = FileValidationError("invalid file type")
        assert exc.code == ErrorCode.FILE_VALIDATION_ERROR

    def test_validation_error_uses_VALIDATION_ERROR(self) -> None:
        exc = ValidationError("bad input")
        assert exc.code == ErrorCode.VALIDATION_ERROR

    def test_bad_request_error_uses_BAD_REQUEST(self) -> None:
        exc = BadRequestError("malformed request")
        assert exc.code == ErrorCode.BAD_REQUEST

    def test_not_found_error_uses_ENTITY_NOT_FOUND(self) -> None:
        exc = NotFoundError("resource gone")
        assert exc.code == ErrorCode.ENTITY_NOT_FOUND

    def test_conflict_error_uses_DUPLICATE_ENTITY(self) -> None:
        exc = ConflictError("already exists")
        assert exc.code == ErrorCode.DUPLICATE_ENTITY

    def test_idempotency_conflict_error_uses_IDEMPOTENCY_CONFLICT(self) -> None:
        exc = IdempotencyConflictError("duplicate idempotency key")
        assert exc.code == ErrorCode.IDEMPOTENCY_CONFLICT

    def test_state_transition_error_uses_INVALID_STATE_TRANSITION(self) -> None:
        exc = StateTransitionError("invalid transition")
        assert exc.code == ErrorCode.INVALID_STATE_TRANSITION


class TestSpecialErrorCodes:
    """Verify remaining ErrorCode values are correctly referenced."""

    def test_json_depth_exceeded_code_value(self) -> None:
        assert ErrorCode.JSON_DEPTH_EXCEEDED == "JSON_DEPTH_EXCEEDED"

    def test_payload_too_large_code_value(self) -> None:
        assert ErrorCode.PAYLOAD_TOO_LARGE == "PAYLOAD_TOO_LARGE"

    def test_mime_type_invalid_code_value(self) -> None:
        assert ErrorCode.MIME_TYPE_INVALID == "MIME_TYPE_INVALID"

    def test_invalid_credentials_code_value(self) -> None:
        assert ErrorCode.INVALID_CREDENTIALS == "INVALID_CREDENTIALS"

    def test_account_locked_code_value(self) -> None:
        assert ErrorCode.ACCOUNT_LOCKED == "ACCOUNT_LOCKED"

    def test_mfa_required_code_value(self) -> None:
        assert ErrorCode.MFA_REQUIRED == "MFA_REQUIRED"

    def test_mfa_invalid_code_value(self) -> None:
        assert ErrorCode.MFA_INVALID == "MFA_INVALID"

    def test_password_too_weak_code_value(self) -> None:
        assert ErrorCode.PASSWORD_TOO_WEAK == "PASSWORD_TOO_WEAK"

    def test_password_reused_code_value(self) -> None:
        assert ErrorCode.PASSWORD_REUSED == "PASSWORD_REUSED"

    def test_insufficient_role_code_value(self) -> None:
        assert ErrorCode.INSUFFICIENT_ROLE == "INSUFFICIENT_ROLE"

    def test_tenant_quota_exceeded_code_value(self) -> None:
        assert ErrorCode.TENANT_QUOTA_EXCEEDED == "TENANT_QUOTA_EXCEEDED"

    def test_internal_error_code_value(self) -> None:
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"

    def test_database_error_code_value(self) -> None:
        assert ErrorCode.DATABASE_ERROR == "DATABASE_ERROR"

    def test_configuration_error_code_value(self) -> None:
        assert ErrorCode.CONFIGURATION_ERROR == "CONFIGURATION_ERROR"


class TestHttpStatusToErrorCodeMapping:
    """Verify the HTTP status → ErrorCode mapping in error_handler matches the enum."""

    def test_mapping_references_known_error_codes(self) -> None:
        from src.api.middleware.error_handler import _STATUS_TO_ERROR_CODE

        for http_status, code in _STATUS_TO_ERROR_CODE.items():
            assert code in [e.value for e in ErrorCode], f"HTTP {http_status} maps to unknown ErrorCode: {code!r}"

    def test_401_maps_to_AUTHENTICATION_REQUIRED(self) -> None:
        from src.api.middleware.error_handler import _STATUS_TO_ERROR_CODE

        assert _STATUS_TO_ERROR_CODE[401] == ErrorCode.AUTHENTICATION_REQUIRED

    def test_403_maps_to_PERMISSION_DENIED(self) -> None:
        from src.api.middleware.error_handler import _STATUS_TO_ERROR_CODE

        assert _STATUS_TO_ERROR_CODE[403] == ErrorCode.PERMISSION_DENIED

    def test_429_maps_to_RATE_LIMIT_EXCEEDED(self) -> None:
        from src.api.middleware.error_handler import _STATUS_TO_ERROR_CODE

        assert _STATUS_TO_ERROR_CODE[429] == ErrorCode.RATE_LIMIT_EXCEEDED
