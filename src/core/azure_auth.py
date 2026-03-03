"""
Azure AD Token Validation

Validates Azure AD id_tokens using Microsoft's JWKS endpoint.
Implements secure token exchange: Azure AD token → Platform JWT.
"""

import logging
from functools import lru_cache
from typing import Any, Optional

import httpx
import jwt
from jwt import PyJWKClient

from src.core.config import settings

logger = logging.getLogger(__name__)

# Microsoft OpenID Connect configuration endpoints
AZURE_OPENID_CONFIG_URL = "https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration"
AZURE_JWKS_URL = "https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"


@lru_cache(maxsize=1)
def get_jwks_client(tenant_id: str) -> PyJWKClient:
    """Get cached JWKS client for Azure AD tenant."""
    jwks_url = AZURE_JWKS_URL.format(tenant_id=tenant_id)
    return PyJWKClient(jwks_url)


def validate_azure_id_token(
    id_token: str,
    client_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Validate an Azure AD id_token.

    Args:
        id_token: The Azure AD id_token to validate
        client_id: Expected audience (client ID). Uses settings if not provided.
        tenant_id: Azure AD tenant ID. Uses settings if not provided.

    Returns:
        Token payload if valid, None otherwise.

    Security:
        - Validates signature using Microsoft's JWKS
        - Verifies issuer matches expected tenant
        - Verifies audience matches expected client ID
        - Checks token expiration
    """
    try:
        # Use settings defaults if not provided
        _client_id = client_id or getattr(settings, "azure_client_id", None)
        _tenant_id = tenant_id or getattr(settings, "azure_tenant_id", None)

        if not _client_id or not _tenant_id:
            logger.warning("Azure AD not configured - missing client_id or tenant_id")
            return None

        # Get signing key from JWKS
        jwks_client = get_jwks_client(_tenant_id)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        # Expected issuer for the tenant
        expected_issuer = f"https://login.microsoftonline.com/{_tenant_id}/v2.0"

        # Decode and validate token
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=_client_id,
            issuer=expected_issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )

        return dict(payload)

    except jwt.ExpiredSignatureError:
        logger.warning("Azure AD token has expired")
        return None
    except jwt.InvalidAudienceError:
        logger.warning("Azure AD token has invalid audience")
        return None
    except jwt.InvalidIssuerError:
        logger.warning("Azure AD token has invalid issuer")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"Azure AD token validation failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error validating Azure AD token: {e}")
        return None


def extract_user_info_from_azure_token(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Extract user information from validated Azure AD token payload.

    Args:
        payload: Validated Azure AD token payload

    Returns:
        User info dict with standardized fields
    """
    return {
        "oid": payload.get("oid"),  # Object ID (unique user identifier)
        "sub": payload.get("sub"),  # Subject (can differ from oid)
        "email": (
            payload.get("email")
            or payload.get("preferred_username")
            or payload.get("upn")
        ),
        "name": payload.get("name", ""),
        "given_name": payload.get("given_name", ""),
        "family_name": payload.get("family_name", ""),
        "job_title": payload.get("jobTitle"),
        "department": payload.get("department"),
    }
