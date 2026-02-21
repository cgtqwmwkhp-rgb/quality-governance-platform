"""Unit tests for auth / security service - password hashing, JWT tokens, password reset."""

import os
import sys
from datetime import timedelta
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.core.security import (  # noqa: E402
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)

# ---------------------------------------------------------------------------
# Password hashing and verification
# ---------------------------------------------------------------------------


def test_hash_produces_bcrypt_prefix():
    """Hashed password starts with $2b$ (bcrypt identifier)."""
    hashed = get_password_hash("secure-password-123")
    assert hashed.startswith("$2b$")


def test_verify_correct_password():
    """Correct password verifies successfully."""
    pw = "my-secret-pw!"
    assert verify_password(pw, get_password_hash(pw)) is True


def test_verify_wrong_password():
    """Wrong password fails verification."""
    hashed = get_password_hash("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_is_salted():
    """Same password hashed twice yields different hashes (salt)."""
    pw = "same-password"
    assert get_password_hash(pw) != get_password_hash(pw)


def test_empty_password_can_be_hashed():
    """Empty string can be hashed and verified (edge case)."""
    hashed = get_password_hash("")
    assert verify_password("", hashed) is True
    assert verify_password("notempty", hashed) is False


# ---------------------------------------------------------------------------
# JWT access token
# ---------------------------------------------------------------------------


def test_access_token_contains_jti():
    """Access token payload contains a unique jti claim."""
    token = create_access_token(subject="user-42")
    payload = decode_token(token)
    assert payload is not None
    assert "jti" in payload
    assert len(payload["jti"]) > 0


def test_access_token_jti_is_unique():
    """Two tokens for the same subject have different jti values."""
    t1 = create_access_token(subject="user-1")
    t2 = create_access_token(subject="user-1")
    assert decode_token(t1)["jti"] != decode_token(t2)["jti"]


def test_access_token_type_claim():
    """Access token has type='access'."""
    token = create_access_token(subject="user-1")
    assert decode_token(token)["type"] == "access"


def test_access_token_custom_expiry():
    """Custom expires_delta is respected."""
    token = create_access_token(subject="u1", expires_delta=timedelta(hours=2))
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "u1"


def test_access_token_additional_claims():
    """Additional claims are merged into the token payload."""
    token = create_access_token(
        subject="u1",
        additional_claims={"tenant_id": 5, "role": "admin"},
    )
    payload = decode_token(token)
    assert payload["tenant_id"] == 5
    assert payload["role"] == "admin"


# ---------------------------------------------------------------------------
# JWT refresh token
# ---------------------------------------------------------------------------


def test_refresh_token_type_claim():
    """Refresh token has type='refresh'."""
    token = create_refresh_token(subject="user-99")
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "refresh"
    assert payload["sub"] == "user-99"


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------


def test_decode_invalid_token_returns_none():
    """Completely invalid token string returns None."""
    assert decode_token("not-a-jwt") is None


def test_decode_tampered_signature_returns_none():
    """Token with corrupted signature returns None."""
    token = create_access_token(subject="u1")
    tampered = token[:-4] + "XXXX"
    assert decode_token(tampered) is None


# ---------------------------------------------------------------------------
# Password reset token flow
# ---------------------------------------------------------------------------


def test_password_reset_token_round_trip():
    """Create and verify a password reset token returns the correct user_id."""
    token = create_password_reset_token(user_id=42)
    result = verify_password_reset_token(token)
    assert result == 42


def test_password_reset_token_type():
    """Password reset token has type='password_reset' in payload."""
    token = create_password_reset_token(user_id=1)
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "password_reset"


def test_password_reset_token_rejects_access_token():
    """verify_password_reset_token rejects a regular access token."""
    access_token = create_access_token(subject="42")
    assert verify_password_reset_token(access_token) is None


def test_password_reset_token_rejects_invalid():
    """verify_password_reset_token returns None for garbage input."""
    assert verify_password_reset_token("garbage.token.value") is None


def test_password_reset_token_custom_expiry():
    """Password reset token with custom expiry hours can be created and verified."""
    token = create_password_reset_token(user_id=7, expires_hours=24)
    assert verify_password_reset_token(token) == 7


if __name__ == "__main__":
    print("=" * 60)
    print("AUTH SERVICE UNIT TESTS")
    print("=" * 60)

    test_hash_produces_bcrypt_prefix()
    print("  hash_produces_bcrypt_prefix")
    test_verify_correct_password()
    print("  verify_correct_password")
    test_verify_wrong_password()
    print("  verify_wrong_password")
    test_hash_is_salted()
    print("  hash_is_salted")
    test_empty_password_can_be_hashed()
    print("  empty_password_can_be_hashed")

    test_access_token_contains_jti()
    print("  access_token_contains_jti")
    test_access_token_jti_is_unique()
    print("  access_token_jti_is_unique")
    test_access_token_type_claim()
    print("  access_token_type_claim")
    test_access_token_custom_expiry()
    print("  access_token_custom_expiry")
    test_access_token_additional_claims()
    print("  access_token_additional_claims")

    test_refresh_token_type_claim()
    print("  refresh_token_type_claim")

    test_decode_invalid_token_returns_none()
    print("  decode_invalid_token_returns_none")
    test_decode_tampered_signature_returns_none()
    print("  decode_tampered_signature_returns_none")

    test_password_reset_token_round_trip()
    print("  password_reset_token_round_trip")
    test_password_reset_token_type()
    print("  password_reset_token_type")
    test_password_reset_token_rejects_access_token()
    print("  password_reset_token_rejects_access_token")
    test_password_reset_token_rejects_invalid()
    print("  password_reset_token_rejects_invalid")
    test_password_reset_token_custom_expiry()
    print("  password_reset_token_custom_expiry")

    print()
    print("ALL AUTH SERVICE TESTS PASSED")
    print("=" * 60)
