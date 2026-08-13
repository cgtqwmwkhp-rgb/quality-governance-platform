"""Microsoft Graph client for the Int-W8 Entra MFA attestation reader.

Reads only: security defaults and Conditional Access policies. No compliance
opinion lives here — that is ``standards_entra_attestation``. Hosts are
hardcoded so a setting cannot turn this into an SSRF client.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

LOGIN_HOST = "https://login.microsoftonline.com"
GRAPH_HOST = "https://graph.microsoft.com"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"
SECURITY_DEFAULTS_PATH = "/v1.0/policies/identitySecurityDefaultsEnforcementPolicy"
CA_POLICIES_PATH = "/v1.0/identity/conditionalAccess/policies"
MAX_POLICY_PAGES = 5
_GUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

_TOKEN_CACHE: dict[str, tuple[float, str]] = {}


class EntraGraphUnavailable(Exception):
    """Graph could not be read. Never treated as a finding."""

    def __init__(self, reason_code: str, *, retry_after: Optional[int] = None):
        self.reason_code = reason_code
        self.retry_after = retry_after
        super().__init__(reason_code)


@dataclass
class GraphPolicySnapshot:
    security_defaults: dict[str, Any]
    policies: list[dict[str, Any]] = field(default_factory=list)
    truncated: bool = False


def reset_token_cache() -> None:
    _TOKEN_CACHE.clear()


def _is_guid(value: str) -> bool:
    return bool(_GUID_RE.match(value or ""))


def _parse_retry_after(response: httpx.Response) -> Optional[int]:
    raw = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _graph_url_allowed(url: str) -> bool:
    return str(url).startswith(f"{GRAPH_HOST}/")


class EntraGraphClient:
    """Client-credentials Graph reader. Logs status codes, never tokens or bodies."""

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        timeout_seconds: float = 5.0,
        transport: Optional[httpx.BaseTransport] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        if not _is_guid(tenant_id):
            raise EntraGraphUnavailable("invalid_tenant")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._client_secret = client_secret
        self._timeout = httpx.Timeout(timeout_seconds)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=self._timeout, transport=transport)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_snapshot(self) -> GraphPolicySnapshot:
        defaults = await self._get_json(f"{GRAPH_HOST}{SECURITY_DEFAULTS_PATH}")
        policies, truncated = await self._fetch_policies()
        return GraphPolicySnapshot(security_defaults=defaults, policies=policies, truncated=truncated)

    async def _token(self) -> str:
        cached = _TOKEN_CACHE.get(self.client_id)
        now = time.monotonic()
        if cached is not None and cached[0] > now:
            return cached[1]

        token_url = f"{LOGIN_HOST}/{self.tenant_id}/oauth2/v2.0/token"
        try:
            response = await self._client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self._client_secret,
                    "scope": GRAPH_SCOPE,
                },
            )
        except httpx.TimeoutException:
            raise EntraGraphUnavailable("timeout") from None
        except httpx.RequestError:
            raise EntraGraphUnavailable("connect_error") from None

        if response.status_code != 200:
            logger.warning("Entra token endpoint status=%s", response.status_code)
            raise EntraGraphUnavailable("token_error")

        try:
            body = response.json()
        except Exception:
            raise EntraGraphUnavailable("token_error") from None
        token = body.get("access_token") if isinstance(body, dict) else None
        expires_in = body.get("expires_in") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise EntraGraphUnavailable("token_error")
        try:
            ttl = int(expires_in) - 300
        except (TypeError, ValueError):
            ttl = 300
        if ttl > 0:
            _TOKEN_CACHE[self.client_id] = (now + ttl, token)
        return token

    async def _get_json(self, url: str) -> dict[str, Any]:
        if not _graph_url_allowed(url):
            raise EntraGraphUnavailable("schema_mismatch")
        token = await self._token()
        try:
            response = await self._client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            raise EntraGraphUnavailable("timeout") from None
        except httpx.RequestError:
            raise EntraGraphUnavailable("connect_error") from None

        if response.status_code == 429:
            logger.warning("Entra Graph status=429")
            raise EntraGraphUnavailable("rate_limited", retry_after=_parse_retry_after(response))
        if response.status_code in (401, 403):
            logger.warning("Entra Graph status=%s", response.status_code)
            raise EntraGraphUnavailable(f"http_{response.status_code}")
        if response.status_code != 200:
            logger.warning("Entra Graph status=%s", response.status_code)
            raise EntraGraphUnavailable(f"http_{response.status_code}")

        try:
            data = response.json()
        except Exception:
            raise EntraGraphUnavailable("non_json") from None
        if not isinstance(data, dict):
            raise EntraGraphUnavailable("schema_mismatch")
        return data

    async def _fetch_policies(self) -> tuple[list[dict[str, Any]], bool]:
        url: Optional[str] = f"{GRAPH_HOST}{CA_POLICIES_PATH}"
        collected: list[dict[str, Any]] = []
        for _page in range(MAX_POLICY_PAGES):
            if url is None:
                return collected, False
            payload = await self._get_json(url)
            value = payload.get("value")
            if not isinstance(value, list):
                raise EntraGraphUnavailable("schema_mismatch")
            for item in value:
                if isinstance(item, dict):
                    collected.append(item)
            next_link = payload.get("@odata.nextLink")
            if not next_link:
                return collected, False
            if not isinstance(next_link, str) or not _graph_url_allowed(next_link):
                raise EntraGraphUnavailable("schema_mismatch")
            url = next_link
        return collected, True
