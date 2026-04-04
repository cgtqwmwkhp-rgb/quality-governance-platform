"""Tests for core/security – JWT tokens, password hashing, role claims."""

from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest

from src.core.security import (
    build_access_token_claims,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "S3cur3P@ssw0rd!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct-password")
        assert verify_password("wrong-password", hashed) is False

    def test_empty_hash_returns_false(self):
        assert verify_password("password", "") is False

    def test_invalid_hash_raises_or_returns_false(self):
        try:
            result = verify_password("password", "not-a-valid-hash")
            assert result is False
        except TypeError:
            pass

    def test_hash_is_unique_per_call(self):
        h1 = get_password_hash("same-password")
        h2 = get_password_hash("same-password")
        assert h1 != h2

    def test_hash_starts_with_bcrypt_prefix(self):
        hashed = get_password_hash("test")
        assert hashed.startswith("$2b$")


class TestBuildAccessTokenClaims:
    def test_basic_roles(self):
        claims = build_access_token_claims(roles=["editor", "viewer"])
        assert claims["roles"] == ["editor", "viewer"]
        assert claims["role"] == "editor"
        assert claims["is_superuser"] is False

    def test_superuser_adds_admin(self):
        claims = build_access_token_claims(is_superuser=True, roles=["manager"])
        assert "admin" in claims["roles"]
        assert claims["is_superuser"] is True

    def test_superuser_with_existing_admin(self):
        claims = build_access_token_claims(is_superuser=True, roles=["admin"])
        assert claims["roles"].count("admin") == 1

    def test_no_roles(self):
        claims = build_access_token_claims()
        assert claims["roles"] == []
        assert "role" not in claims

    def test_deduplication(self):
        claims = build_access_token_claims(roles=["editor", "Editor", "EDITOR"])
        assert len(claims["roles"]) == 1

    def test_empty_and_whitespace_roles_stripped(self):
        claims = build_access_token_claims(roles=["editor", "", "  ", "viewer"])
        assert claims["roles"] == ["editor", "viewer"]

    def test_superuser_false_no_admin_added(self):
        claims = build_access_token_claims(is_superuser=False, roles=["viewer"])
        assert "admin" not in claims["roles"]


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token(subject="user-42")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-42"
        assert payload["type"] == "access"

    def test_custom_expiry(self):
        token = create_access_token(subject="user-1", expires_delta=timedelta(minutes=5))
        payload = decode_token(token)
        assert payload is not None

    def test_additional_claims(self):
        token = create_access_token(
            subject="user-1",
            additional_claims={"roles": ["admin"], "tenant_id": 10},
        )
        payload = decode_token(token)
        assert payload["roles"] == ["admin"]
        assert payload["tenant_id"] == 10

    def test_decode_invalid_token_returns_none(self):
        assert decode_token("invalid.token.string") is None

    def test_decode_tampered_token_returns_none(self):
        token = create_access_token(subject="user-1")
        tampered = token[:-5] + "XXXXX"
        assert decode_token(tampered) is None

    def test_token_has_jti(self):
        token = create_access_token(subject="user-1")
        payload = decode_token(token)
        assert "jti" in payload
        assert len(payload["jti"]) > 0


class TestRefreshToken:
    def test_create_refresh_token(self):
        token = create_refresh_token(subject="user-42")
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-42"
        assert payload["type"] == "refresh"


class TestPasswordResetToken:
    def test_create_and_verify(self):
        token = create_password_reset_token(user_id=99)
        user_id = verify_password_reset_token(token)
        assert user_id == 99

    def test_custom_expiry(self):
        token = create_password_reset_token(user_id=1, expires_hours=24)
        user_id = verify_password_reset_token(token)
        assert user_id == 1

    def test_invalid_token_returns_none(self):
        assert verify_password_reset_token("garbage-token") is None

    def test_access_token_rejected_as_reset(self):
        token = create_access_token(subject="99")
        assert verify_password_reset_token(token) is None

    def test_refresh_token_rejected_as_reset(self):
        token = create_refresh_token(subject="99")
        assert verify_password_reset_token(token) is None
