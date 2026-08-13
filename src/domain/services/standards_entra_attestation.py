"""Int-W8 Entra MFA posture: pure predicate + fail-closed resolver.

The Graph client returns raw dicts. This module decides pass / fail /
unavailable and never logs tokens, secrets, policy JSON, or directory
object IDs. Counts only.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from src.core.entra_graph_client import EntraGraphClient, EntraGraphUnavailable, GraphPolicySnapshot

logger = logging.getLogger(__name__)

KIND_ENTRA_MFA = "entra_mfa"
_MAX_ERROR_TTL = 900


@dataclass(frozen=True)
class EntraAttestationConfig:
    enabled: bool = False
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    qgp_tenant_ids: frozenset[int] = frozenset()
    breakglass_excluded_user_ids: frozenset[str] = frozenset()
    timeout_seconds: float = 5.0
    cache_ttl_seconds: int = 300
    error_cache_ttl_seconds: int = 60
    azure_tenant_id_fallback: str = ""

    @classmethod
    def from_settings(cls, settings: Any) -> "EntraAttestationConfig":
        return cls(
            enabled=bool(getattr(settings, "entra_attestation_enabled", False)),
            tenant_id=str(getattr(settings, "entra_attestation_tenant_id", "") or ""),
            client_id=str(getattr(settings, "entra_attestation_client_id", "") or ""),
            client_secret=str(getattr(settings, "entra_attestation_client_secret", "") or ""),
            qgp_tenant_ids=_csv_ints(getattr(settings, "entra_attestation_qgp_tenant_ids", "")),
            breakglass_excluded_user_ids=_csv_ids(
                getattr(settings, "entra_attestation_breakglass_excluded_user_ids", "")
            ),
            timeout_seconds=float(getattr(settings, "entra_attestation_timeout_seconds", 5.0) or 5.0),
            cache_ttl_seconds=_clamp(
                int(getattr(settings, "entra_attestation_cache_ttl_seconds", 300) or 300), 60, 900
            ),
            error_cache_ttl_seconds=_clamp(
                int(getattr(settings, "entra_attestation_error_cache_ttl_seconds", 60) or 60), 30, 900
            ),
            azure_tenant_id_fallback=str(getattr(settings, "azure_tenant_id", "") or ""),
        )

    @property
    def entra_tenant_id(self) -> str:
        return (self.tenant_id or self.azure_tenant_id_fallback).strip()


@dataclass(frozen=True)
class AttestationPosture:
    status: str
    kinds: tuple[str, ...] = ()
    source: Optional[str] = None
    reason: Optional[str] = None
    observed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status}
        if self.source is not None:
            payload["source"] = self.source
        if self.reason is not None:
            payload["reason"] = self.reason
        if self.observed_at is not None:
            payload["observed_at"] = self.observed_at
        return payload


_CACHE: dict[str, tuple[float, AttestationPosture]] = {}


def reset_attestation_cache() -> None:
    _CACHE.clear()


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _csv_ids(raw: Any) -> frozenset[str]:
    return frozenset(part.strip() for part in str(raw or "").split(",") if part.strip())


def _csv_ints(raw: Any) -> frozenset[int]:
    out: set[int] = set()
    for part in str(raw or "").split(","):
        text = part.strip()
        if not text:
            continue
        try:
            out.add(int(text))
        except ValueError:
            continue
    return frozenset(out)


def _as_list(value: Any) -> Optional[list[Any]]:
    if value is None:
        return None
    if isinstance(value, list):
        return value
    return None


def _lower_set(values: Iterable[Any]) -> set[str]:
    return {str(item).strip().lower() for item in values if str(item).strip()}


def policy_enforces_mfa_for_all(
    policy: dict[str, Any],
    *,
    breakglass_user_ids: frozenset[str] = frozenset(),
) -> bool:
    """True only when every required field is present and conservative.

    Missing, null, or unrecognised fields disqualify the policy. Ambiguous
    means not enforced.
    """
    if not isinstance(policy, dict):
        return False
    if str(policy.get("state") or "").strip().lower() != "enabled":
        return False

    conditions = policy.get("conditions")
    if not isinstance(conditions, dict):
        return False

    users = conditions.get("users")
    if not isinstance(users, dict):
        return False
    include_users = _as_list(users.get("includeUsers"))
    if include_users is None or "All" not in include_users:
        return False
    exclude_groups = _as_list(users.get("excludeGroups"))
    exclude_roles = _as_list(users.get("excludeRoles"))
    exclude_users = _as_list(users.get("excludeUsers"))
    if exclude_groups is None or exclude_roles is None or exclude_users is None:
        return False
    if exclude_groups or exclude_roles:
        return False
    allowed = {uid.lower() for uid in breakglass_user_ids}
    for excluded in exclude_users:
        if str(excluded).strip().lower() not in allowed:
            return False
    if users.get("excludeGuestsOrExternalUsers") is not None:
        return False

    applications = conditions.get("applications")
    if not isinstance(applications, dict):
        return False
    include_apps = _as_list(applications.get("includeApplications"))
    exclude_apps = _as_list(applications.get("excludeApplications"))
    include_actions = _as_list(applications.get("includeUserActions"))
    include_auth_ctx = _as_list(applications.get("includeAuthenticationContextClassReferences"))
    if include_apps is None or "All" not in include_apps:
        return False
    if exclude_apps is None or include_actions is None or include_auth_ctx is None:
        return False
    if exclude_apps or include_actions or include_auth_ctx:
        return False

    client_apps = _as_list(conditions.get("clientAppTypes"))
    if client_apps is None or _lower_set(client_apps) != {"all"}:
        return False
    if conditions.get("platforms") is not None:
        return False

    locations = conditions.get("locations")
    if locations is not None:
        if not isinstance(locations, dict):
            return False
        include_locations = _as_list(locations.get("includeLocations"))
        exclude_locations = _as_list(locations.get("excludeLocations"))
        if include_locations is None or exclude_locations is None:
            return False
        if include_locations != ["All"] or exclude_locations:
            return False

    sign_in_risk = _as_list(conditions.get("signInRiskLevels"))
    user_risk = _as_list(conditions.get("userRiskLevels"))
    if sign_in_risk is None or user_risk is None:
        return False
    if sign_in_risk or user_risk:
        return False

    grants = policy.get("grantControls")
    if not isinstance(grants, dict):
        return False
    if grants.get("authenticationStrength") is not None:
        return False
    built_in = _as_list(grants.get("builtInControls"))
    custom_factors = _as_list(grants.get("customAuthenticationFactors"))
    terms = _as_list(grants.get("termsOfUse"))
    if built_in is None or custom_factors is None or terms is None:
        return False
    controls = [str(item).strip().lower() for item in built_in]
    if "block" in controls:
        return False
    operator = str(grants.get("operator") or "").strip().upper()
    if operator == "AND":
        return "mfa" in controls
    if operator == "OR":
        return set(controls) == {"mfa"} and not custom_factors and not terms
    return False


def evaluate_posture(
    snapshot: GraphPolicySnapshot,
    *,
    breakglass_user_ids: frozenset[str] = frozenset(),
) -> AttestationPosture:
    observed = datetime.now(timezone.utc).isoformat()
    qualifying = any(
        policy_enforces_mfa_for_all(policy, breakglass_user_ids=breakglass_user_ids) for policy in snapshot.policies
    )
    if qualifying:
        return AttestationPosture(
            status="pass",
            kinds=(KIND_ENTRA_MFA,),
            source="conditional_access",
            observed_at=observed,
        )

    defaults = snapshot.security_defaults if isinstance(snapshot.security_defaults, dict) else {}
    if "isEnabled" not in defaults:
        if snapshot.truncated:
            return AttestationPosture(status="unavailable", reason="policy_scan_truncated", observed_at=observed)
        return AttestationPosture(status="unavailable", reason="schema_mismatch", observed_at=observed)

    if snapshot.truncated:
        return AttestationPosture(status="unavailable", reason="policy_scan_truncated", observed_at=observed)

    if defaults.get("isEnabled") is True:
        return AttestationPosture(
            status="pass",
            kinds=(KIND_ENTRA_MFA,),
            source="security_defaults",
            observed_at=observed,
        )

    return AttestationPosture(status="fail", reason="not_enforced", observed_at=observed)


def _store(cache_key: str, posture: AttestationPosture, ttl_seconds: int) -> AttestationPosture:
    _CACHE[cache_key] = (time.monotonic() + max(1, ttl_seconds), posture)
    return posture


async def resolve_attestation(
    *,
    qgp_tenant_id: int,
    config: EntraAttestationConfig,
    graph_client: Optional[EntraGraphClient] = None,
) -> AttestationPosture:
    """Fail-closed posture for one QGP tenant. Never raises to the caller."""
    if not config.enabled:
        return AttestationPosture(status="disabled")
    if qgp_tenant_id not in config.qgp_tenant_ids:
        return AttestationPosture(status="not_applicable")
    if not config.client_id.strip() or not config.client_secret.strip():
        return AttestationPosture(status="unavailable", reason="not_configured")

    entra_tenant = config.entra_tenant_id
    now = time.monotonic()
    cached = _CACHE.get(entra_tenant)
    if cached is not None and cached[0] > now:
        return cached[1]
    _CACHE.pop(entra_tenant, None)

    owns_client = graph_client is None
    client = graph_client
    try:
        if client is None:
            client = EntraGraphClient(
                tenant_id=entra_tenant,
                client_id=config.client_id,
                client_secret=config.client_secret,
                timeout_seconds=config.timeout_seconds,
            )
        snapshot = await client.fetch_snapshot()
        posture = evaluate_posture(snapshot, breakglass_user_ids=config.breakglass_excluded_user_ids)
        ttl = config.cache_ttl_seconds if posture.status in {"pass", "fail"} else config.error_cache_ttl_seconds
        return _store(entra_tenant, posture, ttl)
    except EntraGraphUnavailable as exc:
        logger.warning("Entra attestation unavailable reason=%s", exc.reason_code)
        ttl = config.error_cache_ttl_seconds
        if exc.reason_code == "rate_limited" and exc.retry_after is not None:
            ttl = _clamp(int(exc.retry_after), 30, _MAX_ERROR_TTL)
        return _store(
            entra_tenant,
            AttestationPosture(status="unavailable", reason=exc.reason_code),
            ttl,
        )
    except Exception:
        logger.warning("Entra attestation unavailable reason=unexpected")
        return _store(
            entra_tenant,
            AttestationPosture(status="unavailable", reason="unexpected"),
            config.error_cache_ttl_seconds,
        )
    finally:
        if owns_client and client is not None:
            await client.aclose()
