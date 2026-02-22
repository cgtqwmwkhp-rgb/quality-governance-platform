"""Security utilities for authentication and authorization."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# RSA key cache (loaded once)
_rsa_private_key: Optional[str] = None
_rsa_public_key: Optional[str] = None
_rsa_keys_loaded: bool = False


def _load_rsa_keys() -> tuple[Optional[str], Optional[str]]:
    """Read RSA private/public key files if configured. Results are cached."""
    global _rsa_private_key, _rsa_public_key, _rsa_keys_loaded

    if _rsa_keys_loaded:
        return _rsa_private_key, _rsa_public_key

    _rsa_keys_loaded = True

    if not settings.jwt_private_key_path or not settings.jwt_public_key_path:
        return None, None

    try:
        with open(settings.jwt_private_key_path, "r") as f:
            _rsa_private_key = f.read()
        with open(settings.jwt_public_key_path, "r") as f:
            _rsa_public_key = f.read()
        logger.info("RSA keys loaded — JWT will use RS256")
    except (FileNotFoundError, PermissionError) as exc:
        logger.warning("Failed to load RSA keys, falling back to HS256: %s", exc)
        _rsa_private_key = None
        _rsa_public_key = None

    return _rsa_private_key, _rsa_public_key


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
    """Create a JWT access token.

    Uses RS256 with the configured RSA private key when available,
    otherwise falls back to HS256 with the symmetric secret.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "last_activity": now.isoformat(),
    }

    if additional_claims:
        to_encode.update(additional_claims)

    private_key, _ = _load_rsa_keys()
    if private_key:
        signing_key = private_key
        algorithm = "RS256"
    else:
        signing_key = settings.jwt_secret_key
        algorithm = settings.jwt_algorithm

    encoded_jwt = jwt.encode(to_encode, signing_key, algorithm=algorithm)
    return str(encoded_jwt)


def create_refresh_token(subject: str | Any) -> str:
    """Create a JWT refresh token."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }

    private_key, _ = _load_rsa_keys()
    if private_key:
        signing_key = private_key
        algorithm = "RS256"
    else:
        signing_key = settings.jwt_secret_key
        algorithm = settings.jwt_algorithm

    encoded_jwt = jwt.encode(to_encode, signing_key, algorithm=algorithm)
    return str(encoded_jwt)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT token.

    Tries RS256 with the public key first (if configured), then
    falls back to HS256 with the symmetric secret.
    """
    _, public_key = _load_rsa_keys()

    if public_key:
        try:
            payload = jwt.decode(token, public_key, algorithms=["RS256"])
            return dict(payload)
        except jwt.PyJWTError:
            pass

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
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=expires_hours)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "type": "password_reset",
        "jti": str(uuid.uuid4()),
    }

    private_key, _ = _load_rsa_keys()
    if private_key:
        signing_key = private_key
        algorithm = "RS256"
    else:
        signing_key = settings.jwt_secret_key
        algorithm = settings.jwt_algorithm

    encoded_jwt = jwt.encode(to_encode, signing_key, algorithm=algorithm)
    return str(encoded_jwt)


def verify_password_reset_token(token: str) -> Optional[int]:
    """
    Verify a password reset token and return the user_id if valid.

    Args:
        token: The JWT token to verify

    Returns:
        User ID if token is valid, None otherwise
    """
    payload = decode_token(token)
    if payload is None:
        return None

    if payload.get("type") != "password_reset":
        return None

    user_id_str = payload.get("sub")
    if user_id_str is None:
        return None

    try:
        return int(user_id_str)
    except (ValueError, TypeError):
        return None


async def is_token_revoked(jti: str, db: AsyncSession) -> bool:
    """Check whether a token JTI has been revoked (exists in the blacklist)."""
    from src.domain.models.token_blacklist import TokenBlacklist

    result = await db.execute(select(TokenBlacklist.id).where(TokenBlacklist.jti == jti))
    return result.scalar_one_or_none() is not None
