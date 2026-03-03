"""Azure AD token validation for portal users.

This module provides secure validation of Azure AD JWT tokens using
Microsoft's published JWKS (JSON Web Key Set) endpoints.

Security features:
- RSA signature verification using Microsoft's public keys
- Audience (aud) validation to ensure token is for our app
- Issuer (iss) validation to ensure token is from expected tenant
- Expiration (exp) validation
- JWKS caching with configurable TTL to reduce network calls
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AzureADTokenPayload:
    """Validated Azure AD token payload."""

    sub: str  # Subject (user ID)
    oid: str  # Object ID (Azure AD user object ID)
    email: Optional[str]  # User email (may be in 'email' or 'preferred_username')
    name: Optional[str]  # Display name
    preferred_username: Optional[str]  # Usually the email
    tenant_id: str  # Azure AD tenant ID
    audience: str  # Token audience (client ID)
    issued_at: int  # Token issue time
    expires_at: int  # Token expiration time


class AzureADTokenValidator:
    """Validates Azure AD JWT tokens using JWKS.

    This validator fetches Microsoft's public keys from the JWKS endpoint
    and caches them to reduce network overhead. The cache is refreshed
    based on the configured TTL.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        cache_ttl_seconds: int = 3600,
    ):
        """Initialize the validator.

        Args:
            tenant_id: Azure AD tenant ID. Falls back to settings if not provided.
            client_id: Azure AD application client ID. Falls back to settings if not provided.
            cache_ttl_seconds: How long to cache JWKS keys (default 1 hour).
        """
        self.tenant_id = tenant_id or settings.azure_ad_tenant_id
        self.client_id = client_id or settings.azure_ad_client_id
        self.cache_ttl_seconds = cache_ttl_seconds

        if not self.tenant_id or not self.client_id:
            logger.warning(
                "Azure AD credentials not configured. "
                "Set AZURE_AD_TENANT_ID and AZURE_AD_CLIENT_ID environment variables."
            )

        # Build OIDC endpoints
        self._issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        self._jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"

        # JWKS client with caching
        self._jwks_client: Optional[PyJWKClient] = None
        self._jwks_client_created_at: float = 0

    def _get_jwks_client(self) -> PyJWKClient:
        """Get or create the JWKS client with caching."""
        now = time.time()

        # Check if we need to refresh the client
        if self._jwks_client is None or (now - self._jwks_client_created_at) > self.cache_ttl_seconds:
            self._jwks_client = PyJWKClient(self._jwks_uri)
            self._jwks_client_created_at = now
            logger.debug("Refreshed JWKS client cache")

        return self._jwks_client

    def validate_token(self, token: str) -> Optional[AzureADTokenPayload]:
        """Validate an Azure AD JWT token.

        Args:
            token: The JWT token string (without 'Bearer ' prefix).

        Returns:
            AzureADTokenPayload if valid, None if invalid.
        """
        if not self.tenant_id or not self.client_id:
            logger.error("Azure AD not configured - cannot validate token")
            return None

        try:
            # Get the signing key from JWKS
            jwks_client = self._get_jwks_client()
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Decode and validate the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self._issuer,
                options={
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_iss": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "require": ["sub", "oid", "aud", "iss", "exp", "iat"],
                },
            )

            # Extract email from available claims
            email = payload.get("email") or payload.get("preferred_username")

            return AzureADTokenPayload(
                sub=payload["sub"],
                oid=payload["oid"],
                email=email,
                name=payload.get("name"),
                preferred_username=payload.get("preferred_username"),
                tenant_id=payload.get("tid", self.tenant_id),
                audience=payload["aud"],
                issued_at=payload["iat"],
                expires_at=payload["exp"],
            )

        except PyJWKClientError as e:
            logger.warning(f"Failed to fetch JWKS: {e}")
            return None
        except InvalidTokenError as e:
            logger.debug(f"Invalid Azure AD token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error validating Azure AD token: {e}")
            return None

    def is_configured(self) -> bool:
        """Check if Azure AD validation is properly configured."""
        return bool(self.tenant_id and self.client_id)


# Singleton instance for use across the application
_azure_ad_validator: Optional[AzureADTokenValidator] = None


def get_azure_ad_validator() -> AzureADTokenValidator:
    """Get the singleton Azure AD validator instance."""
    global _azure_ad_validator
    if _azure_ad_validator is None:
        _azure_ad_validator = AzureADTokenValidator(cache_ttl_seconds=settings.azure_ad_jwks_cache_ttl_seconds)
    return _azure_ad_validator


def validate_azure_ad_token(token: str) -> Optional[AzureADTokenPayload]:
    """Convenience function to validate an Azure AD token.

    Args:
        token: The JWT token string (without 'Bearer ' prefix).

    Returns:
        AzureADTokenPayload if valid, None if invalid.
    """
    return get_azure_ad_validator().validate_token(token)
