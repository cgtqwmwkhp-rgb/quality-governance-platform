"""Tests for domain exception hierarchy."""
import pytest
from src.domain.exceptions import (
    DomainError,
    NotFoundError,
    ConflictError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    TenantAccessError,
    StateTransitionError,
    RateLimitError,
    ExternalServiceError,
    IdempotencyConflictError,
    GDPRError,
    FileValidationError,
    TokenError,
    TokenRevokedError,
)


class TestDomainExceptions:
    def test_domain_error_base(self):
        err = DomainError("test message", code="TEST_CODE", details={"key": "val"})
        assert err.message == "test message"
        assert err.code == "TEST_CODE"
        assert err.details == {"key": "val"}
        assert err.http_status == 500

    def test_not_found_error(self):
        err = NotFoundError("entity not found")
        assert err.http_status == 404
        assert err.code == "ENTITY_NOT_FOUND"

    def test_conflict_error(self):
        err = ConflictError("duplicate")
        assert err.http_status == 409
        assert err.code == "DUPLICATE_ENTITY"

    def test_validation_error(self):
        err = ValidationError("invalid input")
        assert err.http_status == 422
        assert err.code == "VALIDATION_ERROR"

    def test_authentication_error(self):
        err = AuthenticationError("not authenticated")
        assert err.http_status == 401

    def test_authorization_error(self):
        err = AuthorizationError("forbidden")
        assert err.http_status == 403

    def test_tenant_access_inherits_authorization(self):
        err = TenantAccessError("wrong tenant")
        assert isinstance(err, AuthorizationError)
        assert err.http_status == 403
        assert err.code == "TENANT_ACCESS_DENIED"

    def test_state_transition_error(self):
        err = StateTransitionError("invalid transition")
        assert err.http_status == 409
        assert err.code == "INVALID_STATE_TRANSITION"

    def test_rate_limit_error(self):
        err = RateLimitError("too many requests")
        assert err.http_status == 429

    def test_external_service_error(self):
        err = ExternalServiceError("service unavailable")
        assert err.http_status == 502

    def test_idempotency_conflict_inherits_conflict(self):
        err = IdempotencyConflictError("duplicate key")
        assert isinstance(err, ConflictError)
        assert err.code == "IDEMPOTENCY_CONFLICT"

    def test_gdpr_error(self):
        err = GDPRError("erasure failed")
        assert err.http_status == 400

    def test_custom_code_override(self):
        err = NotFoundError("not found", code="CUSTOM_CODE")
        assert err.code == "CUSTOM_CODE"

    def test_default_details_empty(self):
        err = DomainError("msg")
        assert err.details == {}

    def test_exception_hierarchy(self):
        assert issubclass(NotFoundError, DomainError)
        assert issubclass(ConflictError, DomainError)
        assert issubclass(TenantAccessError, AuthorizationError)
        assert issubclass(IdempotencyConflictError, ConflictError)
        assert issubclass(FileValidationError, ValidationError)
        assert issubclass(TokenError, AuthenticationError)
        assert issubclass(TokenRevokedError, AuthenticationError)
