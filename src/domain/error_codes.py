"""Structured error codes for consistent error responses across all layers."""

from enum import Enum


class ErrorCode(str, Enum):
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    DUPLICATE_ENTITY = "DUPLICATE_ENTITY"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"

    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    FILE_VALIDATION_ERROR = "FILE_VALIDATION_ERROR"
    JSON_DEPTH_EXCEEDED = "JSON_DEPTH_EXCEEDED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    MIME_TYPE_INVALID = "MIME_TYPE_INVALID"

    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    MFA_REQUIRED = "MFA_REQUIRED"
    MFA_INVALID = "MFA_INVALID"
    PASSWORD_TOO_WEAK = "PASSWORD_TOO_WEAK"
    PASSWORD_REUSED = "PASSWORD_REUSED"

    PERMISSION_DENIED = "PERMISSION_DENIED"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"
    COMPETENCY_GATE_BLOCKED = "COMPETENCY_GATE_BLOCKED"

    # Deliberately not COMPETENCY_GATE_BLOCKED, which is a statement about the
    # person being assessed — they are not competent for the asset type, so the
    # run must not start. This one is a statement about the *assessor*: the
    # subject may well be due a demonstration, but the viewer cannot be the one
    # to witness it. Two clients already branch on COMPETENCY_GATE_BLOCKED to
    # explain the subject's gap, and folding the assessor's ineligibility into
    # it would make both of them say the wrong thing.
    #
    # It also carries an actionable sentence rather than "you lack permission" —
    # there is no permission to grant for "you cannot assess yourself" — so the
    # client is expected to render the server's message verbatim.
    ASSESSOR_NOT_ELIGIBLE = "ASSESSOR_NOT_ELIGIBLE"

    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    TENANT_QUOTA_EXCEEDED = "TENANT_QUOTA_EXCEEDED"

    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    EXTERNAL_SERVICE_TIMEOUT = "EXTERNAL_SERVICE_TIMEOUT"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"

    GDPR_ERROR = "GDPR_ERROR"
    GDPR_ERASURE_PENDING = "GDPR_ERASURE_PENDING"
    DATA_RETENTION_VIOLATION = "DATA_RETENTION_VIOLATION"

    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"

    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # Distinct from DATABASE_ERROR: the query did not fail, it was never asked,
    # because a table it needs is not in the database. Separate code so a client
    # can tell "we could not look" from "the lookup broke".
    MEASUREMENT_UNAVAILABLE = "MEASUREMENT_UNAVAILABLE"

    # The write counterpart of MEASUREMENT_UNAVAILABLE, and a different fact for
    # the user: not "we cannot tell you" but "we did not record what you just
    # did". Both arise from the same absent table, and a client that only wants
    # to know something went wrong can treat them alike, but calling a failed
    # ``POST /distribute`` a "measurement" would be its own small untruth in a
    # response whose purpose is to stop telling them.
    FEATURE_NOT_PROVISIONED = "FEATURE_NOT_PROVISIONED"
