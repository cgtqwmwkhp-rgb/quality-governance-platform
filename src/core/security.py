"""Security utilities for authentication and authorization."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return bool(pwd_context.verify(plain_password, hashed_password))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return str(pwd_context.hash(password))


def create_access_token(
    subject: str | Any,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None,
) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": str(uuid.uuid4()),
    }

    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return str(encoded_jwt)


def create_refresh_token(subject: str | Any) -> str:
    """Create a JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return str(encoded_jwt)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return dict(payload)
    except jwt.PyJWTError:
        return None


def create_password_reset_token(user_id: int, expires_hours: int = 1) -> str:
    """
    Create a JWT token for password reset.

    Args:
        user_id: The ID of the user requesting password reset
        expires_hours: Token validity period in hours (default: 1)

    Returns:
        Encoded JWT token for password reset
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "password_reset",
        "jti": str(uuid.uuid4()),
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return str(encoded_jwt)


def verify_password_reset_token(token: str) -> Optional[int]:
    """
    Verify a password reset token and return the user_id if valid.

    Args:
        token: The JWT token to verify

    Returns:
        User ID if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify token type
        if payload.get("type") != "password_reset":
            return None

        # Extract and return user_id
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None

        return int(user_id_str)
    except (jwt.PyJWTError, ValueError):
        return None


async def is_token_revoked(jti: str, db: AsyncSession) -> bool:
    """Check whether a token JTI has been revoked (exists in the blacklist)."""
    from src.domain.models.token_blacklist import TokenBlacklist

    result = await db.execute(select(TokenBlacklist.id).where(TokenBlacklist.jti == jti))
    return result.scalar_one_or_none() is not None
