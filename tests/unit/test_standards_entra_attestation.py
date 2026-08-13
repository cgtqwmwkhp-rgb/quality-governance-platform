"""Int-W8 Entra MFA attestation: predicate, Graph client, fail-closed cache."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
import pytest

from src.core.entra_graph_client import EntraGraphClient, GraphPolicySnapshot, reset_token_cache
from src.domain.services.standards_entra_attestation import (
    AttestationPosture,
    EntraAttestationConfig,
    evaluate_posture,
    policy_enforces_mfa_for_all,
    reset_attestation_cache,
    resolve_attestation,
)

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"
SECRET = "super-secret-value-xyz"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.not-a-real-token"
BREAKGLASS = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture(autouse=True)
def _clear_caches():
    reset_attestation_cache()
    reset_token_cache()
    yield
    reset_attestation_cache()
    reset_token_cache()


def _cfg(**kwargs: Any) -> EntraAttestationConfig:
    base: dict[str, Any] = {
        "enabled": True,
        "tenant_id": TENANT,
        "client_id": CLIENT,
        "client_secret": SECRET,
        "qgp_tenant_ids": frozenset({1}),
        "timeout_seconds": 5.0,
        "cache_ttl_seconds": 300,
        "error_cache_ttl_seconds": 60,
    }
    base.update(kwargs)
    return EntraAttestationConfig(**base)


def qualifying_ca_policy(**overrides: Any) -> dict[str, Any]:
    policy: dict[str, Any] = {
        "id": "policy-1",
        "state": "enabled",
        "conditions": {
            "users": {
                "includeUsers": ["All"],
                "excludeUsers": [],
                "excludeGroups": [],
                "excludeRoles": [],
                "excludeGuestsOrExternalUsers": None,
            },
            "applications": {
                "includeApplications": ["All"],
                "excludeApplications": [],
                "includeUserActions": [],
                "includeAuthenticationContextClassReferences": [],
            },
            "clientAppTypes": ["all"],
            "platforms": None,
            "locations": None,
            "signInRiskLevels": [],
            "userRiskLevels": [],
        },
        "grantControls": {
            "operator": "AND",
            "builtInControls": ["mfa"],
            "customAuthenticationFactors": [],
            "termsOfUse": [],
            "authenticationStrength": None,
        },
    }
    for key, value in overrides.items():
        if key == "grantControls" and isinstance(value, dict):
            policy["grantControls"] = {**policy["grantControls"], **value}
        elif key == "state":
            policy["state"] = value
        else:
            policy[key] = value
    return policy


def _users(policy: dict[str, Any], **fields: Any) -> dict[str, Any]:
    policy["conditions"]["users"].update(fields)
    return policy


def _apps(policy: dict[str, Any], **fields: Any) -> dict[str, Any]:
    policy["conditions"]["applications"].update(fields)
    return policy


def test_predicate_accepts_all_users_all_apps_mfa_and_operator() -> None:
    assert policy_enforces_mfa_for_all(qualifying_ca_policy()) is True


def test_predicate_accepts_or_operator_with_mfa_as_sole_control() -> None:
    policy = qualifying_ca_policy(
        grantControls={
            "operator": "OR",
            "builtInControls": ["mfa"],
            "customAuthenticationFactors": [],
            "termsOfUse": [],
            "authenticationStrength": None,
        }
    )
    assert policy_enforces_mfa_for_all(policy) is True


def test_predicate_rejects_or_operator_with_compliant_device_alternative() -> None:
    policy = qualifying_ca_policy(
        grantControls={
            "operator": "OR",
            "builtInControls": ["mfa", "compliantDevice"],
            "customAuthenticationFactors": [],
            "termsOfUse": [],
            "authenticationStrength": None,
        }
    )
    assert policy_enforces_mfa_for_all(policy) is False


def test_predicate_rejects_report_only_state() -> None:
    assert policy_enforces_mfa_for_all(qualifying_ca_policy(state="enabledForReportingButNotEnforced")) is False


def test_predicate_rejects_excluded_user_not_in_breakglass_allowlist() -> None:
    policy = _users(qualifying_ca_policy(), excludeUsers=[BREAKGLASS])
    assert policy_enforces_mfa_for_all(policy) is False


def test_predicate_accepts_excluded_user_in_breakglass_allowlist() -> None:
    policy = _users(qualifying_ca_policy(), excludeUsers=[BREAKGLASS])
    assert policy_enforces_mfa_for_all(policy, breakglass_user_ids=frozenset({BREAKGLASS})) is True


def test_predicate_rejects_excluded_group_or_role() -> None:
    grouped = _users(qualifying_ca_policy(), excludeGroups=["g1"])
    assert policy_enforces_mfa_for_all(grouped) is False
    roles = _users(qualifying_ca_policy(), excludeRoles=["r1"])
    assert policy_enforces_mfa_for_all(roles) is False


def test_predicate_rejects_location_exclusion() -> None:
    policy = qualifying_ca_policy()
    policy["conditions"]["locations"] = {
        "includeLocations": ["All"],
        "excludeLocations": ["trusted-office"],
    }
    assert policy_enforces_mfa_for_all(policy) is False


def test_predicate_rejects_platform_or_risk_scoped_policy() -> None:
    platformed = qualifying_ca_policy()
    platformed["conditions"]["platforms"] = {"includePlatforms": ["windows"]}
    assert policy_enforces_mfa_for_all(platformed) is False
    risky = qualifying_ca_policy()
    risky["conditions"]["signInRiskLevels"] = ["high"]
    assert policy_enforces_mfa_for_all(risky) is False


def test_predicate_rejects_app_exclusion_or_user_action_scope() -> None:
    excluded = _apps(qualifying_ca_policy(), excludeApplications=["app-1"])
    assert policy_enforces_mfa_for_all(excluded) is False
    actions = _apps(qualifying_ca_policy(), includeUserActions=["urn:user:registersecurityinfo"])
    assert policy_enforces_mfa_for_all(actions) is False


def test_predicate_rejects_authentication_strength_policy_as_unevaluated() -> None:
    policy = qualifying_ca_policy(
        grantControls={
            "operator": "AND",
            "builtInControls": ["mfa"],
            "customAuthenticationFactors": [],
            "termsOfUse": [],
            "authenticationStrength": {"id": "strength-1"},
        }
    )
    assert policy_enforces_mfa_for_all(policy) is False


def test_predicate_rejects_missing_or_null_grant_controls() -> None:
    missing = qualifying_ca_policy()
    del missing["grantControls"]
    assert policy_enforces_mfa_for_all(missing) is False
    nulled = qualifying_ca_policy()
    nulled["grantControls"] = None
    assert policy_enforces_mfa_for_all(nulled) is False


def test_security_defaults_enabled_is_pass() -> None:
    posture = evaluate_posture(GraphPolicySnapshot(security_defaults={"isEnabled": True}, policies=[]))
    assert posture.status == "pass"
    assert posture.source == "security_defaults"
    assert posture.kinds == ("entra_mfa",)


def test_no_qualifying_policy_and_defaults_off_is_fail() -> None:
    posture = evaluate_posture(
        GraphPolicySnapshot(
            security_defaults={"isEnabled": False},
            policies=[qualifying_ca_policy(state="enabledForReportingButNotEnforced")],
        )
    )
    assert posture.status == "fail"
    assert posture.reason == "not_enforced"


def _transport(
    *,
    token_status: int = 200,
    graph_status: int = 200,
    defaults: Optional[dict[str, Any]] = None,
    policies: Optional[list[dict[str, Any]]] = None,
    retry_after: Optional[int] = None,
    non_json: bool = False,
    timeout: bool = False,
    pages: Optional[int] = None,
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    calls: list[httpx.Request] = []
    page_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if timeout:
            raise httpx.ReadTimeout("read timed out")
        if "/oauth2/v2.0/token" in str(request.url):
            if token_status != 200:
                return httpx.Response(token_status, json={"error": "invalid_client"})
            return httpx.Response(200, json={"access_token": TOKEN, "expires_in": 3600})
        if graph_status != 200:
            headers = {}
            if retry_after is not None:
                headers["Retry-After"] = str(retry_after)
            return httpx.Response(graph_status, headers=headers, json={"error": {"code": "x"}})
        if non_json:
            return httpx.Response(200, text="not-json")
        if "identitySecurityDefaultsEnforcementPolicy" in str(request.url):
            return httpx.Response(200, json=defaults if defaults is not None else {"isEnabled": False})
        if pages is not None:
            page_count["n"] += 1
            next_link = (
                f"https://graph.microsoft.com/v1.0/identity/conditionalAccess/policies?$skiptoken={page_count['n']}"
            )
            return httpx.Response(
                200,
                json={
                    "value": [qualifying_ca_policy(state="enabledForReportingButNotEnforced")],
                    "@odata.nextLink": next_link,
                },
            )
        return httpx.Response(200, json={"value": list(policies or [])})

    return httpx.MockTransport(handler), calls


async def _resolve_with_transport(transport: httpx.MockTransport, **cfg: Any) -> AttestationPosture:
    client = EntraGraphClient(
        tenant_id=TENANT,
        client_id=CLIENT,
        client_secret=SECRET,
        transport=transport,
    )
    try:
        return await resolve_attestation(qgp_tenant_id=1, config=_cfg(**cfg), graph_client=client)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_token_error_is_unavailable_not_fail() -> None:
    transport, _calls = _transport(token_status=500)
    posture = await _resolve_with_transport(transport)
    assert posture.status == "unavailable"
    assert posture.reason == "token_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"graph_status": 401}, "http_401"),
        ({"graph_status": 403}, "http_403"),
        ({"graph_status": 429, "retry_after": 12}, "rate_limited"),
        ({"timeout": True}, "timeout"),
        ({"non_json": True}, "non_json"),
    ],
)
async def test_graph_401_403_429_timeout_and_non_json_are_unavailable(kwargs: dict, reason: str) -> None:
    transport, _calls = _transport(**kwargs)
    posture = await _resolve_with_transport(transport)
    assert posture.status == "unavailable"
    assert posture.reason == reason


@pytest.mark.asyncio
async def test_paging_cap_returns_unavailable_not_fail() -> None:
    transport, calls = _transport(pages=8)
    posture = await _resolve_with_transport(transport)
    assert posture.status == "unavailable"
    assert posture.reason == "policy_scan_truncated"
    policy_gets = [c for c in calls if "conditionalAccess/policies" in str(c.url)]
    assert len(policy_gets) == 5


@pytest.mark.asyncio
async def test_cache_serves_within_ttl_without_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    mono = {"t": 1_000.0}
    monkeypatch.setattr("src.domain.services.standards_entra_attestation.time.monotonic", lambda: mono["t"])
    monkeypatch.setattr("src.core.entra_graph_client.time.monotonic", lambda: mono["t"])
    transport, calls = _transport(policies=[qualifying_ca_policy()], defaults={"isEnabled": False})
    first = await _resolve_with_transport(transport)
    assert first.status == "pass"
    first_count = len(calls)
    second = await _resolve_with_transport(transport)
    assert second.status == "pass"
    assert len(calls) == first_count


@pytest.mark.asyncio
async def test_expired_cache_with_graph_error_returns_unavailable_not_stale_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mono = {"t": 1_000.0}
    monkeypatch.setattr("src.domain.services.standards_entra_attestation.time.monotonic", lambda: mono["t"])
    monkeypatch.setattr("src.core.entra_graph_client.time.monotonic", lambda: mono["t"])
    transport, _calls = _transport(policies=[qualifying_ca_policy()], defaults={"isEnabled": False})
    first = await _resolve_with_transport(transport)
    assert first.status == "pass"
    mono["t"] += 400
    fail_transport, _ = _transport(graph_status=403)
    second = await _resolve_with_transport(fail_transport)
    assert second.status == "unavailable"
    assert second.reason == "http_403"


@pytest.mark.asyncio
async def test_disabled_flag_and_missing_credentials_make_zero_http_calls() -> None:
    transport, calls = _transport()
    client = EntraGraphClient(tenant_id=TENANT, client_id=CLIENT, client_secret=SECRET, transport=transport)
    try:
        disabled = await resolve_attestation(
            qgp_tenant_id=1, config=_cfg(enabled=False), graph_client=client
        )
        assert disabled.status == "disabled"
        missing = await resolve_attestation(
            qgp_tenant_id=1,
            config=_cfg(client_id="", client_secret=""),
            graph_client=client,
        )
        assert missing.status == "unavailable"
        assert missing.reason == "not_configured"
        assert calls == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_tenant_not_in_qgp_allowlist_makes_zero_http_calls() -> None:
    transport, calls = _transport()
    client = EntraGraphClient(tenant_id=TENANT, client_id=CLIENT, client_secret=SECRET, transport=transport)
    try:
        posture = await resolve_attestation(
            qgp_tenant_id=99, config=_cfg(qgp_tenant_ids=frozenset({1})), graph_client=client
        )
        assert posture.status == "not_applicable"
        assert calls == []
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_no_secret_token_or_object_id_in_caplog_or_payload(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    policy = _users(qualifying_ca_policy(), excludeUsers=[BREAKGLASS])
    transport, _ = _transport(policies=[policy], defaults={"isEnabled": False})
    with caplog.at_level(logging.DEBUG):
        posture = await _resolve_with_transport(
            transport, breakglass_excluded_user_ids=frozenset({BREAKGLASS})
        )
    assert posture.status == "pass"
    serialised = str(posture.to_dict()) + caplog.text
    assert SECRET not in serialised
    assert TOKEN not in serialised
    assert BREAKGLASS not in serialised
    assert "access_token" not in serialised
