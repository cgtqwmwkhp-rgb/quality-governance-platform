"""Authentication domain service.

Extracts business logic from auth routes into a testable service class.
Raises domain exceptions (ValueError, PermissionError, LookupError) instead
of HTTPException so that the service layer stays framework-agnostic.
"""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.azure_auth import extract_user_info_from_azure_token, validate_azure_id_token
from src.core.config import settings
from src.core.security import (
    build_access_token_claims,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    is_token_revoked,
    verify_password,
    verify_password_reset_token,
)
from src.domain.models.user import User
from src.domain.services.email_service import email_service
from src.domain.services.token_service import TokenService

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 15 * 60  # 15 minutes

_failed_login_attempts: dict[str, list[float]] = {}


def _access_token_for_user(user: User) -> str:
    return create_access_token(
        subject=user.id,
        additional_claims=build_access_token_claims(
            is_superuser=user.is_superuser,
            roles=[role.name for role in user.roles or []],
        ),
    )


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:3]}***@{domain or '***'}"


class AuthService:
    """Handles authentication, token lifecycle, and password management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User)
            .where(func.lower(User.email) == email.lower())
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def _get_user_by_azure_oid(self, azure_oid: str | None) -> User | None:
        if not azure_oid:
            return None
        result = await self.db.execute(
            select(User).where(User.azure_oid == azure_oid).options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _split_name(name: str | None, email: str) -> tuple[str, str]:
        parts = (name or email.split("@")[0]).strip().split(" ", 1)
        first_name = parts[0] if parts and parts[0] else "User"
        last_name = parts[1] if len(parts) > 1 else ""
        return first_name, last_name

    async def _stamp_last_login(self, user: User) -> None:
        user.last_login = datetime.now(timezone.utc).isoformat()
        await self.db.commit()
        await self.db.refresh(user)

    async def authenticate(self, email: str, password: str) -> tuple[User, str, str]:
        """Authenticate user with email/password credentials.

        Returns:
            Tuple of (user, access_token, refresh_token).

        Raises:
            ValueError: If credentials are invalid or account is locked.
            PermissionError: If the user account is inactive.
        """
        normalized_email = email.lower()
        now = time.time()
        cutoff = now - LOCKOUT_DURATION_SECONDS

        attempts = _failed_login_attempts.get(normalized_email, [])
        recent_attempts = [t for t in attempts if t > cutoff]
        _failed_login_attempts[normalized_email] = recent_attempts

        if len(recent_attempts) >= MAX_FAILED_ATTEMPTS:
            most_recent = max(recent_attempts)
            unlock_in = int(most_recent + LOCKOUT_DURATION_SECONDS - now)
            raise ValueError(
                f"Account temporarily locked due to too many failed login attempts. "
                f"Try again in {unlock_in} seconds."
            )

        user = await self._get_user_by_email(normalized_email)

        if user is None or not verify_password(password, user.hashed_password):
            _failed_login_attempts.setdefault(normalized_email, []).append(now)
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise PermissionError("User account is inactive")

        _failed_login_attempts.pop(normalized_email, None)

        await self._stamp_last_login(user)

        access_token = _access_token_for_user(user)
        refresh_token = create_refresh_token(subject=user.id)

        return user, access_token, refresh_token

    async def refresh_tokens(self, refresh_token: str) -> tuple[str, str]:
        """Validate a refresh token and issue new token pair.

        Returns:
            Tuple of (new_access_token, new_refresh_token).

        Raises:
            ValueError: If the refresh token is invalid, expired, or revoked.
        """
        payload = decode_token(refresh_token)

        if payload is None or payload.get("type") != "refresh":
            raise ValueError("Invalid or expired refresh token")

        jti = payload.get("jti")
        if not jti:
            raise ValueError("Invalid refresh token: missing jti")

        if await is_token_revoked(jti, self.db):
            raise ValueError("Refresh token has been revoked")

        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("Invalid refresh token: missing subject")

        result = await self.db.execute(select(User).where(User.id == int(user_id)).options(selectinload(User.roles)))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise ValueError("User not found or inactive")

        # Revoke the old refresh token
        expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        await TokenService.revoke_token(
            db=self.db,
            jti=jti,
            user_id=int(user_id),
            expires_at=expires_at,
            reason="token_refresh",
        )

        new_access = _access_token_for_user(user)
        new_refresh = create_refresh_token(subject=user.id)

        return new_access, new_refresh

    async def logout(self, token: str) -> None:
        """Revoke an access token.

        Raises:
            ValueError: If the token is invalid or missing required claims.
        """
        payload = decode_token(token)
        if payload is None:
            raise ValueError("Invalid or expired token")

        jti = payload.get("jti")
        if jti is None:
            raise ValueError("Token missing jti claim")

        exp_timestamp = payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else datetime.now(timezone.utc)
        )

        user_id_raw = payload.get("sub")
        user_id = int(user_id_raw) if user_id_raw else None

        await TokenService.revoke_token(
            db=self.db,
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            reason="logout",
        )

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """Change a user's password.

        Raises:
            ValueError: If the current password is incorrect.
        """
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()

    async def request_password_reset(self, email: str) -> None:
        """Send password reset email if a matching active user exists.

        This method intentionally never raises for missing users to prevent
        email enumeration attacks.
        """
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            return

        reset_token = create_password_reset_token(user.id)

        frontend_url = settings.frontend_url
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"

        try:
            await email_service.send_password_reset_email(
                to=user.email,
                reset_url=reset_url,
                user_name=user.first_name or user.email.split("@")[0],
            )
            masked_email = user.email[:3] + "***@" + user.email.split("@")[1]
            logger.info(f"Password reset email sent to {masked_email}")
        except (SQLAlchemyError, ValueError) as e:
            logger.error(f"Failed to send password reset email: {e}")

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Reset a user's password using a reset token.

        Raises:
            ValueError: If the token is invalid/expired, already used, or user is inactive.
        """
        payload = decode_token(token)
        if payload is None or payload.get("type") != "password_reset":
            raise ValueError("Invalid or expired password reset token")

        jti = payload.get("jti")
        if not jti:
            raise ValueError("Invalid password reset token: missing jti")

        if await is_token_revoked(jti, self.db):
            raise ValueError("Password reset token has already been used")

        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise ValueError("Invalid or expired password reset token")

        user_id = int(user_id_str)
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise ValueError("Invalid or expired password reset token")

        user.hashed_password = get_password_hash(new_password)

        expires_at = datetime.fromtimestamp(payload.get("exp", 0), tz=timezone.utc)
        await TokenService.revoke_token(
            db=self.db,
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            reason="password_reset_used",
        )

        await self.db.commit()
        logger.info(f"Password reset successful for user ID {user_id}")

    async def exchange_azure_token(self, id_token: str) -> tuple[User, str, str]:
        """Exchange an Azure AD id_token for platform tokens.

        Returns:
            Tuple of (user, access_token, refresh_token).

        Raises:
            ValueError: If the Azure token is invalid or missing required claims.
        """
        payload = validate_azure_id_token(id_token)
        if payload is None:
            raise ValueError("Invalid Azure AD token")

        user_info = extract_user_info_from_azure_token(payload)
        if not user_info.get("email"):
            raise ValueError("Azure token missing email claim")

        email = user_info["email"].lower()
        azure_oid = user_info.get("oid")
        user = await self._get_user_by_azure_oid(azure_oid)

        if user is None:
            user = await self._get_user_by_email(email)
            if user is not None and azure_oid and user.azure_oid and user.azure_oid != azure_oid:
                logger.warning(
                    "Azure identity conflict for %s",
                    _mask_email(email),
                    extra={
                        "existing_azure_oid": user.azure_oid,
                        "incoming_azure_oid": azure_oid,
                    },
                )
                raise PermissionError("Microsoft identity conflict detected for this account")

        if user is None:
            first_name, last_name = self._split_name(user_info.get("name"), email)

            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                hashed_password="",
                is_active=True,
                is_superuser=False,
                azure_oid=azure_oid,
                department=user_info.get("department"),
                job_title=user_info.get("job_title"),
                last_login=datetime.now(timezone.utc).isoformat(),
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(
                "Created new user from Azure AD",
                extra={"email_masked": _mask_email(email), "azure_oid": azure_oid or "missing"},
            )
        else:
            if not user.is_active:
                raise PermissionError("User account is inactive")

            if azure_oid and user.azure_oid != azure_oid:
                user.azure_oid = azure_oid
            if user.email != email:
                user.email = email
            first_name, last_name = self._split_name(user_info.get("name"), email)
            user.first_name = first_name
            user.last_name = last_name
            user.department = user_info.get("department") or user.department
            user.job_title = user_info.get("job_title") or user.job_title

            await self._stamp_last_login(user)

        access_token = _access_token_for_user(user)
        refresh_token = create_refresh_token(subject=user.id)

        return user, access_token, refresh_token
