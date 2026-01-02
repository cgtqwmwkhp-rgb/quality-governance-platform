"""Unit tests for security module."""

import pytest
from datetime import timedelta

from src.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert len(hashed) > 0

    def test_verify_correct_password(self):
        """Test verifying correct password."""
        password = "testpassword123"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_incorrect_password(self):
        """Test verifying incorrect password."""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(wrong_password, hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "testpassword123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token(self):
        """Test creating access token."""
        token = create_access_token(subject="123")
        
        assert token is not None
        assert len(token) > 0

    def test_create_access_token_with_expiry(self):
        """Test creating access token with custom expiry."""
        token = create_access_token(
            subject="123",
            expires_delta=timedelta(hours=1),
        )
        
        assert token is not None

    def test_create_refresh_token(self):
        """Test creating refresh token."""
        token = create_refresh_token(subject="123")
        
        assert token is not None
        assert len(token) > 0

    def test_decode_valid_token(self):
        """Test decoding valid token."""
        token = create_access_token(subject="123")
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "123"
        assert payload["type"] == "access"

    def test_decode_refresh_token(self):
        """Test decoding refresh token."""
        token = create_refresh_token(subject="456")
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["sub"] == "456"
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        payload = decode_token("invalid.token.here")
        
        assert payload is None

    def test_decode_tampered_token(self):
        """Test decoding tampered token."""
        token = create_access_token(subject="123")
        tampered_token = token[:-5] + "xxxxx"
        payload = decode_token(tampered_token)
        
        assert payload is None

    def test_token_contains_additional_claims(self):
        """Test token with additional claims."""
        token = create_access_token(
            subject="123",
            additional_claims={"role": "admin"},
        )
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["role"] == "admin"
