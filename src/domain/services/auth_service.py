"""Authentication domain service.

Extracts business logic from auth routes into a testable service class.
Raises domain exceptions (ValueError, PermissionError, LookupError) instead
of HTTPException so that the service layer stays framework-agnostic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.azure_auth import extract_user_info_from_azure_token, validate_azure_id_token
from src.core.config import settings
from src.core.security import (
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


class AuthService:
    """Handles authentication, token lifecycle, and password management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate(self, email: str, password: str) -> tuple[User, str, str]:
        """Authenticate user with email/password credentials.

        Returns:
            Tuple of (user, access_token, refresh_token).

        Raises:
            ValueError: If credentials are invalid.
            PermissionError: If the user account is inactive.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise PermissionError("User account is inactive")

        user.last_login = datetime.now(timezone.utc).isoformat()
        await self.db.commit()

        access_token = create_access_token(subject=user.id)
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

        result = await self.db.execute(select(User).where(User.id == int(user_id)))
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

        new_access = create_access_token(subject=user.id)
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
            ValueError: If the token is invalid/expired or user is inactive.
        """
        user_id = verify_password_reset_token(token)
        if user_id is None:
            raise ValueError("Invalid or expired password reset token")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None or not user.is_active:
            raise ValueError("Invalid or expired password reset token")

        user.hashed_password = get_password_hash(new_password)
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

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            name_parts = (user_info.get("name") or email.split("@")[0]).split(" ", 1)
            first_name = name_parts[0] if name_parts else "User"
            last_name = name_parts[1] if len(name_parts) > 1 else ""

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
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            logger.info(f"Created new user from Azure AD: {email}")
        else:
            if azure_oid and not user.azure_oid:
                user.azure_oid = azure_oid
                await self.db.commit()

            user.last_login = datetime.now(timezone.utc).isoformat()
            await self.db.commit()

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return user, access_token, refresh_token
